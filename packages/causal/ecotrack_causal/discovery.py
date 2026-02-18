"""Causal structure discovery for environmental systems.

Implements multiple causal discovery algorithms suitable for
environmental time-series and observational data:

- **Granger causality** — time-series lagged regression test
- **PC algorithm** — constraint-based conditional independence
- **Correlation baseline** — undirected association graph
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd
import structlog
from scipy import stats

logger = structlog.get_logger(__name__)


# ── Enums & Data Classes ─────────────────────────────────────────────


class DiscoveryAlgorithm(str, Enum):
    """Supported causal discovery algorithms."""

    PC = "pc"
    GES = "ges"
    LINGAM = "lingam"
    GRANGER = "granger"
    CORRELATION = "correlation"


@dataclass
class CausalEdge:
    """A directed causal edge.

    Attributes:
        cause: Name of the cause variable.
        effect: Name of the effect variable.
        strength: Estimated effect strength (F-statistic or correlation).
        confidence: Statistical confidence (1 − p-value).
        lag: Time lag in periods (0 for instantaneous).
        mechanism: Optional textual description of the causal mechanism.
    """

    cause: str
    effect: str
    strength: float
    confidence: float
    lag: int = 0
    mechanism: str = ""


@dataclass
class CausalGraph:
    """A discovered causal graph.

    Attributes:
        edges: List of directed causal edges.
        variables: Names of all variables in the graph.
        algorithm: The algorithm used for discovery.
        metadata: Extra information about the discovery run.
    """

    edges: list[CausalEdge]
    variables: list[str]
    algorithm: DiscoveryAlgorithm
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Derived representations ──────────────────────────────────

    @property
    def adjacency_matrix(self) -> np.ndarray:
        """Weighted adjacency matrix (cause → effect)."""
        n = len(self.variables)
        var_idx = {v: i for i, v in enumerate(self.variables)}
        matrix = np.zeros((n, n))
        for edge in self.edges:
            i, j = var_idx[edge.cause], var_idx[edge.effect]
            matrix[i, j] = edge.strength
        return matrix

    def get_causes(self, variable: str) -> list[CausalEdge]:
        """Return all edges where *variable* is the effect."""
        return [e for e in self.edges if e.effect == variable]

    def get_effects(self, variable: str) -> list[CausalEdge]:
        """Return all edges where *variable* is the cause."""
        return [e for e in self.edges if e.cause == variable]

    def get_roots(self) -> list[str]:
        """Return variables with no incoming causal edges."""
        effects = {e.effect for e in self.edges}
        return [v for v in self.variables if v not in effects]

    def get_leaves(self) -> list[str]:
        """Return variables with no outgoing causal edges."""
        causes = {e.cause for e in self.edges}
        return [v for v in self.variables if v not in causes]

    def to_networkx(self) -> Any:
        """Convert to a ``networkx.DiGraph``.

        Returns:
            A directed graph with edge attributes for strength,
            confidence, and lag.
        """
        import networkx as nx

        G = nx.DiGraph()
        G.add_nodes_from(self.variables)
        for edge in self.edges:
            G.add_edge(
                edge.cause,
                edge.effect,
                strength=edge.strength,
                confidence=edge.confidence,
                lag=edge.lag,
            )
        return G


# ── Discovery Engine ─────────────────────────────────────────────────


class CausalDiscovery:
    """Causal structure discovery engine.

    Usage::

        discovery = CausalDiscovery(significance_level=0.05, max_lag=5)
        graph = discovery.discover(dataframe, algorithm=DiscoveryAlgorithm.GRANGER)

    Args:
        significance_level: p-value threshold for statistical tests.
        max_lag: Maximum time lag to test (Granger causality).
    """

    def __init__(
        self,
        significance_level: float = 0.05,
        max_lag: int = 5,
    ) -> None:
        self.significance_level = significance_level
        self.max_lag = max_lag

    def discover(
        self,
        data: pd.DataFrame,
        algorithm: DiscoveryAlgorithm = DiscoveryAlgorithm.GRANGER,
        **kwargs: Any,
    ) -> CausalGraph:
        """Run causal discovery on tabular data.

        Args:
            data: Observational data with named columns. Must not be empty.
            algorithm: Which discovery algorithm to use.
            **kwargs: Algorithm-specific parameters.

        Returns:
            A :class:`CausalGraph` with discovered edges.

        Raises:
            ValueError: If algorithm is not implemented or data is invalid.
        """
        if data.empty:
            logger.warning("causal_discovery_empty_data")
            return CausalGraph(
                edges=[], variables=list(data.columns),
                algorithm=algorithm, metadata={"error": "empty data"},
            )
        if len(data.columns) < 2:
            logger.warning("causal_discovery_insufficient_columns")
            return CausalGraph(
                edges=[], variables=list(data.columns),
                algorithm=algorithm,
                metadata={"error": "need at least 2 variables"},
            )

        dispatch = {
            DiscoveryAlgorithm.GRANGER: self._granger_causality,
            DiscoveryAlgorithm.CORRELATION: self._correlation_based,
            DiscoveryAlgorithm.PC: self._pc_algorithm,
        }
        handler = dispatch.get(algorithm)
        if handler is None:
            raise ValueError(
                f"Algorithm {algorithm.value!r} is not yet implemented. "
                f"Supported: {[a.value for a in dispatch]}"
            )
        return handler(data, **kwargs)

    # ── Granger Causality ────────────────────────────────────────

    def _granger_causality(
        self,
        data: pd.DataFrame,
        max_lag: int | None = None,
    ) -> CausalGraph:
        """Granger causality test for time-series data.

        For each ordered pair ``(X, Y)`` tests whether past values of *X*
        significantly improve the prediction of *Y* beyond its own past,
        using an F-test on nested OLS models.

        Args:
            data: Time-indexed DataFrame (rows = time steps).
            max_lag: Override for ``self.max_lag``.

        Returns:
            :class:`CausalGraph` containing significant Granger-causal edges.
        """
        max_lag = max_lag or self.max_lag
        variables = list(data.columns)
        edges: list[CausalEdge] = []

        # Drop rows with any NaN to get clean slicing
        clean = data.dropna()
        if len(clean) < max_lag + 3:
            logger.warning(
                "granger_insufficient_observations",
                n=len(clean),
                min_required=max_lag + 3,
            )
            return CausalGraph(
                edges=[], variables=variables,
                algorithm=DiscoveryAlgorithm.GRANGER,
                metadata={"error": "insufficient observations after NaN removal"},
            )

        for cause in variables:
            for effect in variables:
                if cause == effect:
                    continue

                best_lag = 0
                best_pvalue = 1.0
                best_fstat = 0.0

                for lag in range(1, max_lag + 1):
                    y = clean[effect].values[lag:]
                    n = len(y)
                    if n < 2 * lag + 2:
                        continue

                    # Restricted model: effect ~ lagged(effect)
                    X_restricted = np.column_stack(
                        [clean[effect].shift(i).values[lag:] for i in range(1, lag + 1)]
                    )
                    # Full model: effect ~ lagged(effect) + lagged(cause)
                    X_cause = np.column_stack(
                        [clean[cause].shift(i).values[lag:] for i in range(1, lag + 1)]
                    )
                    X_full = np.column_stack([X_restricted, X_cause])

                    # Drop any residual NaNs from shifting
                    mask = ~(np.isnan(X_full).any(axis=1) | np.isnan(y))
                    y_c = y[mask]
                    X_r_c = X_restricted[mask]
                    X_f_c = X_full[mask]

                    if len(y_c) < X_f_c.shape[1] + 2:
                        continue

                    try:
                        # Add intercept
                        ones = np.ones((len(y_c), 1))
                        X_r = np.hstack([ones, X_r_c])
                        X_f = np.hstack([ones, X_f_c])

                        beta_r = np.linalg.lstsq(X_r, y_c, rcond=None)[0]
                        beta_f = np.linalg.lstsq(X_f, y_c, rcond=None)[0]

                        rss_r = float(np.sum((y_c - X_r @ beta_r) ** 2))
                        rss_f = float(np.sum((y_c - X_f @ beta_f) ** 2))

                        df1 = lag  # extra parameters in full model
                        df2 = len(y_c) - X_f.shape[1]

                        if rss_f > 0 and df2 > 0:
                            f_stat = ((rss_r - rss_f) / df1) / (rss_f / df2)
                            p_value = float(1 - stats.f.cdf(f_stat, df1, df2))

                            if p_value < best_pvalue:
                                best_pvalue = p_value
                                best_lag = lag
                                best_fstat = float(f_stat)
                    except np.linalg.LinAlgError:
                        continue

                if best_pvalue < self.significance_level:
                    edges.append(
                        CausalEdge(
                            cause=cause,
                            effect=effect,
                            strength=round(best_fstat, 4),
                            confidence=round(1 - best_pvalue, 6),
                            lag=best_lag,
                        )
                    )

        logger.info(
            "granger_discovery_complete",
            variables=len(variables),
            edges=len(edges),
        )
        return CausalGraph(
            edges=edges,
            variables=variables,
            algorithm=DiscoveryAlgorithm.GRANGER,
            metadata={"max_lag": max_lag, "significance_level": self.significance_level},
        )

    # ── Correlation Baseline ─────────────────────────────────────

    def _correlation_based(
        self,
        data: pd.DataFrame,
        threshold: float = 0.5,
    ) -> CausalGraph:
        """Correlation-based undirected association graph (baseline).

        .. warning::
           Correlation does **not** imply causation. This method is a
           baseline for comparison with true causal discovery.

        Args:
            data: Observational DataFrame.
            threshold: Minimum absolute correlation to include an edge.

        Returns:
            :class:`CausalGraph` with undirected edges (represented as
            single directed edges from lower-indexed to higher-indexed
            variable).
        """
        variables = list(data.columns)
        corr_matrix = data.corr()
        edges: list[CausalEdge] = []

        for i, cause in enumerate(variables):
            for j, effect in enumerate(variables):
                if i >= j:
                    continue
                corr = float(abs(corr_matrix.loc[cause, effect]))
                if corr > threshold:
                    edges.append(
                        CausalEdge(
                            cause=cause,
                            effect=effect,
                            strength=round(corr, 4),
                            confidence=round(corr, 4),
                            mechanism="correlation (not causal)",
                        )
                    )

        logger.info(
            "correlation_discovery_complete",
            variables=len(variables),
            edges=len(edges),
            threshold=threshold,
        )
        return CausalGraph(
            edges=edges,
            variables=variables,
            algorithm=DiscoveryAlgorithm.CORRELATION,
            metadata={"threshold": threshold},
        )

    # ── PC Algorithm ─────────────────────────────────────────────

    def _pc_algorithm(
        self,
        data: pd.DataFrame,
        **kwargs: Any,
    ) -> CausalGraph:
        """Simplified PC (Peter-Clark) algorithm.

        Phase 1: Start with the complete undirected graph and remove
        edges when conditional independence is detected via partial
        correlation tests.

        Phase 2 (orientation): Edges are left undirected (represented
        as ``cause → effect`` with lexicographic ordering) because full
        v-structure orientation requires a separating-set bookkeeping
        that is omitted in this simplified version.

        Args:
            data: Observational DataFrame (rows = samples).

        Returns:
            :class:`CausalGraph` with discovered skeleton edges.
        """
        variables = list(data.columns)
        n = len(variables)
        data_np = data.values
        n_samples = data_np.shape[0]

        if n_samples < n + 2:
            logger.warning("pc_insufficient_samples", n_samples=n_samples, n_vars=n)
            return CausalGraph(
                edges=[], variables=variables,
                algorithm=DiscoveryAlgorithm.PC,
                metadata={"error": "insufficient samples"},
            )

        # Adjacency matrix (True = edge present)
        adj = np.ones((n, n), dtype=bool)
        np.fill_diagonal(adj, False)

        # Phase 1: iterative conditional independence testing
        for depth in range(n - 1):
            for i in range(n):
                for j in range(i + 1, n):
                    if not adj[i, j]:
                        continue
                    # Candidate conditioning sets: neighbours of i excluding j
                    neighbours = [
                        k for k in range(n) if k != i and k != j and adj[i, k]
                    ]
                    if len(neighbours) < depth:
                        continue

                    independent = False
                    for subset in combinations(neighbours, min(depth, len(neighbours))):
                        pval = self._partial_correlation_test(
                            data_np, i, j, list(subset), n_samples
                        )
                        if pval > self.significance_level:
                            independent = True
                            break

                    if independent:
                        adj[i, j] = False
                        adj[j, i] = False

            # Early termination: if no node has enough neighbours for
            # the next depth level, stop.
            max_neighbours = max(
                sum(adj[i, :]) for i in range(n)
            ) if n > 0 else 0
            if max_neighbours <= depth + 1:
                break

        # Build edge list from surviving adjacency
        edges: list[CausalEdge] = []
        for i in range(n):
            for j in range(i + 1, n):
                if adj[i, j]:
                    corr = float(abs(np.corrcoef(data_np[:, i], data_np[:, j])[0, 1]))
                    edges.append(
                        CausalEdge(
                            cause=variables[i],
                            effect=variables[j],
                            strength=round(corr, 4),
                            confidence=round(1 - self.significance_level, 4),
                        )
                    )

        logger.info(
            "pc_discovery_complete",
            variables=n,
            edges=len(edges),
        )
        return CausalGraph(
            edges=edges,
            variables=variables,
            algorithm=DiscoveryAlgorithm.PC,
            metadata={"significance_level": self.significance_level},
        )

    @staticmethod
    def _partial_correlation_test(
        data: np.ndarray,
        i: int,
        j: int,
        conditioning: list[int],
        n_samples: int,
    ) -> float:
        """Compute the p-value for a partial-correlation independence test.

        Args:
            data: (n_samples, n_vars) data matrix.
            i: Index of first variable.
            j: Index of second variable.
            conditioning: Indices of conditioning variables.
            n_samples: Number of observations.

        Returns:
            Two-sided p-value for the null hypothesis of zero partial
            correlation.
        """
        if not conditioning:
            corr, pval = stats.pearsonr(data[:, i], data[:, j])
            return float(pval)

        # Partial correlation via residualisation
        Z = data[:, conditioning]
        try:
            beta_i = np.linalg.lstsq(Z, data[:, i], rcond=None)[0]
            beta_j = np.linalg.lstsq(Z, data[:, j], rcond=None)[0]
            residual_i = data[:, i] - Z @ beta_i
            residual_j = data[:, j] - Z @ beta_j
            corr, pval = stats.pearsonr(residual_i, residual_j)
            return float(pval)
        except (np.linalg.LinAlgError, ValueError):
            # On numerical failure, treat as independent
            return 1.0


__all__ = [
    "DiscoveryAlgorithm",
    "CausalEdge",
    "CausalGraph",
    "CausalDiscovery",
]
