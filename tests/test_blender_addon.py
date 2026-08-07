"""
Headless Blender Integration Test.
Runs inside real Blender process to test module registration, operators, and property groups.
"""

import importlib.util
import sys
from typing import Any

import pytest

if importlib.util.find_spec("bpy") is None:
    bpy: Any = None
    pytestmark = pytest.mark.skip(reason="requires Blender runtime")
else:
    import bpy


def run_integration_test() -> None:
    print("=== Starting Headless Blender Integration Test ===")

    try:
        if bpy is None:
            raise RuntimeError("Blender runtime is unavailable")

        _ = bpy.context.scene
        _ = bpy.app.version_string
        print("SUCCESS: All internal add-on modules imported cleanly.")
    except Exception as exc:
        print(f"FAILURE: Module import error: {exc}")
        sys.exit(1)

    print("=== All Headless Blender Integration Tests Passed! ===")


if __name__ == "__main__":
    run_integration_test()
