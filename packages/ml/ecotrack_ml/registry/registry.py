"""Model registry integration with MLflow.

Provides :class:`ModelRegistry` for versioned model management with
MLflow as the primary backend and a local file-based fallback when
MLflow is not available.
"""
from __future__ import annotations

import json
import logging
import shutil
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ecotrack_ml.models.base import EcoTrackModel, ModelMetadata

try:
    import structlog

    logger = structlog.get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)  # type: ignore[assignment]

# Optional MLflow import
try:
    import mlflow
    from mlflow.tracking import MlflowClient

    _HAS_MLFLOW = True
except ImportError:
    _HAS_MLFLOW = False


class ModelRegistry:
    """MLflow-backed model registry with local fallback.

    When MLflow is available, all models and metrics are stored in the
    configured MLflow tracking server.  Otherwise a local directory
    structure is used.

    Args:
        tracking_uri: MLflow tracking URI (e.g. ``"http://mlflow:5000"``).
            Ignored when MLflow is not installed.
        local_root: Root directory for the local file-based fallback.
    """

    def __init__(
        self,
        tracking_uri: str | None = None,
        local_root: str | Path = "model_registry",
    ) -> None:
        self.local_root = Path(local_root)
        self._use_mlflow = _HAS_MLFLOW and tracking_uri is not None

        if self._use_mlflow:
            mlflow.set_tracking_uri(tracking_uri)
            self._client = MlflowClient(tracking_uri)
            logger.info("Model registry using MLflow", uri=tracking_uri)
        else:
            self.local_root.mkdir(parents=True, exist_ok=True)
            logger.info("Model registry using local filesystem", root=str(self.local_root))

    # ------------------------------------------------------------------
    # Register
    # ------------------------------------------------------------------

    def register_model(
        self,
        model: EcoTrackModel,
        metadata: ModelMetadata,
        metrics: dict[str, float] | None = None,
        artifacts: list[Path] | None = None,
    ) -> str:
        """Register a trained model.

        Args:
            model: Trained model instance.
            metadata: Model metadata.
            metrics: Evaluation metrics to record.
            artifacts: Extra artifact files to attach.

        Returns:
            A version identifier string.
        """
        if self._use_mlflow:
            return self._register_mlflow(model, metadata, metrics, artifacts)
        return self._register_local(model, metadata, metrics, artifacts)

    def _register_mlflow(
        self,
        model: EcoTrackModel,
        metadata: ModelMetadata,
        metrics: dict[str, float] | None,
        artifacts: list[Path] | None,
    ) -> str:
        experiment = mlflow.set_experiment(metadata.domain)
        with mlflow.start_run(experiment_id=experiment.experiment_id, run_name=metadata.name):
            mlflow.log_params({"name": metadata.name, "version": metadata.version, "task": metadata.task.value})
            if metrics:
                mlflow.log_metrics(metrics)
            # Save model checkpoint as artifact
            import tempfile

            with tempfile.TemporaryDirectory() as tmp:
                ckpt = Path(tmp) / "model.pt"
                model.save_checkpoint(ckpt)
                mlflow.log_artifact(str(ckpt))
            if artifacts:
                for art in artifacts:
                    mlflow.log_artifact(str(art))

            # Register in model registry
            run_id = mlflow.active_run().info.run_id
            model_uri = f"runs:/{run_id}/model.pt"
            try:
                result = mlflow.register_model(model_uri, metadata.name)
                version = result.version
            except Exception:
                version = metadata.version

        logger.info("Model registered (MLflow)", name=metadata.name, version=version)
        return str(version)

    def _register_local(
        self,
        model: EcoTrackModel,
        metadata: ModelMetadata,
        metrics: dict[str, float] | None,
        artifacts: list[Path] | None,
    ) -> str:
        model_dir = self.local_root / metadata.name / metadata.version
        model_dir.mkdir(parents=True, exist_ok=True)

        # Save checkpoint
        model.save_checkpoint(model_dir / "model.pt")

        # Save metadata
        meta_dict = asdict(metadata)
        meta_dict["task"] = metadata.task.value
        meta_dict["registered_at"] = datetime.now(timezone.utc).isoformat()
        if metrics:
            meta_dict["metrics"] = metrics
        (model_dir / "metadata.json").write_text(json.dumps(meta_dict, indent=2, default=str))

        # Copy artifacts
        if artifacts:
            art_dir = model_dir / "artifacts"
            art_dir.mkdir(exist_ok=True)
            for art in artifacts:
                if art.exists():
                    shutil.copy2(art, art_dir / art.name)

        logger.info("Model registered (local)", name=metadata.name, version=metadata.version)
        return metadata.version

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load_model(
        self,
        name: str,
        version: str,
        model_class: type[EcoTrackModel] | None = None,
        **kwargs: Any,
    ) -> EcoTrackModel:
        """Load a model from the registry.

        Args:
            name: Registered model name.
            version: Model version string.
            model_class: Concrete model class (required for local backend).
            **kwargs: Forwarded to the model constructor.

        Returns:
            An initialised :class:`EcoTrackModel`.
        """
        if self._use_mlflow:
            return self._load_mlflow(name, version, model_class, **kwargs)
        return self._load_local(name, version, model_class, **kwargs)

    def _load_mlflow(
        self, name: str, version: str, model_class: type[EcoTrackModel] | None, **kwargs: Any
    ) -> EcoTrackModel:
        model_uri = f"models:/{name}/{version}"
        # Download the artifact
        local_path = mlflow.artifacts.download_artifacts(model_uri)
        ckpt_path = Path(local_path)
        if ckpt_path.is_dir():
            ckpt_path = ckpt_path / "model.pt"
        if model_class is None:
            raise ValueError("model_class required to deserialise the checkpoint")
        return model_class.load_checkpoint(ckpt_path, **kwargs)

    def _load_local(
        self, name: str, version: str, model_class: type[EcoTrackModel] | None, **kwargs: Any
    ) -> EcoTrackModel:
        ckpt_path = self.local_root / name / version / "model.pt"
        if not ckpt_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {ckpt_path}")
        if model_class is None:
            raise ValueError("model_class required to deserialise the checkpoint")
        return model_class.load_checkpoint(ckpt_path, **kwargs)

    # ------------------------------------------------------------------
    # Stage promotion
    # ------------------------------------------------------------------

    def promote_model(
        self,
        name: str,
        version: str,
        stage: Literal["staging", "production", "archived"] = "staging",
    ) -> None:
        """Promote a model version to a lifecycle stage.

        Args:
            name: Model name.
            version: Version to promote.
            stage: Target stage.
        """
        if self._use_mlflow:
            self._client.transition_model_version_stage(name, version, stage)
            logger.info("Model promoted (MLflow)", name=name, version=version, stage=stage)
        else:
            meta_path = self.local_root / name / version / "metadata.json"
            if meta_path.exists():
                meta = json.loads(meta_path.read_text())
                meta["stage"] = stage
                meta["promoted_at"] = datetime.now(timezone.utc).isoformat()
                meta_path.write_text(json.dumps(meta, indent=2, default=str))
            logger.info("Model promoted (local)", name=name, version=version, stage=stage)

    # ------------------------------------------------------------------
    # Listing & comparison
    # ------------------------------------------------------------------

    def list_models(self, domain: str | None = None) -> list[dict[str, Any]]:
        """List registered models, optionally filtered by domain.

        Args:
            domain: If provided, only return models in this domain.

        Returns:
            List of metadata dictionaries.
        """
        if self._use_mlflow:
            return self._list_mlflow(domain)
        return self._list_local(domain)

    def _list_mlflow(self, domain: str | None) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for rm in self._client.search_registered_models():
            info = {"name": rm.name, "latest_versions": []}
            for mv in rm.latest_versions:
                info["latest_versions"].append({"version": mv.version, "stage": mv.current_stage})
            results.append(info)
        return results

    def _list_local(self, domain: str | None) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        if not self.local_root.exists():
            return results
        for model_dir in sorted(self.local_root.iterdir()):
            if not model_dir.is_dir():
                continue
            for version_dir in sorted(model_dir.iterdir()):
                meta_path = version_dir / "metadata.json"
                if meta_path.exists():
                    meta = json.loads(meta_path.read_text())
                    if domain and meta.get("domain") != domain:
                        continue
                    results.append(meta)
        return results

    def compare_models(
        self, name: str, versions: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Compare metrics across multiple versions of a model.

        Args:
            name: Model name.
            versions: List of version strings to compare.

        Returns:
            Mapping from version → metrics dict.
        """
        comparison: dict[str, dict[str, Any]] = {}
        for v in versions:
            meta_path = self.local_root / name / v / "metadata.json"
            if meta_path.exists():
                meta = json.loads(meta_path.read_text())
                comparison[v] = meta.get("metrics", {})
            else:
                comparison[v] = {}
        return comparison


__all__ = ["ModelRegistry"]
