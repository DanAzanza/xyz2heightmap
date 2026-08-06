"""
Import Operators & Scene Properties Module.
Defines PropertyGroup, File Picker Operator, and Standalone Generation Operators.
"""

import os
import bpy
from bpy.props import (
    StringProperty,
    BoolProperty,
    FloatProperty,
    IntProperty,
    EnumProperty
)
from bpy_extras.io_utils import ImportHelper

from .xyz_parser import load_xyz_file
from .heightmap_generator import generate_heightmap_grid, create_blender_image, export_heightmap_16bit_png
from .mesh_generator import (
    create_point_cloud_object,
    extract_points_from_object,
    create_displaced_plane,
    create_triangulated_mesh
)


class XYZTerrainProperties(bpy.types.PropertyGroup):
    """Scene properties for XYZ Terrain plugin"""
    xyz_filepath: StringProperty(
        name="XYZ Point Cloud File",
        description="Path to the .xyz point cloud data file",
        subtype='FILE_PATH'
    )

    center_to_origin: BoolProperty(
        name="Center to Scene Origin (0,0,0)",
        description="Shift point cloud coordinates so bounding box center is positioned at Blender origin (0, 0, 0)",
        default=True
    )

    auto_filter_height: BoolProperty(
        name="Auto-Filter Noise Outliers",
        description="Automatically remove extreme noise percentiles below 0.1% and above 99.9%",
        default=True
    )

    use_manual_height_filter: BoolProperty(
        name="Use Manual Elevation Filter",
        description="Enable hard minimum and maximum elevation thresholds",
        default=False
    )

    min_height: FloatProperty(
        name="Min Height (m)",
        description="Manual minimum elevation filter threshold",
        default=0.0
    )

    max_height: FloatProperty(
        name="Max Height (m)",
        description="Manual maximum elevation filter threshold",
        default=500.0
    )

    resolution_mode: EnumProperty(
        name="Resolution Mode",
        description="Choose between Pixels per Meter or Custom Pixel Dimensions",
        items=[
            ('PPM', "Pixels per Meter", "Set resolution based on pixels per meter"),
            ('CUSTOM', "Custom Resolution", "Explicit pixel width and height dimensions"),
        ],
        default='PPM'
    )

    pixels_per_meter: FloatProperty(
        name="Pixels per Meter",
        description="Resolution of the generated heightmap grid (pixels / meter)",
        default=1.0,
        min=0.1,
        max=50.0
    )

    custom_res_x: IntProperty(
        name="Width (px)",
        description="Custom pixel width of heightmap image",
        default=1024,
        min=64,
        max=16384
    )

    custom_res_y: IntProperty(
        name="Height (px)",
        description="Custom pixel height of heightmap image",
        default=1024,
        min=64,
        max=16384
    )

    idw_k_neighbors: IntProperty(
        name="IDW Neighbors",
        description="Number of nearest neighbors used for Inverse Distance Weighting KDTree gap filling",
        default=8,
        min=1,
        max=32
    )

    subdivision_levels: IntProperty(
        name="Subdivision Levels",
        description="Subdivision Surface modifier viewport iteration level",
        default=4,
        min=0,
        max=7
    )

    triangulation_density_pct: FloatProperty(
        name="Detail Density (%)",
        description="Percentage of selected object vertices included in triangulation (1% to 100%)",
        default=10.0,
        min=0.1,
        max=100.0,
        subtype='PERCENTAGE'
    )

    max_triangulation_points: IntProperty(
        name="Max Vertex Cap",
        description="Maximum point count cap for triangulation safety",
        default=500000,
        min=1000,
        max=5000000
    )

    export_png_path: StringProperty(
        name="PNG Export Path",
        description="File path destination for 16-bit PNG export",
        subtype='FILE_PATH',
        default="//heightmap_16bit.png"
    )


def show_error_popup(message: str, title: str = "XYZ Terrain Notice"):
    """Displays a modal popup dialog with error/warning message in Blender UI."""
    def draw(self, context):
        self.layout.label(text=message, icon='ERROR')
    try:
        bpy.context.window_manager.popup_menu(draw, title=title, icon='ERROR')
    except Exception:
        pass


