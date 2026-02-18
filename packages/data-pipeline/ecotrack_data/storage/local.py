"""Local filesystem storage backend."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiofiles
import aiofiles.os
from ecotrack.logging import get_logger

from .base import StorageBackend

logger = get_logger(__name__)


class LocalStorage(StorageBackend):
    """Local filesystem storage backend.

    Stores objects as files under a configurable base directory.
    Uses :mod:`aiofiles` for non-blocking file I/O.

    Metadata is persisted in sidecar ``.meta.json`` files alongside
    each stored object.

    Example::

        storage = LocalStorage(base_dir=Path("data/output"))
        uri = await storage.put("climate/obs.parquet", data_bytes)
        content = await storage.get("climate/obs.parquet")
    """

    def __init__(self, base_dir: Path | str = "data/storage") -> None:
        self.base_dir = Path(base_dir)

    def _resolve(self, key: str) -> Path:
        """Resolve a key to an absolute filesystem path.

        Args:
            key: Storage key.

        Returns:
            Absolute path under ``base_dir``.
        """
        # Prevent path traversal
        safe_key = Path(key)
        if safe_key.is_absolute() or ".." in safe_key.parts:
            raise ValueError(f"Invalid key (path traversal detected): {key}")
        return self.base_dir / safe_key

    # ------------------------------------------------------------------
    # StorageBackend interface
    # ------------------------------------------------------------------

    async def put(
        self,
        key: str,
        data: bytes,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Write data to a file.

        Parent directories are created automatically.

        Args:
            key: Storage key (relative path).
            data: Raw bytes.
            metadata: Optional metadata persisted as a sidecar JSON file.

        Returns:
            File URI (``file://…``).
        """
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(path, "wb") as f:
            await f.write(data)

        if metadata:
            meta_path = path.with_suffix(path.suffix + ".meta.json")
            async with aiofiles.open(meta_path, "w") as mf:
                await mf.write(json.dumps(metadata, default=str, indent=2))

        uri = path.as_uri()
        logger.info("local.put", key=key, size_bytes=len(data), path=str(path))
        return uri

    async def get(self, key: str) -> bytes:
        """Read a file's contents.

        Args:
            key: Storage key.

        Returns:
            File contents as bytes.

        Raises:
            KeyError: If the file does not exist.
        """
        path = self._resolve(key)
        if not path.exists():
            raise KeyError(f"Key not found: {key}")

        async with aiofiles.open(path, "rb") as f:
            content: bytes = await f.read()

        logger.debug("local.get", key=key, size_bytes=len(content))
        return content

    async def exists(self, key: str) -> bool:
        """Check if a file exists.

        Args:
            key: Storage key.

        Returns:
            ``True`` if the file exists.
        """
        path = self._resolve(key)
        return path.exists()

    async def delete(self, key: str) -> None:
        """Delete a file and its sidecar metadata.

        Args:
            key: Storage key.

        Raises:
            KeyError: If the file does not exist.
        """
        path = self._resolve(key)
        if not path.exists():
            raise KeyError(f"Key not found: {key}")

        await aiofiles.os.remove(path)

        # Remove sidecar metadata if present
        meta_path = path.with_suffix(path.suffix + ".meta.json")
        if meta_path.exists():
            await aiofiles.os.remove(meta_path)

        logger.info("local.delete", key=key)

    async def list_keys(self, prefix: str) -> list[str]:
        """List files matching a prefix.

        The prefix is treated as a directory path under ``base_dir``.
        Only actual data files are returned (sidecar ``.meta.json``
        files are excluded).

        Args:
            prefix: Directory prefix.

        Returns:
            List of storage keys relative to ``base_dir``.
        """
        base = self._resolve(prefix)
        keys: list[str] = []

        if not base.exists():
            return keys

        if base.is_file():
            rel = base.relative_to(self.base_dir)
            return [str(rel)]

        for item in base.rglob("*"):
            if item.is_file() and not item.name.endswith(".meta.json"):
                rel = item.relative_to(self.base_dir)
                keys.append(str(rel).replace("\\", "/"))

        logger.debug("local.list_keys", prefix=prefix, count=len(keys))
        return sorted(keys)

    async def get_metadata(self, key: str) -> dict[str, Any]:
        """Read sidecar metadata for a stored object.

        Args:
            key: Storage key.

        Returns:
            Metadata dict, or empty dict if no sidecar exists.
        """
        path = self._resolve(key)
        meta_path = path.with_suffix(path.suffix + ".meta.json")
        if not meta_path.exists():
            return {}

        async with aiofiles.open(meta_path, "r") as f:
            content = await f.read()
            return json.loads(content)


__all__ = ["LocalStorage"]
