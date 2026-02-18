"""Feature store for ML pipeline.

Provides :class:`FeatureStore` for offline (Parquet-backed) feature
management with point-in-time retrieval, feature set registration,
and training dataset assembly.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np

try:
    import pandas as pd

    _HAS_PANDAS = True
except ImportError:
    _HAS_PANDAS = False

try:
    import structlog

    logger = structlog.get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)  # type: ignore[assignment]


@dataclass
class FeatureSetSchema:
    """Schema definition for a feature set.

    Attributes:
        name: Unique identifier for the feature set.
        entity_column: Name of the column identifying entities.
        timestamp_column: Name of the timestamp column.
        feature_columns: Ordered list of feature column names.
        description: Human-readable description.
        tags: Arbitrary metadata tags.
    """

    name: str
    entity_column: str = "entity_id"
    timestamp_column: str = "event_timestamp"
    feature_columns: list[str] = field(default_factory=list)
    description: str = ""
    tags: dict[str, str] = field(default_factory=dict)


class FeatureStore:
    """Simple Parquet-backed feature store.

    Features are stored as Parquet files organised by feature-set name
    and date partition.  An optional Redis connection can be provided
    for low-latency online serving.

    Args:
        root: Root directory for Parquet storage.
        redis_url: Optional Redis connection URL for online serving.
    """

    def __init__(
        self,
        root: str | Path = "feature_store",
        redis_url: str | None = None,
    ) -> None:
        if not _HAS_PANDAS:
            raise ImportError(
                "pandas is required for FeatureStore. Install it with: pip install pandas>=2.1"
            )

        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._schemas: dict[str, FeatureSetSchema] = {}
        self._redis: Any = None

        # Load existing schemas
        self._load_schemas()

        if redis_url:
            try:
                import redis

                self._redis = redis.from_url(redis_url)
                logger.info("Feature store online serving enabled", redis_url=redis_url)
            except ImportError:
                logger.warning("redis package not installed; online serving disabled")

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_feature_set(
        self,
        name: str,
        schema: FeatureSetSchema | None = None,
        description: str = "",
    ) -> FeatureSetSchema:
        """Register a new feature set.

        Args:
            name: Unique name for the feature set.
            schema: Pre-built schema.  If ``None``, a minimal schema is
                created automatically.
            description: Human-readable description.

        Returns:
            The registered :class:`FeatureSetSchema`.
        """
        if schema is None:
            schema = FeatureSetSchema(name=name, description=description)
        else:
            schema.name = name
            if description:
                schema.description = description

        self._schemas[name] = schema
        self._save_schemas()

        fs_dir = self.root / name
        fs_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Feature set registered", name=name)
        return schema

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest(self, feature_set_name: str, dataframe: "pd.DataFrame") -> int:
        """Ingest features from a DataFrame.

        Data is appended to a Parquet file partitioned by date.

        Args:
            feature_set_name: Target feature set (must be registered).
            dataframe: DataFrame containing the features.

        Returns:
            Number of rows ingested.
        """
        if feature_set_name not in self._schemas:
            raise KeyError(f"Feature set '{feature_set_name}' not registered.")

        schema = self._schemas[feature_set_name]
        fs_dir = self.root / feature_set_name

        # Add ingestion timestamp if not present
        if schema.timestamp_column not in dataframe.columns:
            dataframe = dataframe.copy()
            dataframe[schema.timestamp_column] = datetime.now(timezone.utc)

        # Update schema feature columns from data
        feature_cols = [
            c for c in dataframe.columns
            if c not in {schema.entity_column, schema.timestamp_column}
        ]
        if not schema.feature_columns:
            schema.feature_columns = feature_cols
            self._save_schemas()

        # Partition by date
        ts = pd.to_datetime(dataframe[schema.timestamp_column])
        date_str = ts.iloc[0].strftime("%Y-%m-%d") if len(ts) > 0 else "unknown"
        partition_path = fs_dir / f"{date_str}.parquet"

        if partition_path.exists():
            existing = pd.read_parquet(partition_path)
            dataframe = pd.concat([existing, dataframe], ignore_index=True)

        dataframe.to_parquet(partition_path, index=False)

        # Push to Redis for online serving
        if self._redis is not None:
            self._push_to_redis(feature_set_name, dataframe, schema)

        logger.info(
            "Features ingested",
            feature_set=feature_set_name,
            n_rows=len(dataframe),
        )
        return len(dataframe)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get_features(
        self,
        feature_set_name: str,
        entity_ids: Sequence[str] | None = None,
        timestamp: datetime | str | None = None,
    ) -> "pd.DataFrame":
        """Point-in-time feature retrieval.

        Args:
            feature_set_name: Feature set to query.
            entity_ids: Optional filter on entity IDs.
            timestamp: If provided, return the latest features at or
                before this time.

        Returns:
            DataFrame of matching features.
        """
        if feature_set_name not in self._schemas:
            raise KeyError(f"Feature set '{feature_set_name}' not registered.")

        schema = self._schemas[feature_set_name]
        fs_dir = self.root / feature_set_name

        # Read all partitions
        frames: list["pd.DataFrame"] = []
        for parquet_file in sorted(fs_dir.glob("*.parquet")):
            frames.append(pd.read_parquet(parquet_file))

        if not frames:
            return pd.DataFrame()

        df = pd.concat(frames, ignore_index=True)

        # Filter by entity
        if entity_ids is not None and schema.entity_column in df.columns:
            df = df[df[schema.entity_column].isin(entity_ids)]

        # Point-in-time filter
        if timestamp is not None and schema.timestamp_column in df.columns:
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            ts_col = pd.to_datetime(df[schema.timestamp_column])
            df = df[ts_col <= pd.Timestamp(timestamp, tz=timezone.utc if timestamp.tzinfo else None)]
            # Take latest per entity
            if schema.entity_column in df.columns:
                df = df.sort_values(schema.timestamp_column).groupby(schema.entity_column).last().reset_index()

        return df

    def get_training_data(
        self,
        feature_sets: list[str],
        entity_ids: Sequence[str] | None = None,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
    ) -> "pd.DataFrame":
        """Assemble a training dataset from multiple feature sets.

        Feature sets are joined on their entity column.

        Args:
            feature_sets: Names of feature sets to join.
            entity_ids: Optional entity filter.
            start_time: Start of the time range.
            end_time: End of the time range.

        Returns:
            Merged DataFrame.
        """
        merged: "pd.DataFrame" | None = None

        for fs_name in feature_sets:
            if fs_name not in self._schemas:
                raise KeyError(f"Feature set '{fs_name}' not registered.")

            schema = self._schemas[fs_name]
            fs_dir = self.root / fs_name

            frames: list["pd.DataFrame"] = []
            for parquet_file in sorted(fs_dir.glob("*.parquet")):
                frames.append(pd.read_parquet(parquet_file))

            if not frames:
                continue

            df = pd.concat(frames, ignore_index=True)

            # Time range filter
            if schema.timestamp_column in df.columns:
                ts_col = pd.to_datetime(df[schema.timestamp_column])
                if start_time is not None:
                    start_ts = pd.Timestamp(start_time) if isinstance(start_time, str) else pd.Timestamp(start_time)
                    df = df[ts_col >= start_ts]
                if end_time is not None:
                    end_ts = pd.Timestamp(end_time) if isinstance(end_time, str) else pd.Timestamp(end_time)
                    df = df[ts_col <= end_ts]

            # Entity filter
            if entity_ids is not None and schema.entity_column in df.columns:
                df = df[df[schema.entity_column].isin(entity_ids)]

            # Merge
            if merged is None:
                merged = df
            else:
                entity_col = schema.entity_column
                if entity_col in merged.columns and entity_col in df.columns:
                    # Suffix overlapping columns
                    merged = merged.merge(df, on=entity_col, how="outer", suffixes=("", f"_{fs_name}"))
                else:
                    merged = pd.concat([merged, df], axis=1)

        return merged if merged is not None else pd.DataFrame()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _save_schemas(self) -> None:
        """Persist feature set schemas to disk."""
        schemas_path = self.root / "_schemas.json"
        data = {}
        for name, schema in self._schemas.items():
            data[name] = {
                "entity_column": schema.entity_column,
                "timestamp_column": schema.timestamp_column,
                "feature_columns": schema.feature_columns,
                "description": schema.description,
                "tags": schema.tags,
            }
        schemas_path.write_text(json.dumps(data, indent=2))

    def _load_schemas(self) -> None:
        """Load existing schemas from disk."""
        schemas_path = self.root / "_schemas.json"
        if schemas_path.exists():
            data = json.loads(schemas_path.read_text())
            for name, info in data.items():
                self._schemas[name] = FeatureSetSchema(
                    name=name,
                    entity_column=info.get("entity_column", "entity_id"),
                    timestamp_column=info.get("timestamp_column", "event_timestamp"),
                    feature_columns=info.get("feature_columns", []),
                    description=info.get("description", ""),
                    tags=info.get("tags", {}),
                )

    def _push_to_redis(
        self, feature_set_name: str, df: "pd.DataFrame", schema: FeatureSetSchema
    ) -> None:
        """Push latest features to Redis for online serving."""
        if self._redis is None or schema.entity_column not in df.columns:
            return
        try:
            latest = df.sort_values(schema.timestamp_column).groupby(schema.entity_column).last()
            for entity_id, row in latest.iterrows():
                key = f"features:{feature_set_name}:{entity_id}"
                value = row[schema.feature_columns].to_dict() if schema.feature_columns else row.to_dict()
                self._redis.set(key, json.dumps(value, default=str))
        except Exception:
            logger.warning("Failed to push features to Redis", exc_info=True)


__all__ = ["FeatureSetSchema", "FeatureStore"]
