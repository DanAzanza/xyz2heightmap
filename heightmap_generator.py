# pyright: reportMissingImports=false, reportMissingModuleSource=false
"""
Heightmap Generator Module.
Converts 3D point cloud data into a 2D heightmap raster grid using NumPy,
performs Inverse Distance Weighting (IDW) gap-filling in physical meter space,
and packs the data into a 32-bit float Blender Image data-block.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, cast

import numpy as np

try:
    from .xyz_parser import XYZCloudData
except ImportError:
    from xyz_parser import XYZCloudData

try:
    import bpy
    import mathutils
except ImportError:
    bpy = None  # type: ignore[assignment]
    mathutils = None  # type: ignore[assignment]

if TYPE_CHECKING:
    import bpy as bpy_types

MAX_VECTORIZED_IDW_PAIRS: int = 40_000_000
IDW_CHUNK_BUDGET: int = 2_000_000
IDW_EPSILON: float = 1e-5


def _interpolate_gaps_vectorized(
    grid: np.ndarray,
    valid_x: np.ndarray,
    valid_y: np.ndarray,
    invalid_x: np.ndarray,
    invalid_y: np.ndarray,
    step_x_m: float,
    step_y_m: float,
    k_neighbors: int,
    idw_power: float,
    fallback_z: float,
) -> np.ndarray:
    """
    Vectorized pure-NumPy IDW interpolation operating in physical meter coordinates.
    Processes invalid pixels in bounded memory chunks.
    """
    grid_filled = grid.copy()
    num_valid = len(valid_x)
    num_invalid = len(invalid_x)
    k = min(k_neighbors, num_valid)

    vx_m = valid_x.astype(np.float32) * np.float32(step_x_m)
    vy_m = valid_y.astype(np.float32) * np.float32(step_y_m)
    vz = grid[valid_y, valid_x].astype(np.float32)

    chunk_size = max(1, min(num_invalid, IDW_CHUNK_BUDGET // max(1, num_valid)))

    for start in range(0, num_invalid, chunk_size):
        end = min(start + chunk_size, num_invalid)
        ix_chunk = invalid_x[start:end]
        iy_chunk = invalid_y[start:end]

        qx_m = ix_chunk.astype(np.float32)[:, None] * np.float32(step_x_m)
        qy_m = iy_chunk.astype(np.float32)[:, None] * np.float32(step_y_m)

        dist = np.hypot(qx_m - vx_m[None, :], qy_m - vy_m[None, :])

        if k < num_valid:
            knn_idx = np.argpartition(dist, k - 1, axis=1)[:, :k]
            knn_dist = np.take_along_axis(dist, knn_idx, axis=1)
            knn_vals = vz[knn_idx]
        else:
            knn_dist = dist
            knn_vals = np.broadcast_to(vz[None, :], dist.shape)

        weights = 1.0 / np.power(knn_dist + IDW_EPSILON, np.float32(idw_power))
        weights_sum = np.sum(weights, axis=1)
        weighted_vals = np.sum(weights * knn_vals, axis=1)

        filled_chunk = np.where(weights_sum > 0.0, weighted_vals / weights_sum, np.float32(fallback_z))
        grid_filled[iy_chunk, ix_chunk] = filled_chunk

    return grid_filled


def _interpolate_gaps_kdtree(
    grid: np.ndarray,
    valid_x: np.ndarray,
    valid_y: np.ndarray,
    invalid_x: np.ndarray,
    invalid_y: np.ndarray,
    step_x_m: float,
    step_y_m: float,
    k_neighbors: int,
    idw_power: float,
    fallback_z: float,
) -> np.ndarray:
    """
    KDTree-accelerated IDW interpolation for large point clouds inside Blender 5.x.
    Pre-extracts physical meter coordinates and Z values into flat native lists to
    eliminate per-neighbor NumPy scalar indexing overhead.
    """
    if mathutils is None:
        raise RuntimeError("_interpolate_gaps_kdtree requires mathutils runtime.")

    grid_filled = grid.copy()
    num_valid = len(valid_x)
    num_invalid = len(invalid_x)
    k = min(k_neighbors, num_valid)

    vx_m_list = (valid_x.astype(np.float64) * step_x_m).tolist()
    vy_m_list = (valid_y.astype(np.float64) * step_y_m).tolist()
    vz_list = grid[valid_y, valid_x].astype(np.float64).tolist()

    kd = mathutils.kdtree.KDTree(num_valid)
    for idx in range(num_valid):
        kd.insert((vx_m_list[idx], vy_m_list[idx], 0.0), idx)
    kd.balance()

    ix_m_list = (invalid_x.astype(np.float64) * step_x_m).tolist()
    iy_m_list = (invalid_y.astype(np.float64) * step_y_m).tolist()
    filled_vals = np.empty(num_invalid, dtype=np.float32)

    for idx in range(num_invalid):
        co = (ix_m_list[idx], iy_m_list[idx], 0.0)
        results = kd.find_n(co, k)
        weights_sum = 0.0
        val_sum = 0.0

        for _co_found, index_found, dist in results:
            w = 1.0 / ((dist + IDW_EPSILON) ** idw_power)
            val_sum += w * vz_list[index_found]
            weights_sum += w

        filled_vals[idx] = val_sum / weights_sum if weights_sum > 0.0 else fallback_z

    grid_filled[invalid_y, invalid_x] = filled_vals
    return grid_filled


def generate_heightmap_grid(
    cloud: XYZCloudData,
    pixels_per_meter: float = 1.0,
    target_res: tuple[int, int] | None = None,
    k_neighbors: int = 8,
    idw_power: float = 2.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Rasterizes a 3D point cloud to a 2D bottom-up heightmap grid (row 0 = ymin/South,
    row res_y-1 = ymax/North, matching Blender UV and Image.pixels layout) and fills
    missing cells using Inverse Distance Weighting (IDW).

    :param cloud: Immutable XYZCloudData metrics.
    :param pixels_per_meter: Grid resolution (pixels per meter) when target_res is None.
    :param target_res: Optional explicit (res_x, res_y) pixel dimensions override.
    :param k_neighbors: Number of nearest neighbors for IDW gap filling (>= 1).
    :param idw_power: Power exponent for Inverse Distance Weighting (> 0).
    :return: Tuple of (raw_height_grid, normalized_grid) as float32 arrays of shape (res_y, res_x).
    """
    if pixels_per_meter <= 0.0 and target_res is None:
        raise ValueError(f"pixels_per_meter must be positive, got {pixels_per_meter}.")
    if k_neighbors < 1:
        raise ValueError(f"k_neighbors must be at least 1, got {k_neighbors}.")
    if idw_power <= 0.0:
        raise ValueError(f"idw_power must be positive, got {idw_power}.")

    if target_res is not None:
        if target_res[0] < 1 or target_res[1] < 1:
            raise ValueError(f"target_res dimensions must be >= 1, got {target_res}.")
        res_x, res_y = int(target_res[0]), int(target_res[1])
        scale_x = res_x / cloud.width_m if cloud.width_m > 0.0 else 1.0
        scale_y = res_y / cloud.height_m if cloud.height_m > 0.0 else 1.0
    else:
        res_x = max(1, int(np.ceil(cloud.width_m * pixels_per_meter))) if cloud.width_m > 0.0 else 1
        res_y = max(1, int(np.ceil(cloud.height_m * pixels_per_meter))) if cloud.height_m > 0.0 else 1
        scale_x = pixels_per_meter
        scale_y = pixels_per_meter

    step_x_m = 1.0 / scale_x if scale_x > 0.0 else 1.0
    step_y_m = 1.0 / scale_y if scale_y > 0.0 else 1.0

    cols = np.clip(np.floor((cloud.points[:, 0] - cloud.xmin) * scale_x).astype(np.int32), 0, res_x - 1)
    rows = np.clip(np.floor((cloud.points[:, 1] - cloud.ymin) * scale_y).astype(np.int32), 0, res_y - 1)

    grid = np.full((res_y, res_x), -np.inf, dtype=np.float32)
    np.maximum.at(grid, (rows, cols), cloud.points[:, 2].astype(np.float32))

    valid_y, valid_x = np.where(np.isfinite(grid))
    invalid_y, invalid_x = np.where(np.isinf(grid))

    num_valid = len(valid_y)
    num_invalid = len(invalid_y)

    if num_invalid == 0 or num_valid == 0:
        grid_filled = np.where(np.isfinite(grid), grid, np.float32(cloud.zmin))
    elif mathutils is not None and (num_valid * num_invalid) > MAX_VECTORIZED_IDW_PAIRS:
        grid_filled = _interpolate_gaps_kdtree(
            grid, valid_x, valid_y, invalid_x, invalid_y, step_x_m, step_y_m, k_neighbors, idw_power, cloud.zmin
        )
    else:
        grid_filled = _interpolate_gaps_vectorized(
            grid, valid_x, valid_y, invalid_x, invalid_y, step_x_m, step_y_m, k_neighbors, idw_power, cloud.zmin
        )

    if cloud.depth_m <= 1e-9:
        normalized_grid = np.zeros_like(grid_filled, dtype=np.float32)
    else:
        normalized_grid = np.clip((grid_filled - cloud.zmin) / cloud.depth_m, 0.0, 1.0).astype(np.float32)

    return grid_filled, normalized_grid


