# pyright: reportMissingImports=false, reportMissingModuleSource=false
"""
Import Operators & Scene Properties Module.
Defines PropertyGroup, File Picker Operator, and Standalone Generation Operators.
"""

from __future__ import annotations

import os
from typing import Any, cast

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    StringProperty,
)
from bpy_extras.io_utils import ImportHelper

try:
    from .heightmap_generator import (
        create_blender_image,
        export_heightmap_16bit_png,
        generate_heightmap_grid,
    )
    from .mesh_generator import (
        create_displaced_plane,
        create_point_cloud_object,
        create_triangulated_mesh,
        extract_points_from_object,
        resolve_source_mesh_object,
    )
    from .xyz_parser import load_xyz_file
except ImportError:
    from heightmap_generator import (
        create_blender_image,
        export_heightmap_16bit_png,
        generate_heightmap_grid,
    )
    from mesh_generator import (
        create_displaced_plane,
        create_point_cloud_object,
        create_triangulated_mesh,
        extract_points_from_object,
        resolve_source_mesh_object,
    )
    from xyz_parser import load_xyz_file


_PATH_OPTS: set[Any] = (
    {"PATH_SUPPORTS_BLEND_RELATIVE"}
    if hasattr(bpy, "app") and getattr(bpy.app, "version", (4, 0, 0)) >= (4, 2, 0)
    else set()
)


class XYZTerrainProperties(bpy.types.PropertyGroup):
    """Scene properties for XYZ Terrain add-on."""

    xyz_filepath: StringProperty(  # type: ignore[valid-type]
        name="XYZ Point Cloud File",
        description="Path to the .xyz, .pts, or .txt point cloud data file",
        subtype="FILE_PATH",
        options=_PATH_OPTS,
    )

    center_to_origin: BoolProperty(  # type: ignore[valid-type]
        name="Center to Scene Origin (0,0,0)",
        description="Shift point cloud coordinates so bounding box X/Y center and Z base sit at Blender origin (0, 0, 0)",
        default=True,
    )

    auto_filter_height: BoolProperty(  # type: ignore[valid-type]
        name="Auto-Filter Noise Outliers",
        description="Automatically remove extreme noise percentiles below 0.1% and above 99.9% on clouds with >= 100 points",
        default=True,
    )

    use_manual_height_filter: BoolProperty(  # type: ignore[valid-type]
        name="Use Manual Elevation Filter",
        description="Enable hard minimum and maximum elevation thresholds",
        default=False,
    )

    min_height: FloatProperty(  # type: ignore[valid-type]
        name="Min Height (m)",
        description="Manual minimum elevation filter threshold",
        default=0.0,
    )

    max_height: FloatProperty(  # type: ignore[valid-type]
        name="Max Height (m)",
        description="Manual maximum elevation filter threshold",
        default=500.0,
    )

    resolution_mode: EnumProperty(  # type: ignore[valid-type]
        name="Resolution Mode",
        description="Choose between Pixels per Meter or Custom Pixel Dimensions",
        items=[
            ("PPM", "Pixels per Meter", "Set resolution based on pixels per meter"),
            (
                "CUSTOM",
                "Custom Resolution",
                "Explicit pixel width and height dimensions",
            ),
        ],
        default="PPM",
    )

    pixels_per_meter: FloatProperty(  # type: ignore[valid-type]
        name="Pixels per Meter",
        description="Resolution of the generated heightmap grid (pixels / meter)",
        default=1.0,
        min=0.1,
        max=50.0,
    )

    custom_res_x: IntProperty(  # type: ignore[valid-type]
        name="Width (px)",
        description="Custom pixel width of heightmap image",
        default=2048,
        min=64,
        max=16384,
    )

    custom_res_y: IntProperty(  # type: ignore[valid-type]
        name="Height (px)",
        description="Custom pixel height of heightmap image",
        default=2048,
        min=64,
        max=16384,
    )

    idw_k_neighbors: IntProperty(  # type: ignore[valid-type]
        name="IDW Neighbors",
        description="Number of nearest neighbors used for Inverse Distance Weighting gap filling",
        default=8,
        min=1,
        max=32,
    )

    subdivision_levels: IntProperty(  # type: ignore[valid-type]
        name="Subdivision Levels",
        description="Subdivision Surface modifier viewport iteration level",
        default=6,
        min=0,
        max=10,
    )

    triangulation_density_pct: FloatProperty(  # type: ignore[valid-type]
        name="Detail Density (%)",
        description="Percentage of selected object vertices included in triangulation (0.1% to 100%)",
        default=10.0,
        min=0.1,
        max=100.0,
        subtype="PERCENTAGE",
    )

    max_triangulation_points: IntProperty(  # type: ignore[valid-type]
        name="Max Vertex Cap",
        description="Maximum point count cap for triangulation safety",
        default=500000,
        min=3,
        max=10000000,
    )

    export_png_path: StringProperty(  # type: ignore[valid-type]
        name="PNG Export Path",
        description="File path destination for 16-bit PNG export",
        subtype="FILE_PATH",
        default="//heightmap_16bit.png",
        options=_PATH_OPTS,
    )


