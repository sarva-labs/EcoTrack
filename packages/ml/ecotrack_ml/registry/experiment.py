"""Experiment tracking for model development.

Provides :class:`ExperimentTracker` with MLflow integration and a local
file-based fallback.  Supports use as a context manager.
"""
from __future__ import annotations

import json
import logging
import shutil
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

try:
    import structlog

    logger = structlog.get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)  # type: ignore[assignment]

# Optional MLflow
try:
    import mlflow

    _HAS_MLFLOW = True
except ImportError:
    _HAS_MLFLOW = False


@dataclass
class _LocalRun:
    """State for a local experiment run."""

    experiment_name: str
    run_name: str
    start_time: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)


class ExperimentTracker:
    """Experiment tracking with MLflow and local fallback.

    Args:
        tracking_uri: MLflow tracking URI.  ``None`` → local fallback.
        local_root: Root directory for local experiment files.
    """

    def __init__(
        self,
        tracking_uri: str | None = None,
        local_root: str | Path = "experiments",
    ) -> None:
        self.local_root = Path(local_root)
        self._use_mlflow = _HAS_MLFLOW and tracking_uri is not None
        self._local_run: _LocalRun | None = None

        if self._use_mlflow:
            mlflow.set_tracking_uri(tracking_uri)
            logger.info("Experiment tracker using MLflow", uri=tracking_uri)
        else:
            self.local_root.mkdir(parents=True, exist_ok=True)
            logger.info("Experiment tracker using local filesystem", root=str(self.local_root))

    # ------------------------------------------------------------------
    # Run lifecycle
    # ------------------------------------------------------------------

    @contextmanager
    def start_run(
        self, experiment_name: str, run_name: str | None = None
    ) -> Generator["ExperimentTracker", None, None]:
        """Start a tracking run as a context manager.

        Usage::

            with tracker.start_run("climate_exp", "run_42") as t:
                t.log_params({"lr": 0.001})
                t.log_metrics({"loss": 0.5}, step=1)

        Args:
            experiment_name: Name of the experiment group.
            run_name: Optional name for this specific run.

        Yields:
            ``self`` for chained method calls.
        """
        self._begin_run(experiment_name, run_name)
        try:
            yield self
        finally:
            self.end_run()

    def _begin_run(self, experiment_name: str, run_name: str | None) -> None:
        """Internal: start tracking."""
        run_name = run_name or f"run_{int(time.time())}"

        if self._use_mlflow:
            experiment = mlflow.set_experiment(experiment_name)
            mlflow.start_run(experiment_id=experiment.experiment_id, run_name=run_name)
        else:
            self._local_run = _LocalRun(
                experiment_name=experiment_name,
                run_name=run_name,
                start_time=datetime.now(timezone.utc).isoformat(),
            )
        logger.info("Run started", experiment=experiment_name, run=run_name)

    def end_run(self) -> None:
        """End the current tracking run and flush data."""
        if self._use_mlflow:
            mlflow.end_run()
        elif self._local_run is not None:
            self._flush_local_run()
            self._local_run = None
        logger.info("Run ended")

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def log_params(self, params: dict[str, Any]) -> None:
        """Log hyper-parameters for the current run.

        Args:
            params: Key-value parameter mapping.
        """
        if self._use_mlflow:
            mlflow.log_params({k: str(v) for k, v in params.items()})
        elif self._local_run is not None:
            self._local_run.params.update(params)
        else:
            logger.warning("No active run; params not logged.")

    def log_metrics(self, metrics: dict[str, float], step: int | None = None) -> None:
        """Log metrics for the current run.

        Args:
            metrics: Key-value metric mapping.
            step: Optional step index (epoch / iteration).
        """
        if self._use_mlflow:
            mlflow.log_metrics(metrics, step=step)
        elif self._local_run is not None:
            for key, value in metrics.items():
                self._local_run.metrics.setdefault(key, []).append(
                    {"value": value, "step": step, "timestamp": datetime.now(timezone.utc).isoformat()}
                )
        else:
            logger.warning("No active run; metrics not logged.")

    def log_artifact(self, path: str | Path) -> None:
        """Log an artifact file for the current run.

        Args:
            path: Path to the artifact file.
        """
        path = Path(path)
        if self._use_mlflow:
            mlflow.log_artifact(str(path))
        elif self._local_run is not None:
            self._local_run.artifacts.append(str(path))
        else:
            logger.warning("No active run; artifact not logged.")

    # ------------------------------------------------------------------
    # Local fallback persistence
    # ------------------------------------------------------------------

    def _flush_local_run(self) -> None:
        """Write local run data to disk."""
        if self._local_run is None:
            return
        run_dir = (
            self.local_root
            / self._local_run.experiment_name
            / self._local_run.run_name
        )
        run_dir.mkdir(parents=True, exist_ok=True)

        run_data = {
            "experiment_name": self._local_run.experiment_name,
            "run_name": self._local_run.run_name,
            "start_time": self._local_run.start_time,
            "end_time": datetime.now(timezone.utc).isoformat(),
            "params": self._local_run.params,
            "metrics": self._local_run.metrics,
        }
        (run_dir / "run.json").write_text(json.dumps(run_data, indent=2, default=str))

        # Copy artifacts into the run directory
        art_dir = run_dir / "artifacts"
        art_dir.mkdir(exist_ok=True)
        for art_path_str in self._local_run.artifacts:
            art_path = Path(art_path_str)
            if art_path.exists():
                shutil.copy2(art_path, art_dir / art_path.name)

        logger.info("Local run flushed", path=str(run_dir))


__all__ = ["ExperimentTracker"]
