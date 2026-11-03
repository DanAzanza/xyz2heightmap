"""
Cross-Platform CLI Runner for xyz2heightmap In-Blender Integration Tests.
Executes headless Blender with factory startup and streams test execution results.
"""

from __future__ import annotations

import glob
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("xyz_test_runner")


def _find_windows_blender() -> str | None:
    """Helper to detect Blender across standard Windows directories and AppX packages."""
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        for alias in ("blender.exe", "blender-launcher.exe"):
            win_alias = Path(local_app_data) / "Microsoft" / "WindowsApps" / alias
            if win_alias.is_file():
                return str(win_alias)

    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    pattern = os.path.join(program_files, "Blender Foundation", "Blender *", "blender.exe")
    candidates = sorted(glob.glob(pattern), reverse=True)
    if candidates:
        return candidates[0]

    # Windows Store AppX Package detection via PowerShell
    try:
        cmd = ["powershell", "-NoProfile", "-Command", "(Get-AppxPackage *BlenderFoundation*).InstallLocation"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0 and res.stdout.strip():
            for loc in res.stdout.strip().splitlines():
                cand = Path(loc.strip()) / "Blender" / "blender.exe"
                if cand.is_file():
                    return str(cand)
                cand_direct = Path(loc.strip()) / "blender.exe"
                if cand_direct.is_file():
                    return str(cand_direct)
    except (subprocess.SubprocessError, OSError) as exc:
        logger.debug("PowerShell AppX query skipped: %s", exc)

    return None


def find_blender_binary() -> str | None:
    """Locate Blender executable across Windows, macOS, and Linux platforms."""
    # 1. User-specified environment variable
    custom_bin = os.environ.get("BLENDER_PATH") or os.environ.get("BLENDER_BIN")
    if custom_bin and Path(custom_bin).is_file():
        return custom_bin

    # 2. System PATH
    path_bin = shutil.which("blender")
    if path_bin:
        return path_bin

    # 3. Windows
    if sys.platform == "win32":
        return _find_windows_blender()

    # 4. macOS
    if sys.platform == "darwin":
        mac_app = Path("/Applications/Blender.app/Contents/MacOS/Blender")
        if mac_app.is_file():
            return str(mac_app)

    # 5. Linux
    if sys.platform.startswith("linux"):
        for loc in ("/usr/bin/blender", "/usr/local/bin/blender", "/snap/bin/blender", "/opt/blender/blender"):
            if Path(loc).is_file():
                return loc

    return None


def run_blender_tests(test_file: str | None = None) -> int:
    """Runs the headless Blender integration test using the located Blender binary."""
    blender_bin = find_blender_binary()
    if not blender_bin:
        print(
            "[ERROR] Could not locate Blender executable.\n"
            "Please ensure Blender 5.0+ is installed or set the BLENDER_PATH environment variable.",
            file=sys.stderr,
        )
        return 1

    repo_root = Path(__file__).resolve().parent.parent
    if test_file is None:
        test_path = repo_root / "tests" / "test_blender_addon.py"
    else:
        test_path = Path(test_file).resolve()

    if not test_path.is_file():
        print(f"[ERROR] Test script not found at: {test_path}", file=sys.stderr)
        return 1

    cmd = [
        blender_bin,
        "--background",
        "--factory-startup",
        "--python-exit-code",
        "1",
        "--python",
        str(test_path),
    ]

    print(f"[INFO] Using Blender binary: {blender_bin}")
    print(f"[INFO] Running in-Blender test: {test_path.name}")
    print(f"[INFO] Command: {' '.join(cmd)}\n")

    res = subprocess.run(cmd, cwd=str(repo_root))
    return res.returncode


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(run_blender_tests(target))
