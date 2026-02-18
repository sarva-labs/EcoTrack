"""Tests for API endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from ecotrack_api.main import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


class TestHealthEndpoints:
    def test_health_check(self, client: TestClient) -> None:
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_list_domains(self, client: TestClient) -> None:
        response = client.get("/api/v1/domains")
        assert response.status_code == 200
        data = response.json()
        assert len(data["domains"]) >= 5


class TestClimateEndpoints:
    def test_get_observations(self, client: TestClient) -> None:
        response = client.get("/api/v1/climate/observations")
        assert response.status_code == 200

    def test_get_variables(self, client: TestClient) -> None:
        response = client.get("/api/v1/climate/variables")
        assert response.status_code == 200

    def test_get_anomalies(self, client: TestClient) -> None:
        response = client.get("/api/v1/climate/anomalies")
        assert response.status_code == 200


class TestBiodiversityEndpoints:
    def test_get_species(self, client: TestClient) -> None:
        response = client.get("/api/v1/biodiversity/species")
        assert response.status_code == 200

    def test_get_ecosystem_health(self, client: TestClient) -> None:
        response = client.get("/api/v1/biodiversity/ecosystem-health")
        assert response.status_code == 200


class TestAgentEndpoints:
    def test_get_agent_status(self, client: TestClient) -> None:
        response = client.get("/api/v1/agents/status")
        assert response.status_code == 200

    def test_get_agent_tools(self, client: TestClient) -> None:
        response = client.get("/api/v1/agents/tools")
        assert response.status_code == 200
