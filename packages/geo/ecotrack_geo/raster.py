"""Raster processing utilities for EcoTrack."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


def read_raster_window(
    path: Path | str,
    bbox: tuple[float, float, float, float] | None = None,
) -> np.ndarray:
    """Read a raster file, optionally windowed to a bounding box.

    Args:
        path: Path to the raster file (GeoTIFF, etc.).
        bbox: Optional (min_lon, min_lat, max_lon, max_lat) bounding box.

    Returns:
        Numpy array of raster data.

    Raises:
        NotImplementedError: This is a stub for future implementation.
    """
    raise NotImplementedError("Raster reading will be implemented in a future phase.")


def compute_ndvi(red: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """Compute Normalized Difference Vegetation Index.

    Args:
        red: Red band array.
        nir: Near-infrared band array.

    Returns:
        NDVI array with values in [-1, 1].

    Raises:
        NotImplementedError: This is a stub for future implementation.
    """
    raise NotImplementedError("NDVI computation will be implemented in a future phase.")


def reproject_raster(
    data: np.ndarray,
    src_crs: str,
    dst_crs: str,
    src_transform: Any,
) -> tuple[np.ndarray, Any]:
    """Reproject a raster array to a different CRS.

    Args:
        data: Input raster array.
        src_crs: Source CRS string.
        dst_crs: Destination CRS string.
        src_transform: Source affine transform.

    Returns:
        Tuple of (reprojected array, new transform).

    Raises:
        NotImplementedError: This is a stub for future implementation.
    """
    raise NotImplementedError("Raster reprojection will be implemented in a future phase.")


__all__ = [
    "read_raster_window",
    "compute_ndvi",
    "reproject_raster",
]
