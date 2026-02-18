"""Tests for causal discovery algorithms."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ecotrack_causal.discovery import CausalDiscovery, CausalGraph, DiscoveryAlgorithm


class TestCausalDiscovery:
    @pytest.fixture
    def correlated_data(self) -> pd.DataFrame:
        """Create data with known correlations."""
        np.random.seed(42)
        n = 500
        x = np.random.randn(n)
        y = 0.8 * x + 0.2 * np.random.randn(n)
        z = 0.5 * y + 0.3 * np.random.randn(n)
        return pd.DataFrame({"x": x, "y": y, "z": z})

    def test_correlation_based_discovery(self, correlated_data: pd.DataFrame) -> None:
        discovery = CausalDiscovery()
        graph = discovery.discover(correlated_data, algorithm=DiscoveryAlgorithm.CORRELATION, threshold=0.3)
        assert len(graph.edges) > 0
        assert len(graph.variables) == 3

    def test_causal_graph_adjacency_matrix(self, correlated_data: pd.DataFrame) -> None:
        discovery = CausalDiscovery()
        graph = discovery.discover(correlated_data, algorithm=DiscoveryAlgorithm.CORRELATION)
        matrix = graph.adjacency_matrix
        assert matrix.shape == (3, 3)

    def test_causal_graph_to_networkx(self, correlated_data: pd.DataFrame) -> None:
        discovery = CausalDiscovery()
        graph = discovery.discover(correlated_data, algorithm=DiscoveryAlgorithm.CORRELATION)
        G = graph.to_networkx()
        assert len(G.nodes) == 3
