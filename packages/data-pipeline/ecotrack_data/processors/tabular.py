"""Tabular data processor for CSV/JSON data."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from ecotrack.logging import get_logger

from .base import DataProcessor

logger = get_logger(__name__)


@dataclass
class TabularSchema:
    """Expected schema for tabular data validation.

    Attributes:
        required_columns: Columns that must exist.
        column_types: Expected dtype per column (pandas dtype strings).
        lat_column: Name of the latitude column.
        lon_column: Name of the longitude column.
        unique_columns: Columns that define uniqueness for deduplication.
    """

    required_columns: list[str] = field(default_factory=list)
    column_types: dict[str, str] = field(default_factory=dict)
    lat_column: str = "latitude"
    lon_column: str = "longitude"
    unique_columns: list[str] = field(default_factory=list)


class TabularProcessor(DataProcessor[pd.DataFrame, pd.DataFrame]):
    """Processor for CSV and JSON tabular data.

    Provides coordinate normalisation, schema validation,
    deduplication, and missing-value interpolation.
    """

    def __init__(self, schema: TabularSchema | None = None) -> None:
        self.schema = schema or TabularSchema()

    # ------------------------------------------------------------------
    # DataProcessor interface
    # ------------------------------------------------------------------

    async def process(self, data: pd.DataFrame) -> pd.DataFrame:
        """Run the default processing pipeline on *data*.

        Steps:
        1. Normalise coordinates.
        2. Validate schema.
        3. Deduplicate.
        4. Interpolate missing values.

        Args:
            data: Input DataFrame.

        Returns:
            Cleaned and normalised DataFrame.
        """
        df = await self.normalize_coordinates(data)
        if not await self.validate_schema(df):
            logger.warning("tabular.process: schema validation failed, continuing")
        df = await self.deduplicate(df)
        df = await self.interpolate_missing(df)
        return df

    async def validate_input(self, data: pd.DataFrame) -> bool:
        """Validate that the input is a non-empty DataFrame.

        Args:
            data: Input data.

        Returns:
            ``True`` if *data* is a non-empty :class:`pd.DataFrame`.
        """
        if not isinstance(data, pd.DataFrame):
            logger.warning("tabular.validate_input: not a DataFrame")
            return False
        if data.empty:
            logger.warning("tabular.validate_input: empty DataFrame")
            return False
        return True

    async def validate_output(self, data: pd.DataFrame) -> bool:
        """Validate the processed output.

        Args:
            data: Processed DataFrame.

        Returns:
            ``True`` if the output is a non-empty DataFrame.
        """
        return isinstance(data, pd.DataFrame) and not data.empty

    # ------------------------------------------------------------------
    # Processing methods
    # ------------------------------------------------------------------

    async def normalize_coordinates(
        self,
        df: pd.DataFrame,
        *,
        lat_col: str | None = None,
        lon_col: str | None = None,
    ) -> pd.DataFrame:
        """Normalise geographic coordinates.

        - Clamps latitude to [-90, 90] and longitude to [-180, 180].
        - Detects and swaps lat/lon if they appear reversed.
        - Renames columns to the schema's ``lat_column`` / ``lon_column``.

        Args:
            df: Input DataFrame.
            lat_col: Override for latitude column name.
            lon_col: Override for longitude column name.

        Returns:
            DataFrame with normalised coordinate columns.
        """
        result = df.copy()
        lat = lat_col or self.schema.lat_column
        lon = lon_col or self.schema.lon_column

        # Try to detect common alternative column names
        lat_aliases = {"lat", "latitude", "decimallatitude", "y", "lat_dd"}
        lon_aliases = {"lon", "lng", "longitude", "decimallongitude", "x", "lon_dd"}

        lat_found = _find_column(result.columns, lat, lat_aliases)
        lon_found = _find_column(result.columns, lon, lon_aliases)

        if lat_found and lat_found != lat:
            result = result.rename(columns={lat_found: lat})
        if lon_found and lon_found != lon:
            result = result.rename(columns={lon_found: lon})

        if lat in result.columns and lon in result.columns:
            # Convert to numeric
            result[lat] = pd.to_numeric(result[lat], errors="coerce")
            result[lon] = pd.to_numeric(result[lon], errors="coerce")

            # Detect swapped lat/lon (lat values in lon range)
            lat_vals = result[lat].dropna()
            if len(lat_vals) > 0 and (lat_vals.abs() > 90).mean() > 0.5:
                logger.warning("tabular.normalize_coordinates: swapping lat/lon")
                result[lat], result[lon] = result[lon].copy(), result[lat].copy()

            # Clamp values
            result[lat] = result[lat].clip(-90, 90)
            result[lon] = result[lon].clip(-180, 180)

            logger.info(
                "tabular.normalize_coordinates",
                rows=len(result),
                lat_col=lat,
                lon_col=lon,
            )
        else:
            logger.warning(
                "tabular.normalize_coordinates: coordinate columns not found",
                available=list(result.columns),
            )

        return result

    async def validate_schema(
        self,
        df: pd.DataFrame,
        schema: TabularSchema | None = None,
    ) -> bool:
        """Validate DataFrame against a schema.

        Checks for required columns and expected data types.

        Args:
            df: DataFrame to validate.
            schema: Override schema (default: instance schema).

        Returns:
            ``True`` if all schema checks pass.
        """
        s = schema or self.schema

        # Check required columns
        missing = set(s.required_columns) - set(df.columns)
        if missing:
            logger.warning(
                "tabular.validate_schema: missing columns",
                missing=list(missing),
            )
            return False

        # Check column types
        for col, expected_dtype in s.column_types.items():
            if col in df.columns:
                actual = str(df[col].dtype)
                if not _dtype_compatible(actual, expected_dtype):
                    logger.warning(
                        "tabular.validate_schema: type mismatch",
                        column=col,
                        expected=expected_dtype,
                        actual=actual,
                    )
                    return False

        logger.info("tabular.validate_schema: passed")
        return True

    async def deduplicate(
        self,
        df: pd.DataFrame,
        *,
        subset: list[str] | None = None,
        keep: str = "first",
    ) -> pd.DataFrame:
        """Remove duplicate rows.

        Args:
            df: Input DataFrame.
            subset: Columns to consider for identifying duplicates.
                Defaults to the schema's ``unique_columns``.
            keep: ``"first"`` or ``"last"`` — which duplicate to keep.

        Returns:
            Deduplicated DataFrame.
        """
        cols = subset or self.schema.unique_columns or None
        before = len(df)
        result = df.drop_duplicates(subset=cols, keep=keep)
        after = len(result)

        if before != after:
            logger.info(
                "tabular.deduplicate",
                removed=before - after,
                remaining=after,
            )
        return result.reset_index(drop=True)

    async def interpolate_missing(
        self,
        df: pd.DataFrame,
        *,
        method: str = "linear",
        limit: int | None = 5,
        columns: list[str] | None = None,
    ) -> pd.DataFrame:
        """Interpolate missing values in numeric columns.

        Args:
            df: Input DataFrame.
            method: Interpolation method (e.g. ``"linear"``, ``"time"``,
                ``"nearest"``).
            limit: Maximum number of consecutive NaNs to fill.
            columns: Specific columns to interpolate.  Defaults to all
                numeric columns.

        Returns:
            DataFrame with interpolated values.
        """
        result = df.copy()
        target_cols = columns or result.select_dtypes(include=[np.number]).columns.tolist()
        filled_count = 0

        for col in target_cols:
            if col not in result.columns:
                continue
            nans_before = result[col].isna().sum()
            if nans_before == 0:
                continue

            result[col] = result[col].interpolate(method=method, limit=limit)
            nans_after = result[col].isna().sum()
            filled_count += nans_before - nans_after

        if filled_count > 0:
            logger.info(
                "tabular.interpolate_missing",
                filled=filled_count,
                method=method,
            )
        return result

    async def add_h3_index(
        self,
        df: pd.DataFrame,
        *,
        resolution: int = 9,
        lat_col: str | None = None,
        lon_col: str | None = None,
    ) -> pd.DataFrame:
        """Add an H3 spatial index column to the DataFrame.

        Args:
            df: Input DataFrame with coordinate columns.
            resolution: H3 resolution (0–15, default 9).
            lat_col: Latitude column name.
            lon_col: Longitude column name.

        Returns:
            DataFrame with an ``h3_index`` column.
        """
        import h3

        result = df.copy()
        lat = lat_col or self.schema.lat_column
        lon = lon_col or self.schema.lon_column

        if lat not in result.columns or lon not in result.columns:
            logger.warning("tabular.add_h3_index: coordinate columns not found")
            return result

        result["h3_index"] = result.apply(
            lambda row: (
                h3.latlng_to_cell(row[lat], row[lon], resolution)
                if pd.notna(row[lat]) and pd.notna(row[lon])
                else None
            ),
            axis=1,
        )

        logger.info(
            "tabular.add_h3_index",
            resolution=resolution,
            non_null=result["h3_index"].notna().sum(),
        )
        return result


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _find_column(
    columns: pd.Index,
    preferred: str,
    aliases: set[str],
) -> str | None:
    """Find a column by preferred name or alias (case-insensitive).

    Args:
        columns: DataFrame column index.
        preferred: Preferred column name.
        aliases: Set of alternative names.

    Returns:
        The matched column name, or ``None``.
    """
    lower_map = {c.lower(): c for c in columns}
    if preferred.lower() in lower_map:
        return lower_map[preferred.lower()]
    for alias in aliases:
        if alias in lower_map:
            return lower_map[alias]
    return None


def _dtype_compatible(actual: str, expected: str) -> bool:
    """Check if *actual* dtype is compatible with *expected*.

    Args:
        actual: Actual pandas dtype string.
        expected: Expected dtype string.

    Returns:
        ``True`` if compatible.
    """
    actual_l = actual.lower()
    expected_l = expected.lower()
    if expected_l in actual_l:
        return True
    numeric_kinds = {"float", "int", "number"}
    if expected_l in numeric_kinds and any(k in actual_l for k in numeric_kinds):
        return True
    return False


__all__ = ["TabularProcessor", "TabularSchema"]
