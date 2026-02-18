"""Data pipeline orchestrator for EcoTrack."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine

from ecotrack.logging import get_logger

from .sources.base import DataSource, FetchResult

logger = get_logger(__name__)


class PipelineStage(str, Enum):
    """Identifiers for pipeline stages."""

    FETCH = "fetch"
    VALIDATE = "validate"
    TRANSFORM = "transform"
    STORE = "store"


class PipelineStatus(str, Enum):
    """Overall pipeline execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DRY_RUN = "dry_run"


@dataclass
class StageResult:
    """Result of a single pipeline stage execution.

    Attributes:
        stage: The stage that was executed.
        success: Whether the stage completed successfully.
        duration_s: Wall-clock duration in seconds.
        records: Number of records processed.
        error: Error message if the stage failed.
        metadata: Arbitrary stage metadata.
    """

    stage: PipelineStage
    success: bool
    duration_s: float
    records: int = 0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """Aggregate result of a full pipeline run.

    Attributes:
        status: Final pipeline status.
        source_name: Name of the data source.
        started_at: Timestamp when the run began.
        finished_at: Timestamp when the run completed.
        total_duration_s: Total wall-clock duration.
        total_records: Total records ingested.
        stages: List of per-stage results.
        errors: List of error messages.
    """

    status: PipelineStatus
    source_name: str
    started_at: datetime
    finished_at: datetime | None = None
    total_duration_s: float = 0.0
    total_records: int = 0
    stages: list[StageResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# Type alias for a storage function
StoreFn = Callable[[list[Any]], Coroutine[Any, Any, int]]


class DataPipeline:
    """Orchestrates the Source → Validate → Transform → Store pipeline.

    Chains a :class:`DataSource` with an optional storage callable,
    handles retries on transient failures, emits structured log events
    at each stage, and supports a dry-run mode that skips storage.

    Example::

        source = NOAAClimateSource(api_key="...")
        storage = LocalStorage("data/output")

        async def store_fn(records):
            for r in records:
                await storage.put(f"climate/{r.id}.json", r.json().encode())
            return len(records)

        pipeline = DataPipeline(source=source, store=store_fn)
        result = await pipeline.run(
            bbox=(-90, 30, -80, 40),
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 31),
        )
        print(result.total_records)
    """

    def __init__(
        self,
        source: DataSource[Any],
        *,
        store: StoreFn | None = None,
        max_retries: int = 3,
        retry_delay_s: float = 5.0,
        dry_run: bool = False,
    ) -> None:
        self.source = source
        self._store = store
        self.max_retries = max_retries
        self.retry_delay_s = retry_delay_s
        self.dry_run = dry_run

    async def run(
        self,
        bbox: tuple[float, float, float, float] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        **kwargs: Any,
    ) -> PipelineResult:
        """Execute the full ingestion pipeline.

        Steps for each page yielded by the source:
        1. **Fetch** — retrieve data from the source.
        2. **Validate** — check data quality.
        3. **Transform** — convert to domain models.
        4. **Store** — persist transformed records (skipped in dry-run).

        Args:
            bbox: Bounding box filter.
            start_time: Temporal range start.
            end_time: Temporal range end.
            **kwargs: Source-specific parameters.

        Returns:
            :class:`PipelineResult` summarising the run.
        """
        run_start = time.monotonic()
        result = PipelineResult(
            status=PipelineStatus.RUNNING,
            source_name=self.source.config.name,
            started_at=datetime.utcnow(),
        )

        logger.info(
            "pipeline.start",
            source=self.source.config.name,
            dry_run=self.dry_run,
            bbox=bbox,
            start_time=str(start_time),
            end_time=str(end_time),
        )

        try:
            async with self.source:
                async for fetch_result in self.source.fetch(
                    bbox=bbox,
                    start_time=start_time,
                    end_time=end_time,
                    **kwargs,
                ):
                    page_result = await self._process_page(fetch_result)
                    result.stages.extend(page_result["stages"])
                    result.total_records += page_result["records"]
                    if page_result["errors"]:
                        result.errors.extend(page_result["errors"])

            result.status = (
                PipelineStatus.DRY_RUN if self.dry_run else PipelineStatus.COMPLETED
            )

        except Exception as exc:
            result.status = PipelineStatus.FAILED
            result.errors.append(str(exc))
            logger.error(
                "pipeline.failed",
                source=self.source.config.name,
                error=str(exc),
            )

        result.finished_at = datetime.utcnow()
        result.total_duration_s = time.monotonic() - run_start

        logger.info(
            "pipeline.complete",
            source=self.source.config.name,
            status=result.status.value,
            total_records=result.total_records,
            duration_s=round(result.total_duration_s, 2),
            errors=len(result.errors),
        )

        return result

    async def _process_page(
        self, fetch_result: FetchResult
    ) -> dict[str, Any]:
        """Process a single fetched page through validate → transform → store.

        Args:
            fetch_result: A :class:`FetchResult` from the source.

        Returns:
            Dict with ``stages``, ``records``, and ``errors``.
        """
        stages: list[StageResult] = []
        errors: list[str] = []
        records = 0

        # --- Fetch stage (already done, just log) ---
        stages.append(
            StageResult(
                stage=PipelineStage.FETCH,
                success=True,
                duration_s=0.0,
                records=1,
                metadata={"size_bytes": fetch_result.size_bytes},
            )
        )

        # --- Validate ---
        validate_start = time.monotonic()
        try:
            is_valid = await self.source.validate(fetch_result)
            validate_dur = time.monotonic() - validate_start
            stages.append(
                StageResult(
                    stage=PipelineStage.VALIDATE,
                    success=is_valid,
                    duration_s=validate_dur,
                )
            )
            if not is_valid:
                errors.append(
                    f"Validation failed for {fetch_result.source} "
                    f"at {fetch_result.timestamp}"
                )
                logger.warning(
                    "pipeline.validate_failed",
                    source=fetch_result.source,
                )
                return {"stages": stages, "records": 0, "errors": errors}
        except Exception as exc:
            validate_dur = time.monotonic() - validate_start
            stages.append(
                StageResult(
                    stage=PipelineStage.VALIDATE,
                    success=False,
                    duration_s=validate_dur,
                    error=str(exc),
                )
            )
            errors.append(f"Validate error: {exc}")
            return {"stages": stages, "records": 0, "errors": errors}

        # --- Transform ---
        transform_start = time.monotonic()
        try:
            domain_models = await self.source.transform(fetch_result)
            transform_dur = time.monotonic() - transform_start
            stages.append(
                StageResult(
                    stage=PipelineStage.TRANSFORM,
                    success=True,
                    duration_s=transform_dur,
                    records=len(domain_models),
                )
            )
            logger.debug(
                "pipeline.transformed",
                count=len(domain_models),
            )
        except Exception as exc:
            transform_dur = time.monotonic() - transform_start
            stages.append(
                StageResult(
                    stage=PipelineStage.TRANSFORM,
                    success=False,
                    duration_s=transform_dur,
                    error=str(exc),
                )
            )
            errors.append(f"Transform error: {exc}")
            return {"stages": stages, "records": 0, "errors": errors}

        # --- Store ---
        if self.dry_run or self._store is None:
            records = len(domain_models)
            stages.append(
                StageResult(
                    stage=PipelineStage.STORE,
                    success=True,
                    duration_s=0.0,
                    records=records,
                    metadata={"dry_run": self.dry_run, "store_fn": self._store is None},
                )
            )
        else:
            store_start = time.monotonic()
            attempt = 0
            stored = False
            while attempt < self.max_retries and not stored:
                try:
                    records = await self._store(domain_models)
                    store_dur = time.monotonic() - store_start
                    stages.append(
                        StageResult(
                            stage=PipelineStage.STORE,
                            success=True,
                            duration_s=store_dur,
                            records=records,
                        )
                    )
                    stored = True
                except Exception as exc:
                    attempt += 1
                    if attempt >= self.max_retries:
                        store_dur = time.monotonic() - store_start
                        stages.append(
                            StageResult(
                                stage=PipelineStage.STORE,
                                success=False,
                                duration_s=store_dur,
                                error=str(exc),
                            )
                        )
                        errors.append(f"Store error after {attempt} retries: {exc}")
                        logger.error(
                            "pipeline.store_failed",
                            error=str(exc),
                            attempts=attempt,
                        )
                    else:
                        logger.warning(
                            "pipeline.store_retry",
                            attempt=attempt,
                            error=str(exc),
                            delay=self.retry_delay_s,
                        )
                        await asyncio.sleep(self.retry_delay_s)

        return {"stages": stages, "records": records, "errors": errors}


__all__ = [
    "DataPipeline",
    "PipelineResult",
    "PipelineStage",
    "PipelineStatus",
    "StageResult",
]
