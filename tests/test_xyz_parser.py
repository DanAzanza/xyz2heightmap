"""
Unit tests for XYZ Point Cloud Parser module (xyz_parser.py).
"""

import pytest
import numpy as np
from xyz_parser import load_xyz_file, XYZCloudData


def create_sample_xyz_file(filepath, points):
    """Utility helper to write XYZ points array to file."""
    with open(filepath, "w") as f:
        for p in points:
            f.write(f"{p[0]} {p[1]} {p[2]}\n")


def test_load_xyz_basic(tmp_path):
    """Test reading basic valid 3D points."""
    xyz_file = tmp_path / "sample.xyz"
    raw_points = [
        [0.0, 0.0, 10.0],
        [10.0, 0.0, 20.0],
        [0.0, 10.0, 15.0],
        [10.0, 10.0, 25.0]
    ]
    create_sample_xyz_file(xyz_file, raw_points)

    data = load_xyz_file(str(xyz_file), auto_clean_outliers=False, center_to_origin=False)

    assert isinstance(data, XYZCloudData)
    assert len(data.points) == 4
    assert data.xmin == 0.0
    assert data.xmax == 10.0
    assert data.ymin == 0.0
    assert data.ymax == 10.0
    assert data.zmin == 10.0
    assert data.zmax == 25.0
    assert data.width_m == 10.0
    assert data.height_m == 10.0
    assert data.depth_m == 15.0


def test_load_xyz_center_to_origin(tmp_path):
    """Test point centering to world origin (0, 0, 0)."""
    xyz_file = tmp_path / "centered.xyz"
    raw_points = [
        [100.0, 200.0, 10.0],
        [110.0, 220.0, 30.0]
    ]
    create_sample_xyz_file(xyz_file, raw_points)

    data = load_xyz_file(str(xyz_file), auto_clean_outliers=False, center_to_origin=True)

    # Center of X is 105.0, center of Y is 210.0, base Z is 10.0
    assert data.origin_offset == (105.0, 210.0, 10.0)
    assert np.isclose(data.xmin, -5.0)
    assert np.isclose(data.xmax, 5.0)
    assert np.isclose(data.ymin, -10.0)
    assert np.isclose(data.ymax, 10.0)


def test_load_xyz_manual_height_filter(tmp_path):
    """Test min/max elevation threshold filtering."""
    xyz_file = tmp_path / "filtered.xyz"
    raw_points = [
        [0.0, 0.0, -100.0],  # Outlier below min
        [1.0, 1.0, 50.0],    # Valid
        [2.0, 2.0, 100.0],   # Valid
        [3.0, 3.0, 999.0]    # Outlier above max
    ]
    create_sample_xyz_file(xyz_file, raw_points)

    data = load_xyz_file(
        str(xyz_file),
        min_height=0.0,
        max_height=200.0,
        auto_clean_outliers=False,
        center_to_origin=False
    )

    assert len(data.points) == 2
    assert data.zmin == 50.0
    assert data.zmax == 100.0


def test_load_xyz_file_not_found():
    """Test FileNotFoundError on non-existent path."""
    with pytest.raises(FileNotFoundError):
        load_xyz_file("non_existent_file.xyz")


def test_load_xyz_invalid_height_range(tmp_path):
    """Test ValueError when min_height >= max_height."""
    valid_file = tmp_path / "valid.xyz"
    create_sample_xyz_file(valid_file, [[0, 0, 10]])
    with pytest.raises(ValueError, match="must be strictly less than"):
        load_xyz_file(str(valid_file), min_height=100.0, max_height=50.0)
