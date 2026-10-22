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
blender --background --factory-startup --python-exit-code 1 --python tests/test_blender_addon.py
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