def refresh_image_preview(image: Any) -> None:
    """Updates a Blender Image data-block and refreshes its viewport OpenGL texture when UI is active."""
    image.update()
    if bpy is not None and not bpy.app.background:
        try:
            image.gl_touch()
        except (RuntimeError, ReferenceError):
            pass


def create_blender_image(
    normalized_grid: np.ndarray,
    image_name: str = "XYZ_Heightmap",
) -> bpy_types.types.Image:
    """
    Creates or updates a 32-bit float Blender Image data-block from a 2D normalized grid.

    :param normalized_grid: 2D numpy array of shape (height, width) with float values in [0, 1].
    :param image_name: Name of the Blender Image asset.
    :return: bpy.types.Image object.
    """
    if bpy is None:
        raise RuntimeError("create_blender_image requires an active Blender (bpy) runtime.")

    clean_name = os.path.splitext(image_name)[0]
    res_y, res_x = normalized_grid.shape

    if clean_name in bpy.data.images:
        image = bpy.data.images[clean_name]
        img_size = cast(Any, image.size)
        if img_size[0] != res_x or img_size[1] != res_y:
            image.scale(res_x, res_y)
    else:
        image = bpy.data.images.new(
            name=clean_name,
            width=res_x,
            height=res_y,
            alpha=False,
            float_buffer=True,
            is_data=True,
        )

    if image.colorspace_settings is not None and cast(Any, image.colorspace_settings).name != "Non-Color":
        cast(Any, image.colorspace_settings).name = "Non-Color"

    rgba = np.empty((res_y, res_x, 4), dtype=np.float32)
    rgba[:, :, 0] = normalized_grid
    rgba[:, :, 1] = normalized_grid
    rgba[:, :, 2] = normalized_grid
    rgba[:, :, 3] = 1.0

    image.pixels.foreach_set(cast(Any, rgba.ravel()))
    refresh_image_preview(image)
    return image


