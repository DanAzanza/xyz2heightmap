"""
Heightmap Generator Module.
Converts 3D point cloud data into a 2D heightmap raster grid using NumPy,
performs modern Inverse Distance Weighting (IDW) KDTree gap-filling,
and packs the data into a 32-bit float Blender Image data-block.
"""

from typing import Tuple, Optional
import os
import numpy as np
import mathutils
import bpy

from .xyz_parser import XYZCloudData


def generate_heightmap_grid(
    cloud: XYZCloudData,
    pixels_per_meter: float = 1.0,
    target_res: Optional[Tuple[int, int]] = None,
    k_neighbors: int = 8,
    idw_power: float = 2.0
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Rasterizes point cloud to a 2D grid and fills missing data using KDTree IDW.

    :param cloud: XYZCloudData metrics.
    :param pixels_per_meter: Grid resolution (pixels per meter).
    :param target_res: Optional explicit (res_x, res_y) dimensions override.
    :param k_neighbors: Number of nearest neighbors for IDW gap filling.
    :param idw_power: Power exponent for Inverse Distance Weighting.
    :return: Tuple of (raw_height_grid, normalized_grid).
    """
    if target_res and target_res[0] > 0 and target_res[1] > 0:
        res_x, res_y = target_res
        scale_x = res_x / cloud.width_m if cloud.width_m > 0 else 1.0
        scale_y = res_y / cloud.height_m if cloud.height_m > 0 else 1.0
    else:
        res_x = max(1, int(np.ceil(cloud.width_m * pixels_per_meter)))
        res_y = max(1, int(np.ceil(cloud.height_m * pixels_per_meter)))
        scale_x = pixels_per_meter
        scale_y = pixels_per_meter

    cols = np.clip(((cloud.points[:, 0] - cloud.xmin) * scale_x).astype(np.int32), 0, res_x - 1)
    rows = np.clip(((cloud.ymax - cloud.points[:, 1]) * scale_y).astype(np.int32), 0, res_y - 1)

    grid = np.full((res_y, res_x), -np.inf, dtype=np.float32)

    # Max Z per grid cell using numpy ufunc for speed
    np.maximum.at(grid, (rows, cols), cloud.points[:, 2])

    # Find valid and missing pixel coordinates
    valid_y, valid_x = np.where(np.isfinite(grid))
    invalid_y, invalid_x = np.where(np.isinf(grid))

    num_valid = len(valid_y)
    num_invalid = len(invalid_y)

    grid_filled = grid.copy()

    # Fill gaps using KDTree Inverse Distance Weighting if invalid cells exist
    if num_invalid > 0 and num_valid > 0:
        kd = mathutils.kdtree.KDTree(num_valid)
        for idx in range(num_valid):
            kd.insert((float(valid_x[idx]), float(valid_y[idx]), 0.0), idx)
        kd.balance()

        for idx in range(num_invalid):
            iy = int(invalid_y[idx])
            ix = int(invalid_x[idx])
            co = (float(ix), float(iy), 0.0)

            results = kd.find_n(co, k_neighbors)
            weights_sum = 0.0
            val_sum = 0.0

            for (co_found, index_found, dist) in results:
                w = 1.0 / ((dist + 1e-5) ** idw_power)
                r_f = valid_y[index_found]
                c_f = valid_x[index_found]
                val_sum += w * grid[r_f, c_f]
                weights_sum += w

            grid_filled[iy, ix] = val_sum / weights_sum if weights_sum > 0 else cloud.zmin

    # Normalize grid to [0.0, 1.0] float range relative to zmin and zmax
    z_span = max(cloud.depth_m, 1e-5)
    normalized_grid = np.clip((grid_filled - cloud.zmin) / z_span, 0.0, 1.0).astype(np.float32)

    # Invert vertical orientation (flipud) so 3D North (ymax) aligns with top of heightmap image
    grid_filled = np.flipud(grid_filled)
    normalized_grid = np.flipud(normalized_grid)

    return grid_filled, normalized_grid


def create_blender_image(
    normalized_grid: np.ndarray,
    image_name: str = "XYZ_Heightmap"
) -> bpy.types.Image:
    """
    Creates or updates a 32-bit float Blender Image data-block from a 2D normalized grid.

    :param normalized_grid: 2D numpy array of shape (height, width) with float values in [0, 1].
    :param image_name: Name of the Blender Image asset.
    :return: bpy.types.Image object.
    """
    clean_name = os.path.splitext(image_name)[0]
    res_y, res_x = normalized_grid.shape

    # Reuse existing image data-block to preserve texture & shader node links
    if clean_name in bpy.data.images:
        image = bpy.data.images[clean_name]
        if image.size[0] != res_x or image.size[1] != res_y:
            image.scale(res_x, res_y)
    else:
        image = bpy.data.images.new(
            name=clean_name,
            width=res_x,
            height=res_y,
            alpha=False,
            float_buffer=True,
            is_data=True
        )

    image.colorspace_settings.name = 'Non-Color'

    rgba = np.empty((res_y, res_x, 4), dtype=np.float32)
    rgba[:, :, 0] = normalized_grid
    rgba[:, :, 1] = normalized_grid
    rgba[:, :, 2] = normalized_grid
    rgba[:, :, 3] = 1.0

    image.pixels.foreach_set(rgba.ravel())
    image.update()

    try:
        image.gl_touch()
    except Exception:
        pass

    return image


def export_heightmap_16bit_png(image: bpy.types.Image, output_path: str):
    """
    Exports a Blender heightmap image asset as a 16-bit Grayscale PNG file to disk.

    :param image: bpy.types.Image asset.
    :param output_path: Absolute file destination path.
    """
    scene = bpy.context.scene
    render_settings = scene.render.image_settings
    prev_format = render_settings.file_format
    prev_depth = render_settings.color_depth
    prev_mode = render_settings.color_mode

    view_settings = scene.view_settings
    prev_transform = getattr(view_settings, "view_transform", None)

    try:
        render_settings.file_format = 'PNG'
        render_settings.color_depth = '16'
        render_settings.color_mode = 'BW'

        if prev_transform and 'Raw' in view_settings.bl_rna.properties['view_transform'].enum_items:
            view_settings.view_transform = 'Raw'
        elif prev_transform and 'Standard' in view_settings.bl_rna.properties['view_transform'].enum_items:
            view_settings.view_transform = 'Standard'

        image.save_render(output_path, scene=scene)
    finally:
        render_settings.file_format = prev_format
        render_settings.color_depth = prev_depth
        render_settings.color_mode = prev_mode
        if prev_transform:
            view_settings.view_transform = prev_transform
