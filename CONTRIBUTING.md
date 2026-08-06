# Contributing to xyz2heightmap

Thank you for your interest in contributing to **xyz2heightmap**!

---

## 🛠️ Development Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/<your-username>/xyz2heightmap.git
   cd xyz2heightmap
   ```

2. **Environment & Dependencies**:
   - Python 3.10+
   - NumPy (`pip install numpy`)
   - Pytest (`pip install pytest`)

3. **Link to Blender for Live Testing**:
   Copy or symlink this folder to your Blender extensions or add-ons folder:
   - **Windows**: `%APPDATA%\Blender Foundation\Blender\<version>\extensions\user_default\xyz_pointcloud_importer`

---

## 🧪 Code Quality & Guidelines

- **Code Style**: Follow PEP 8 guidelines. Write clear, self-documenting code with Python type hints.
- **Strict English**: All code, function names, variable names, docstrings, and commit messages MUST be in English.
- **Zero Placeholders**: Always output complete, functional code without dummy fallbacks or missing logic.
- **Layer Isolation**:
  - `xyz_parser.py`: Pure I/O parsing (no `bpy` dependencies).
  - `heightmap_generator.py`: Grid calculation & buffer generation.
  - `mesh_generator.py`: Mesh & geometry building logic.
  - `import_operator.py`: Operator execution handlers.
  - `ui_panel.py`: Interface layout.

---

## 🔍 Running Tests & Static Analysis

Before opening a pull request, ensure all tests and type checks pass:

```bash
# Run Pytest suite
python -m pytest -v

# Run Pyright type checking
npx pyright@latest .
```

---

## 📥 Submitting Pull Requests

1. Fork the repository and create your feature branch:
   ```bash
   git checkout -b feature/my-new-feature
   ```
2. Commit your changes using imperative mood commit messages (e.g. `Add XYZ point cloud intensity support`).
3. Push to your branch and open a Pull Request against `main`.
