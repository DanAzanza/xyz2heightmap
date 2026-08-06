"""
UI Panel Module.
Defines Sidebar Panels in the 3D Viewport (N-Panel > XYZ Terrain Tab).
"""

import os
import bpy
from .import_operator import (
    OBJECT_OT_xyz_import_pointcloud,
    OBJECT_OT_xyz_generate_heightmap,
    OBJECT_OT_xyz_generate_triangulation,
    OBJECT_OT_xyz_export_16bit_png
)


class VIEW3D_PT_xyz_1_import(bpy.types.Panel):
    """Panel 1: Point Cloud File Import & Setup"""
    bl_label = "1. Point Cloud Import"
    bl_idname = "VIEW3D_PT_xyz_1_import"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "XYZ Terrain"
    bl_order = 1

    def draw(self, context):
        layout = self.layout
        props = context.scene.xyz_terrain_props

        layout.prop(props, "xyz_filepath", text="File Path")
        
        if not props.xyz_filepath:
            box = layout.box()
            box.label(text="Select an XYZ file to begin", icon='INFO')
        else:
            abs_path = bpy.path.abspath(props.xyz_filepath)
            if not os.path.exists(abs_path):
                box = layout.box()
                box.alert = True
                box.label(text="File does not exist on disk!", icon='ERROR')

        layout.prop(props, "center_to_origin")
        layout.prop(props, "auto_filter_height")

        layout.prop(props, "use_manual_height_filter")
        if props.use_manual_height_filter:
            sub = layout.column(align=True)
            sub.prop(props, "min_height")
            sub.prop(props, "max_height")
            if props.min_height >= props.max_height:
                box = layout.box()
                box.alert = True
                box.label(text="Min Height must be lower than Max!", icon='ERROR')

        row_imp = layout.row(align=True)
        row_imp.scale_y = 1.3
        row_imp.operator(
            OBJECT_OT_xyz_import_pointcloud.bl_idname,
            text="Import Point Cloud",
            icon='IMPORT'
        )


class VIEW3D_PT_xyz_2_heightmap(bpy.types.Panel):
    """Panel 2: Heightmap Plane Generator & 16-Bit PNG Export"""
    bl_label = "2. Heightmap Plane Generator"
    bl_idname = "VIEW3D_PT_xyz_2_heightmap"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "XYZ Terrain"
    bl_order = 2

    def draw(self, context):
        layout = self.layout
        props = context.scene.xyz_terrain_props

        active_obj = context.active_object
        if not active_obj:
            box = layout.box()
            box.label(text="Select a Point Cloud object in Viewport", icon='RESTRICT_SELECT_OFF')
        elif active_obj.type != 'MESH':
            box = layout.box()
            box.alert = True
            box.label(text=f"Selected object is {active_obj.type} (Mesh required)", icon='ERROR')
        elif not active_obj.data or len(active_obj.data.vertices) == 0:
            box = layout.box()
            box.alert = True
            box.label(text="Selected mesh has 0 vertices!", icon='ERROR')

        layout.prop(props, "resolution_mode", expand=True)
        if props.resolution_mode == 'PPM':
            layout.prop(props, "pixels_per_meter")
        else:
            col = layout.column(align=True)
            col.prop(props, "custom_res_x")
            col.prop(props, "custom_res_y")

        layout.prop(props, "idw_k_neighbors")
        layout.prop(props, "subdivision_levels")

        btn_hm = layout.row(align=True)
        btn_hm.scale_y = 1.4
        btn_hm.operator(
            OBJECT_OT_xyz_generate_heightmap.bl_idname,
            text="Generate Heightmap Plane",
            icon='RENDER_RESULT'
        )

        layout.separator()
        layout.label(text="16-Bit PNG Export", icon='IMAGE_FILE')
        
        img_found = any(img.name.startswith("XYZ_Heightmap") for img in bpy.data.images)
        if not img_found:
            box = layout.box()
            box.label(text="No Heightmap texture found in scene", icon='INFO')

        layout.prop(props, "export_png_path", text="PNG Path")
        btn_exp = layout.row(align=True)
        btn_exp.scale_y = 1.2
        btn_exp.operator(
            OBJECT_OT_xyz_export_16bit_png.bl_idname,
            text="Export 16-Bit PNG",
            icon='EXPORT'
        )


class VIEW3D_PT_xyz_3_triangulation(bpy.types.Panel):
    """Panel 3: Triangulated 3D Mesh Studio (Delaunay CDT)"""
    bl_label = "3. Triangulated 3D Mesh"
    bl_idname = "VIEW3D_PT_xyz_3_triangulation"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "XYZ Terrain"
    bl_order = 3

    def draw(self, context):
        layout = self.layout
        props = context.scene.xyz_terrain_props

        active_obj = context.active_object
        if not active_obj:
            box = layout.box()
            box.label(text="Select a Point Cloud object in Viewport", icon='RESTRICT_SELECT_OFF')
        elif active_obj.type != 'MESH':
            box = layout.box()
            box.alert = True
            box.label(text=f"Selected object is {active_obj.type} (Mesh required)", icon='ERROR')
        elif not active_obj.data or len(active_obj.data.vertices) == 0:
            box = layout.box()
            box.alert = True
            box.label(text="Selected mesh has 0 vertices!", icon='ERROR')

        layout.prop(props, "triangulation_density_pct")
        layout.prop(props, "max_triangulation_points")

        btn_tri = layout.row(align=True)
        btn_tri.scale_y = 1.4
        btn_tri.operator(
            OBJECT_OT_xyz_generate_triangulation.bl_idname,
            text="Generate Triangulated Mesh",
            icon='MOD_TRIANGULATE'
        )
