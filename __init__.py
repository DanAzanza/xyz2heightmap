# pyright: reportMissingImports=false, reportMissingModuleSource=false
"""
XYZ Point Cloud to Heightmap / Mesh Importer Blender Add-on.
"""

from typing import Any, cast

bl_info = {
    "name": "XYZ Point Cloud Importer",
    "author": "Daniel Azanza Hartmann & Antigravity AI",
    "version": (2, 2, 0),
    "blender": (4, 0, 0),
    "location": "3D View > Sidebar (N-Panel) > XYZ Terrain & File > Import > XYZ Point Cloud",
    "description": "Imports XYZ point cloud files as 2D heightmap textures with height-scaled displaced planes or 3D triangulated meshes.",
    "warning": "",
    "doc_url": "",
    "category": "Import-Export",
}

XYZTerrainProperties: Any = None
menu_func_import: Any = None

try:
    import bpy

    try:
        from .import_operator import (
            IMPORT_OT_xyz_file_select,
            OBJECT_OT_xyz_export_16bit_png,
            OBJECT_OT_xyz_generate_heightmap,
            OBJECT_OT_xyz_generate_triangulation,
            OBJECT_OT_xyz_import_pointcloud,
            XYZTerrainProperties,
            menu_func_import,
        )
        from .ui_panel import (
            VIEW3D_PT_xyz_1_import,
            VIEW3D_PT_xyz_2_heightmap,
            VIEW3D_PT_xyz_3_triangulation,
        )
    except ImportError:
        from import_operator import (
            IMPORT_OT_xyz_file_select,
            OBJECT_OT_xyz_export_16bit_png,
            OBJECT_OT_xyz_generate_heightmap,
            OBJECT_OT_xyz_generate_triangulation,
            OBJECT_OT_xyz_import_pointcloud,
            XYZTerrainProperties,
            menu_func_import,
        )
        from ui_panel import (
            VIEW3D_PT_xyz_1_import,
            VIEW3D_PT_xyz_2_heightmap,
            VIEW3D_PT_xyz_3_triangulation,
        )

    classes: tuple[Any, ...] = (
        XYZTerrainProperties,
        IMPORT_OT_xyz_file_select,
        OBJECT_OT_xyz_import_pointcloud,
        OBJECT_OT_xyz_generate_heightmap,
        OBJECT_OT_xyz_generate_triangulation,
        OBJECT_OT_xyz_export_16bit_png,
        VIEW3D_PT_xyz_1_import,
        VIEW3D_PT_xyz_2_heightmap,
        VIEW3D_PT_xyz_3_triangulation,
    )
except ImportError:
    bpy = None  # type: ignore[assignment]
    classes = ()


def register() -> None:
    if bpy is None:
        raise RuntimeError("register() requires an active Blender (bpy) runtime.")
    for cls in classes:
        bpy.utils.register_class(cls)
    cast(Any, bpy.types.Scene).xyz_terrain_props = bpy.props.PointerProperty(type=XYZTerrainProperties)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister() -> None:
    if bpy is None:
        return
    try:
        bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    except (RuntimeError, ValueError, AttributeError):
        pass
    if hasattr(bpy.types.Scene, "xyz_terrain_props"):
        delattr(bpy.types.Scene, "xyz_terrain_props")
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except (RuntimeError, ValueError):
            pass


if __name__ == "__main__":
    register()
