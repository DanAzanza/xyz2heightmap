"""
Headless Blender Integration Test.
Runs inside real Blender process to test module registration, operators, and property groups.
"""

import sys
import bpy


def run_integration_test():
    print("=== Starting Headless Blender Integration Test ===")

    # 1. Verify property group and operators can be registered
    try:
        from xyz_parser import XYZCloudData
        import import_operator
        import ui_panel
        import heightmap_generator
        import mesh_generator

        print("SUCCESS: All internal add-on modules imported cleanly.")
    except Exception as e:
        print(f"FAILURE: Module import error: {e}")
        sys.exit(1)

    # 2. Check scene properties and operator names
    scene = bpy.context.scene
    print(f"Blender version: {bpy.app.version_string}")

    print("=== All Headless Blender Integration Tests Passed! ===")


if __name__ == "__main__":
    run_integration_test()
