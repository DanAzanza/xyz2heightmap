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

            # 1b. Negative Test: Point cloud import rejects relative path '//' on unsaved blend
            props.xyz_filepath = "//unsaved_relative.xyz"
            rejected_import_rel = False
            try:
                res_imp_rel = bpy.ops.object.xyz_import_pointcloud()
                rejected_import_rel = "CANCELLED" in res_imp_rel
            except RuntimeError as exc:
                rejected_import_rel = "Cannot use relative path" in str(exc)
            assert rejected_import_rel
            props.xyz_filepath = xyz_path

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

            hm_img = bpy.data.images.get("XYZ_Heightmap_terrain_test")
            assert hm_img is not None
            assert max(hm_img.pixels[:]) > 0.99
            if hasattr(hm_img, "buffers_free"):
                hm_img.buffers_free()

            depsgraph = bpy.context.evaluated_depsgraph_get()
            eval_plane = plane_obj.evaluated_get(depsgraph)
            eval_mesh = eval_plane.to_mesh()
            eval_z_max = max(v.co.z for v in eval_mesh.vertices)
            eval_plane.to_mesh_clear()
            assert eval_z_max > 15.0

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

            # 7. Boundary & Negative Tests for Core Generator Functions
            import numpy as np

            from heightmap_generator import export_heightmap_16bit_png
            from mesh_generator import (
                create_displaced_plane,
                create_point_cloud_object,
                create_triangulated_mesh,
                extract_points_from_object,
            )
            from xyz_parser import XYZCloudData

            sample_cloud = XYZCloudData(
                points=np.array([[0.0, 0.0, 1.0], [1.0, 1.0, 2.0], [2.0, 0.0, 3.0]]),
                xmin=0.0, xmax=2.0, ymin=0.0, ymax=1.0, zmin=1.0, zmax=3.0,
                origin_offset=(0.0, 0.0, 0.0),
            )

            # 7a. Missing target_collection must raise ValueError
            try:
                create_point_cloud_object(sample_cloud, target_collection=None)
                raise AssertionError("Expected ValueError for missing target_collection")
            except ValueError as exc:
                assert "target_collection must be explicitly provided" in str(exc)

            # 7b. Colinear 1D cloud in create_displaced_plane must raise ValueError
            colinear_cloud = XYZCloudData(
                points=np.array([[0.0, 0.0, 1.0], [1.0, 0.0, 2.0]]),
                xmin=0.0, xmax=1.0, ymin=0.0, ymax=0.0, zmin=1.0, zmax=2.0,
                origin_offset=(0.0, 0.0, 0.0),
            )
            try:
                create_displaced_plane(hm_img, colinear_cloud, target_collection=scene.collection)
                raise AssertionError("Expected ValueError for colinear 1D cloud")
            except ValueError as exc:
                assert "colinear point cloud" in str(exc)

            # 7c. < 3 points in create_triangulated_mesh must raise ValueError
            try:
                create_triangulated_mesh(colinear_cloud, target_collection=scene.collection)
                raise AssertionError("Expected ValueError for <3 points")
            except ValueError as exc:
                assert "requires at least 3 points" in str(exc)

            # 7d. Invalid density in create_triangulated_mesh must raise ValueError
            try:
                create_triangulated_mesh(sample_cloud, point_density_pct=0.0, target_collection=scene.collection)
                raise AssertionError("Expected ValueError for density <= 0")
            except ValueError as exc:
                assert "point_density_pct must be in (0, 100]" in str(exc)

            # 7e. Missing scene in export_heightmap_16bit_png must raise ValueError
            try:
                export_heightmap_16bit_png(hm_img, png_out, scene=None)
                raise AssertionError("Expected ValueError for missing scene")
            except ValueError as exc:
                assert "scene parameter must be explicitly provided" in str(exc)

            # 7f. Non-mesh object in extract_points_from_object must raise ValueError
            empty_obj = bpy.data.objects.new(name="Empty_Test", object_data=None)
            scene.collection.objects.link(empty_obj)
            try:
                extract_points_from_object(empty_obj)
                raise AssertionError("Expected ValueError for non-mesh object")
            except ValueError as exc:
                assert "Please select a Mesh or Point Cloud object" in str(exc)
            finally:
                scene.collection.objects.unlink(empty_obj)
                bpy.data.objects.remove(empty_obj)

    finally:
        addon_init.unregister()

    print("=== All Headless Blender Integration Tests Passed! ===")


if __name__ == "__main__":
    run_integration_test()
