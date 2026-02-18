"""H3 and Mercantile tiling helpers for spatial indexing."""
from __future__ import annotations

from typing import Any

import h3
import mercantile

from ecotrack.models.geospatial import BoundingBox, GeoPoint


def point_to_h3(point: GeoPoint, resolution: int = 9) -> str:
    """Convert a GeoPoint to an H3 cell index.

    Args:
        point: Geographic point.
        resolution: H3 resolution (0-15). Default is 9.

    Returns:
        H3 cell index string.
    """
    return h3.latlng_to_cell(point.latitude, point.longitude, resolution)


def bbox_to_h3_cells(bbox: BoundingBox, resolution: int = 7) -> list[str]:
    """Get all H3 cells covering a bounding box.

    Args:
        bbox: Geographic bounding box.
        resolution: H3 resolution (0-15). Default is 7.

    Returns:
        List of H3 cell index strings.
    """
    # Create a polygon from the bbox corners
    polygon = [
        (bbox.min_lat, bbox.min_lon),
        (bbox.min_lat, bbox.max_lon),
        (bbox.max_lat, bbox.max_lon),
        (bbox.max_lat, bbox.min_lon),
    ]
    return list(h3.geo_to_cells({"type": "Polygon", "coordinates": [polygon]}, resolution))


def bbox_to_tiles(bbox: BoundingBox, zoom: int) -> list[mercantile.Tile]:
    """Get all Mercator tiles covering a bounding box.

    Args:
        bbox: Geographic bounding box.
        zoom: Tile zoom level.

    Returns:
        List of mercantile Tile objects.
    """
    return list(mercantile.tiles(bbox.min_lon, bbox.min_lat, bbox.max_lon, bbox.max_lat, zoom))


def tile_bounds(tile: mercantile.Tile) -> BoundingBox:
    """Get the geographic bounds of a Mercator tile.

    Args:
        tile: A mercantile Tile object.

    Returns:
        BoundingBox for the tile.
    """
    bounds = mercantile.bounds(tile)
    return BoundingBox(
        min_lon=bounds.west,
        min_lat=bounds.south,
        max_lon=bounds.east,
        max_lat=bounds.north,
    )


__all__ = [
    "point_to_h3",
    "bbox_to_h3_cells",
    "bbox_to_tiles",
    "tile_bounds",
]
