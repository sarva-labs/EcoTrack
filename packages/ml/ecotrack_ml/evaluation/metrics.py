"""Evaluation metrics for EcoTrack models.

Provides domain-specific metric classes for regression, classification,
segmentation, and forecasting tasks.  All implementations use NumPy and
handle common edge cases (empty arrays, single-class predictions, etc.).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_numpy(a: Any) -> np.ndarray:
    """Coerce input to a float64 NumPy array."""
    if hasattr(a, "cpu"):  # torch.Tensor
        a = a.detach().cpu().numpy()
    return np.asarray(a, dtype=np.float64)


def _safe_divide(num: float, den: float, default: float = 0.0) -> float:
    """Division that returns *default* on zero denominator."""
    return num / den if den != 0 else default


# ---------------------------------------------------------------------------
# Regression
# ---------------------------------------------------------------------------


class RegressionMetrics:
    """Regression evaluation metrics.

    Args:
        y_true: Ground truth values.
        y_pred: Predicted values.
    """

    def __init__(self, y_true: Any, y_pred: Any) -> None:
        self.y_true = _to_numpy(y_true).ravel()
        self.y_pred = _to_numpy(y_pred).ravel()
        if self.y_true.shape != self.y_pred.shape:
            raise ValueError(
                f"Shape mismatch: y_true {self.y_true.shape} vs y_pred {self.y_pred.shape}"
            )

    def rmse(self) -> float:
        """Root Mean Squared Error."""
        if len(self.y_true) == 0:
            return 0.0
        return float(np.sqrt(np.mean((self.y_true - self.y_pred) ** 2)))

    def mae(self) -> float:
        """Mean Absolute Error."""
        if len(self.y_true) == 0:
            return 0.0
        return float(np.mean(np.abs(self.y_true - self.y_pred)))

    def r_squared(self) -> float:
        """Coefficient of determination (R²).

        Returns 0.0 when the total variance of *y_true* is zero.
        """
        if len(self.y_true) == 0:
            return 0.0
        ss_res = np.sum((self.y_true - self.y_pred) ** 2)
        ss_tot = np.sum((self.y_true - np.mean(self.y_true)) ** 2)
        return float(_safe_divide(1.0 - ss_res, 1.0) if ss_tot == 0 else 1.0 - ss_res / ss_tot)

    def mape(self) -> float:
        """Mean Absolute Percentage Error.

        Ignores samples where ``y_true == 0`` to avoid division by zero.
        """
        if len(self.y_true) == 0:
            return 0.0
        mask = self.y_true != 0
        if not np.any(mask):
            return 0.0
        return float(np.mean(np.abs((self.y_true[mask] - self.y_pred[mask]) / self.y_true[mask])) * 100)

    def bias(self) -> float:
        """Mean bias (mean of prediction − truth)."""
        if len(self.y_true) == 0:
            return 0.0
        return float(np.mean(self.y_pred - self.y_true))

    def compute_all(self) -> dict[str, float]:
        """Compute all regression metrics at once."""
        return {
            "rmse": self.rmse(),
            "mae": self.mae(),
            "r_squared": self.r_squared(),
            "mape": self.mape(),
            "bias": self.bias(),
        }


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


class ClassificationMetrics:
    """Classification evaluation metrics.

    Supports both binary and multi-class classification.  For multi-class
    metrics, macro-averaging is used.

    Args:
        y_true: Ground truth class indices.
        y_pred: Predicted class indices.
        n_classes: Number of classes (inferred if ``None``).
    """

    def __init__(
        self, y_true: Any, y_pred: Any, n_classes: int | None = None
    ) -> None:
        self.y_true = _to_numpy(y_true).ravel().astype(int)
        self.y_pred = _to_numpy(y_pred).ravel().astype(int)
        if self.y_true.shape != self.y_pred.shape:
            raise ValueError("Shape mismatch between y_true and y_pred.")
        self.n_classes = n_classes or int(max(self.y_true.max(), self.y_pred.max()) + 1) if len(self.y_true) > 0 else 0

    def accuracy(self) -> float:
        """Overall accuracy."""
        if len(self.y_true) == 0:
            return 0.0
        return float(np.mean(self.y_true == self.y_pred))

    def precision(self) -> float:
        """Macro-averaged precision."""
        if len(self.y_true) == 0 or self.n_classes == 0:
            return 0.0
        precisions: list[float] = []
        for c in range(self.n_classes):
            tp = np.sum((self.y_pred == c) & (self.y_true == c))
            fp = np.sum((self.y_pred == c) & (self.y_true != c))
            precisions.append(_safe_divide(float(tp), float(tp + fp)))
        return float(np.mean(precisions))

    def recall(self) -> float:
        """Macro-averaged recall."""
        if len(self.y_true) == 0 or self.n_classes == 0:
            return 0.0
        recalls: list[float] = []
        for c in range(self.n_classes):
            tp = np.sum((self.y_pred == c) & (self.y_true == c))
            fn = np.sum((self.y_pred != c) & (self.y_true == c))
            recalls.append(_safe_divide(float(tp), float(tp + fn)))
        return float(np.mean(recalls))

    def f1_score(self) -> float:
        """Macro-averaged F1 score."""
        p = self.precision()
        r = self.recall()
        return float(_safe_divide(2 * p * r, p + r))

    def confusion_matrix(self) -> np.ndarray:
        """Compute the confusion matrix.

        Returns:
            Array of shape ``(n_classes, n_classes)`` where entry ``[i, j]``
            is the count of true-class *i* predicted as class *j*.
        """
        n = max(self.n_classes, 1)
        cm = np.zeros((n, n), dtype=np.int64)
        for t, p in zip(self.y_true, self.y_pred):
            if 0 <= t < n and 0 <= p < n:
                cm[t, p] += 1
        return cm

    def compute_all(self) -> dict[str, Any]:
        """Compute all classification metrics at once."""
        return {
            "accuracy": self.accuracy(),
            "precision": self.precision(),
            "recall": self.recall(),
            "f1_score": self.f1_score(),
            "confusion_matrix": self.confusion_matrix(),
        }


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------


class SegmentationMetrics:
    """Semantic segmentation evaluation metrics.

    Args:
        y_true: Ground truth masks of shape ``(N, H, W)`` or ``(H, W)``.
        y_pred: Predicted masks of the same shape.
        n_classes: Number of classes.
    """

    def __init__(
        self, y_true: Any, y_pred: Any, n_classes: int = 10
    ) -> None:
        self.y_true = _to_numpy(y_true).astype(int)
        self.y_pred = _to_numpy(y_pred).astype(int)
        self.n_classes = n_classes

    def iou(self, class_id: int) -> float:
        """Intersection over Union for a single class.

        Returns 0.0 when the class is absent from both ground truth and
        prediction (union == 0).
        """
        pred_mask = self.y_pred == class_id
        true_mask = self.y_true == class_id
        intersection = float(np.sum(pred_mask & true_mask))
        union = float(np.sum(pred_mask | true_mask))
        return _safe_divide(intersection, union)

    def dice(self, class_id: int) -> float:
        """Dice coefficient (F1 for segmentation) for a single class."""
        pred_mask = self.y_pred == class_id
        true_mask = self.y_true == class_id
        intersection = float(np.sum(pred_mask & true_mask))
        total = float(np.sum(pred_mask) + np.sum(true_mask))
        return _safe_divide(2.0 * intersection, total)

    def pixel_accuracy(self) -> float:
        """Overall pixel-level accuracy."""
        total = self.y_true.size
        if total == 0:
            return 0.0
        return float(np.sum(self.y_true == self.y_pred) / total)

    def mean_iou(self) -> float:
        """Mean IoU across all classes."""
        ious = [self.iou(c) for c in range(self.n_classes)]
        return float(np.mean(ious))

    def compute_all(self) -> dict[str, Any]:
        """Compute all segmentation metrics at once."""
        per_class_iou = {f"iou_class_{c}": self.iou(c) for c in range(self.n_classes)}
        per_class_dice = {f"dice_class_{c}": self.dice(c) for c in range(self.n_classes)}
        return {
            "pixel_accuracy": self.pixel_accuracy(),
            "mean_iou": self.mean_iou(),
            **per_class_iou,
            **per_class_dice,
        }


# ---------------------------------------------------------------------------
# Forecasting
# ---------------------------------------------------------------------------


class ForecastMetrics:
    """Probabilistic forecasting evaluation metrics.

    Args:
        y_true: Ground truth values.
        y_pred_mean: Mean (point) forecast.
        y_pred_std: Standard deviation of the forecast distribution.
            Required for CRPS, coverage, and sharpness.
        reference_mse: MSE of a reference (e.g. climatological) forecast
            for skill score computation.
    """

    def __init__(
        self,
        y_true: Any,
        y_pred_mean: Any,
        y_pred_std: Any | None = None,
        reference_mse: float | None = None,
    ) -> None:
        self.y_true = _to_numpy(y_true).ravel()
        self.y_pred_mean = _to_numpy(y_pred_mean).ravel()
        self.y_pred_std = _to_numpy(y_pred_std).ravel() if y_pred_std is not None else None
        self.reference_mse = reference_mse

    def crps(self) -> float:
        """Continuous Ranked Probability Score (Gaussian approximation).

        Uses the closed-form CRPS for a Gaussian predictive distribution.

        Returns 0.0 when std is not provided.
        """
        if self.y_pred_std is None or len(self.y_true) == 0:
            return 0.0

        std = np.maximum(self.y_pred_std, 1e-8)
        z = (self.y_true - self.y_pred_mean) / std

        # Standard normal PDF and CDF
        pdf = np.exp(-0.5 * z ** 2) / np.sqrt(2 * np.pi)
        cdf = 0.5 * (1 + _erf_approx(z / np.sqrt(2)))

        crps_vals = std * (z * (2 * cdf - 1) + 2 * pdf - 1 / np.sqrt(np.pi))
        return float(np.mean(crps_vals))

    def coverage(self, alpha: float = 0.05) -> float:
        """Prediction interval coverage probability.

        Computes the fraction of true values falling within the
        ``(1 - alpha)`` prediction interval.

        Args:
            alpha: Significance level (default 5 % → 95 % interval).
        """
        if self.y_pred_std is None or len(self.y_true) == 0:
            return 0.0
        z_alpha = _norm_ppf(1 - alpha / 2)
        lower = self.y_pred_mean - z_alpha * self.y_pred_std
        upper = self.y_pred_mean + z_alpha * self.y_pred_std
        return float(np.mean((self.y_true >= lower) & (self.y_true <= upper)))

    def sharpness(self) -> float:
        """Sharpness: mean width of the 95 % prediction interval.

        Smaller is better (given adequate coverage).
        """
        if self.y_pred_std is None or len(self.y_true) == 0:
            return 0.0
        z_95 = _norm_ppf(0.975)
        widths = 2 * z_95 * self.y_pred_std
        return float(np.mean(widths))

    def skill_score(self) -> float:
        """Skill score relative to a reference forecast.

        .. math::

            SS = 1 - \\frac{\\text{MSE}_{\\text{model}}}{\\text{MSE}_{\\text{ref}}}

        Returns 0.0 when no reference MSE is provided.
        """
        if self.reference_mse is None or self.reference_mse == 0 or len(self.y_true) == 0:
            return 0.0
        model_mse = float(np.mean((self.y_true - self.y_pred_mean) ** 2))
        return float(1.0 - model_mse / self.reference_mse)

    def compute_all(self) -> dict[str, float]:
        """Compute all forecasting metrics at once."""
        return {
            "crps": self.crps(),
            "coverage_95": self.coverage(alpha=0.05),
            "sharpness": self.sharpness(),
            "skill_score": self.skill_score(),
        }


# ---------------------------------------------------------------------------
# Pure-numpy approximations for normal PDF / CDF / PPF
# ---------------------------------------------------------------------------

def _erf_approx(x: np.ndarray) -> np.ndarray:
    """Approximation of the error function (Abramowitz & Stegun 7.1.26)."""
    sign = np.sign(x)
    x = np.abs(x)
    t = 1.0 / (1.0 + 0.3275911 * x)
    y = 1.0 - (
        ((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592
    ) * t * np.exp(-x * x)
    return sign * y


def _norm_ppf(p: float) -> float:
    """Approximate inverse of the standard normal CDF (Rational approx)."""
    # Beasley-Springer-Moro algorithm (simplified)
    if p <= 0:
        return -6.0
    if p >= 1:
        return 6.0
    if p == 0.5:
        return 0.0

    if p < 0.5:
        t = np.sqrt(-2.0 * np.log(p))
    else:
        t = np.sqrt(-2.0 * np.log(1.0 - p))

    # Rational approximation coefficients
    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308

    result = t - (c0 + c1 * t + c2 * t * t) / (1.0 + d1 * t + d2 * t * t + d3 * t * t * t)
    return float(result if p >= 0.5 else -result)


__all__ = [
    "ClassificationMetrics",
    "ForecastMetrics",
    "RegressionMetrics",
    "SegmentationMetrics",
]
