"""Vector processing utilities for EcoTrack."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def read_vector_file(path: Path | str) -> Any:
    """Read a vector file (GeoJSON, Shapefile, GeoPackage) into a GeoDataFrame.

    Args:
        path: Path to the vector file.

    Returns:
        GeoDataFrame with the vector data.

    Raises:
        NotImplementedError: This is a stub for future implementation.
    """
    raise NotImplementedError("Vector reading will be implemented in a future phase.")


def spatial_join(
    left: Any,
    right: Any,
    how: str = "inner",
    predicate: str = "intersects",
) -> Any:
    """Perform a spatial join between two GeoDataFrames.

    Args:
        left: Left GeoDataFrame.
        right: Right GeoDataFrame.
        how: Type of join (inner, left, right).
        predicate: Spatial predicate (intersects, contains, within).

    Returns:
        Joined GeoDataFrame.

    Raises:
        NotImplementedError: This is a stub for future implementation.
    """
    raise NotImplementedError("Spatial join will be implemented in a future phase.")


def simplify_geometry(geometry: Any, tolerance: float = 0.001) -> Any:
    """Simplify a geometry to reduce complexity.

    Args:
        geometry: Shapely geometry object.
        tolerance: Simplification tolerance in CRS units.

    Returns:
        Simplified geometry.

    Raises:
        NotImplementedError: This is a stub for future implementation.
    """
    raise NotImplementedError("Geometry simplification will be implemented in a future phase.")


__all__ = [
    "read_vector_file",
    "spatial_join",
    "simplify_geometry",
]
