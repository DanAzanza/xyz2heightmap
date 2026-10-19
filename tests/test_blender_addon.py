# pyright: reportMissingImports=false, reportMissingModuleSource=false
"""
Headless Blender Integration Test.
Runs inside a real headless Blender process to verify add-on registration,
end-to-end point cloud import, displaced heightmap plane generation (including UV layer
and re-generation round-trip), Delaunay 2.5D triangulation, and 16-bit PNG export.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    import pytest
except ImportError:
    pytest = None  # type: ignore[assignment]

if importlib.util.find_spec("bpy") is None or not hasattr(importlib.import_module("bpy"), "context"):
    bpy: Any = None
    if pytest is not None:
        pytestmark = pytest.mark.skip(reason="requires real Blender runtime")
else:
    import bpy


def run_integration_test() -> None:
    print("=== Starting Headless Blender End-to-End Integration Test ===")

    if bpy is None or not hasattr(bpy, "context"):
        raise RuntimeError("Real Blender runtime is unavailable")

    repo_root = str(Path(__file__).resolve().parent.parent)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    import __init__ as addon_init

    addon_init.register()

    try:
        scene = bpy.context.scene
        props = scene.xyz_terrain_props

        with tempfile.TemporaryDirectory() as tmp_dir:
            xyz_path = os.path.join(tmp_dir, "terrain_test.xyz")
            with open(xyz_path, "w", encoding="utf-8") as f:
                f.write("100.0 200.0 10.0\n")
                f.write("110.0 200.0 20.0\n")
                f.write("100.0 210.0 15.0\n")
                f.write("110.0 210.0 30.0\n")
                f.write("105.0 205.0 25.0\n")

            # 1. Test Point Cloud Import Operator
            props.xyz_filepath = xyz_path
            props.center_to_origin = True
            props.auto_filter_height = False
            res_imp = bpy.ops.object.xyz_import_pointcloud()
            assert "FINISHED" in res_imp

            pc_obj = bpy.context.active_object
            assert pc_obj is not None
            assert pc_obj.get("is_xyz_pointcloud") is True
            assert len(pc_obj.data.vertices) == 5
            assert pc_obj["real_world_offset_x"] == 105.0
            assert pc_obj["real_world_offset_y"] == 205.0
            assert pc_obj["real_world_offset_z"] == 10.0

            # 2. Test Heightmap Plane Generation Operator
            props.resolution_mode = "CUSTOM"
            props.custom_res_x = 64
            props.custom_res_y = 64
            props.subdivision_levels = 2
            res_hm = bpy.ops.object.xyz_generate_heightmap()
            assert "FINISHED" in res_hm

            plane_obj = bpy.context.active_object
            assert plane_obj is not None
            assert plane_obj.get("is_xyz_displaced_plane") is True
            assert len(plane_obj.data.uv_layers) == 1
            assert len(plane_obj.modifiers) == 2

            # 3. Test Re-Generation Round-Trip while Displaced Plane is still selected
            res_hm_repeat = bpy.ops.object.xyz_generate_heightmap()
            assert "FINISHED" in res_hm_repeat

            # 4. Test Triangulated Mesh Generation (resolving source cloud from plane)
            props.triangulation_density_pct = 100.0
            res_tri = bpy.ops.object.xyz_generate_triangulation()
            assert "FINISHED" in res_tri

            tri_obj = bpy.context.active_object
            assert tri_obj is not None
            assert len(tri_obj.data.vertices) == 5
            assert len(tri_obj.data.polygons) >= 2

            # 5. Negative Test: Unsaved blend file relative path '//' export must be rejected
            props.export_png_path = "//unsaved_relative.png"
            rejected_relative = False
            try:
                res_exp_rel = bpy.ops.object.xyz_export_16bit_png()
                rejected_relative = "CANCELLED" in res_exp_rel
            except RuntimeError as exc:
                rejected_relative = "Cannot use relative path" in str(exc)
            assert rejected_relative

            # 6. Positive Test: 16-Bit PNG Export to absolute path
            png_out = os.path.join(tmp_dir, "exported_16bit.png")
            props.export_png_path = png_out
            res_exp = bpy.ops.object.xyz_export_16bit_png()
            assert "FINISHED" in res_exp
            assert os.path.isfile(png_out)
            assert os.path.getsize(png_out) > 0

    finally:
        addon_init.unregister()

    print("=== All Headless Blender Integration Tests Passed! ===")


if __name__ == "__main__":
    run_integration_test()