def export_heightmap_16bit_png(image: bpy_types.types.Image, output_path: str) -> None:
    """
    Exports a Blender heightmap image asset as a 16-bit Grayscale PNG file to disk.

    :param image: bpy.types.Image asset.
    :param output_path: Absolute file destination path.
    """
    if bpy is None:
        raise RuntimeError("export_heightmap_16bit_png requires an active Blender (bpy) runtime.")

    scene = bpy.context.scene
    render_settings = scene.render.image_settings
    prev_format = render_settings.file_format
    prev_depth = render_settings.color_depth
    prev_mode = render_settings.color_mode

    view_settings = scene.view_settings
    prev_transform = getattr(view_settings, "view_transform", None)

    try:
        render_settings.file_format = "PNG"
        render_settings.color_depth = "16"
        render_settings.color_mode = "BW"

        if prev_transform:
            enum_items = view_settings.bl_rna.properties["view_transform"].enum_items
            if "Raw" in enum_items:
                view_settings.view_transform = "Raw"
            elif "Standard" in enum_items:
                view_settings.view_transform = "Standard"

        image.save_render(output_path, scene=scene)
    finally:
        render_settings.file_format = prev_format
        render_settings.color_depth = prev_depth
        render_settings.color_mode = prev_mode
        if prev_transform:
            view_settings.view_transform = prev_transform
