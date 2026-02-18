"""EcoTrack Data Pipeline — ETL and data ingestion for environmental data."""
from __future__ import annotations

__version__ = "0.1.0"

from .pipeline import DataPipeline, PipelineResult, PipelineStatus
from .registry import SourceRegistry, get_registry

__all__ = [
    "__version__",
    "DataPipeline",
    "PipelineResult",
    "PipelineStatus",
    "SourceRegistry",
    "get_registry",
]