def show_error_popup(message: str, title: str = "XYZ Terrain Notice") -> None:
    """Displays a modal popup dialog with error/warning message in Blender UI when interactive."""
    if bpy.app.background or bpy.context.window_manager is None:
        return

    def draw(self: Any, _context: Any) -> None:
        self.layout.label(text=message, icon="ERROR")

    try:
        bpy.context.window_manager.popup_menu(draw, title=title, icon="ERROR")
    except (RuntimeError, AttributeError):
        pass


def _select_and_activate(context: Any, target_obj: Any) -> None:
    """Deselects all objects in the active view layer and makes target_obj active without bpy.ops."""
    for obj in context.view_layer.objects:
        obj.select_set(False)
    target_obj.select_set(True)
    context.view_layer.objects.active = target_obj


def _clean_terrain_base_name(obj_name: str) -> str:
    """Strips standard XYZ prefixes from an object name to form a clean asset base name."""
    return (
        obj_name.replace("XYZ_PointCloud_", "")
        .replace("XYZ_Terrain_Plane_", "")
        .replace("XYZ_Terrain_Triangulated_", "")
        .replace("XYZ_Terrain_", "")
    )


def _find_active_heightmap_image(context: Any) -> Any | None:
    """Finds the heightmap image from the active object's material or falls back to scene images."""
    obj = context.active_object
    mat = obj.material_slots[0].material if (obj and obj.material_slots) else None
    if mat and mat.use_nodes and mat.node_tree is not None:
        tex_node = next(
            (n for n in mat.node_tree.nodes if n.type == "TEX_IMAGE" and getattr(n, "image", None)),
            None,
        )
        if tex_node is not None:
            return getattr(tex_node, "image", None)

    return next(
        (img for img in bpy.data.images if img.name.startswith("XYZ_Heightmap")),
        None,
    )


