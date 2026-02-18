"""S3/MinIO object storage backend."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ecotrack.logging import get_logger

from .base import StorageBackend

logger = get_logger(__name__)

#: Default multipart upload threshold (8 MiB).
_MULTIPART_THRESHOLD = 8 * 1024 * 1024

#: Multipart chunk size (8 MiB).
_MULTIPART_CHUNKSIZE = 8 * 1024 * 1024


@dataclass
class S3Config:
    """Configuration for the S3 storage backend.

    Attributes:
        bucket: S3 bucket name.
        prefix: Key prefix prepended to all keys.
        region: AWS region (e.g. ``"us-east-1"``).
        endpoint_url: Custom endpoint for MinIO or LocalStack.
        aws_access_key_id: Optional explicit access key.
        aws_secret_access_key: Optional explicit secret key.
    """

    bucket: str = "ecotrack-data"
    prefix: str = ""
    region: str = "us-east-1"
    endpoint_url: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None


class S3Storage(StorageBackend):
    """Amazon S3 / MinIO object storage backend.

    Uses :mod:`aioboto3` for asynchronous I/O.  Large objects are
    uploaded using multipart transfers automatically.

    Example::

        storage = S3Storage(S3Config(bucket="ecotrack-data", prefix="climate/"))
        uri = await storage.put("obs/2024-01.parquet", data_bytes)
        content = await storage.get("obs/2024-01.parquet")
    """

    def __init__(self, config: S3Config | None = None) -> None:
        self.config = config or S3Config()
        self._session: Any = None

    def _full_key(self, key: str) -> str:
        """Prepend the configured prefix to *key*.

        Args:
            key: Relative key.

        Returns:
            Fully-qualified S3 key.
        """
        if self.config.prefix:
            return f"{self.config.prefix.rstrip('/')}/{key}"
        return key

    def _get_session(self) -> Any:
        """Lazily create an ``aioboto3`` session.

        Returns:
            An :class:`aioboto3.Session` instance.
        """
        if self._session is None:
            import aioboto3

            kwargs: dict[str, Any] = {"region_name": self.config.region}
            if self.config.aws_access_key_id:
                kwargs["aws_access_key_id"] = self.config.aws_access_key_id
            if self.config.aws_secret_access_key:
                kwargs["aws_secret_access_key"] = self.config.aws_secret_access_key
            self._session = aioboto3.Session(**kwargs)
        return self._session

    def _resource_kwargs(self) -> dict[str, Any]:
        """Extra keyword arguments for :pymethod:`session.resource`.

        Returns:
            Dict with ``endpoint_url`` if configured.
        """
        kwargs: dict[str, Any] = {}
        if self.config.endpoint_url:
            kwargs["endpoint_url"] = self.config.endpoint_url
        return kwargs

    # ------------------------------------------------------------------
    # StorageBackend interface
    # ------------------------------------------------------------------

    async def put(
        self,
        key: str,
        data: bytes,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Store *data* in S3.

        Objects larger than 8 MiB are uploaded using the multipart
        transfer mechanism automatically handled by boto3.

        Args:
            key: Storage key.
            data: Raw bytes.
            metadata: Optional S3 object metadata.

        Returns:
            S3 URI (``s3://bucket/key``).
        """
        full_key = self._full_key(key)
        session = self._get_session()

        extra: dict[str, Any] = {}
        if metadata:
            extra["Metadata"] = {k: str(v) for k, v in metadata.items()}

        async with session.client("s3", **self._resource_kwargs()) as s3:
            if len(data) > _MULTIPART_THRESHOLD:
                # Use multipart upload
                await self._multipart_upload(s3, full_key, data, extra)
            else:
                await s3.put_object(
                    Bucket=self.config.bucket,
                    Key=full_key,
                    Body=data,
                    **extra,
                )

        uri = f"s3://{self.config.bucket}/{full_key}"
        logger.info(
            "s3.put",
            key=full_key,
            size_bytes=len(data),
            uri=uri,
        )
        return uri

    async def get(self, key: str) -> bytes:
        """Retrieve an object from S3.

        Args:
            key: Storage key.

        Returns:
            Object content as bytes.

        Raises:
            KeyError: If the object does not exist.
        """
        full_key = self._full_key(key)
        session = self._get_session()

        try:
            async with session.client("s3", **self._resource_kwargs()) as s3:
                response = await s3.get_object(
                    Bucket=self.config.bucket, Key=full_key
                )
                content: bytes = await response["Body"].read()
                logger.debug("s3.get", key=full_key, size_bytes=len(content))
                return content
        except Exception as exc:
            if "NoSuchKey" in str(exc) or "404" in str(exc):
                raise KeyError(f"Key not found: {full_key}") from exc
            raise

    async def exists(self, key: str) -> bool:
        """Check if an object exists in S3.

        Args:
            key: Storage key.

        Returns:
            ``True`` if the object exists.
        """
        full_key = self._full_key(key)
        session = self._get_session()

        try:
            async with session.client("s3", **self._resource_kwargs()) as s3:
                await s3.head_object(Bucket=self.config.bucket, Key=full_key)
                return True
        except Exception:
            return False

    async def delete(self, key: str) -> None:
        """Delete an object from S3.

        Args:
            key: Storage key.

        Raises:
            KeyError: If the object does not exist.
        """
        full_key = self._full_key(key)
        if not await self.exists(key):
            raise KeyError(f"Key not found: {full_key}")

        session = self._get_session()
        async with session.client("s3", **self._resource_kwargs()) as s3:
            await s3.delete_object(Bucket=self.config.bucket, Key=full_key)
            logger.info("s3.delete", key=full_key)

    async def list_keys(self, prefix: str) -> list[str]:
        """List objects with a given prefix.

        Args:
            prefix: Key prefix.

        Returns:
            List of matching keys (without the configured prefix).
        """
        full_prefix = self._full_key(prefix)
        session = self._get_session()
        keys: list[str] = []

        async with session.client("s3", **self._resource_kwargs()) as s3:
            paginator = s3.get_paginator("list_objects_v2")
            async for page in paginator.paginate(
                Bucket=self.config.bucket, Prefix=full_prefix
            ):
                for obj in page.get("Contents", []):
                    obj_key = obj["Key"]
                    # Strip the configured prefix for the caller
                    if self.config.prefix and obj_key.startswith(self.config.prefix):
                        obj_key = obj_key[len(self.config.prefix) :].lstrip("/")
                    keys.append(obj_key)

        logger.debug("s3.list_keys", prefix=prefix, count=len(keys))
        return keys

    # ------------------------------------------------------------------
    # Multipart upload helper
    # ------------------------------------------------------------------

    async def _multipart_upload(
        self,
        s3: Any,
        key: str,
        data: bytes,
        extra: dict[str, Any],
    ) -> None:
        """Perform a multipart upload for large objects.

        Args:
            s3: The S3 client.
            key: Full S3 key.
            data: Raw bytes.
            extra: Extra put_object kwargs.
        """
        mp = await s3.create_multipart_upload(
            Bucket=self.config.bucket, Key=key, **extra
        )
        upload_id = mp["UploadId"]
        parts: list[dict[str, Any]] = []

        try:
            part_num = 1
            offset = 0
            while offset < len(data):
                chunk = data[offset : offset + _MULTIPART_CHUNKSIZE]
                resp = await s3.upload_part(
                    Bucket=self.config.bucket,
                    Key=key,
                    PartNumber=part_num,
                    UploadId=upload_id,
                    Body=chunk,
                )
                parts.append({"ETag": resp["ETag"], "PartNumber": part_num})
                offset += _MULTIPART_CHUNKSIZE
                part_num += 1

            await s3.complete_multipart_upload(
                Bucket=self.config.bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
            logger.info(
                "s3.multipart_complete", key=key, parts=len(parts)
            )
        except Exception:
            await s3.abort_multipart_upload(
                Bucket=self.config.bucket, Key=key, UploadId=upload_id
            )
            raise


__all__ = ["S3Storage", "S3Config"]
