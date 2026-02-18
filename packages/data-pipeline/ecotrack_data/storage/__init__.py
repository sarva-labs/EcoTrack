"""Storage backends for persisting processed environmental data."""
from __future__ import annotations

from .base import StorageBackend
from .database import DatabaseConfig, DatabaseStorage
from .local import LocalStorage
from .s3 import S3Config, S3Storage

__all__ = [
    "StorageBackend",
    "DatabaseConfig",
    "DatabaseStorage",
    "LocalStorage",
    "S3Config",
    "S3Storage",
]
