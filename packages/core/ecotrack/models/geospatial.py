"""Geospatial domain models."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from shapely.geometry import shape

from .base import EcoTrackModel


class BoundingBox(BaseModel):
    """Geographic bounding box."""

    min_lon: float = Field(ge=-180, le=180)
    min_lat: float = Field(ge=-90, le=90)
    max_lon: float = Field(ge=-180, le=180)
    max_lat: float = Field(ge=-90, le=90)

    @property
    def as_tuple(self) -> tuple[float, float, float, float]:
        """Return bounding box as (min_lon, min_lat, max_lon, max_lat)."""
        return (self.min_lon, self.min_lat, self.max_lon, self.max_lat)


class GeoPoint(BaseModel):
    """Geographic point with optional elevation."""

    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    elevation_m: float | None = None

    @property
    def h3_index(self) -> str:
        """Get H3 index at resolution 9."""
        import h3

        return h3.latlng_to_cell(self.latitude, self.longitude, 9)


class GeoRegion(EcoTrackModel):
    """A geographic region with GeoJSON geometry."""

    name: str
    geometry: dict[str, Any]  # GeoJSON geometry
    properties: dict[str, Any] = Field(default_factory=dict)
    area_km2: float | None = None

    @property
    def shapely_geometry(self) -> Any:
        """Convert GeoJSON geometry to a Shapely geometry object."""
        return shape(self.geometry)


class SpatioTemporalExtent(BaseModel):
    """Combined spatial and temporal extent."""

    bbox: BoundingBox
    start_time: datetime
    end_time: datetime
    spatial_resolution_m: float | None = None
    temporal_resolution_s: float | None = None


__all__ = [
    "BoundingBox",
    "GeoPoint",
    "GeoRegion",
    "SpatioTemporalExtent",
]
