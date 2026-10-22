"""
Unit and boundary tests for Mesh Generator module (mesh_generator.py).
Tests standalone functions, runtime guards, metadata assignments, and validation logic.
"""

from typing import Any

import numpy as np
import pytest

from mesh_generator import (
    _assign_terrain_metadata,
    create_displaced_plane,
    create_point_cloud_object,
    create_triangulated_mesh,
    extract_points_from_object,
    resolve_source_mesh_object,
)
from xyz_parser import XYZCloudData


def _make_sample_cloud(points_list: list[list[float]]) -> XYZCloudData:
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
        origin_offset=(10.0, 20.0, 30.0),
    )


def test_resolve_source_mesh_object_none() -> None:
    """Verify passing None returns None safely."""
    assert resolve_source_mesh_object(None) is None


def test_extract_points_from_object_none() -> None:
    """Verify passing None object raises descriptive ValueError."""
    with pytest.raises(ValueError, match="No object selected"):
        extract_points_from_object(None)  # type: ignore[arg-type]


def test_assign_terrain_metadata() -> None:
    """Verify metadata assignment helper correctly stores real-world offsets and elevation bounds."""
    cloud = _make_sample_cloud([[0.0, 0.0, 5.0], [10.0, 10.0, 25.0]])
    mock_obj: dict[str, Any] = {}

    _assign_terrain_metadata(mock_obj, cloud, source_pointcloud_name="Source_Cloud")

    assert mock_obj["real_world_offset_x"] == 10.0
    assert mock_obj["real_world_offset_y"] == 20.0
    assert mock_obj["real_world_offset_z"] == 30.0
    assert mock_obj["elevation_zmin"] == 5.0
    assert mock_obj["elevation_zmax"] == 25.0
    assert mock_obj["source_pointcloud_name"] == "Source_Cloud"


def test_mesh_generator_runtime_guards_without_bpy() -> None:
    """Verify runtime guards fail fast with descriptive RuntimeError when bpy is not loaded."""
    cloud = _make_sample_cloud([[0.0, 0.0, 0.0], [5.0, 5.0, 10.0], [10.0, 10.0, 20.0]])

    with pytest.raises(RuntimeError, match="create_point_cloud_object requires an active Blender"):
        create_point_cloud_object(cloud)

    with pytest.raises(RuntimeError, match="create_displaced_plane requires an active Blender"):
        create_displaced_plane(None, cloud)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="create_triangulated_mesh requires an active Blender"):
        create_triangulated_mesh(cloud)
