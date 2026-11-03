"""
Unit tests for the extension build and packaging script.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from scripts.build_extension import _add_file_to_zip, build_package, get_version


def test_get_version_success(tmp_path: Path) -> None:
    manifest = tmp_path / "blender_manifest.toml"
    manifest.write_text('schema_version = "1.0.0"\nversion = "3.2.1"\n', encoding="utf-8")
    assert get_version(tmp_path) == "3.2.1"


def test_get_version_missing_manifest(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Blender manifest"):
        get_version(tmp_path)


def test_get_version_empty_version(tmp_path: Path) -> None:
    manifest = tmp_path / "blender_manifest.toml"
    manifest.write_text('schema_version = "1.0.0"\n', encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="valid version not found"):
        get_version(tmp_path)


def test_get_version_mismatch_with_bl_info(tmp_path: Path) -> None:
    manifest = tmp_path / "blender_manifest.toml"
    manifest.write_text('version = "3.0.0"\n', encoding="utf-8")
    init_file = tmp_path / "__init__.py"
    init_file.write_text('bl_info = {"version": (2, 9, 0)}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="Version mismatch"):
        get_version(tmp_path)


def test_get_version_parity_with_bl_info(tmp_path: Path) -> None:
    manifest = tmp_path / "blender_manifest.toml"
    manifest.write_text('version = "3.0.0"\n', encoding="utf-8")
    init_file = tmp_path / "__init__.py"
    init_file.write_text('bl_info = {"version": (3, 0, 0)}\n', encoding="utf-8")

    assert get_version(tmp_path) == "3.0.0"


def test_add_file_to_zip_permissions(tmp_path: Path) -> None:
    sample_file = tmp_path / "sample.txt"
    sample_file.write_text("hello", encoding="utf-8")
    zip_path = tmp_path / "out.zip"

    with zipfile.ZipFile(zip_path, "w") as zf:
        _add_file_to_zip(zf, sample_file, "sample.txt")

    with zipfile.ZipFile(zip_path, "r") as zf:
        info = zf.getinfo("sample.txt")
        # System 3 is UNIX, permission upper bits contain 0o644 | 0o100000
        assert info.create_system == 3
        perms = (info.external_attr >> 16) & 0o777
        assert perms == 0o644


def test_build_package_in_repo(tmp_path: Path) -> None:
    manifest = tmp_path / "blender_manifest.toml"
    manifest.write_text('schema_version = "1.0.0"\nversion = "1.0.0"\n', encoding="utf-8")
    (tmp_path / "__init__.py").write_text("# init", encoding="utf-8")
    (tmp_path / "xyz_parser.py").write_text("# parser", encoding="utf-8")

    zip_path = build_package(repo_root=tmp_path, clean_dist=True)
    assert zip_path.exists()
    assert zip_path.name == "xyz2heightmap-v1.0.0.zip"

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        assert "blender_manifest.toml" in names
        assert "__init__.py" in names
        assert "xyz_parser.py" in names
