"""
Unit and boundary tests for Heightmap Generator module (heightmap_generator.py).
Tests pure NumPy rasterization, UV bottom-up orientation, and physical-space IDW gap filling.
"""

import numpy as np
import pytest

from heightmap_generator import (
    create_blender_image,
    export_heightmap_16bit_png,
    generate_heightmap_grid,
)
from xyz_parser import XYZCloudData


def _make_cloud(points_list: list[list[float]]) -> XYZCloudData:
    pts = np.array(points_list, dtype=np.float64)
    xmin, ymin, zmin = pts.min(axis=0)
    xmax, ymax, zmax = pts.max(axis=0)
    return XYZCloudData(
        points=pts,
        xmin=float(xmin),
        xmax=float(xmax),
        ymin=float(ymin),
        ymax=float(ymax),
        zmin=float(zmin),
        zmax=float(zmax),
        origin_offset=(0.0, 0.0, 0.0),
    )


def test_generate_heightmap_orientation_and_bounds() -> None:
    """
    Verify bottom-up row indexing:
    row 0 = ymin (South), row res_y-1 = ymax (North),
    col 0 = xmin (West), col res_x-1 = xmax (East).
    """
    cloud = _make_cloud(
        [
            [0.0, 0.0, 10.0],   # SW corner -> row 0, col 0
            [10.0, 0.0, 20.0],  # SE corner -> row 0, col 1
            [0.0, 10.0, 30.0],  # NW corner -> row 1, col 0
            [10.0, 10.0, 50.0], # NE corner -> row 1, col 1
        ]
    )

    raw_grid, norm_grid = generate_heightmap_grid(cloud, target_res=(2, 2), k_neighbors=4)

    assert raw_grid.shape == (2, 2)
    assert norm_grid.shape == (2, 2)
    assert np.isclose(raw_grid[0, 0], 10.0)
    assert np.isclose(raw_grid[0, 1], 20.0)
    assert np.isclose(raw_grid[1, 0], 30.0)
    assert np.isclose(raw_grid[1, 1], 50.0)

    assert np.isclose(norm_grid[0, 0], 0.0)
    assert np.isclose(norm_grid[0, 1], 0.25)
    assert np.isclose(norm_grid[1, 0], 0.5)
    assert np.isclose(norm_grid[1, 1], 1.0)


def test_generate_heightmap_max_z_per_cell() -> None:
    """Verify multiple points landing in the same cell retain the maximum Z elevation."""
    cloud = _make_cloud(
        [
            [0.0, 0.0, 5.0],
            [0.1, 0.1, 42.0],
            [0.2, 0.2, 12.0],
            [10.0, 10.0, 10.0],
        ]
    )

    raw_grid, _norm_grid = generate_heightmap_grid(cloud, target_res=(4, 4), k_neighbors=2)
    assert np.isclose(raw_grid[0, 0], 42.0)


def test_generate_heightmap_idw_anisotropic_physical_space() -> None:
    """
    Verify IDW measures distance in physical meters rather than stretched pixel indices
    when target_res has an anisotropic aspect ratio on a square physical domain.
    """
    # 10m x 10m physical square:
    # Point A at (0m, 5m) with Z = 100
    # Point B at (5m, 0m) with Z = 0
    # Query at (0m, 0m) is physically 5m from A and 5m from B -> equal weights -> Z should be ~50.
    cloud = _make_cloud(
        [
            [0.0, 5.0, 100.0],
            [5.0, 0.0, 0.0],
            [10.0, 10.0, 50.0],
        ]
    )

    # Use a 4:1 anisotropic pixel resolution (40x10) on the 10m x 10m square
    raw_grid, _norm = generate_heightmap_grid(cloud, target_res=(40, 10), k_neighbors=2, idw_power=2.0)
    assert np.isclose(raw_grid[0, 0], 50.0, atol=1.0)


def test_generate_heightmap_flat_z_and_1d_cloud() -> None:
    """Verify flat Z clouds (depth_m == 0) and 1D colinear clouds do not produce NaN or crash."""
    flat_cloud = _make_cloud([[0.0, 0.0, 15.0], [10.0, 10.0, 15.0]])
    raw_grid, norm_grid = generate_heightmap_grid(flat_cloud, target_res=(4, 4))
    assert np.allclose(raw_grid, 15.0)
    assert np.allclose(norm_grid, 0.0)
    assert np.all(np.isfinite(norm_grid))

    colinear_x = _make_cloud([[0.0, 5.0, 0.0], [10.0, 5.0, 20.0]])
    raw_1d, norm_1d = generate_heightmap_grid(colinear_x, pixels_per_meter=1.0)
    assert raw_1d.shape == (1, 10)
    assert np.all(np.isfinite(norm_1d))


def test_generate_heightmap_negative_validation() -> None:
    """Test invalid arguments and Blender runtime guards."""
    cloud = _make_cloud([[0.0, 0.0, 0.0], [10.0, 10.0, 10.0]])

    with pytest.raises(ValueError, match="pixels_per_meter must be positive"):
        generate_heightmap_grid(cloud, pixels_per_meter=0.0)

    with pytest.raises(ValueError, match="target_res dimensions must be >= 1"):
        generate_heightmap_grid(cloud, target_res=(0, 10))

    with pytest.raises(ValueError, match="k_neighbors must be at least 1"):
        generate_heightmap_grid(cloud, k_neighbors=0)

    with pytest.raises(ValueError, match="idw_power must be positive"):
        generate_heightmap_grid(cloud, idw_power=0.0)

    with pytest.raises(RuntimeError, match="requires an active Blender"):
        create_blender_image(np.zeros((2, 2), dtype=np.float32))

    with pytest.raises(RuntimeError, match="requires an active Blender"):
        export_heightmap_16bit_png(None, "out.png")  # type: ignore[arg-type]
