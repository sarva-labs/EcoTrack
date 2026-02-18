"""Causal inference engine for estimating treatment effects.

Implements three estimators for the Average Treatment Effect (ATE):

- **IPTW** — Inverse Probability of Treatment Weighting
- **Matching** — Propensity-score nearest-neighbour matching
- **Regression** — Covariate-adjusted OLS regression

Also provides sensitivity analysis (Rosenbaum bounds) and
dose-response curve estimation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import structlog
from scipy import stats
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

logger = structlog.get_logger(__name__)


# ── Data Classes ─────────────────────────────────────────────────────


@dataclass
class TreatmentEffect:
    """Result of a causal effect estimation.

    Attributes:
        ate: Average Treatment Effect estimate.
        att: Average Treatment Effect on the Treated (may equal ``ate``
            for methods that do not distinguish).
        confidence_interval: ``(lower, upper)`` bounds at 95 %.
        p_value: Two-sided p-value for the null hypothesis ATE = 0.
        method: Name of the estimation method.
        metadata: Extra diagnostics (e.g. propensity-score stats).
    """

    ate: float
    att: float
    confidence_interval: tuple[float, float]
    p_value: float
    method: str
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Inference Engine ─────────────────────────────────────────────────


class CausalInference:
    """Causal inference engine for observational environmental data.

    Usage::

        ci = CausalInference()
        effect = ci.estimate_ate(
            data=df,
            treatment="deforestation",
            outcome="biodiversity_index",
            confounders=["temperature", "rainfall"],
            method="iptw",
        )
    """

    # ── Main Entry Point ─────────────────────────────────────────

    def estimate_ate(
        self,
        data: pd.DataFrame,
        treatment: str,
        outcome: str,
        confounders: list[str] | None = None,
        method: str = "iptw",
    ) -> TreatmentEffect:
        """Estimate the Average Treatment Effect.

        Args:
            data: Observational dataset.
            treatment: Binary treatment column name (0/1).
            outcome: Continuous outcome column name.
            confounders: List of confounding covariate column names.
            method: ``"iptw"``, ``"matching"``, or ``"regression"``.

        Returns:
            A :class:`TreatmentEffect` with the estimated ATE and diagnostics.

        Raises:
            ValueError: If method is unknown or data is invalid.
        """
        confounders = confounders or []
        required_cols = [treatment, outcome] + confounders
        missing = [c for c in required_cols if c not in data.columns]
        if missing:
            raise ValueError(f"Missing columns in data: {missing}")

        # Drop rows with NaN in relevant columns
        clean = data[required_cols].dropna()
        if len(clean) < 10:
            raise ValueError(
                f"Insufficient observations after dropping NaN ({len(clean)}). "
                f"Need at least 10."
            )

        treatment_values = clean[treatment].unique()
        if not set(treatment_values).issubset({0, 1, 0.0, 1.0}):
            raise ValueError(
                f"Treatment column '{treatment}' must be binary (0/1). "
                f"Found values: {sorted(treatment_values)}"
            )

        dispatch = {
            "iptw": self._iptw_estimator,
            "matching": self._matching_estimator,
            "regression": self._regression_estimator,
        }
        estimator = dispatch.get(method)
        if estimator is None:
            raise ValueError(
                f"Unknown method {method!r}. Choose from {list(dispatch)}."
            )
        return estimator(clean, treatment, outcome, confounders)

    # ── IPTW Estimator ───────────────────────────────────────────

    def _iptw_estimator(
        self,
        data: pd.DataFrame,
        treatment: str,
        outcome: str,
        confounders: list[str],
    ) -> TreatmentEffect:
        """Inverse Probability of Treatment Weighting (IPTW).

        1. Fit a logistic regression of treatment on confounders to
           obtain propensity scores.
        2. Compute inverse-probability weights.
        3. Estimate ATE as the weighted difference in means.

        Args:
            data: Cleaned DataFrame.
            treatment: Binary treatment column.
            outcome: Outcome column.
            confounders: Confounder columns.

        Returns:
            :class:`TreatmentEffect`.
        """
        t = data[treatment].values.astype(float)
        y = data[outcome].values.astype(float)

        if not confounders:
            # Without confounders, simple difference in means
            return self._simple_diff(y, t, method="iptw (no confounders)")

        X = data[confounders].values
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Propensity score model
        ps_model = LogisticRegression(max_iter=1000, solver="lbfgs")
        ps_model.fit(X_scaled, t)
        ps = ps_model.predict_proba(X_scaled)[:, 1]

        # Clip propensity scores to avoid extreme weights
        ps = np.clip(ps, 0.01, 0.99)

        # IPW weights
        w1 = t / ps  # treated
        w0 = (1 - t) / (1 - ps)  # control

        # Weighted means
        mean_treated = np.sum(w1 * y) / np.sum(w1)
        mean_control = np.sum(w0 * y) / np.sum(w0)
        ate = float(mean_treated - mean_control)

        # ATT
        att_weights = t + (1 - t) * ps / (1 - ps)
        mean_control_att = np.sum(att_weights * (1 - t) * y) / np.sum(att_weights * (1 - t))
        mean_treated_att = np.mean(y[t == 1])
        att = float(mean_treated_att - mean_control_att)

        # Bootstrap confidence interval
        ci, pval = self._bootstrap_ci(data, treatment, outcome, confounders, "iptw")

        return TreatmentEffect(
            ate=round(ate, 6),
            att=round(att, 6),
            confidence_interval=ci,
            p_value=round(pval, 6),
            method="iptw",
            metadata={
                "propensity_score_mean": round(float(np.mean(ps)), 4),
                "propensity_score_std": round(float(np.std(ps)), 4),
                "effective_sample_size_treated": round(float(np.sum(w1) ** 2 / np.sum(w1 ** 2)), 1),
                "effective_sample_size_control": round(float(np.sum(w0) ** 2 / np.sum(w0 ** 2)), 1),
            },
        )

    # ── Matching Estimator ───────────────────────────────────────

    def _matching_estimator(
        self,
        data: pd.DataFrame,
        treatment: str,
        outcome: str,
        confounders: list[str],
    ) -> TreatmentEffect:
        """Propensity-score nearest-neighbour matching estimator.

        1. Compute propensity scores.
        2. For each treated unit, find the nearest control on propensity.
        3. ATE = mean(Y_treated − Y_matched_control).

        Args:
            data: Cleaned DataFrame.
            treatment: Binary treatment column.
            outcome: Outcome column.
            confounders: Confounder columns.

        Returns:
            :class:`TreatmentEffect`.
        """
        t = data[treatment].values.astype(float)
        y = data[outcome].values.astype(float)

        if not confounders:
            return self._simple_diff(y, t, method="matching (no confounders)")

        X = data[confounders].values
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Propensity scores
        ps_model = LogisticRegression(max_iter=1000, solver="lbfgs")
        ps_model.fit(X_scaled, t)
        ps = ps_model.predict_proba(X_scaled)[:, 1].reshape(-1, 1)

        treated_idx = np.where(t == 1)[0]
        control_idx = np.where(t == 0)[0]

        if len(treated_idx) == 0 or len(control_idx) == 0:
            raise ValueError("Treatment must have both treated and control units.")

        # Nearest-neighbour matching on propensity score
        nn = NearestNeighbors(n_neighbors=1, metric="euclidean")
        nn.fit(ps[control_idx])
        distances, indices = nn.kneighbors(ps[treated_idx])
        matched_control_idx = control_idx[indices.flatten()]

        # Treatment effects
        te_per_unit = y[treated_idx] - y[matched_control_idx]
        att = float(np.mean(te_per_unit))
        ate = att  # For matching, ATT ≈ ATE when matching is symmetric

        # Also match controls to treated for symmetric ATE
        nn_t = NearestNeighbors(n_neighbors=1, metric="euclidean")
        nn_t.fit(ps[treated_idx])
        _, indices_t = nn_t.kneighbors(ps[control_idx])
        matched_treated_idx = treated_idx[indices_t.flatten()]
        te_control = y[matched_treated_idx] - y[control_idx]
        ate = float((np.sum(te_per_unit) + np.sum(te_control)) / len(data))

        # Standard error and CI
        se = float(np.std(te_per_unit, ddof=1) / np.sqrt(len(te_per_unit)))
        z = 1.96
        ci = (round(att - z * se, 6), round(att + z * se, 6))
        t_stat = att / se if se > 0 else 0.0
        pval = float(2 * (1 - stats.norm.cdf(abs(t_stat))))

        return TreatmentEffect(
            ate=round(ate, 6),
            att=round(att, 6),
            confidence_interval=ci,
            p_value=round(pval, 6),
            method="matching",
            metadata={
                "n_treated": int(len(treated_idx)),
                "n_control": int(len(control_idx)),
                "mean_match_distance": round(float(np.mean(distances)), 6),
                "max_match_distance": round(float(np.max(distances)), 6),
            },
        )

    # ── Regression Estimator ─────────────────────────────────────

    def _regression_estimator(
        self,
        data: pd.DataFrame,
        treatment: str,
        outcome: str,
        confounders: list[str],
    ) -> TreatmentEffect:
        """Covariate-adjusted OLS regression estimator.

        Fits ``Y ~ T + X`` and extracts the coefficient on *T*.

        Args:
            data: Cleaned DataFrame.
            treatment: Binary treatment column.
            outcome: Outcome column.
            confounders: Confounder columns.

        Returns:
            :class:`TreatmentEffect`.
        """
        t = data[treatment].values.astype(float)
        y = data[outcome].values.astype(float)

        if not confounders:
            return self._simple_diff(y, t, method="regression (no confounders)")

        X = data[confounders].values
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Design matrix: [treatment, confounders]
        design = np.column_stack([t, X_scaled])
        model = LinearRegression()
        model.fit(design, y)

        ate = float(model.coef_[0])
        att = ate  # OLS does not distinguish ATT/ATE

        # Standard errors via residual variance
        y_pred = model.predict(design)
        residuals = y - y_pred
        n = len(y)
        p = design.shape[1] + 1  # +1 for intercept
        mse = float(np.sum(residuals ** 2) / (n - p))
        try:
            xtx_inv = np.linalg.inv(design.T @ design)
            se_treatment = float(np.sqrt(mse * xtx_inv[0, 0]))
        except np.linalg.LinAlgError:
            se_treatment = float(np.std(residuals) / np.sqrt(n))

        z = 1.96
        ci = (round(ate - z * se_treatment, 6), round(ate + z * se_treatment, 6))
        t_stat = ate / se_treatment if se_treatment > 0 else 0.0
        pval = float(2 * (1 - stats.norm.cdf(abs(t_stat))))

        return TreatmentEffect(
            ate=round(ate, 6),
            att=round(att, 6),
            confidence_interval=ci,
            p_value=round(pval, 6),
            method="regression",
            metadata={
                "r_squared": round(float(model.score(design, y)), 4),
                "se_treatment": round(se_treatment, 6),
                "n_observations": n,
            },
        )

    # ── Sensitivity Analysis ─────────────────────────────────────

    def sensitivity_analysis(
        self,
        data: pd.DataFrame,
        treatment: str,
        outcome: str,
        confounders: list[str],
        gamma_range: tuple[float, float] = (1.0, 3.0),
        n_steps: int = 10,
    ) -> dict[str, Any]:
        """Rosenbaum bounds sensitivity analysis.

        Evaluates how robust the estimated treatment effect is to
        hidden bias by computing upper/lower p-value bounds across
        a range of Γ (odds-ratio of differential treatment assignment
        due to an unobserved confounder).

        Args:
            data: Observational dataset.
            treatment: Binary treatment column.
            outcome: Outcome column.
            confounders: Confounder columns.
            gamma_range: ``(min_gamma, max_gamma)`` range to evaluate.
            n_steps: Number of Γ values to test.

        Returns:
            Dictionary with ``gamma_values``, ``upper_p_values``,
            ``lower_p_values``, and ``critical_gamma``.
        """
        clean = data[[treatment, outcome] + confounders].dropna()
        t = clean[treatment].values.astype(float)
        y = clean[outcome].values.astype(float)

        treated_idx = np.where(t == 1)[0]
        control_idx = np.where(t == 0)[0]

        if len(treated_idx) == 0 or len(control_idx) == 0:
            return {"error": "Need both treated and control units."}

        # Observed test statistic (Wilcoxon rank-sum)
        _, obs_pval = stats.ranksums(y[treated_idx], y[control_idx])
        obs_stat = float(np.mean(y[treated_idx]) - np.mean(y[control_idx]))

        gammas = np.linspace(gamma_range[0], gamma_range[1], n_steps)
        upper_pvals: list[float] = []
        lower_pvals: list[float] = []

        n_t = len(treated_idx)
        n_c = len(control_idx)
        se = float(np.sqrt(
            np.var(y[treated_idx], ddof=1) / n_t
            + np.var(y[control_idx], ddof=1) / n_c
        ))

        for gamma in gammas:
            # Adjusted bounds on the test statistic
            bias = np.log(gamma) * se
            upper_stat = obs_stat + bias
            lower_stat = obs_stat - bias

            upper_z = upper_stat / se if se > 0 else 0
            lower_z = lower_stat / se if se > 0 else 0

            upper_pvals.append(round(float(2 * (1 - stats.norm.cdf(abs(upper_z)))), 6))
            lower_pvals.append(round(float(2 * (1 - stats.norm.cdf(abs(lower_z)))), 6))

        # Find critical gamma (where upper p-value first exceeds 0.05)
        critical_gamma = float(gamma_range[1])
        for g, p in zip(gammas, upper_pvals):
            if p > 0.05:
                critical_gamma = round(float(g), 3)
                break

        return {
            "gamma_values": [round(float(g), 3) for g in gammas],
            "upper_p_values": upper_pvals,
            "lower_p_values": lower_pvals,
            "critical_gamma": critical_gamma,
            "interpretation": (
                f"The result is robust to hidden bias up to Γ = {critical_gamma}. "
                f"An unobserved confounder would need to change the odds of treatment "
                f"by a factor of {critical_gamma} to invalidate the finding."
            ),
        }

    # ── Dose-Response Estimation ─────────────────────────────────

    def estimate_dose_response(
        self,
        data: pd.DataFrame,
        treatment: str,
        outcome: str,
        confounders: list[str] | None = None,
        n_bins: int = 10,
    ) -> dict[str, Any]:
        """Estimate a dose-response curve.

        Bins the continuous treatment into quantiles and estimates the
        confounder-adjusted mean outcome within each bin.

        Args:
            data: Observational dataset.
            treatment: Continuous treatment column.
            outcome: Outcome column.
            confounders: Confounder columns for regression adjustment.
            n_bins: Number of treatment bins.

        Returns:
            Dictionary with ``dose_levels``, ``response_means``,
            ``response_ci_lower``, ``response_ci_upper``, and ``n_per_bin``.
        """
        confounders = confounders or []
        required = [treatment, outcome] + confounders
        clean = data[required].dropna()

        if len(clean) < n_bins * 2:
            n_bins = max(2, len(clean) // 5)
            logger.warning("dose_response_reduced_bins", n_bins=n_bins)

        # Create quantile bins
        clean = clean.copy()
        clean["_bin"] = pd.qcut(clean[treatment], q=n_bins, duplicates="drop")
        bins = clean.groupby("_bin", observed=True)

        dose_levels: list[float] = []
        response_means: list[float] = []
        response_lower: list[float] = []
        response_upper: list[float] = []
        counts: list[int] = []

        for bin_label, group in bins:
            dose_levels.append(round(float(group[treatment].mean()), 4))
            counts.append(len(group))

            if confounders and len(group) > len(confounders) + 1:
                # Adjusted mean via regression
                X = group[confounders].values
                y = group[outcome].values
                X_with_intercept = np.column_stack([np.ones(len(y)), X])
                try:
                    beta = np.linalg.lstsq(X_with_intercept, y, rcond=None)[0]
                    y_adj = y - X_with_intercept @ beta + beta[0]
                    mean_adj = float(np.mean(y_adj))
                    se = float(np.std(y_adj, ddof=1) / np.sqrt(len(y_adj)))
                except np.linalg.LinAlgError:
                    mean_adj = float(group[outcome].mean())
                    se = float(group[outcome].std() / np.sqrt(len(group)))
            else:
                mean_adj = float(group[outcome].mean())
                se = float(group[outcome].std() / np.sqrt(len(group))) if len(group) > 1 else 0.0

            response_means.append(round(mean_adj, 6))
            response_lower.append(round(mean_adj - 1.96 * se, 6))
            response_upper.append(round(mean_adj + 1.96 * se, 6))

        return {
            "dose_levels": dose_levels,
            "response_means": response_means,
            "response_ci_lower": response_lower,
            "response_ci_upper": response_upper,
            "n_per_bin": counts,
            "n_bins": len(dose_levels),
        }

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _simple_diff(
        y: np.ndarray,
        t: np.ndarray,
        method: str,
    ) -> TreatmentEffect:
        """Naïve difference in means (no confounder adjustment).

        Args:
            y: Outcome values.
            t: Treatment indicators (0/1).
            method: Label for the method.

        Returns:
            :class:`TreatmentEffect`.
        """
        treated = y[t == 1]
        control = y[t == 0]
        if len(treated) == 0 or len(control) == 0:
            raise ValueError("Need both treated and control observations.")
        ate = float(np.mean(treated) - np.mean(control))
        se = float(np.sqrt(np.var(treated, ddof=1) / len(treated)
                           + np.var(control, ddof=1) / len(control)))
        z = 1.96
        ci = (round(ate - z * se, 6), round(ate + z * se, 6))
        t_stat = ate / se if se > 0 else 0.0
        pval = float(2 * (1 - stats.norm.cdf(abs(t_stat))))
        return TreatmentEffect(
            ate=round(ate, 6),
            att=round(ate, 6),
            confidence_interval=ci,
            p_value=round(pval, 6),
            method=method,
        )

    def _bootstrap_ci(
        self,
        data: pd.DataFrame,
        treatment: str,
        outcome: str,
        confounders: list[str],
        method: str,
        n_boot: int = 200,
        alpha: float = 0.05,
    ) -> tuple[tuple[float, float], float]:
        """Bootstrap confidence interval and p-value.

        Args:
            data: Cleaned data.
            treatment: Treatment column.
            outcome: Outcome column.
            confounders: Confounder columns.
            method: Estimation method.
            n_boot: Number of bootstrap replications.
            alpha: Significance level.

        Returns:
            ``(ci_tuple, p_value)``.
        """
        boot_ates: list[float] = []
        n = len(data)
        for _ in range(n_boot):
            boot_idx = np.random.choice(n, size=n, replace=True)
            boot_data = data.iloc[boot_idx].reset_index(drop=True)
            try:
                if method == "iptw":
                    result = self._iptw_estimator(boot_data, treatment, outcome, confounders)
                elif method == "matching":
                    result = self._matching_estimator(boot_data, treatment, outcome, confounders)
                else:
                    result = self._regression_estimator(boot_data, treatment, outcome, confounders)
                boot_ates.append(result.ate)
            except (ValueError, np.linalg.LinAlgError):
                continue

        if len(boot_ates) < 10:
            return ((-np.inf, np.inf), 1.0)

        boot_arr = np.array(boot_ates)
        lower = float(np.percentile(boot_arr, 100 * alpha / 2))
        upper = float(np.percentile(boot_arr, 100 * (1 - alpha / 2)))
        # P-value: fraction of bootstrap samples crossing zero
        pval = float(np.mean(boot_arr * boot_arr[0] < 0)) * 2
        pval = min(pval, 1.0)
        return ((round(lower, 6), round(upper, 6)), round(pval, 6))


__all__ = ["TreatmentEffect", "CausalInference"]
