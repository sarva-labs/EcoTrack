"""Model inference engine with ONNX Runtime support.

Provides :class:`InferenceEngine`, a thread-safe inference backend that
supports both native PyTorch and ONNX Runtime execution.
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, Literal

import numpy as np
import torch
import torch.nn as nn

from ecotrack_ml.models.base import EcoTrackModel, PredictionResult

try:
    import structlog

    logger = structlog.get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)  # type: ignore[assignment]


class InferenceEngine:
    """Unified inference engine with PyTorch and ONNX Runtime backends.

    Features:

    * Automatic device management (CPU / CUDA detection).
    * Automatic batching for large inputs.
    * Thread-safe prediction via a reentrant lock.
    * Warm-up inference to JIT-compile / optimise kernels.
    * MC Dropout–based uncertainty estimation.

    Args:
        device: Torch device.  ``None`` → auto-detect.
    """

    def __init__(self, device: torch.device | None = None) -> None:
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._model: nn.Module | None = None
        self._ort_session: Any = None
        self._backend: Literal["pytorch", "onnx"] = "pytorch"
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_model(
        self,
        path: str | Path,
        backend: Literal["pytorch", "onnx"] = "pytorch",
        model_class: type[EcoTrackModel] | None = None,
        **kwargs: Any,
    ) -> None:
        """Load a model from a file.

        Args:
            path: Path to a ``.pt`` checkpoint or ``.onnx`` file.
            backend: ``"pytorch"`` or ``"onnx"``.
            model_class: Required for PyTorch backend; the concrete
                :class:`EcoTrackModel` subclass to instantiate.
            **kwargs: Forwarded to the model constructor (PyTorch only).
        """
        path = Path(path)
        self._backend = backend

        if backend == "onnx":
            self._load_onnx(path)
        else:
            self._load_pytorch(path, model_class, **kwargs)

        self._warmup()
        logger.info("Model loaded", backend=backend, path=str(path))

    def _load_pytorch(
        self, path: Path, model_class: type[EcoTrackModel] | None, **kwargs: Any
    ) -> None:
        if model_class is None:
            raise ValueError("model_class is required for PyTorch backend")
        model = model_class.load_checkpoint(path, **kwargs)
        model = model.to(self.device).eval()
        self._model = model

    def _load_onnx(self, path: Path) -> None:
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise ImportError(
                "Install onnxruntime for ONNX inference: pip install onnxruntime>=1.17"
            ) from exc

        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        self._ort_session = ort.InferenceSession(str(path), providers=providers)

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(
        self,
        inputs: np.ndarray | torch.Tensor,
        batch_size: int = 64,
    ) -> PredictionResult:
        """Run inference on *inputs*.

        Large inputs are automatically split into mini-batches.

        Args:
            inputs: Input data as a NumPy array or Torch tensor.
            batch_size: Maximum batch size.

        Returns:
            :class:`PredictionResult`.
        """
        with self._lock:
            if self._backend == "onnx":
                return self._predict_onnx(inputs, batch_size)
            return self._predict_pytorch(inputs, batch_size)

    def predict_with_uncertainty(
        self,
        inputs: np.ndarray | torch.Tensor,
        n_samples: int = 10,
        batch_size: int = 64,
    ) -> PredictionResult:
        """Run inference with MC Dropout uncertainty.

        Performs *n_samples* stochastic forward passes and returns the
        mean prediction with per-sample standard deviation as
        uncertainty.

        Args:
            inputs: Input data.
            n_samples: Number of stochastic forward passes.
            batch_size: Maximum batch size.

        Returns:
            :class:`PredictionResult` with ``uncertainty`` populated.
        """
        if self._backend == "onnx":
            logger.warning("Uncertainty not supported with ONNX backend; returning point prediction.")
            return self.predict(inputs, batch_size)

        with self._lock:
            return self._mc_dropout_predict(inputs, n_samples, batch_size)

    # ------------------------------------------------------------------
    # Private: PyTorch
    # ------------------------------------------------------------------

    def _predict_pytorch(
        self, inputs: np.ndarray | torch.Tensor, batch_size: int
    ) -> PredictionResult:
        assert self._model is not None, "No model loaded"
        self._model.eval()

        tensor = self._to_tensor(inputs)
        all_outputs: list[np.ndarray] = []
        start = time.perf_counter()

        for batch in self._batchify(tensor, batch_size):
            with torch.no_grad():
                out = self._model(batch.to(self.device))
            all_outputs.append(out.cpu().numpy())

        elapsed = (time.perf_counter() - start) * 1000
        return PredictionResult(
            predictions=np.concatenate(all_outputs, axis=0),
            inference_time_ms=elapsed,
        )

    def _mc_dropout_predict(
        self,
        inputs: np.ndarray | torch.Tensor,
        n_samples: int,
        batch_size: int,
    ) -> PredictionResult:
        assert self._model is not None, "No model loaded"

        # Enable dropout layers
        for m in self._model.modules():
            if isinstance(m, (nn.Dropout, nn.Dropout2d, nn.Dropout3d)):
                m.train()

        tensor = self._to_tensor(inputs)
        all_samples: list[np.ndarray] = []
        start = time.perf_counter()

        for _ in range(n_samples):
            batch_outputs: list[np.ndarray] = []
            for batch in self._batchify(tensor, batch_size):
                with torch.no_grad():
                    out = self._model(batch.to(self.device))
                batch_outputs.append(out.cpu().numpy())
            all_samples.append(np.concatenate(batch_outputs, axis=0))

        self._model.eval()  # restore
        elapsed = (time.perf_counter() - start) * 1000

        stacked = np.stack(all_samples, axis=0)  # (n_samples, N, ...)
        mean = np.mean(stacked, axis=0)
        std = np.std(stacked, axis=0)

        return PredictionResult(
            predictions=mean,
            uncertainty=std,
            inference_time_ms=elapsed,
            metadata={"n_mc_samples": n_samples},
        )

    # ------------------------------------------------------------------
    # Private: ONNX
    # ------------------------------------------------------------------

    def _predict_onnx(
        self, inputs: np.ndarray | torch.Tensor, batch_size: int
    ) -> PredictionResult:
        assert self._ort_session is not None, "No ONNX session loaded"

        if isinstance(inputs, torch.Tensor):
            inputs = inputs.cpu().numpy()
        inputs = np.asarray(inputs, dtype=np.float32)

        input_name = self._ort_session.get_inputs()[0].name
        all_outputs: list[np.ndarray] = []
        start = time.perf_counter()

        for i in range(0, len(inputs), batch_size):
            batch = inputs[i : i + batch_size]
            result = self._ort_session.run(None, {input_name: batch})
            all_outputs.append(result[0])

        elapsed = (time.perf_counter() - start) * 1000
        return PredictionResult(
            predictions=np.concatenate(all_outputs, axis=0),
            inference_time_ms=elapsed,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _to_tensor(self, inputs: np.ndarray | torch.Tensor) -> torch.Tensor:
        if isinstance(inputs, np.ndarray):
            return torch.from_numpy(inputs).float()
        return inputs.float()

    @staticmethod
    def _batchify(tensor: torch.Tensor, batch_size: int):
        """Yield mini-batches from *tensor*."""
        for i in range(0, len(tensor), batch_size):
            yield tensor[i : i + batch_size]

    def _warmup(self) -> None:
        """Run a single warm-up pass to JIT-compile kernels."""
        try:
            if self._backend == "pytorch" and self._model is not None:
                dummy = torch.randn(1, *self._guess_input_shape(), device=self.device)
                with torch.no_grad():
                    self._model(dummy)
            elif self._ort_session is not None:
                inp = self._ort_session.get_inputs()[0]
                shape = [d if isinstance(d, int) else 1 for d in inp.shape]
                dummy = np.random.randn(*shape).astype(np.float32)
                self._ort_session.run(None, {inp.name: dummy})
        except Exception:
            logger.debug("Warm-up failed (non-critical)", exc_info=True)

    def _guess_input_shape(self) -> tuple[int, ...]:
        """Best-effort guess at model input shape from metadata."""
        if self._model is not None and hasattr(self._model, "metadata"):
            meta = getattr(self._model, "metadata", None)
            if meta and meta.input_shape:
                return meta.input_shape
        return (1,)


__all__ = ["InferenceEngine"]
