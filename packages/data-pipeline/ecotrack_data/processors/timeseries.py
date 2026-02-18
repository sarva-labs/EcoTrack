"""Time series data processor."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import numpy as np
import pandas as pd
from ecotrack.logging import get_logger

from .base import DataProcessor

logger = get_logger(__name__)


@dataclass
class TimeSeriesConfig:
    """Configuration for time series processing.

    Attributes:
        time_column: Name of the datetime column.
        value_columns: Columns containing measurement values.
        resample_rule: Default resampling frequency (pandas offset alias).
        aggregation: Default aggregation function name.
        anomaly_std_threshold: Standard deviations for anomaly detection.
        rolling_window: Default rolling window size.
        max_gap: Maximum gap to interpolate across.
    """

    time_column: str = "timestamp"
    value_columns: list[str] = field(default_factory=lambda: ["value"])
    resample_rule: str = "1h"
    aggregation: str = "mean"
    anomaly_std_threshold: float = 3.0
    rolling_window: int = 24
    max_gap: timedelta = field(default_factory=lambda: timedelta(hours=6))


@dataclass
class AnomalyResult:
    """Result of anomaly detection on a time series.

    Attributes:
        anomalies: DataFrame with detected anomaly rows.
        total_points: Total number of data points analysed.
        anomaly_count: Number of anomalies detected.
        anomaly_rate: Fraction of points that are anomalous.
        threshold_upper: Upper threshold used for detection.
        threshold_lower: Lower threshold used for detection.
    """

    anomalies: pd.DataFrame
    total_points: int
    anomaly_count: int
    anomaly_rate: float
    threshold_upper: float
    threshold_lower: float


class TimeSeriesProcessor(DataProcessor[pd.DataFrame, pd.DataFrame]):
    """Processor for temporal data.

    Provides temporal resampling, anomaly detection, rolling statistics,
    and gap-filling for environmental time series data.
    """

    def __init__(self, config: TimeSeriesConfig | None = None) -> None:
        self.config = config or TimeSeriesConfig()

    # ------------------------------------------------------------------
    # DataProcessor interface
    # ------------------------------------------------------------------

    async def process(self, data: pd.DataFrame) -> pd.DataFrame:
        """Default processing: ensure datetime index, resample, fill gaps.

        Args:
            data: Input time series DataFrame.

        Returns:
            Resampled and gap-filled DataFrame.
        """
        df = self._ensure_datetime_index(data)
        df = await self.fill_gaps(df)
        df = await self.resample_temporal(df, rule=self.config.resample_rule)
        return df

    async def validate_input(self, data: pd.DataFrame) -> bool:
        """Validate the input time series.

        Checks:
        - Data is a non-empty DataFrame.
        - Contains the configured time column or has a DatetimeIndex.
        - Contains at least one value column.

        Args:
            data: Input data.

        Returns:
            ``True`` if valid.
        """
        if not isinstance(data, pd.DataFrame) or data.empty:
            logger.warning("timeseries.validate_input: empty or not DataFrame")
            return False

        has_time = (
            isinstance(data.index, pd.DatetimeIndex)
            or self.config.time_column in data.columns
        )
        if not has_time:
            logger.warning(
                "timeseries.validate_input: no time column found",
                expected=self.config.time_column,
            )
            return False

        return True

    async def validate_output(self, data: pd.DataFrame) -> bool:
        """Validate the processed output.

        Args:
            data: Processed DataFrame.

        Returns:
            ``True`` if output is a non-empty DataFrame with DatetimeIndex.
        """
        if not isinstance(data, pd.DataFrame) or data.empty:
            return False
        return isinstance(data.index, pd.DatetimeIndex)

    # ------------------------------------------------------------------
    # Processing methods
    # ------------------------------------------------------------------

    async def resample_temporal(
        self,
        df: pd.DataFrame,
        *,
        rule: str | None = None,
        aggregation: str | None = None,
    ) -> pd.DataFrame:
        """Resample time series to a regular interval.

        Args:
            df: Input DataFrame with DatetimeIndex.
            rule: Pandas offset alias (e.g. ``"1h"``, ``"1D"``, ``"1W"``).
            aggregation: Aggregation function (``"mean"``, ``"sum"``,
                ``"min"``, ``"max"``, ``"median"``).

        Returns:
            Resampled DataFrame.
        """
        result = self._ensure_datetime_index(df)
        rule = rule or self.config.resample_rule
        agg = aggregation or self.config.aggregation

        resampler = result.resample(rule)

        agg_map: dict[str, Any] = {
            "mean": resampler.mean,
            "sum": resampler.sum,
            "min": resampler.min,
            "max": resampler.max,
            "median": resampler.median,
        }
        agg_fn = agg_map.get(agg, resampler.mean)
        resampled = agg_fn(numeric_only=True)

        logger.info(
            "timeseries.resample",
            rule=rule,
            aggregation=agg,
            rows_before=len(df),
            rows_after=len(resampled),
        )
        return resampled

    async def detect_anomalies(
        self,
        df: pd.DataFrame,
        *,
        column: str | None = None,
        std_threshold: float | None = None,
        method: str = "zscore",
    ) -> AnomalyResult:
        """Detect anomalies in a time series column.

        Supports two methods:

        - ``"zscore"``: Flag points where |z-score| > threshold.
        - ``"iqr"``: Flag points outside the IQR fences.

        Args:
            df: Input DataFrame with DatetimeIndex.
            column: Value column to analyse.  Defaults to the first
                configured value column.
            std_threshold: Z-score threshold (default from config).
            method: ``"zscore"`` or ``"iqr"``.

        Returns:
            :class:`AnomalyResult` with detected anomalies.
        """
        result = self._ensure_datetime_index(df)
        col = column or self.config.value_columns[0]
        threshold = std_threshold or self.config.anomaly_std_threshold

        if col not in result.columns:
            raise ValueError(f"Column '{col}' not found in DataFrame")

        series = result[col].dropna()

        if method == "iqr":
            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
        else:
            # Z-score method
            mean = series.mean()
            std = series.std()
            lower = mean - threshold * std
            upper = mean + threshold * std

        mask = (series < lower) | (series > upper)
        anomalies = result.loc[mask.index[mask]]

        anomaly_result = AnomalyResult(
            anomalies=anomalies,
            total_points=len(series),
            anomaly_count=int(mask.sum()),
            anomaly_rate=float(mask.mean()),
            threshold_upper=float(upper),
            threshold_lower=float(lower),
        )

        logger.info(
            "timeseries.detect_anomalies",
            method=method,
            column=col,
            anomalies=anomaly_result.anomaly_count,
            rate=round(anomaly_result.anomaly_rate, 4),
        )
        return anomaly_result

    async def compute_rolling_stats(
        self,
        df: pd.DataFrame,
        *,
        window: int | None = None,
        columns: list[str] | None = None,
        stats: list[str] | None = None,
    ) -> pd.DataFrame:
        """Compute rolling window statistics.

        Args:
            df: Input DataFrame with DatetimeIndex.
            window: Rolling window size (number of periods).
            columns: Columns to compute stats for.
            stats: Statistics to compute (``"mean"``, ``"std"``, ``"min"``,
                ``"max"``).

        Returns:
            DataFrame with additional rolling statistic columns.
        """
        result = self._ensure_datetime_index(df).copy()
        win = window or self.config.rolling_window
        cols = columns or self.config.value_columns
        stat_names = stats or ["mean", "std"]

        for col in cols:
            if col not in result.columns:
                continue
            roller = result[col].rolling(window=win, min_periods=1)
            for stat in stat_names:
                stat_fn = getattr(roller, stat, None)
                if stat_fn is not None:
                    result[f"{col}_rolling_{stat}"] = stat_fn()

        logger.info(
            "timeseries.rolling_stats",
            window=win,
            columns=cols,
            stats=stat_names,
        )
        return result

    async def fill_gaps(
        self,
        df: pd.DataFrame,
        *,
        method: str = "linear",
        max_gap: timedelta | None = None,
        columns: list[str] | None = None,
    ) -> pd.DataFrame:
        """Fill temporal gaps in time series data.

        Reindexes the DataFrame to a regular frequency and interpolates
        missing values for gaps shorter than *max_gap*.

        Args:
            df: Input DataFrame with DatetimeIndex.
            method: Interpolation method (e.g. ``"linear"``, ``"nearest"``,
                ``"pad"``).
            max_gap: Maximum gap duration to fill.
            columns: Specific columns to interpolate.

        Returns:
            Gap-filled DataFrame.
        """
        result = self._ensure_datetime_index(df)
        gap_limit = max_gap or self.config.max_gap

        if len(result) < 2:
            return result

        # Infer frequency
        freq = pd.infer_freq(result.index)
        if freq is None:
            # Estimate median time delta
            deltas = result.index.to_series().diff().dropna()
            if len(deltas) > 0:
                median_delta = deltas.median()
                freq = median_delta
            else:
                return result

        # Reindex to regular frequency
        new_index = pd.date_range(
            start=result.index.min(),
            end=result.index.max(),
            freq=freq,
        )
        reindexed = result.reindex(new_index)

        # Determine max consecutive NaNs to fill
        if isinstance(freq, str):
            freq_delta = pd.tseries.frequencies.to_offset(freq)
            if freq_delta is not None:
                limit = int(gap_limit / freq_delta.delta) if hasattr(freq_delta, 'delta') else None
            else:
                limit = None
        elif isinstance(freq, timedelta):
            limit = int(gap_limit / freq) if freq.total_seconds() > 0 else None
        else:
            limit = None

        target_cols = columns or reindexed.select_dtypes(include=[np.number]).columns.tolist()
        for col in target_cols:
            if col in reindexed.columns:
                reindexed[col] = reindexed[col].interpolate(
                    method=method, limit=limit
                )

        gaps_filled = len(reindexed) - len(result)
        if gaps_filled > 0:
            logger.info(
                "timeseries.fill_gaps",
                gaps_filled=gaps_filled,
                method=method,
                max_gap=str(gap_limit),
            )
        return reindexed

    async def compute_change_rate(
        self,
        df: pd.DataFrame,
        *,
        column: str | None = None,
        periods: int = 1,
    ) -> pd.DataFrame:
        """Compute the rate of change between consecutive time steps.

        Args:
            df: Input DataFrame.
            column: Column to compute change for.
            periods: Number of periods for the diff.

        Returns:
            DataFrame with a ``{column}_change_rate`` column.
        """
        result = self._ensure_datetime_index(df).copy()
        col = column or self.config.value_columns[0]

        if col not in result.columns:
            raise ValueError(f"Column '{col}' not found")

        result[f"{col}_change_rate"] = result[col].pct_change(periods=periods)
        result[f"{col}_diff"] = result[col].diff(periods=periods)

        logger.info(
            "timeseries.change_rate",
            column=col,
            periods=periods,
        )
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ensure_datetime_index(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure the DataFrame has a DatetimeIndex.

        If the time column exists but is not the index, set it.

        Args:
            df: Input DataFrame.

        Returns:
            DataFrame with DatetimeIndex.
        """
        if isinstance(df.index, pd.DatetimeIndex):
            return df

        if self.config.time_column in df.columns:
            result = df.copy()
            result[self.config.time_column] = pd.to_datetime(
                result[self.config.time_column], errors="coerce"
            )
            result = result.set_index(self.config.time_column).sort_index()
            return result

        # Try to convert the existing index
        try:
            result = df.copy()
            result.index = pd.to_datetime(result.index)
            return result
        except (ValueError, TypeError):
            return df


__all__ = ["TimeSeriesProcessor", "TimeSeriesConfig", "AnomalyResult"]
