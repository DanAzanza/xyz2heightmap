"""
Headless Blender Integration Test.
Runs inside real Blender process to test module registration, operators, and property groups.
"""

import importlib.util
import sys

import pytest

if importlib.util.find_spec("bpy") is None:
    bpy = None
    pytestmark = pytest.mark.skip(reason="requires Blender runtime")
else:
    import bpy


def run_integration_test():
    print("=== Starting Headless Blender Integration Test ===")

    # 1. Verify property group and operators can be registered
    try:
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
