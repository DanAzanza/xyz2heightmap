"""
Unit tests for developer automation scripts (run_blender_tests, verify_ci).
"""

from __future__ import annotations

import sys
from pathlib import Path

from scripts.run_blender_tests import find_blender_binary, run_blender_tests
from scripts.verify_ci import check_dependency_parity, run_command


def test_find_blender_binary_custom_env(tmp_path: Path, monkeypatch) -> None:
    fake_blender = tmp_path / "blender.exe"
    fake_blender.write_text("fake binary", encoding="utf-8")
    monkeypatch.setenv("BLENDER_PATH", str(fake_blender))

    assert find_blender_binary() == str(fake_blender)


def test_find_blender_binary_missing_env(tmp_path: Path, monkeypatch) -> None:
    non_existent = tmp_path / "does_not_exist" / "blender.exe"
    monkeypatch.setenv("BLENDER_PATH", str(non_existent))
    monkeypatch.delenv("BLENDER_BIN", raising=False)
    monkeypatch.setattr("shutil.which", lambda _cmd: None)
    monkeypatch.setattr("sys.platform", "unknown_os")

    assert find_blender_binary() is None


def test_run_blender_tests_missing_blender(monkeypatch) -> None:
    monkeypatch.setattr("scripts.run_blender_tests.find_blender_binary", lambda: None)
    code = run_blender_tests()
    assert code == 1


def test_run_blender_tests_missing_script(tmp_path: Path, monkeypatch) -> None:
    fake_blender = tmp_path / "blender.exe"
    fake_blender.write_text("binary", encoding="utf-8")
    monkeypatch.setattr("scripts.run_blender_tests.find_blender_binary", lambda: str(fake_blender))

    missing_script = str(tmp_path / "non_existent_test.py")
    code = run_blender_tests(test_file=missing_script)
    assert code == 1


def test_check_dependency_parity_success(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = ["numpy>=1.26.0"]

[project.optional-dependencies]
dev = ["pytest>=8.0.0", "pytest-cov>=4.0.0", "pyright>=1.1.390", "ruff>=0.8.0"]
""",
        encoding="utf-8",
    )
    assert check_dependency_parity(tmp_path) is True


def test_check_dependency_parity_missing_file(tmp_path: Path) -> None:
    assert check_dependency_parity(tmp_path) is False


def test_check_dependency_parity_missing_pkg(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = ["numpy>=1.26.0"]
""",
        encoding="utf-8",
    )
    assert check_dependency_parity(tmp_path) is False


def test_run_command_success(tmp_path: Path) -> None:
    assert run_command([sys.executable, "-c", "pass"], "test pass", tmp_path) is True


def test_run_command_failure(tmp_path: Path) -> None:
    assert run_command([sys.executable, "-c", "import sys; sys.exit(1)"], "test fail", tmp_path) is False