class IMPORT_OT_xyz_file_select(bpy.types.Operator, ImportHelper):
    """Select XYZ Point Cloud file for import"""
    bl_idname = "import_scene.xyz_file_select"
    bl_label = "Select XYZ Point Cloud"

    filename_ext = ".xyz"

    filter_glob: StringProperty(
        default="*.xyz;*.txt;*.pts",
        options={'HIDDEN'},
        maxlen=255,
    )

    def execute(self, context):
        props = context.scene.xyz_terrain_props
        props.xyz_filepath = self.filepath
        self.report({'INFO'}, f"Selected XYZ file: {self.filepath}")
        return {'FINISHED'}


class OBJECT_OT_xyz_import_pointcloud(bpy.types.Operator):
    """Step 1: Import XYZ File as a Point Cloud Object into 3D Viewport"""
    bl_idname = "object.xyz_import_pointcloud"
    bl_label = "Import Point Cloud Object"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.xyz_terrain_props
        filepath = props.xyz_filepath

        if not filepath or not os.path.exists(filepath):
            msg = "Please select a valid .xyz file first!"
            show_error_popup(msg, title="File Not Found")
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}

        min_h = props.min_height if props.use_manual_height_filter else None
        max_h = props.max_height if props.use_manual_height_filter else None

        if props.use_manual_height_filter and min_h is not None and max_h is not None and min_h >= max_h:
            msg = f"Min Height ({min_h:.1f}m) must be strictly lower than Max Height ({max_h:.1f}m)!"
            show_error_popup(msg, title="Invalid Height Thresholds")
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}

        try:
            cloud = load_xyz_file(
                filepath,
                min_height=min_h,
                max_height=max_h,
                auto_clean_outliers=props.auto_filter_height,
                center_to_origin=props.center_to_origin
            )
        except Exception as e:
            show_error_popup(str(e), title="Import Error")
            self.report({'ERROR'}, f"Failed to parse file: {str(e)}")
            return {'CANCELLED'}

        base_name = os.path.splitext(os.path.basename(filepath))[0]
        obj_name = f"XYZ_PointCloud_{base_name}"

        pc_obj = create_point_cloud_object(cloud, object_name=obj_name)

        bpy.ops.object.select_all(action='DESELECT')
        pc_obj.select_set(True)
        context.view_layer.objects.active = pc_obj

        self.report(
            {'INFO'},
            f"Imported Point Cloud Object '{pc_obj.name}' with {len(cloud.points):,} points."
        )
        return {'FINISHED'}


class OBJECT_OT_xyz_generate_heightmap(bpy.types.Operator):
    """Step 2: Generate Heightmap Float Image & Displaced Plane from Selected Object"""
    bl_idname = "object.xyz_generate_heightmap"
    bl_label = "Generate Heightmap Plane"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.xyz_terrain_props
        active_obj = context.active_object

        if not active_obj:
            msg = "No object selected! Select a Point Cloud object in the 3D Viewport."
            show_error_popup(msg, title="No Object Selected")
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}

        if active_obj.type != 'MESH':
            msg = f"Selected '{active_obj.name}' is a {active_obj.type}. Please select a Mesh or Point Cloud object!"
            show_error_popup(msg, title="Invalid Object Type")
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}

        if not active_obj.data or len(active_obj.data.vertices) == 0:
            msg = f"Selected mesh '{active_obj.name}' contains 0 vertices!"
            show_error_popup(msg, title="Empty Mesh")
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}

        try:
            cloud = extract_points_from_object(active_obj)
            target_res = (props.custom_res_x, props.custom_res_y) if props.resolution_mode == 'CUSTOM' else None

            raw_grid, norm_grid = generate_heightmap_grid(
                cloud,
                pixels_per_meter=props.pixels_per_meter,
                target_res=target_res,
                k_neighbors=props.idw_k_neighbors
            )

            clean_src_name = active_obj.name.replace("XYZ_PointCloud_", "").replace("XYZ_Terrain_", "")
            img_name = f"XYZ_Heightmap_{clean_src_name}"
            img = create_blender_image(norm_grid, image_name=img_name)

            plane_obj = create_displaced_plane(
                img,
                cloud,
                subdivision_levels=props.subdivision_levels,
                object_name=f"XYZ_Terrain_Plane_{clean_src_name}"
            )

            bpy.ops.object.select_all(action='DESELECT')
            plane_obj.select_set(True)
            context.view_layer.objects.active = plane_obj

            self.report(
                {'INFO'},
                f"Created Heightmap Plane '{plane_obj.name}' ({cloud.width_m:.1f}m x {cloud.height_m:.1f}m, Res: {img.size[0]}x{img.size[1]})"
            )
            return {'FINISHED'}
        except Exception as e:
            show_error_popup(str(e), title="Heightmap Generation Error")
            self.report({'ERROR'}, f"Generation failed: {str(e)}")
            return {'CANCELLED'}


