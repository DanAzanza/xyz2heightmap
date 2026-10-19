"""
XYZ Point Cloud Parser Module.
Reads ASCII XYZ, PTS, and TXT point cloud files using NumPy.
"""

import os
from dataclasses import dataclass

import numpy as np

MIN_OUTLIER_FILTER_POINTS: int = 100
OUTLIER_LOWER_PERCENTILE: float = 0.1
OUTLIER_UPPER_PERCENTILE: float = 99.9


@dataclass(frozen=True)
class XYZCloudData:
    """Immutable value object holding processed point cloud data and bounding box metrics."""

    points: np.ndarray
    xmin: float
    xmax: float
    ymin: float
    ymax: float
    zmin: float
    zmax: float
    origin_offset: tuple[float, float, float]  # (offset_x, offset_y, offset_z)

    def __post_init__(self) -> None:
        if self.points.ndim != 2 or self.points.shape[1] != 3:
            raise ValueError("XYZCloudData.points must be a 2D array of shape (N, 3).")
        self.points.setflags(write=False)

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


def _is_comment_or_empty(line: str) -> bool:
    """Returns True if a line is blank or starts with a standard comment prefix."""
    stripped = line.strip()
    return (
        not stripped
        or stripped.startswith("#")
        or stripped.startswith("//")
        or stripped.startswith(";")
    )


def _split_tokens(line: str) -> list[str]:
    """Splits a data line by comma, semicolon, or whitespace."""
    stripped = line.strip()
    if "," in stripped:
        return [tok.strip() for tok in stripped.split(",") if tok.strip()]
    if ";" in stripped:
        return [tok.strip() for tok in stripped.split(";") if tok.strip()]
    return stripped.split()


def _try_parse_floats(tokens: list[str]) -> list[float] | None:
    """Attempts to parse all tokens as finite floats; returns None if any token is non-numeric."""
    try:
        vals = [float(t) for t in tokens]
    except ValueError:
        return None
    if not np.all(np.isfinite(vals)):
        raise ValueError("XYZ file contains non-finite (NaN or Inf) coordinate values.")
    return vals


def _try_fast_uniform_parse(filepath: str, raw_bytes: bytes) -> np.ndarray | None:
    """
    Fast C-level NumPy path for uniform whitespace-delimited numeric files without headers/comments.
    Returns None if the file requires line-by-line header/delimiter handling.
    """
    if any(ch in raw_bytes for ch in (b"#", b",", b";", b"/")):
        return None

    lines = [ln for ln in raw_bytes.splitlines() if ln.strip()]
    if not lines:
        return None

    num_cols = len(lines[0].split())
    if num_cols < 3:
        return None

    if not all(len(ln.split()) == num_cols for ln in lines):
        return None

    try:
        arr = np.fromfile(filepath, sep=" ", dtype=np.float64)
    except (ValueError, OSError):
        return None

    if len(arr) != len(lines) * num_cols:
        return None

    if not np.all(np.isfinite(arr)):
        raise ValueError("XYZ file contains non-finite (NaN or Inf) coordinate values.")

    return arr.reshape((len(lines), num_cols))[:, :3].copy()


def _is_pts_count_header(tokens: list[str], seen_data_row: bool) -> bool:
    """Returns True if the first non-comment row is a single integer point-count header (.pts format)."""
    if seen_data_row or len(tokens) != 1:
        return False
    try:
        return int(tokens[0]) >= 0
    except ValueError:
        return False


def _parse_xyz_points(filepath: str) -> np.ndarray:
    """
    Parses 3D coordinates from an ASCII .xyz, .pts, or .txt file.
    Uses a fast C-level NumPy path for uniform whitespace-delimited tables and
    falls back to a validated line parser when headers, comments, or custom delimiters exist.
    """
    with open(filepath, "rb") as fb:
        raw_bytes = fb.read()

    if not raw_bytes or not raw_bytes.strip():
        raise ValueError(f"File '{os.path.basename(filepath)}' is empty.")

    fast_pts = _try_fast_uniform_parse(filepath, raw_bytes)
    if fast_pts is not None:
        return fast_pts

    text = raw_bytes.decode("utf-8-sig", errors="replace")
    parsed_rows: list[tuple[float, float, float]] = []
    seen_data_row = False

    for line_num, raw_line in enumerate(text.splitlines(), start=1):
        if _is_comment_or_empty(raw_line):
            continue

        tokens = _split_tokens(raw_line)
        if not tokens or _is_pts_count_header(tokens, seen_data_row):
            continue

        floats = _try_parse_floats(tokens)
        if floats is None:
            if not seen_data_row:
                continue
            raise ValueError(
                f"Malformed coordinate data on line {line_num} in '{os.path.basename(filepath)}': '{raw_line.strip()}'"
            )

        if len(floats) < 3:
            raise ValueError(
                f"Line {line_num} in '{os.path.basename(filepath)}' has {len(floats)} value(s); at least 3 (X, Y, Z) are required."
            )

        seen_data_row = True
        parsed_rows.append((floats[0], floats[1], floats[2]))

    if not parsed_rows:
        raise ValueError(f"File '{os.path.basename(filepath)}' contains no valid 3D XYZ coordinate data.")

    return np.array(parsed_rows, dtype=np.float64)


