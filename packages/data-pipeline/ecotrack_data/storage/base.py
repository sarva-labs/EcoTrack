"""Storage backend abstractions."""
from __future__ import annotations

import abc
from datetime import datetime
from typing import Any


class StorageBackend(abc.ABC):
    """Abstract storage backend.

    Defines the contract for storing and retrieving arbitrary binary
    data keyed by string identifiers.  Concrete implementations may
    target cloud object stores, local filesystems, or databases.
    """

    @abc.abstractmethod
    async def put(
        self,
        key: str,
        data: bytes,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Store data and return a storage URI.

        Args:
            key: Unique storage key (e.g. ``"climate/2024/obs.parquet"``).
            data: Raw bytes to persist.
            metadata: Optional key-value metadata to attach.

        Returns:
            A URI or path identifying the stored object.
        """
        ...  # pragma: no cover

    @abc.abstractmethod
    async def get(self, key: str) -> bytes:
        """Retrieve data by key.

        Args:
            key: Storage key.

        Returns:
            Raw bytes of the stored object.

        Raises:
            KeyError: If the key does not exist.
        """
        ...  # pragma: no cover

    @abc.abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a key exists.

        Args:
            key: Storage key.

        Returns:
            ``True`` if the object exists.
        """
        ...  # pragma: no cover

    @abc.abstractmethod
    async def delete(self, key: str) -> None:
        """Delete data by key.

        Args:
            key: Storage key.

        Raises:
            KeyError: If the key does not exist.
        """
        ...  # pragma: no cover

    @abc.abstractmethod
    async def list_keys(self, prefix: str) -> list[str]:
        """List keys matching a prefix.

        Args:
            prefix: Key prefix (e.g. ``"climate/"``).

        Returns:
            List of matching key strings.
        """
        ...  # pragma: no cover


__all__ = ["StorageBackend"]