def _execute_pointcloud_import(operator: Any, context: Any) -> Any:
    """Shared execution helper that validates settings, parses the XYZ file, and creates the point cloud object."""
    props = context.scene.xyz_terrain_props
    raw_filepath = props.xyz_filepath.strip() if props.xyz_filepath else ""

    if not raw_filepath:
        msg = "Please select a valid .xyz, .pts, or .txt file first!"
        show_error_popup(msg, title="File Not Found")
        operator.report({"ERROR"}, msg)
        return {"CANCELLED"}

    filepath = bpy.path.abspath(raw_filepath)
    if not os.path.isfile(filepath):
        msg = f"XYZ file does not exist on disk: '{filepath}'"
        show_error_popup(msg, title="File Not Found")
        operator.report({"ERROR"}, msg)
        return {"CANCELLED"}

    min_h = props.min_height if props.use_manual_height_filter else None
    max_h = props.max_height if props.use_manual_height_filter else None

    if (
        props.use_manual_height_filter
        and min_h is not None
        and max_h is not None
        and min_h >= max_h
    ):
        msg = f"Min Height ({min_h:.1f}m) must be strictly lower than Max Height ({max_h:.1f}m)!"
        show_error_popup(msg, title="Invalid Height Thresholds")
        operator.report({"ERROR"}, msg)
        return {"CANCELLED"}

    try:
        cloud = load_xyz_file(
            filepath,
            min_height=min_h,
            max_height=max_h,
            auto_clean_outliers=props.auto_filter_height,
            center_to_origin=props.center_to_origin,
        )
    except (ValueError, FileNotFoundError, OSError) as exc:
        show_error_popup(str(exc), title="Import Error")
        operator.report({"ERROR"}, f"Failed to parse file: {exc!s}")
        return {"CANCELLED"}

    base_name = os.path.splitext(os.path.basename(filepath))[0]
    obj_name = f"XYZ_PointCloud_{base_name}"
    pc_obj = create_point_cloud_object(cloud, object_name=obj_name)
    _select_and_activate(context, pc_obj)

    operator.report(
        {"INFO"},
        f"Imported Point Cloud Object '{pc_obj.name}' with {len(cloud.points):,} points.",
    )
    return {"FINISHED"}


class IMPORT_OT_xyz_file_select(bpy.types.Operator, ImportHelper):  # type: ignore[misc]
    """Select and import an XYZ/PTS/TXT Point Cloud file"""

    bl_idname = "import_scene.xyz_file_select"
    bl_label = "Import XYZ Point Cloud"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".xyz"

    filter_glob: StringProperty(  # type: ignore[valid-type]
        default="*.xyz;*.txt;*.pts",
        options={"HIDDEN"},
        maxlen=255,
    )

    def execute(self, context: Any) -> Any:
        props = context.scene.xyz_terrain_props
        props.xyz_filepath = getattr(self, "filepath", "")
        return _execute_pointcloud_import(self, context)


class OBJECT_OT_xyz_import_pointcloud(bpy.types.Operator):
    """Step 1: Import XYZ File as a Point Cloud Object into 3D Viewport"""

    bl_idname = "object.xyz_import_pointcloud"
    bl_label = "Import Point Cloud Object"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: Any) -> Any:
        return _execute_pointcloud_import(self, context)


class OBJECT_OT_xyz_generate_heightmap(bpy.types.Operator):
    """Step 2: Generate Heightmap Float Image & Displaced Plane from Selected Object"""

    bl_idname = "object.xyz_generate_heightmap"
    bl_label = "Generate Heightmap Plane"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: Any) -> Any:
        props = context.scene.xyz_terrain_props
        active_obj = context.active_object

        try:
            source_obj = resolve_source_mesh_object(active_obj)
            cloud = extract_points_from_object(source_obj)
            target_res = (
                (props.custom_res_x, props.custom_res_y)
                if props.resolution_mode == "CUSTOM"
                else None
            )

            _raw_grid, norm_grid = generate_heightmap_grid(
                cloud,
                pixels_per_meter=props.pixels_per_meter,
                target_res=target_res,
                k_neighbors=props.idw_k_neighbors,
            )

            clean_src_name = _clean_terrain_base_name(source_obj.name)
            img_name = f"XYZ_Heightmap_{clean_src_name}"
            img = create_blender_image(norm_grid, image_name=img_name)

            plane_obj = create_displaced_plane(
                img,
                cloud,
                subdivision_levels=props.subdivision_levels,
                object_name=f"XYZ_Terrain_Plane_{clean_src_name}",
                source_pointcloud_name=source_obj.name,
            )

            _select_and_activate(context, plane_obj)
            img_size = cast(Any, img.size)

            self.report(
                {"INFO"},
                f"Created Heightmap Plane '{plane_obj.name}' ({cloud.width_m:.1f}m x {cloud.height_m:.1f}m, Res: {img_size[0]}x{img_size[1]})",
            )
            return {"FINISHED"}
        except (ValueError, RuntimeError) as exc:
            show_error_popup(str(exc), title="Heightmap Generation Error")
            self.report({"ERROR"}, f"Generation failed: {exc!s}")
            return {"CANCELLED"}


