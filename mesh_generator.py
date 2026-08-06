"""
Mesh Generator Module.
Creates 3D Terrain Plane Objects with Displacement Modifiers matching exact physical
dimensions and elevation scaling, or generates 2D/3D Delaunay triangulated meshes.
"""

import numpy as np
import mathutils
import mathutils.geometry as geom
import bpy

from .xyz_parser import XYZCloudData


def create_point_cloud_object(
    cloud: XYZCloudData,
    object_name: str = "XYZ_PointCloud"
) -> bpy.types.Object:
    """
    Creates a pure Point Cloud Mesh Object in Blender containing all 3D vertices from the .xyz file.
    Does NOT delete or overwrite existing point clouds.

    :param cloud: XYZCloudData metrics and points.
    :param object_name: Desired object name.
    :return: Created bpy.types.Object.
    """
    pts = cloud.points

    mesh = bpy.data.meshes.new(name=f"{object_name}_Mesh")
    mesh.from_pydata(pts.tolist(), [], [])
    mesh.update()

    # Handle duplicate object naming automatically in Blender
    obj = bpy.data.objects.new(name=object_name, object_data=mesh)
    bpy.context.scene.collection.objects.link(obj)

    obj["is_xyz_pointcloud"] = True
    obj["real_world_offset_x"] = cloud.origin_offset[0]
    obj["real_world_offset_y"] = cloud.origin_offset[1]
    obj["real_world_offset_z"] = cloud.origin_offset[2]
    obj["elevation_zmin"] = cloud.zmin
    obj["elevation_zmax"] = cloud.zmax

    return obj


def extract_points_from_object(obj: bpy.types.Object) -> XYZCloudData:
    """
    Extracts 3D vertex coordinates from any selected Mesh or Point Cloud object in Blender.

    :param obj: Selected bpy.types.Object.
    :return: XYZCloudData dataclass containing extracted coordinates and bounds.
    """
    if not obj:
        raise ValueError("No object selected! Please select a Point Cloud or Mesh object in the 3D Viewport.")
    if obj.type != 'MESH':
        raise ValueError(f"Selected object '{obj.name}' is of type '{obj.type}'. Please select a Mesh or Point Cloud object.")
    if not obj.data or len(obj.data.vertices) == 0:
        raise ValueError(f"Selected mesh '{obj.name}' contains 0 vertices.")

    mw = obj.matrix_world
    v_co = np.empty(len(obj.data.vertices) * 3, dtype=np.float64)
    obj.data.vertices.foreach_get("co", v_co)
    coords = v_co.reshape((-1, 3))

    if mw != mathutils.Matrix.Identity(4):
        rot = np.array(mw.to_3x3(), dtype=np.float64)
        trans = np.array(mw.translation, dtype=np.float64)
        coords = coords @ rot.T + trans

    xmin, ymin, zmin = coords.min(axis=0)
    xmax, ymax, zmax = coords.max(axis=0)

    offset_x = float(obj.get("real_world_offset_x", 0.0))
    offset_y = float(obj.get("real_world_offset_y", 0.0))
    offset_z = float(obj.get("real_world_offset_z", 0.0))

    return XYZCloudData(
        points=coords,
        xmin=float(xmin),
        xmax=float(xmax),
        ymin=float(ymin),
        ymax=float(ymax),
        zmin=float(zmin),
        zmax=float(zmax),
        origin_offset=(offset_x, offset_y, offset_z)
    )


