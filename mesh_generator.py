# pyright: reportMissingImports=false, reportMissingModuleSource=false
"""
Mesh Generator Module.
Creates 3D Terrain Plane Objects with Displacement Modifiers matching exact physical
dimensions and elevation scaling, or generates 2.5D Delaunay triangulated meshes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import numpy as np

try:
    from .heightmap_generator import refresh_image_preview
    from .xyz_parser import XYZCloudData
except ImportError:
    from heightmap_generator import refresh_image_preview
    from xyz_parser import XYZCloudData

try:
    import bpy
    import mathutils
    import mathutils.geometry as geom
except ImportError:
    bpy = None  # type: ignore[assignment]
    mathutils = None  # type: ignore[assignment]
    geom = None  # type: ignore[assignment]

if TYPE_CHECKING:
    import bpy as bpy_types

DELAUNAY_EPSILON: float = 1e-5
DEFAULT_RNG_SEED: int = 42


def _assign_terrain_metadata(
    obj: Any,
    cloud: XYZCloudData,
    source_pointcloud_name: str | None = None,
) -> None:
    """Assigns real-world origin offsets and elevation bounds as custom properties on a Blender object."""
    obj["real_world_offset_x"] = cloud.origin_offset[0]
    obj["real_world_offset_y"] = cloud.origin_offset[1]
    obj["real_world_offset_z"] = cloud.origin_offset[2]
    obj["elevation_zmin"] = cloud.zmin
    obj["elevation_zmax"] = cloud.zmax
    if source_pointcloud_name:
        obj["source_pointcloud_name"] = source_pointcloud_name


def create_point_cloud_object(
    cloud: XYZCloudData,
    object_name: str = "XYZ_PointCloud",
) -> bpy_types.types.Object:
    """
    Creates a Point Cloud Mesh Object in Blender 5.x using direct C-buffer foreach_set
    population for multi-million-point datasets without intermediate Python list allocation.

    :param cloud: XYZCloudData metrics and points.
    :param object_name: Desired object name.
    :return: Created bpy.types.Object.
    """
    if bpy is None:
        raise RuntimeError("create_point_cloud_object requires an active Blender (bpy) runtime.")

    mesh = bpy.data.meshes.new(name=f"{object_name}_Mesh")
    num_pts = len(cloud.points)
    if num_pts > 0:
        mesh.vertices.add(num_pts)
        flat_co = np.ascontiguousarray(cloud.points, dtype=np.float32).ravel()
        mesh.vertices.foreach_set("co", cast(Any, flat_co))
    mesh.update()

    obj = bpy.data.objects.new(name=object_name, object_data=mesh)
    bpy.context.scene.collection.objects.link(obj)

    obj["is_xyz_pointcloud"] = True
    _assign_terrain_metadata(obj, cloud)
    return obj


def resolve_source_mesh_object(obj: Any) -> Any:
    """
    If the given object is a generated 4-vertex displaced plane, resolves its linked
    source point cloud object when available in bpy.data.objects.
    """
    if obj is None:
        return None
    if obj.get("is_xyz_displaced_plane", False):
        src_name = obj.get("source_pointcloud_name")
        if src_name and bpy is not None and src_name in bpy.data.objects:
            return bpy.data.objects[src_name]
        raise ValueError(
            f"Selected object '{obj.name}' is a generated 4-vertex Heightmap Plane, and its source "
            "Point Cloud is no longer in the scene. Please select a Point Cloud object."
        )
    return obj


def extract_points_from_object(obj: bpy_types.types.Object) -> XYZCloudData:
    """
    Extracts 3D vertex coordinates from a selected Mesh or Point Cloud object in Blender.

    :param obj: Selected bpy.types.Object.
    :return: Immutable XYZCloudData containing extracted coordinates and bounds.
    """
    if not obj:
        raise ValueError("No object selected! Please select a Point Cloud or Mesh object in the 3D Viewport.")

    target_obj = resolve_source_mesh_object(obj)

    if target_obj.type != "MESH":
        raise ValueError(
            f"Selected object '{target_obj.name}' is of type '{target_obj.type}'. Please select a Mesh or Point Cloud object."
        )
    if not target_obj.data or len(target_obj.data.vertices) == 0:
        raise ValueError(f"Selected mesh '{target_obj.name}' contains 0 vertices.")

    mw = target_obj.matrix_world
    v_co = np.empty(len(target_obj.data.vertices) * 3, dtype=np.float64)
    target_obj.data.vertices.foreach_get("co", cast(Any, v_co))
    coords = v_co.reshape((-1, 3))

    if mathutils is not None and mw != mathutils.Matrix.Identity(4):
        rot = np.array(mw.to_3x3(), dtype=np.float64)
        trans = np.array(mw.translation, dtype=np.float64)
        coords = coords @ rot.T + trans

    xmin, ymin, zmin = coords.min(axis=0)
    xmax, ymax, zmax = coords.max(axis=0)

    if xmax <= xmin and ymax <= ymin:
        raise ValueError(f"Selected mesh '{target_obj.name}' has zero physical width and height in X/Y.")

    offset_x = float(target_obj.get("real_world_offset_x", 0.0))
    offset_y = float(target_obj.get("real_world_offset_y", 0.0))
    offset_z = float(target_obj.get("real_world_offset_z", 0.0))

    return XYZCloudData(
        points=coords,
        xmin=float(xmin),
        xmax=float(xmax),
        ymin=float(ymin),
        ymax=float(ymax),
        zmin=float(zmin),
        zmax=float(zmax),
        origin_offset=(offset_x, offset_y, offset_z),
    )


def _configure_plane_material(plane_obj: Any, image: Any, object_name: str) -> None:
    """Creates or updates the Principled BSDF material linked to the heightmap texture."""
    if bpy is None:
        raise RuntimeError("_configure_plane_material requires an active Blender (bpy) runtime.")

    mat_name = f"{object_name}_Material"
    mat = bpy.data.materials[mat_name] if mat_name in bpy.data.materials else bpy.data.materials.new(name=mat_name)

    mat.use_nodes = True
    node_tree = mat.node_tree
    if node_tree is None:
        raise RuntimeError(f"Material '{mat_name}' has no active node_tree.")

    nodes = node_tree.nodes
    links = node_tree.links

    tex_node: Any = next((n for n in nodes if n.type == "TEX_IMAGE"), None)
    if tex_node is None:
        nodes.clear()
        output_node = nodes.new(type="ShaderNodeOutputMaterial")
        output_node.location = (400, 0)

        bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
        bsdf.location = (100, 0)

        tex_node = nodes.new(type="ShaderNodeTexImage")
        tex_node.location = (-300, 0)

        links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])
        links.new(bsdf.outputs["BSDF"], output_node.inputs["Surface"])

    tex_node.image = image

    if len(plane_obj.data.materials) == 0:
        plane_obj.data.materials.append(mat)
    else:
        plane_obj.data.materials[0] = mat


def create_displaced_plane(
    image: bpy_types.types.Image,
    cloud: XYZCloudData,
    subdivision_levels: int = 6,
    object_name: str = "XYZ_Terrain_Plane",
    source_pointcloud_name: str | None = None,
) -> bpy_types.types.Object:
    """
    Creates a 3D Plane matching exact physical X/Y bounds without using context-sensitive
    bpy.ops calls, and configures a Displacement modifier scaled to (zmax - zmin).

    :param image: bpy.types.Image heightmap texture.
    :param cloud: XYZCloudData coordinate bounds.
    :param subdivision_levels: Subsurf viewport level.
    :param object_name: Name of the created mesh object.
    :param source_pointcloud_name: Optional name of the source point cloud object.
    :return: Created bpy.types.Object.
    """
    if bpy is None:
        raise RuntimeError("create_displaced_plane requires an active Blender (bpy) runtime.")
    if cloud.width_m <= 0.0 or cloud.height_m <= 0.0:
        raise ValueError(
            "Cannot create a 2D displaced terrain plane from a 1D colinear point cloud (both width and height must be > 0)."
        )

    center_x = cloud.xmin + (cloud.width_m / 2.0)
    center_y = cloud.ymin + (cloud.height_m / 2.0)
    center_z = cloud.zmin

    half_w = cloud.width_m / 2.0
    half_h = cloud.height_m / 2.0

    verts = [
        (-half_w, -half_h, 0.0),
        (half_w, -half_h, 0.0),
        (half_w, half_h, 0.0),
        (-half_w, half_h, 0.0),
    ]
    faces = [(0, 1, 2, 3)]

    mesh = bpy.data.meshes.new(name=f"{object_name}_Mesh")
    mesh.from_pydata(verts, [], faces)

    uv_layer = mesh.uv_layers.new(name="UVMap")
    uv_flat = np.array([0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0], dtype=np.float32)
    uv_layer.data.foreach_set("uv", cast(Any, uv_flat))
    mesh.update()

    plane_obj = bpy.data.objects.new(name=object_name, object_data=mesh)
    plane_obj.location = (center_x, center_y, center_z)
    bpy.context.scene.collection.objects.link(plane_obj)

    plane_obj["is_xyz_displaced_plane"] = True
    _assign_terrain_metadata(plane_obj, cloud, source_pointcloud_name=source_pointcloud_name)

    texture_name = f"{object_name}_Texture"
    tex: Any = (
        bpy.data.textures[texture_name]
        if texture_name in bpy.data.textures
        else bpy.data.textures.new(name=texture_name, type="IMAGE")
    )
    tex.image = image

    subsurf_mod = cast(Any, plane_obj.modifiers.new(name="Subdivision", type="SUBSURF"))
    subsurf_mod.subdivision_type = "SIMPLE"
    subsurf_mod.levels = subdivision_levels
    subsurf_mod.render_levels = max(subdivision_levels + 1, 6)

    displace_mod = cast(Any, plane_obj.modifiers.new(name="XYZ_Displacement", type="DISPLACE"))
    displace_mod.texture = tex
    displace_mod.texture_coords = "UV"
    displace_mod.mid_level = 0.0
    displace_mod.strength = cloud.depth_m

    _configure_plane_material(plane_obj, image, object_name)
    refresh_image_preview(image)
    return plane_obj


def create_triangulated_mesh(
    cloud: XYZCloudData,
    point_density_pct: float = 100.0,
    max_points: int = 500000,
    object_name: str = "XYZ_Terrain_Triangulated",
    source_pointcloud_name: str | None = None,
) -> bpy_types.types.Object:
    """
    Directly triangulates 3D points into a Terrain Mesh using 2D Delaunay CDT.

    :param cloud: XYZCloudData coordinate bounds.
    :param point_density_pct: Percentage of total points to include (0.1% to 100%).
    :param max_points: Maximum cap of vertices for performance protection.
    :param object_name: Name of created mesh object.
    :param source_pointcloud_name: Optional name of the source point cloud object.
    :return: Created bpy.types.Object.
    """
    if bpy is None or mathutils is None or geom is None:
        raise RuntimeError("create_triangulated_mesh requires an active Blender (bpy/mathutils) runtime.")
    if point_density_pct <= 0.0 or point_density_pct > 100.0:
        raise ValueError(f"point_density_pct must be in (0, 100], got {point_density_pct}.")

    pts = cloud.points
    total_pts = len(pts)

    if total_pts < 3:
        raise ValueError(
            f"Delaunay 3D triangulation requires at least 3 points, but point cloud only has {total_pts} points."
        )

    raw_target = int(round((point_density_pct / 100.0) * total_pts))
    target_count = max(3, min(raw_target, max_points, total_pts))

    if target_count < total_pts:
        rng = np.random.default_rng(seed=DEFAULT_RNG_SEED)
        indices = rng.choice(total_pts, size=target_count, replace=False)
        pts = pts[indices]

    pts_xy = pts[:, :2].tolist()
    verts_2d = [mathutils.Vector(xy) for xy in pts_xy]
    cdt_res = geom.delaunay_2d_cdt(verts_2d, [], [], 0, DELAUNAY_EPSILON)
    out_verts, _out_edges, out_faces, orig_verts, _, _ = cdt_res

    if len(out_faces) == 0:
        raise ValueError("Delaunay triangulation produced 0 faces (points are colinear in X/Y).")

    z_list = pts[:, 2].tolist()
    zmin_fallback = cloud.zmin
    mesh_verts = []
    for idx, v2d in enumerate(out_verts):
        orig_indices = orig_verts[idx]
        if len(orig_indices) == 1:
            z_val = z_list[orig_indices[0]]
        elif orig_indices:
            z_val = max(z_list[i] for i in orig_indices)
        else:
            z_val = zmin_fallback
        mesh_verts.append((v2d.x, v2d.y, z_val))

    mesh_faces = [list(face) for face in out_faces]

    mesh = bpy.data.meshes.new(name=f"{object_name}_Mesh")
    mesh.from_pydata(mesh_verts, [], mesh_faces)
    mesh.update()

    obj = bpy.data.objects.new(name=object_name, object_data=mesh)
    bpy.context.scene.collection.objects.link(obj)

    _assign_terrain_metadata(obj, cloud, source_pointcloud_name=source_pointcloud_name)
    return obj
