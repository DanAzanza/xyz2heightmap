"""
XYZ Point Cloud Parser Module.
Reads space/tab-separated ASCII XYZ files efficiently using NumPy.
"""

import os
from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np


@dataclass
class XYZCloudData:
    """Class holding processed point cloud data and bounding box metrics."""
    points: np.ndarray
    xmin: float
    xmax: float
    ymin: float
    ymax: float
    zmin: float
    zmax: float
    origin_offset: Tuple[float, float, float]  # (offset_x, offset_y, offset_z)

    @property
    def width_m(self) -> float:
        """Physical width in meters (X dimension)."""
        return float(self.xmax - self.xmin)

    @property
    def height_m(self) -> float:
        """Physical length in meters (Y dimension)."""
        return float(self.ymax - self.ymin)

    @property
    def depth_m(self) -> float:
        """Physical elevation span in meters (Z dimension)."""
        return float(self.zmax - self.zmin)


def load_xyz_file(
    filepath: str,
    min_height: Optional[float] = None,
    max_height: Optional[float] = None,
    auto_clean_outliers: bool = True,
    center_to_origin: bool = True
) -> XYZCloudData:
    """
    Parses an XYZ ASCII file and computes coordinate metrics.

    :param filepath: Path to the .xyz file.
    :param min_height: Hard minimum elevation threshold (optional).
    :param max_height: Hard maximum elevation threshold (optional).
    :param auto_clean_outliers: If True, uses percentiles when no min/max is set.
    :param center_to_origin: If True, shifts points so bounding box center is at (0, 0).
    :return: XYZCloudData dataclass containing filtered points and bounds.
    """
    if not filepath or not os.path.exists(filepath):
        raise FileNotFoundError(f"XYZ file path '{filepath}' does not exist or is invalid.")

    if min_height is not None and max_height is not None and min_height >= max_height:
        raise ValueError(f"Manual Min Height ({min_height}m) must be strictly less than Max Height ({max_height}m).")

    try:
        raw_data = np.fromfile(filepath, sep=' ', dtype=np.float64)
    except Exception as err:
        raise ValueError(f"Could not read XYZ file '{filepath}': {str(err)}")

    num_floats = len(raw_data)
    num_points = num_floats // 3

    if num_points == 0:
        raise ValueError(f"File '{os.path.basename(filepath)}' contains no valid 3D XYZ coordinate data.")

    points = raw_data[:num_points * 3].reshape((num_points, 3))
    z_vals = points[:, 2]

    # Height filtering logic
    if min_height is not None and max_height is not None:
        valid_mask = (z_vals >= min_height) & (z_vals <= max_height)
    elif auto_clean_outliers:
        p1, p99 = np.percentile(z_vals, [0.1, 99.9])
        valid_mask = (z_vals >= p1) & (z_vals <= p99)
    else:
        valid_mask = np.ones(len(points), dtype=bool)

    filtered_pts = points[valid_mask].copy()

    if len(filtered_pts) == 0:
        filtered_pts = points.copy()

    xmin_raw, ymin_raw, zmin_raw = filtered_pts.min(axis=0)
    xmax_raw, ymax_raw, zmax_raw = filtered_pts.max(axis=0)

    center_x = float(xmin_raw + xmax_raw) / 2.0
    center_y = float(ymin_raw + ymax_raw) / 2.0
    z_base = float(zmin_raw)

    if center_to_origin:
        origin_offset = (center_x, center_y, z_base)
        filtered_pts[:, 0] -= center_x
        filtered_pts[:, 1] -= center_y
        xmin, ymin, zmin = filtered_pts.min(axis=0)
        xmax, ymax, zmax = filtered_pts.max(axis=0)
    else:
        origin_offset = (0.0, 0.0, 0.0)
        xmin, xmax = float(xmin_raw), float(xmax_raw)
        ymin, ymax = float(ymin_raw), float(ymax_raw)
        zmin, zmax = float(zmin_raw), float(zmax_raw)

    if xmax <= xmin and ymax <= ymin:
        raise ValueError("Point cloud has zero physical width and height (all points coincide).")

    return XYZCloudData(
        points=filtered_pts,
        xmin=float(xmin),
        xmax=float(xmax),
        ymin=float(ymin),
        ymax=float(ymax),
        zmin=float(zmin),
        zmax=float(zmax),
        origin_offset=origin_offset
    )
