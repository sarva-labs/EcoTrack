"""Tests for ML evaluation metrics."""
from __future__ import annotations

import numpy as np
import pytest

from ecotrack_ml.evaluation.metrics import RegressionMetrics, ClassificationMetrics, ForecastMetrics


class TestRegressionMetrics:
    def test_rmse(self) -> None:
        y_true = np.array([1.0, 2.0, 3.0, 4.0])
        y_pred = np.array([1.1, 2.2, 2.8, 4.1])
        metrics = RegressionMetrics(y_true, y_pred)
        rmse = metrics.rmse()
        assert 0 < rmse < 0.3

    def test_mae(self) -> None:
        y_true = np.array([1.0, 2.0, 3.0])
        y_pred = np.array([1.0, 2.0, 3.0])
        metrics = RegressionMetrics(y_true, y_pred)
        mae = metrics.mae()
        assert mae == 0.0

    def test_r_squared_perfect(self) -> None:
        y_true = np.array([1.0, 2.0, 3.0])
        y_pred = np.array([1.0, 2.0, 3.0])
        metrics = RegressionMetrics(y_true, y_pred)
        r2 = metrics.r_squared()
        assert r2 == pytest.approx(1.0)

    def test_r_squared_poor(self) -> None:
        y_true = np.array([1.0, 2.0, 3.0])
        y_pred = np.array([3.0, 1.0, 2.0])
        metrics = RegressionMetrics(y_true, y_pred)
        r2 = metrics.r_squared()
        assert r2 < 0.5


class TestClassificationMetrics:
    def test_accuracy(self) -> None:
        y_true = np.array([0, 1, 1, 0, 1])
        y_pred = np.array([0, 1, 1, 0, 0])
        metrics = ClassificationMetrics(y_true, y_pred)
        acc = metrics.accuracy()
        assert acc == pytest.approx(0.8)

    def test_perfect_classification(self) -> None:
        y_true = np.array([0, 1, 0, 1])
        y_pred = np.array([0, 1, 0, 1])
        metrics = ClassificationMetrics(y_true, y_pred)
        assert metrics.accuracy() == 1.0


class TestForecastMetrics:
    def test_crps_with_std(self) -> None:
        y_true = np.array([1.0, 2.0, 3.0])
        y_pred_mean = np.array([1.1, 2.0, 2.9])
        y_pred_std = np.array([0.5, 0.5, 0.5])
        metrics = ForecastMetrics(y_true, y_pred_mean, y_pred_std)
        crps = metrics.crps()
        assert isinstance(crps, float)

    def test_coverage(self) -> None:
        y_true = np.array([1.0, 2.0, 3.0])
        y_pred_mean = np.array([1.0, 2.0, 3.0])
        y_pred_std = np.array([1.0, 1.0, 1.0])
        metrics = ForecastMetrics(y_true, y_pred_mean, y_pred_std)
        coverage = metrics.coverage(alpha=0.05)
        assert coverage == pytest.approx(1.0)

    def test_skill_score_no_reference(self) -> None:
        y_true = np.array([1.0, 2.0, 3.0])
        y_pred_mean = np.array([1.0, 2.0, 3.0])
        metrics = ForecastMetrics(y_true, y_pred_mean)
        assert metrics.skill_score() == 0.0
