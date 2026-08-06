# XYZ Point Cloud to Heightmap / Mesh Importer for Blender

[![Blender Version](https://img.shields.io/badge/Blender-4.0%2B%20%7C%204.2%2B-orange.svg)](https://www.blender.org/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

An advanced, high-performance **Blender Add-on / Extension** for importing ASCII **XYZ point cloud data files** (`.xyz`, `.txt`, `.pts`) into Blender.

Convert real-world LiDAR, GIS, or DEM elevation data into **3D terrain meshes** or **32-bit floating-point heightmaps** complete with automated displacement shaders, IDW gap filling, and 16-bit PNG export capabilities.

---

## 🌟 Key Features

- **🚀 High-Performance Parsing**: Powered by `numpy.fromfile` for lightning-fast parsing of million-point datasets.
- **🗺️ Dual Generation Modes**:
  1. **2D Float Heightmap Grid**: Generates a 32-bit float texture buffer mapped onto a subdividible plane with an active `Displace` modifier and preconfigured material setup (`Non-Color` color space).
  2. **3D Delaunay/CDT Triangulated Mesh**: Uses Blender's native `mathutils.geometry.delaunay_2d_cdt` for clean, robust 2.5D surface triangulation directly from point clouds.
- **🧹 Noise Outlier Cleaning**: Automatic percentile filtering (`0.1%` to `99.9%`) to eliminate severe measurement noise spikes, plus optional hard elevation min/max thresholds.
- **🎯 Smart Origin Centering**: Automatically shifts geographic coordinates so the bounding box center aligns cleanly with Blender's world origin (`0, 0, 0`).
- **🌐 IDW Gap Filling**: Uses `mathutils.kdtree.KDTree` Inverse Distance Weighting to seamlessly fill missing grid cells in sparse point clouds.
- **💾 16-Bit PNG Heightmap Export**: Built-in utility operator to export generated heightmaps as 16-bit grayscale PNG images for game engines (Unreal Engine, Unity, Godot) or digital sculpting tools.

---

## 🛠️ Installation

### Option A: Blender 4.2+ Extension System (Recommended)

1. Download or clone this repository as a `.zip` archive or directory folder.
2. In Blender, navigate to **Edit > Preferences > Extensions**.
3. Click the drop-down menu in the top right corner and select **Install from Disk...**.
4. Choose `xyz2heightmap.zip` (or select `blender_manifest.toml` inside the unzipped directory).
5. Ensure the extension is enabled.

### Option B: Blender 4.0 & 4.1 (Legacy Add-on Installation)

1. Download the repository source as a `.zip` file.
2. Open Blender, go to **Edit > Preferences > Add-ons**.
3. Click **Install...** and select the `.zip` file.
4. Search for `XYZ Point Cloud Importer` and check the checkbox to activate.

---

## 📖 Usage Guide

The add-on adds a dedicated **XYZ Terrain** tab to the **3D Viewport Sidebar (N-Panel)**, organized into a clean 3-step workflow:

### Step 1: Import XYZ Point Cloud
1. Open the N-Panel (press `N` in the 3D Viewport) and navigate to the **XYZ Terrain** tab.
2. Click **Select XYZ File...** and choose your `.xyz`, `.txt`, or `.pts` dataset.
3. Configure alignment & filtering options:
   - **Center to Origin**: Keeps terrain centered at `(0, 0, 0)`.
   - **Auto-Filter Noise Outliers**: Cleans extreme elevation spikes.
   - **Manual Elevation Filter**: Enforce explicit min/max height limits (in meters).
4. Click **Import Point Cloud**. This imports a point cloud geometry object into the scene.

### Step 2: Generate 2D Heightmap Grid & Displacement
1. Select the imported point cloud object in your viewport.
2. Set your desired resolution:
   - **Pixels per Meter (PPM)**: Automatically calculates image dimensions based on terrain physical size.
   - **Custom Resolution**: Explicitly define pixel width & height (e.g. 1024x1024, 4096x4096).
3. Set **IDW Neighbors** (number of nearest points used for interpolation).
4. Set **Subdivision Levels** for viewport detail.
5. Click **Generate Heightmap Mesh**.
   - *Result*: Creates a displaced terrain plane, generates a 32-bit float texture, applies a `Displace` modifier set to physical Z-amplitude, and creates a preconfigured Cycles/Eevee material with `Non-Color` space settings.

### Step 3: Generate 3D Delaunay Mesh (Alternative)
1. Select the imported point cloud object.
2. Set **Detail Density (%)** to control vertex sampling density (1% to 100%).
3. Set **Max Vertex Cap** for viewport safety.
4. Click **Triangulate 3D Mesh**.
   - *Result*: Generates a clean 3D triangulated mesh object representing the terrain surface.

### Step 4: Export 16-Bit PNG Heightmap
1. Under **Heightmap Generator**, set your output path (e.g. `//terrain_heightmap.png`).
2. Click **Export 16-Bit PNG**. The heightmap is saved as a 16-bit single-channel grayscale PNG image.

---

## 🏗️ Architecture & Codebase Structure

```
xyz2heightmap/
├── __init__.py               # Add-on entry point, bl_info metadata & registration
├── blender_manifest.toml     # Blender 4.2+ Extension manifest specification
├── xyz_parser.py             # Pure Python/NumPy parser & bounding box calculator
├── heightmap_generator.py    # Heightmap rasterizer, IDW KDTree, displacement material
├── mesh_generator.py         # Point cloud mesh & Delaunay 2.5D triangulation builder
├── import_operator.py        # PropertyGroup & UI execution operators
├── ui_panel.py               # N-Panel 3D Viewport layout panels
├── tests/                    # Pytest test suite for core logic
│   └── test_xyz_parser.py
├── LICENSE                   # GNU General Public License v3.0
└── README.md                 # Project documentation
```

---

## 🧪 Running Tests

To run the automated unit test suite locally:

```bash
python -m pytest -v
```

To run Pyright static type checks:

```bash
npx pyright@latest .
```

---

## 📜 License

Distributed under the **GNU General Public License v3.0 (GPLv3)**. See [`LICENSE`](LICENSE) for more information.
