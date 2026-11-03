"""
xyz2heightmap Central Local CI & Quality Gate Verification Script.
Validates dependencies against pyproject.toml, runs linters, type checkers,
unit test suite with coverage, and in-Blender integration tests.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]


def check_dependency_parity(repo_root: Path) -> bool:
    """Verifies that all runtime and dev dependencies are explicitly declared in pyproject.toml."""
    pyproject_path = repo_root / "pyproject.toml"
    if not pyproject_path.exists():
        print("[ERROR] [DepCheck] pyproject.toml not found!")
        return False

    if tomllib is not None:
        with pyproject_path.open("rb") as f:
            data = tomllib.load(f)
        project_deps = data.get("project", {}).get("dependencies", [])
        dev_deps = data.get("project", {}).get("optional-dependencies", {}).get("dev", [])
    else:
        content = pyproject_path.read_text(encoding="utf-8")
        project_deps = re.findall(r'"([^"]+)"', content)
        dev_deps = []

    all_declared = set()
    for dep in project_deps + dev_deps:
        pkg_name = dep.split(">=")[0].split("==")[0].split("<")[0].split(";")[0].strip().lower()
        all_declared.add(pkg_name)

    required_packages = ["numpy", "pytest", "pytest-cov", "pyright", "ruff"]
    missing = [pkg for pkg in required_packages if pkg not in all_declared]

    if missing:
        print(f"[ERROR] [DepCheck] Undeclared dependencies in pyproject.toml: {missing}")
        return False

    print("[PASS] [DepCheck] All dependencies properly declared in pyproject.toml.")
    return True


def run_command(cmd: list[str], desc: str, cwd: Path) -> bool:
    """Runs a subprocess command and reports pass/fail."""
    print(f"\n[INFO] Verifying: {desc}...")
    res = subprocess.run(cmd, cwd=str(cwd), text=True)
    if res.returncode != 0:
        print(f"[FAIL] {desc} exited with code {res.returncode}")
        return False
    print(f"[PASS] {desc}")
    return True


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent

    print("=" * 60)
    print("xyz2heightmap Pre-Commit Quality & CI Parity Gate")
    print("=" * 60)

    if not check_dependency_parity(repo_root):
        return 1

    if not run_command([sys.executable, "-m", "ruff", "check", "."], "Ruff Linter", repo_root):
        return 1

    if not run_command([sys.executable, "-m", "pyright"], "Pyright Static Type Checker", repo_root):
        return 1

    pytest_cmd = [
        sys.executable,
        "-m",
        "pytest",
        "--cov=.",
        "--cov-report=term-missing",
        "-v",
    ]
    if not run_command(pytest_cmd, "Pytest Test Suite with Coverage", repo_root):
        return 1

    # In-Blender integration test suite check
    require_blender = "--require-blender" in sys.argv
    skip_blender = "--skip-blender" in sys.argv

    if skip_blender:
        print("\n[SKIP] Blender integration tests skipped (--skip-blender specified).")
    else:
        try:
            from scripts.run_blender_tests import find_blender_binary, run_blender_tests
        except ImportError:
            sys.path.insert(0, str(repo_root))
            from scripts.run_blender_tests import find_blender_binary, run_blender_tests

        blender_bin = find_blender_binary()
        if blender_bin:
            print("\n[INFO] Verifying: In-Blender Integration Test Suite...")
            code = run_blender_tests()
            if code != 0:
                print(f"[FAIL] In-Blender Integration Test Suite exited with code {code}")
                return 1
            print("[PASS] In-Blender Integration Test Suite")
        elif require_blender:
            print("[FAIL] [BlenderGate] Blender binary required (--require-blender) but not found!")
            return 1
        else:
            print("\n[SKIP] Blender executable not detected. Skipping in-Blender integration tests.")

    print("\n" + "=" * 60)
    print("ALL GATES PASSED DETERMINISTICALLY! Ready for Commit & Push.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
