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
- `[manifest]`: `__init__.py` and `blender_manifest.toml` (Extension registration and Blender 5.0+ Extension metadata)
- `[tests]` / `[ci]` / `[docs]`: Test suites, GitHub Actions workflows, and documentation

---

## 3. Blender 5.0+ Extension & Runtime Gotchas
- **Manifest Version Synchronization**: Blender 5.0+ Extensions rely exclusively on [`blender_manifest.toml`](../blender_manifest.toml) (no legacy `bl_info` dictionary in [`__init__.py`](../__init__.py)). Keep `version` in [`blender_manifest.toml`](../blender_manifest.toml) and [`pyproject.toml`](../pyproject.toml) strictly synchronized.
- **Blend-Relative Paths (`//`)**: `bpy.props.StringProperty(subtype="FILE_PATH")` requires `options={"PATH_SUPPORTS_BLEND_RELATIVE"}` so Blender 5.x accepts `//` project-relative paths without emitting a `RuntimeWarning`.
- **Fast C-Buffer Mesh Population**: For multi-million point LiDAR clouds, always populate `bpy.types.Mesh` via `mesh.vertices.add(n)` and `mesh.vertices.foreach_set("co", flat_float32_array)` rather than `mesh.from_pydata(points.tolist(), [], [])` to avoid multi-hundred-MB Python list allocations.
- **Blender 5.x `colorspace_settings` ImBuf Reset**: Assigning `image.colorspace_settings.name = "Non-Color"` in Blender 5.x invalidates and zeroes any unsaved in-memory float pixel buffer (`ImBuf`). Always set `colorspace_settings.name` *before* calling `image.pixels.foreach_set(...)`, and never reassign it afterward in material setup helpers.
- **Embedded Blender Python in CI**: Official standalone Blender tarballs do not bundle `pytest` in their embedded Python environment. `tests/test_blender_addon.py` must guard `import pytest` with `try...except ImportError` so it executes cleanly under `blender --background --python tests/test_blender_addon.py`.
- **Operator Error Reporting in Python Calls**: Invoking a `bpy.ops.*` operator from Python that calls `self.report({"ERROR"}, ...)` and returns `{"CANCELLED"}` raises a `RuntimeError` in the caller rather than returning `{"CANCELLED"}`.
- **Bottom-Up Texture Buffer Orientation**: Blender's `bpy.types.Image.pixels` buffer is ordered bottom-to-top (`row 0` = South / `ymin` / `V = 0.0`, `row res_y - 1` = North / `ymax` / `V = 1.0`). `generate_heightmap_grid` indexes rows directly from `ymin` so `normalized_grid` maps 1:1 to UV coordinates without vertical flipping.
