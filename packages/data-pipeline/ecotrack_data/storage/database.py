"""PostgreSQL database storage backend using SQLAlchemy async sessions."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Sequence
from uuid import uuid4

from ecotrack.logging import get_logger
from sqlalchemy import Column, DateTime, LargeBinary, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# ORM model for the generic blob store table
# ---------------------------------------------------------------------------

class _Base(DeclarativeBase):
    """Declarative base for internal ORM models."""


class StoredObject(_Base):
    """Generic object store table used by :class:`DatabaseStorage`.

    This table is used for binary blob storage.  For domain-specific
    records (climate observations, species, etc.) use dedicated tables
    via :pymethod:`batch_upsert`.
    """

    __tablename__ = "stored_objects"
    __table_args__ = {"schema": "pipeline"}

    key = Column(String(512), primary_key=True)
    data = Column(LargeBinary, nullable=False)
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class DatabaseConfig:
    """Configuration for the database storage backend.

    Attributes:
        dsn: Async PostgreSQL DSN (e.g.
            ``"postgresql+asyncpg://user:pass@host:5432/ecotrack"``).
        pool_size: Connection pool size.
        max_overflow: Maximum overflow connections above pool_size.
        echo: Echo SQL statements for debugging.
        schema: Default database schema.
    """

    dsn: str = "postgresql+asyncpg://ecotrack:ecotrack@localhost:5432/ecotrack"
    pool_size: int = 10
    max_overflow: int = 20
    echo: bool = False
    schema: str = "pipeline"


# ---------------------------------------------------------------------------
# Storage implementation
# ---------------------------------------------------------------------------

class DatabaseStorage:
    """PostgreSQL storage for processed records.

    Provides two interfaces:

    1. **Blob storage**: ``put`` / ``get`` / ``exists`` / ``delete`` —
       stores arbitrary binary objects in a ``pipeline.stored_objects``
       table.
    2. **Batch upsert**: ``batch_upsert`` — bulk-inserts rows into
       domain-specific tables with ``ON CONFLICT`` handling.

    Uses SQLAlchemy 2.x async sessions with ``asyncpg`` and connection
    pooling.

    Example::

        db = DatabaseStorage(DatabaseConfig(dsn="postgresql+asyncpg://..."))
        await db.initialize()
        await db.batch_upsert(
            "climate.observations",
            records=[...],
            conflict_columns=["h3_index", "timestamp", "variable"],
        )
        await db.close()
    """

    def __init__(self, config: DatabaseConfig | None = None) -> None:
        self.config = config or DatabaseConfig()
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    async def initialize(self) -> None:
        """Create the engine, session factory, and ensure the schema exists.

        Must be called before any other operations.
        """
        self._engine = create_async_engine(
            self.config.dsn,
            pool_size=self.config.pool_size,
            max_overflow=self.config.max_overflow,
            echo=self.config.echo,
        )
        self._session_factory = async_sessionmaker(
            self._engine, expire_on_commit=False
        )

        # Ensure schema and blob table exist
        async with self._engine.begin() as conn:
            await conn.execute(
                text(f"CREATE SCHEMA IF NOT EXISTS {self.config.schema}")
            )
            await conn.run_sync(_Base.metadata.create_all)

        logger.info("database.initialized", dsn=self.config.dsn)

    async def close(self) -> None:
        """Dispose of the connection pool."""
        if self._engine:
            await self._engine.dispose()
            logger.info("database.closed")

    def _get_session(self) -> AsyncSession:
        """Create a new async session.

        Returns:
            An :class:`AsyncSession`.

        Raises:
            RuntimeError: If :pymethod:`initialize` has not been called.
        """
        if self._session_factory is None:
            raise RuntimeError(
                "DatabaseStorage not initialised — call initialize() first"
            )
        return self._session_factory()

    # ------------------------------------------------------------------
    # Blob storage (StorageBackend-like interface)
    # ------------------------------------------------------------------

    async def put(
        self,
        key: str,
        data: bytes,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Store a binary object in the database.

        Uses ``INSERT ... ON CONFLICT UPDATE`` for idempotent writes.

        Args:
            key: Unique key.
            data: Raw bytes.
            metadata: Optional JSON metadata.

        Returns:
            The key.
        """
        async with self._get_session() as session:
            async with session.begin():
                stmt = text(
                    f"""
                    INSERT INTO {self.config.schema}.stored_objects
                        (key, data, metadata, created_at, updated_at)
                    VALUES (:key, :data, :metadata, NOW(), NOW())
                    ON CONFLICT (key) DO UPDATE
                        SET data = EXCLUDED.data,
                            metadata = EXCLUDED.metadata,
                            updated_at = NOW()
                    """
                )
                await session.execute(
                    stmt,
                    {
                        "key": key,
                        "data": data,
                        "metadata": json.dumps(metadata or {}),
                    },
                )
        logger.info("database.put", key=key, size_bytes=len(data))
        return key

    async def get(self, key: str) -> bytes:
        """Retrieve a binary object by key.

        Args:
            key: Storage key.

        Returns:
            Raw bytes.

        Raises:
            KeyError: If the key does not exist.
        """
        async with self._get_session() as session:
            result = await session.execute(
                text(
                    f"SELECT data FROM {self.config.schema}.stored_objects WHERE key = :key"
                ),
                {"key": key},
            )
            row = result.fetchone()
            if row is None:
                raise KeyError(f"Key not found: {key}")
            return bytes(row[0])

    async def exists(self, key: str) -> bool:
        """Check if a key exists.

        Args:
            key: Storage key.

        Returns:
            ``True`` if the object exists.
        """
        async with self._get_session() as session:
            result = await session.execute(
                text(
                    f"SELECT 1 FROM {self.config.schema}.stored_objects WHERE key = :key"
                ),
                {"key": key},
            )
            return result.fetchone() is not None

    async def delete(self, key: str) -> None:
        """Delete a stored object.

        Args:
            key: Storage key.

        Raises:
            KeyError: If the key does not exist.
        """
        if not await self.exists(key):
            raise KeyError(f"Key not found: {key}")

        async with self._get_session() as session:
            async with session.begin():
                await session.execute(
                    text(
                        f"DELETE FROM {self.config.schema}.stored_objects WHERE key = :key"
                    ),
                    {"key": key},
                )
        logger.info("database.delete", key=key)

    async def list_keys(self, prefix: str) -> list[str]:
        """List keys with a given prefix.

        Args:
            prefix: Key prefix.

        Returns:
            List of matching keys.
        """
        async with self._get_session() as session:
            result = await session.execute(
                text(
                    f"SELECT key FROM {self.config.schema}.stored_objects "
                    f"WHERE key LIKE :prefix ORDER BY key"
                ),
                {"prefix": f"{prefix}%"},
            )
            return [row[0] for row in result.fetchall()]

    # ------------------------------------------------------------------
    # Batch upsert for domain tables
    # ------------------------------------------------------------------

    async def batch_upsert(
        self,
        table: str,
        records: list[dict[str, Any]],
        *,
        conflict_columns: list[str] | None = None,
        update_columns: list[str] | None = None,
        batch_size: int = 500,
    ) -> int:
        """Bulk insert records with conflict handling (upsert).

        Uses PostgreSQL ``INSERT ... ON CONFLICT DO UPDATE`` for
        idempotent writes.

        Args:
            table: Fully-qualified table name (e.g. ``"climate.observations"``).
            records: List of row dicts.
            conflict_columns: Columns that define uniqueness.  If ``None``,
                a plain ``INSERT`` is performed (ignoring conflicts).
            update_columns: Columns to update on conflict.  Defaults to
                all non-conflict columns.
            batch_size: Number of rows per INSERT statement.

        Returns:
            Total number of rows written.
        """
        if not records:
            return 0

        columns = list(records[0].keys())
        total = 0

        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            sql = self._build_upsert_sql(
                table, columns, len(batch), conflict_columns, update_columns
            )
            params = self._flatten_params(batch, columns)

            async with self._get_session() as session:
                async with session.begin():
                    await session.execute(text(sql), params)
                    total += len(batch)

        logger.info(
            "database.batch_upsert",
            table=table,
            total=total,
            batches=(len(records) + batch_size - 1) // batch_size,
        )
        return total

    # ------------------------------------------------------------------
    # SQL builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_upsert_sql(
        table: str,
        columns: list[str],
        num_rows: int,
        conflict_columns: list[str] | None,
        update_columns: list[str] | None,
    ) -> str:
        """Build a parameterised upsert SQL statement.

        Args:
            table: Table name.
            columns: Column names.
            num_rows: Number of rows in the batch.
            conflict_columns: Conflict target columns.
            update_columns: Columns to update on conflict.

        Returns:
            SQL string with named ``:param`` placeholders.
        """
        col_list = ", ".join(columns)

        # Build value rows: (:col0_r0, :col1_r0, ...), (:col0_r1, ...)
        value_rows: list[str] = []
        for r in range(num_rows):
            placeholders = ", ".join(f":{c}_{r}" for c in columns)
            value_rows.append(f"({placeholders})")
        values_clause = ", ".join(value_rows)

        sql = f"INSERT INTO {table} ({col_list}) VALUES {values_clause}"

        if conflict_columns:
            conflict_cols = ", ".join(conflict_columns)
            # Determine columns to update
            if update_columns is None:
                update_columns = [c for c in columns if c not in conflict_columns]
            if update_columns:
                set_clause = ", ".join(
                    f"{c} = EXCLUDED.{c}" for c in update_columns
                )
                sql += f" ON CONFLICT ({conflict_cols}) DO UPDATE SET {set_clause}"
            else:
                sql += f" ON CONFLICT ({conflict_cols}) DO NOTHING"
        else:
            sql += " ON CONFLICT DO NOTHING"

        return sql

    @staticmethod
    def _flatten_params(
        batch: list[dict[str, Any]], columns: list[str]
    ) -> dict[str, Any]:
        """Flatten a batch of row dicts into named parameters.

        Each parameter is named ``{column}_{row_index}``.

        Args:
            batch: List of row dicts.
            columns: Column names.

        Returns:
            Flat parameter dict.
        """
        params: dict[str, Any] = {}
        for r, row in enumerate(batch):
            for c in columns:
                val = row.get(c)
                # Serialize dicts/lists to JSON strings for JSONB columns
                if isinstance(val, (dict, list)):
                    val = json.dumps(val)
                params[f"{c}_{r}"] = val
        return params

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> DatabaseStorage:
        await self.initialize()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()


__all__ = ["DatabaseStorage", "DatabaseConfig"]