def load_xyz_file(
    filepath: str,
    min_height: float | None = None,
    max_height: float | None = None,
    auto_clean_outliers: bool = True,
    center_to_origin: bool = True,
) -> XYZCloudData:
    """
    Parses an XYZ/PTS/TXT ASCII file and computes coordinate metrics.

    :param filepath: Path to the .xyz, .pts, or .txt file.
    :param min_height: Hard minimum elevation threshold (optional).
    :param max_height: Hard maximum elevation threshold (optional).
    :param auto_clean_outliers: If True, clips [0.1%, 99.9%] percentiles on datasets >= 100 points when no manual bounds are set.
    :param center_to_origin: If True, shifts X/Y center and Z base to Blender origin (0, 0, 0).
    :return: Immutable XYZCloudData containing filtered points and bounds.
    """
    if not filepath or not os.path.isfile(filepath):
        raise FileNotFoundError(f"XYZ file path '{filepath}' does not exist or is invalid.")

    if min_height is not None and max_height is not None and min_height >= max_height:
        raise ValueError(
            f"Manual Min Height ({min_height}m) must be strictly less than Max Height ({max_height}m)."
        )

    points = _parse_xyz_points(filepath)
    z_vals = points[:, 2]

    # Height filtering logic
    if min_height is not None or max_height is not None:
        valid_mask = np.ones(len(points), dtype=bool)
        if min_height is not None:
            valid_mask &= z_vals >= min_height
        if max_height is not None:
            valid_mask &= z_vals <= max_height
    elif auto_clean_outliers and len(points) >= MIN_OUTLIER_FILTER_POINTS:
        p_low, p_high = np.percentile(z_vals, [OUTLIER_LOWER_PERCENTILE, OUTLIER_UPPER_PERCENTILE])
        valid_mask = (z_vals >= p_low) & (z_vals <= p_high)
    else:
        valid_mask = np.ones(len(points), dtype=bool)

    filtered_pts = points[valid_mask].copy()

    if len(filtered_pts) == 0:
        raise ValueError(
            "No points remain after applying elevation filter thresholds. Adjust Min/Max Height settings."
        )

    xmin_raw, ymin_raw, zmin_raw = filtered_pts.min(axis=0)
    xmax_raw, ymax_raw, zmax_raw = filtered_pts.max(axis=0)

    if xmax_raw <= xmin_raw and ymax_raw <= ymin_raw:
        raise ValueError("Point cloud has zero physical width and height (all points coincide in X/Y).")

    center_x = float(xmin_raw + xmax_raw) / 2.0
    center_y = float(ymin_raw + ymax_raw) / 2.0
    z_base = float(zmin_raw)

    if center_to_origin:
        origin_offset = (center_x, center_y, z_base)
        filtered_pts[:, 0] -= center_x
        filtered_pts[:, 1] -= center_y
        filtered_pts[:, 2] -= z_base
        xmin, ymin, zmin = filtered_pts.min(axis=0)
        xmax, ymax, zmax = filtered_pts.max(axis=0)
    else:
        origin_offset = (0.0, 0.0, 0.0)
        xmin, xmax = float(xmin_raw), float(xmax_raw)
        ymin, ymax = float(ymin_raw), float(ymax_raw)
        zmin, zmax = float(zmin_raw), float(zmax_raw)

    return XYZCloudData(
        points=filtered_pts,
        xmin=float(xmin),
        xmax=float(xmax),
        ymin=float(ymin),
        ymax=float(ymax),
        zmin=float(zmin),
        zmax=float(zmax),
        origin_offset=origin_offset,
    )
