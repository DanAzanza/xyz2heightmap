# Project Knowledge Base (`xyz2heightmap`)

## 1. Central Verification & CI Parity Gate Commands
Run the following commands from the repository root before any commit or release:

```bash
# 1. Linter & Import Sorting
python -m ruff check .

# 2. Static Type Checking (Pure Core + Blender Modules)
python -m pyright

# 3. Unit & Domain Test Suite (Pure Python / NumPy)
python -m pytest -v

# 4. Headless Blender End-to-End Integration Test
blender --background --python tests/test_blender_addon.py
```

---

## 2. Version Control Commit Scopes
Prefix commit subject lines (max 50 chars, imperative mood) with one of the following component scopes in brackets:
- `[parser]`: `xyz_parser.py` (ASCII `.xyz`/`.pts`/`.txt` loading, outlier filtering, coordinate bounds)
- `[heightmap]`: `heightmap_generator.py` (2D grid rasterization, physical-space IDW interpolation, float image buffer & 16-bit PNG export)
- `[mesh]`: `mesh_generator.py` (Point cloud mesh creation, UV-mapped displaced plane, Delaunay 2.5D triangulation)
- `[operators]`: `import_operator.py` (`XYZTerrainProperties` RNA definitions and Blender operator execution handlers)
- `[ui]`: `ui_panel.py` (3D Viewport N-Panel layout and validation badges)
- `[manifest]`: `__init__.py` and `blender_manifest.toml` (Add-on registration and Blender 4.2+ Extension metadata)
- `[tests]` / `[ci]` / `[docs]`: Test suites, GitHub Actions workflows, and documentation

---

## 3. Blender 4.0+ / 4.2+ Extension & Runtime Gotchas
- **Dual Manifest Requirement**: Keep `bl_info["version"]` in [`__init__.py`](../__init__.py), `version` in [`blender_manifest.toml`](../blender_manifest.toml), and `version` in [`pyproject.toml`](../pyproject.toml) strictly synchronized.
- **Blender 4.2+ Blend-Relative Paths (`//`)**: `bpy.props.StringProperty(subtype="FILE_PATH")` emits a `RuntimeWarning` in Blender 4.2+ when assigned a `//` path unless `options={"PATH_SUPPORTS_BLEND_RELATIVE"}` is passed. Guard this option with `bpy.app.version >= (4, 2, 0)` to preserve Blender 4.0/4.1 compatibility.
- **Embedded Blender Python in CI**: Official standalone Blender tarballs do not bundle `pytest` in their embedded Python environment. `tests/test_blender_addon.py` must guard `import pytest` with `try...except ImportError` so it executes cleanly under `blender --background --python tests/test_blender_addon.py`.
- **Operator Error Reporting in Python Calls**: Invoking a `bpy.ops.*` operator from Python that calls `self.report({"ERROR"}, ...)` and returns `{"CANCELLED"}` raises a `RuntimeError` in the caller rather than returning `{"CANCELLED"}`.
- **Bottom-Up Texture Buffer Orientation**: Blender's `bpy.types.Image.pixels` buffer is ordered bottom-to-top (`row 0` = South / `ymin` / `V = 0.0`, `row res_y - 1` = North / `ymax` / `V = 1.0`). `generate_heightmap_grid` indexes rows directly from `ymin` so `normalized_grid` maps 1:1 to UV coordinates without vertical flipping.