class OBJECT_OT_xyz_generate_triangulation(bpy.types.Operator):
    """Step 3: Triangulate Selected Object into a 3D Terrain Mesh using Delaunay CDT"""

    bl_idname = "object.xyz_generate_triangulation"
    bl_label = "Generate Triangulated Mesh"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: Any) -> Any:
        props = context.scene.xyz_terrain_props
        active_obj = context.active_object

        try:
            source_obj = resolve_source_mesh_object(active_obj)
            cloud = extract_points_from_object(source_obj)
            clean_src_name = _clean_terrain_base_name(source_obj.name)
            tri_obj = create_triangulated_mesh(
                cloud,
                point_density_pct=props.triangulation_density_pct,
                max_points=props.max_triangulation_points,
                object_name=f"XYZ_Terrain_Triangulated_{clean_src_name}",
                source_pointcloud_name=source_obj.name,
            )

            _select_and_activate(context, tri_obj)
            tri_mesh = cast(Any, tri_obj.data)

            self.report(
                {"INFO"},
                f"Created Triangulated Mesh '{tri_obj.name}' ({len(tri_mesh.vertices):,} verts, {len(tri_mesh.polygons):,} faces)",
            )
            return {"FINISHED"}
        except (ValueError, RuntimeError) as exc:
            show_error_popup(str(exc), title="Triangulation Error")
            self.report({"ERROR"}, f"Triangulation failed: {exc!s}")
            return {"CANCELLED"}


class OBJECT_OT_xyz_export_16bit_png(bpy.types.Operator):
    """Export active heightmap texture asset as 16-Bit Grayscale PNG file"""

    bl_idname = "object.xyz_export_16bit_png"
    bl_label = "Export 16-Bit PNG Heightmap"
    bl_options = {"REGISTER"}

    def execute(self, context: Any) -> Any:
        props = context.scene.xyz_terrain_props
        raw_path = props.export_png_path.strip() if props.export_png_path else ""

        if not raw_path:
            msg = "Please specify a valid PNG Export Path!"
            show_error_popup(msg, title="Export Path Error")
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}

        if raw_path.startswith("//") and not bpy.data.is_saved:
            msg = "Cannot use relative path '//' before saving the .blend file. Save the project or choose an absolute path."
            show_error_popup(msg, title="Unsaved Blend File")
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}

        out_path = os.path.abspath(bpy.path.abspath(raw_path))
        out_dir = os.path.dirname(out_path)
        if out_dir and not os.path.isdir(out_dir):
            msg = f"Destination directory '{out_dir}' does not exist!"
            show_error_popup(msg, title="Export Folder Missing")
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}

        img = _find_active_heightmap_image(context)
        if img is None:
            msg = "No generated XYZ Heightmap image found in scene. Please generate a heightmap first."
            show_error_popup(msg, title="Image Not Found")
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}

        try:
            export_heightmap_16bit_png(img, out_path)
            self.report(
                {"INFO"}, f"Successfully saved 16-Bit PNG Heightmap to: {out_path}"
            )
            return {"FINISHED"}
        except (RuntimeError, OSError, ValueError) as exc:
            show_error_popup(str(exc), title="PNG Export Error")
            self.report({"ERROR"}, f"Export failed: {exc!s}")
            return {"CANCELLED"}


def menu_func_import(self: Any, _context: Any) -> None:
    self.layout.operator(
        IMPORT_OT_xyz_file_select.bl_idname, text="XYZ Point Cloud (.xyz/.pts/.txt)"
    )
