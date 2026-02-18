"""Counterfactual analysis for environmental policy evaluation.

Provides tools for asking *what-if* questions about environmental
interventions, computing counterfactual outcomes under hypothetical
scenarios, evaluating policies at different levels, and attributing
observed outcomes to contributing factors.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import structlog
from scipy import stats
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler

from .discovery import CausalEdge, CausalGraph

logger = structlog.get_logger(__name__)


# ── Data Classes ─────────────────────────────────────────────────────


@dataclass
class CounterfactualScenario:
    """A hypothetical intervention scenario.

    Attributes:
        name: Short label for the scenario.
        description: Human-readable description.
        interventions: Mapping of variable name → new value to impose.
        constraints: Optional variable constraints (e.g. bounds).
    """

    name: str
    description: str
    interventions: dict[str, float]
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass
class CounterfactualResult:
    """Result of a counterfactual computation.

    Attributes:
        scenario: The evaluated scenario.
        factual_outcome: Observed outcome under the real data.
        counterfactual_outcome: Predicted outcome under the intervention.
        treatment_effect: Difference (counterfactual − factual).
        confidence_interval: 95 % CI for the treatment effect.
        metadata: Additional diagnostics.
    """

    scenario: CounterfactualScenario
    factual_outcome: float
    counterfactual_outcome: float
    treatment_effect: float
    confidence_interval: tuple[float, float]
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Counterfactual Analyzer ──────────────────────────────────────────


class CounterfactualAnalyzer:
    """Counterfactual and what-if analysis engine.

    Uses the discovered :class:`CausalGraph` to propagate hypothetical
    interventions through the causal structure and predict downstream
    outcomes.

    Usage::

        analyzer = CounterfactualAnalyzer(causal_graph)
        scenario = CounterfactualScenario(
            name="reduce_co2",
            description="50 % CO₂ reduction",
            interventions={"co2": 200.0},
        )
        result = analyzer.compute_counterfactual(data, scenario, "temperature")
    """

    def __init__(self, causal_graph: CausalGraph) -> None:
        self._graph = causal_graph
        self._structural_models: dict[str, LinearRegression] = {}
        self._scalers: dict[str, StandardScaler] = {}
        self._fitted = False

    # ── Internal: Fit Structural Equations ────────────────────────

    def _fit_structural_models(self, data: pd.DataFrame) -> None:
        """Fit a linear structural equation for each variable that has
        at least one incoming causal edge.

        Args:
            data: Observational dataset.
        """
        for variable in self._graph.variables:
            parents = [e.cause for e in self._graph.get_causes(variable)]
            if not parents:
                continue
            available = [p for p in parents if p in data.columns]
            if not available:
                continue
            clean = data[[variable] + available].dropna()
            if len(clean) < len(available) + 2:
                continue

            X = clean[available].values
            y = clean[variable].values

            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            model = LinearRegression()
            model.fit(X_scaled, y)

            self._structural_models[variable] = model
            self._scalers[variable] = scaler
            logger.debug(
                "structural_model_fitted",
                variable=variable,
                parents=available,
                r2=round(float(model.score(X_scaled, y)), 4),
            )
        self._fitted = True

    def _ensure_fitted(self, data: pd.DataFrame) -> None:
        """Fit structural models lazily if not already done."""
        if not self._fitted:
            self._fit_structural_models(data)

    # ── Counterfactual Computation ────────────────────────────────

    def compute_counterfactual(
        self,
        data: pd.DataFrame,
        scenario: CounterfactualScenario,
        outcome_variable: str,
    ) -> CounterfactualResult:
        """Compute counterfactual outcome for a given scenario.

        Propagates interventions through the causal graph using the
        fitted structural equations to predict the outcome under the
        hypothetical intervention.

        Args:
            data: Observational dataset.
            scenario: The counterfactual scenario to evaluate.
            outcome_variable: The target outcome variable.

        Returns:
            A :class:`CounterfactualResult`.

        Raises:
            ValueError: If outcome variable is missing from data.
        """
        if outcome_variable not in data.columns:
            raise ValueError(f"Outcome '{outcome_variable}' not in data columns.")

        self._ensure_fitted(data)

        # Factual outcome
        factual = float(data[outcome_variable].mean())

        # Create counterfactual data by intervening (do-calculus)
        cf_data = data.copy()
        for var, val in scenario.interventions.items():
            if var in cf_data.columns:
                cf_data[var] = val

        # Propagate through causal graph in topological order
        cf_values = self._propagate_interventions(cf_data, scenario.interventions)

        # Compute counterfactual outcome
        if outcome_variable in cf_values:
            counterfactual = cf_values[outcome_variable]
        elif outcome_variable in self._structural_models:
            parents = [
                e.cause for e in self._graph.get_causes(outcome_variable)
            ]
            available = [p for p in parents if p in cf_data.columns]
            if available:
                X_cf = cf_data[available].mean().values.reshape(1, -1)
                scaler = self._scalers[outcome_variable]
                X_scaled = scaler.transform(X_cf)
                counterfactual = float(
                    self._structural_models[outcome_variable].predict(X_scaled)[0]
                )
            else:
                counterfactual = factual
        else:
            counterfactual = float(cf_data[outcome_variable].mean())

        treatment_effect = counterfactual - factual

        # Bootstrap CI
        ci = self._bootstrap_counterfactual_ci(
            data, scenario, outcome_variable
        )

        return CounterfactualResult(
            scenario=scenario,
            factual_outcome=round(factual, 6),
            counterfactual_outcome=round(counterfactual, 6),
            treatment_effect=round(treatment_effect, 6),
            confidence_interval=ci,
            metadata={
                "n_observations": len(data),
                "n_structural_models": len(self._structural_models),
                "intervened_variables": list(scenario.interventions.keys()),
            },
        )

    def _propagate_interventions(
        self,
        data: pd.DataFrame,
        interventions: dict[str, float],
    ) -> dict[str, float]:
        """Propagate interventions through the causal graph.

        Uses a topological traversal: starting from intervened variables,
        predict each downstream variable using its structural equation.

        Args:
            data: Modified data with interventions applied.
            interventions: Variable → value pairs.

        Returns:
            Mapping of variable → predicted mean value.
        """
        values: dict[str, float] = {}
        # Set intervened values
        for var, val in interventions.items():
            values[var] = val

        # Topological sort (Kahn's algorithm)
        order = self._topological_sort()

        for variable in order:
            if variable in values:
                continue
            if variable not in self._structural_models:
                values[variable] = float(data[variable].mean()) if variable in data.columns else 0.0
                continue

            parents = [e.cause for e in self._graph.get_causes(variable)]
            available = [p for p in parents if p in data.columns]
            if not available:
                values[variable] = float(data[variable].mean()) if variable in data.columns else 0.0
                continue

            # Build parent vector from propagated values or data means
            parent_vals = []
            for p in available:
                if p in values:
                    parent_vals.append(values[p])
                else:
                    parent_vals.append(float(data[p].mean()))

            X_cf = np.array(parent_vals).reshape(1, -1)
            scaler = self._scalers[variable]
            X_scaled = scaler.transform(X_cf)
            values[variable] = float(
                self._structural_models[variable].predict(X_scaled)[0]
            )

        return values

    def _topological_sort(self) -> list[str]:
        """Topological sort of the causal graph variables.

        Returns:
            Variables in causal order (parents before children).
        """
        in_degree: dict[str, int] = {v: 0 for v in self._graph.variables}
        adjacency: dict[str, list[str]] = {v: [] for v in self._graph.variables}
        for edge in self._graph.edges:
            if edge.cause in adjacency and edge.effect in in_degree:
                adjacency[edge.cause].append(edge.effect)
                in_degree[edge.effect] += 1

        queue = [v for v, d in in_degree.items() if d == 0]
        order: list[str] = []
        while queue:
            node = queue.pop(0)
            order.append(node)
            for child in adjacency.get(node, []):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        # Add any remaining (cycles) at the end
        for v in self._graph.variables:
            if v not in order:
                order.append(v)
        return order

    def _bootstrap_counterfactual_ci(
        self,
        data: pd.DataFrame,
        scenario: CounterfactualScenario,
        outcome_variable: str,
        n_boot: int = 200,
        alpha: float = 0.05,
    ) -> tuple[float, float]:
        """Bootstrap confidence interval for the counterfactual effect.

        Args:
            data: Original data.
            scenario: Counterfactual scenario.
            outcome_variable: Outcome to evaluate.
            n_boot: Bootstrap replications.
            alpha: Significance level.

        Returns:
            ``(lower, upper)`` confidence bounds.
        """
        effects: list[float] = []
        n = len(data)
        for _ in range(n_boot):
            idx = np.random.choice(n, size=n, replace=True)
            boot = data.iloc[idx].reset_index(drop=True)
            try:
                # Re-fit structural models on bootstrap sample
                temp_analyzer = CounterfactualAnalyzer(self._graph)
                temp_analyzer._fit_structural_models(boot)
                factual = float(boot[outcome_variable].mean())
                cf_data = boot.copy()
                for var, val in scenario.interventions.items():
                    if var in cf_data.columns:
                        cf_data[var] = val
                cf_vals = temp_analyzer._propagate_interventions(
                    cf_data, scenario.interventions
                )
                if outcome_variable in cf_vals:
                    cf_outcome = cf_vals[outcome_variable]
                else:
                    cf_outcome = float(cf_data[outcome_variable].mean())
                effects.append(cf_outcome - factual)
            except (ValueError, np.linalg.LinAlgError):
                continue

        if len(effects) < 10:
            return (-float("inf"), float("inf"))

        arr = np.array(effects)
        lower = float(np.percentile(arr, 100 * alpha / 2))
        upper = float(np.percentile(arr, 100 * (1 - alpha / 2)))
        return (round(lower, 6), round(upper, 6))

    # ── What-If Analysis ─────────────────────────────────────────

    def what_if_analysis(
        self,
        data: pd.DataFrame,
        interventions: dict[str, float],
        target_variables: list[str],
    ) -> dict[str, CounterfactualResult]:
        """Multi-variable what-if analysis.

        Applies a single set of interventions and reports the
        counterfactual effect on multiple target variables.

        Args:
            data: Observational dataset.
            interventions: Variable → new value pairs.
            target_variables: Outcomes to evaluate.

        Returns:
            Mapping of target variable → :class:`CounterfactualResult`.
        """
        scenario = CounterfactualScenario(
            name="what_if",
            description=f"Interventions: {interventions}",
            interventions=interventions,
        )
        results: dict[str, CounterfactualResult] = {}
        for target in target_variables:
            if target not in data.columns:
                logger.warning("what_if_missing_target", target=target)
                continue
            results[target] = self.compute_counterfactual(data, scenario, target)
        return results

    # ── Policy Evaluation ────────────────────────────────────────

    def policy_evaluation(
        self,
        data: pd.DataFrame,
        policy_variable: str,
        policy_values: list[float],
        outcome: str,
    ) -> dict[str, Any]:
        """Evaluate a policy at different intervention levels.

        Sweeps the *policy_variable* across ``policy_values`` and
        computes the counterfactual outcome for each.

        Args:
            data: Observational dataset.
            policy_variable: The variable representing the policy lever.
            policy_values: Values to evaluate.
            outcome: Target outcome variable.

        Returns:
            Dictionary with ``policy_levels``, ``predicted_outcomes``,
            ``treatment_effects``, and ``optimal_level``.
        """
        self._ensure_fitted(data)
        factual = float(data[outcome].mean())

        predicted: list[float] = []
        effects: list[float] = []

        for val in policy_values:
            scenario = CounterfactualScenario(
                name=f"policy_{policy_variable}_{val}",
                description=f"Set {policy_variable} = {val}",
                interventions={policy_variable: val},
            )
            result = self.compute_counterfactual(data, scenario, outcome)
            predicted.append(result.counterfactual_outcome)
            effects.append(result.treatment_effect)

        # Determine optimal level (maximum positive effect or minimum negative)
        best_idx = int(np.argmax(effects)) if effects else 0

        return {
            "policy_variable": policy_variable,
            "policy_levels": policy_values,
            "factual_outcome": round(factual, 6),
            "predicted_outcomes": [round(p, 6) for p in predicted],
            "treatment_effects": [round(e, 6) for e in effects],
            "optimal_level": policy_values[best_idx] if policy_values else None,
            "optimal_effect": round(effects[best_idx], 6) if effects else None,
        }

    # ── Attribution Analysis ─────────────────────────────────────

    def attribution_analysis(
        self,
        data: pd.DataFrame,
        outcome: str,
        factors: list[str],
    ) -> dict[str, Any]:
        """Shapley-value based attribution of factors to the outcome.

        Approximates Shapley values by computing the marginal
        contribution of each factor across all possible orderings
        (up to a combinatorial limit, then falls back to sampling).

        Args:
            data: Observational dataset.
            outcome: Target outcome variable.
            factors: Contributing factor column names.

        Returns:
            Dictionary with ``shapley_values``, ``total_effect``,
            ``factor_ranking``, and ``relative_contributions``.
        """
        self._ensure_fitted(data)
        factors = [f for f in factors if f in data.columns]
        if not factors:
            return {"error": "No valid factors found in data."}

        n_factors = len(factors)
        baseline_outcome = float(data[outcome].mean())

        # For small number of factors, compute exact Shapley values
        # For larger sets, use sampling
        from itertools import permutations
        import math

        max_exact = 8  # factorial(8) = 40320, manageable
        if n_factors <= max_exact:
            orderings = list(permutations(range(n_factors)))
        else:
            # Sample orderings
            n_samples = min(5000, math.factorial(n_factors))
            orderings = [
                tuple(np.random.permutation(n_factors))
                for _ in range(n_samples)
            ]

        marginal_contributions: dict[str, list[float]] = {
            f: [] for f in factors
        }

        for ordering in orderings:
            current_interventions: dict[str, float] = {}
            prev_outcome = baseline_outcome

            for idx in ordering:
                factor = factors[idx]
                # Intervene by setting this factor to its mean (baseline)
                current_interventions[factor] = float(data[factor].mean())

                # Compute outcome with current set of interventions
                scenario = CounterfactualScenario(
                    name="attribution",
                    description=f"Attribution step",
                    interventions=dict(current_interventions),
                )
                try:
                    result = self.compute_counterfactual(data, scenario, outcome)
                    current_outcome = result.counterfactual_outcome
                except (ValueError, np.linalg.LinAlgError):
                    current_outcome = prev_outcome

                marginal = current_outcome - prev_outcome
                marginal_contributions[factor].append(marginal)
                prev_outcome = current_outcome

        # Average marginal contributions = Shapley values
        shapley_values: dict[str, float] = {}
        for factor, contributions in marginal_contributions.items():
            shapley_values[factor] = round(
                float(np.mean(contributions)) if contributions else 0.0, 6
            )

        total_effect = sum(abs(v) for v in shapley_values.values())
        relative: dict[str, float] = {}
        if total_effect > 0:
            relative = {
                f: round(abs(v) / total_effect, 4)
                for f, v in shapley_values.items()
            }
        else:
            relative = {f: 0.0 for f in factors}

        # Rank by absolute contribution
        ranking = sorted(
            shapley_values.keys(),
            key=lambda f: abs(shapley_values[f]),
            reverse=True,
        )

        return {
            "shapley_values": shapley_values,
            "total_effect": round(total_effect, 6),
            "factor_ranking": ranking,
            "relative_contributions": relative,
            "baseline_outcome": round(baseline_outcome, 6),
        }


__all__ = [
    "CounterfactualScenario",
    "CounterfactualResult",
    "CounterfactualAnalyzer",
]