def create_displaced_plane(
    image: bpy.types.Image,
    cloud: XYZCloudData,
    subdivision_levels: int = 4,
    object_name: str = "XYZ_Terrain_Plane"
) -> bpy.types.Object:
    """
    Creates a 3D Plane matching exact physical X/Y bounds and configures a
    Displacement modifier scaled to the exact elevation span (zmax - zmin).

    :param image: bpy.types.Image heightmap texture.
    :param cloud: XYZCloudData coordinate bounds.
    :param subdivision_levels: Subsurf viewport level.
    :param object_name: Name of the created mesh object.
    :return: Created bpy.types.Object.
    """
    # Position plane centered at X/Y midpoint
    center_x = cloud.xmin + (cloud.width_m / 2.0)
    center_y = cloud.ymin + (cloud.height_m / 2.0)
    center_z = cloud.zmin

    bpy.ops.mesh.primitive_plane_add(
        size=1.0,
        calc_uvs=True,
        enter_editmode=False,
        align='WORLD',
        location=(center_x, center_y, center_z)
    )
    plane_obj = bpy.context.active_object
    plane_obj.name = object_name
    plane_obj.data.name = f"{object_name}_Mesh"

    # Save real-world origin offsets as custom properties on object
    plane_obj["real_world_offset_x"] = cloud.origin_offset[0]
    plane_obj["real_world_offset_y"] = cloud.origin_offset[1]
    plane_obj["real_world_offset_z"] = cloud.origin_offset[2]
    plane_obj["elevation_zmin"] = cloud.zmin
    plane_obj["elevation_zmax"] = cloud.zmax

    # Scale plane to physical width & height
    plane_obj.scale.x = cloud.width_m
    plane_obj.scale.y = cloud.height_m
    plane_obj.scale.z = 1.0
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    # Setup Texture for Displace Modifier
    texture_name = f"{object_name}_Texture"
    if texture_name in bpy.data.textures:
        tex = bpy.data.textures[texture_name]
    else:
        tex = bpy.data.textures.new(name=texture_name, type='IMAGE')
    tex.image = image

    # Add Subdivision Surface Modifier for detailed geometry
    subsurf_mod = plane_obj.modifiers.new(name="Subdivision", type='SUBSURF')
    subsurf_mod.subdivision_type = 'SIMPLE'
    subsurf_mod.levels = subdivision_levels
    subsurf_mod.render_levels = max(subdivision_levels + 1, 6)

    # Add Displace Modifier
    displace_mod = plane_obj.modifiers.new(name="XYZ_Displacement", type='DISPLACE')
    displace_mod.texture = tex
    displace_mod.texture_coords = 'UV'
    displace_mod.mid_level = 0.0
    displace_mod.strength = cloud.depth_m

    # Create or update Shader Material
    mat_name = f"{object_name}_Material"
    if mat_name in bpy.data.materials:
        mat = bpy.data.materials[mat_name]
    else:
        mat = bpy.data.materials.new(name=mat_name)

    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    tex_node = None
    for n in nodes:
        if n.type == 'TEX_IMAGE':
            tex_node = n
            break

    if not tex_node:
        nodes.clear()

        output_node = nodes.new(type='ShaderNodeOutputMaterial')
        output_node.location = (400, 0)

        bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
        bsdf.location = (100, 0)

        tex_node = nodes.new(type='ShaderNodeTexImage')
        tex_node.location = (-300, 0)

        links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
        links.new(bsdf.outputs['BSDF'], output_node.inputs['Surface'])

    tex_node.image = image
    if hasattr(tex_node.image, "colorspace_settings"):
        tex_node.image.colorspace_settings.name = 'Non-Color'

    if len(plane_obj.data.materials) == 0:
        plane_obj.data.materials.append(mat)
    else:
        plane_obj.data.materials[0] = mat

    image.update()
    try:
        image.gl_touch()
    except Exception:
        pass

    return plane_obj


def create_triangulated_mesh(
    cloud: XYZCloudData,
    point_density_pct: float = 100.0,
    max_points: int = 500000,
    object_name: str = "XYZ_Terrain_Triangulated"
) -> bpy.types.Object:
    """
    Directly triangulates 3D points into a Terrain Mesh using 2D Delaunay CDT.

    :param cloud: XYZCloudData coordinate bounds.
    :param point_density_pct: Percentage of total points to include (1% to 100%).
    :param max_points: Maximum cap of vertices for performance protection.
    :param object_name: Name of created mesh object.
    :return: Created bpy.types.Object.
    """
    pts = cloud.points
    total_pts = len(pts)

    if total_pts < 3:
        raise ValueError(f"Delaunay 3D triangulation requires at least 3 points, but point cloud only has {total_pts} points.")

    target_count = int(round((point_density_pct / 100.0) * total_pts))
    target_count = max(100, min(target_count, max_points))

    if target_count < total_pts:
        indices = np.random.choice(total_pts, size=target_count, replace=False)
        pts = pts[indices]

    verts_2d = [mathutils.Vector((p[0], p[1])) for p in pts]

    cdt_res = geom.delaunay_2d_cdt(
        verts_2d,
        [],
        [],
        0,
        1e-5
    )

    out_verts, out_edges, out_faces, orig_verts, _, _ = cdt_res

    mesh_verts = []
    for idx, v2d in enumerate(out_verts):
        orig_indices = orig_verts[idx]
        if orig_indices:
            z_val = float(pts[orig_indices[0]][2])
        else:
            z_val = cloud.zmin
        mesh_verts.append((v2d.x, v2d.y, z_val))

    mesh_faces = [[f for f in face] for face in out_faces]

    mesh = bpy.data.meshes.new(name=f"{object_name}_Mesh")
    mesh.from_pydata(mesh_verts, [], mesh_faces)
    mesh.update()

    obj = bpy.data.objects.new(name=object_name, object_data=mesh)
    bpy.context.scene.collection.objects.link(obj)

    # Save real-world origin offsets
    obj["real_world_offset_x"] = cloud.origin_offset[0]
    obj["real_world_offset_y"] = cloud.origin_offset[1]
    obj["real_world_offset_z"] = cloud.origin_offset[2]

    return obj