class OBJECT_OT_xyz_generate_triangulation(bpy.types.Operator):
    """Step 3: Triangulate Selected Object into a 3D Terrain Mesh using Delaunay CDT"""
    bl_idname = "object.xyz_generate_triangulation"
    bl_label = "Generate Triangulated Mesh"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.xyz_terrain_props
        active_obj = context.active_object

        if not active_obj:
            msg = "No object selected! Select a Point Cloud object in the 3D Viewport."
            show_error_popup(msg, title="No Object Selected")
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}

        if active_obj.type != 'MESH':
            msg = f"Selected '{active_obj.name}' is a {active_obj.type}. Please select a Mesh object!"
            show_error_popup(msg, title="Invalid Object Type")
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}

        if not active_obj.data or len(active_obj.data.vertices) == 0:
            msg = f"Selected mesh '{active_obj.name}' contains 0 vertices!"
            show_error_popup(msg, title="Empty Mesh")
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}

        try:
            cloud = extract_points_from_object(active_obj)
            clean_src_name = active_obj.name.replace("XYZ_PointCloud_", "").replace("XYZ_Terrain_", "")
            tri_obj = create_triangulated_mesh(
                cloud,
                point_density_pct=props.triangulation_density_pct,
                max_points=props.max_triangulation_points,
                object_name=f"XYZ_Terrain_Triangulated_{clean_src_name}"
            )

            bpy.ops.object.select_all(action='DESELECT')
            tri_obj.select_set(True)
            context.view_layer.objects.active = tri_obj

            self.report(
                {'INFO'},
                f"Created Triangulated Mesh '{tri_obj.name}' ({len(tri_obj.data.vertices):,} verts, {len(tri_obj.data.polygons):,} faces)"
            )
            return {'FINISHED'}
        except Exception as e:
            show_error_popup(str(e), title="Triangulation Error")
            self.report({'ERROR'}, f"Triangulation failed: {str(e)}")
            return {'CANCELLED'}


class OBJECT_OT_xyz_export_16bit_png(bpy.types.Operator):
    """Export active heightmap texture asset as 16-Bit Grayscale PNG file"""
    bl_idname = "object.xyz_export_16bit_png"
    bl_label = "Export 16-Bit PNG Heightmap"
    bl_options = {'REGISTER'}

    def execute(self, context):
        props = context.scene.xyz_terrain_props
        out_path = bpy.path.abspath(props.export_png_path)

        if not out_path or out_path.strip() == "":
            msg = "Please specify a valid PNG Export Path!"
            show_error_popup(msg, title="Export Path Error")
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}

        out_dir = os.path.dirname(out_path)
        if out_dir and not os.path.exists(out_dir):
            msg = f"Destination directory '{out_dir}' does not exist!"
            show_error_popup(msg, title="Export Folder Missing")
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}

        img = None
        obj = context.active_object
        if obj and obj.material_slots:
            mat = obj.material_slots[0].material
            if mat and mat.use_nodes:
                for node in mat.node_tree.nodes:
                    if node.type == 'TEX_IMAGE' and node.image:
                        img = node.image
                        break

        if not img:
            for image in bpy.data.images:
                if image.name.startswith("XYZ_Heightmap"):
                    img = image
                    break

        if not img:
            msg = "No generated XYZ Heightmap image found in scene. Please generate a heightmap first."
            show_error_popup(msg, title="Image Not Found")
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}

        try:
            export_heightmap_16bit_png(img, out_path)
            self.report({'INFO'}, f"Successfully saved 16-Bit PNG Heightmap to: {out_path}")
        except Exception as e:
            show_error_popup(str(e), title="PNG Export Error")
            self.report({'ERROR'}, f"Export failed: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


def menu_func_import(self, context):
    self.layout.operator(IMPORT_OT_xyz_file_select.bl_idname, text="XYZ Point Cloud (.xyz)")
