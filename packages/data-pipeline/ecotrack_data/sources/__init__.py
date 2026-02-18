"""Data source connectors for EcoTrack."""
from __future__ import annotations

from .base import DataFormat, DataSource, DataSourceConfig, FetchResult
from .copernicus import CopernicusSource
from .era5 import ERA5Source
from .gbif import GBIFSource
from .nasa_earthdata import NASAEarthdataSource
from .noaa_climate import NOAAClimateSource
from .openaq import OpenAQSource
from .usda_cropscape import USDAcropSource

__all__ = [
    "DataFormat",
    "DataSource",
    "DataSourceConfig",
    "FetchResult",
    "CopernicusSource",
    "ERA5Source",
    "GBIFSource",
    "NASAEarthdataSource",
    "NOAAClimateSource",
    "OpenAQSource",
    "USDAcropSource",
]
