"""CRS (Coordinate Reference System) transformation utilities."""
from __future__ import annotations

from typing import Any

from pyproj import Transformer


def get_transformer(src_crs: str, dst_crs: str) -> Transformer:
    """Create a pyproj Transformer between two CRS.

    Args:
        src_crs: Source CRS string (e.g., "EPSG:4326").
        dst_crs: Destination CRS string (e.g., "EPSG:3857").

    Returns:
        A pyproj Transformer instance.
    """
    return Transformer.from_crs(src_crs, dst_crs, always_xy=True)


def transform_coords(
    lon: float,
    lat: float,
    src_crs: str = "EPSG:4326",
    dst_crs: str = "EPSG:3857",
) -> tuple[float, float]:
    """Transform a single coordinate pair between CRS.

    Args:
        lon: Longitude in source CRS.
        lat: Latitude in source CRS.
        src_crs: Source CRS string.
        dst_crs: Destination CRS string.

    Returns:
        Tuple of (x, y) in destination CRS.
    """
    transformer = get_transformer(src_crs, dst_crs)
    x, y = transformer.transform(lon, lat)
    return (x, y)


__all__ = [
    "get_transformer",
    "transform_coords",
]
