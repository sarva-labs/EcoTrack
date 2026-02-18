"""AI agent interaction endpoints."""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class AgentQueryRequest(BaseModel):
    """Natural language query for the agent system."""

    query: str = Field(description="Natural language question or instruction")
    context: dict[str, Any] = Field(default_factory=dict, description="Additional context for the query")
    domains: list[str] | None = Field(
        default=None,
        description="Optional list of domains to consult (climate, biodiversity, health, food_security, resources)",
    )


class AgentSource(BaseModel):
    """A data source referenced by an agent response."""

    source_type: str = Field(description="Type: dataset, observation, model_output, publication")
    name: str
    url: str | None = None
    relevance_score: float = Field(ge=0, le=1)


class AgentQueryResponse(BaseModel):
    """Response from the agent system."""

    query_id: str = Field(description="Unique query identifier")
    answer: str = Field(description="Natural language answer")
    sources: list[AgentSource] = Field(description="Data sources consulted")
    agents_consulted: list[str] = Field(description="List of specialist agents that contributed")
    confidence: float = Field(ge=0, le=1, description="Overall confidence score")
    processing_time_ms: float = Field(description="Processing time in milliseconds")
    follow_up_suggestions: list[str] = Field(default_factory=list, description="Suggested follow-up queries")


class AgentToolInfo(BaseModel):
    """Information about an available agent tool."""

    name: str
    description: str
    domains: list[str]
    input_schema: dict[str, Any] = Field(default_factory=dict)


class AgentSystemStatus(BaseModel):
    """Status of the agent system."""

    status: str
    active_agents: int
    available_tools: int
    queries_processed_today: int
    average_response_time_ms: float
    uptime_hours: float


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/query",
    response_model=AgentQueryResponse,
    status_code=200,
    summary="Submit a natural language query",
    responses={200: {"description": "Query answered"}, 422: {"description": "Validation error"}},
)
async def submit_agent_query(request: AgentQueryRequest) -> AgentQueryResponse:
    """Submit a natural language query to the EcoTrack AI agent system.

    The orchestrator routes the query to relevant specialist agents
    (climate, biodiversity, health, food security, resource equity),
    synthesises their responses, and returns a unified answer.
    """
    query_id = f"aq-{uuid.uuid4().hex[:12]}"
    domains = request.domains or ["climate", "biodiversity", "health", "food_security", "resources"]

    # Stub: simulate agent processing
    agents_consulted = [f"{d}_specialist" for d in domains[:3]]

    return AgentQueryResponse(
        query_id=query_id,
        answer=(
            f"Based on analysis across {len(agents_consulted)} specialist agents: "
            f"The query '{request.query}' has been processed. "
            "Current data indicates moderate environmental stress in the specified region "
            "with climate trends showing a 0.3°C/decade warming rate, biodiversity indices "
            "declining at 2.1% annually, and air quality in the 'Moderate' category. "
            "Recommended actions include enhanced monitoring and cross-domain correlation analysis."
        ),
        sources=[
            AgentSource(
                source_type="dataset",
                name="ERA5 Climate Reanalysis",
                url="https://cds.climate.copernicus.eu/",
                relevance_score=0.92,
            ),
            AgentSource(
                source_type="model_output",
                name="EcoTrack Climate Forecaster v3",
                relevance_score=0.88,
            ),
            AgentSource(
                source_type="dataset",
                name="GBIF Species Occurrences",
                url="https://www.gbif.org/",
                relevance_score=0.75,
            ),
        ],
        agents_consulted=agents_consulted,
        confidence=0.85,
        processing_time_ms=1247.5,
        follow_up_suggestions=[
            "What are the specific climate anomalies in this region?",
            "Show me biodiversity hotspot threats near this area",
            "What is the food security outlook for the next 6 months?",
        ],
    )


@router.get(
    "/status",
    response_model=AgentSystemStatus,
    summary="Get agent system status",
    responses={200: {"description": "Agent system status"}},
)
async def get_agent_status() -> AgentSystemStatus:
    """Get the current status of the EcoTrack AI agent system.

    Returns information about active agents, available tools,
    and processing statistics.
    """
    return AgentSystemStatus(
        status="operational",
        active_agents=5,
        available_tools=12,
        queries_processed_today=342,
        average_response_time_ms=1150.0,
        uptime_hours=168.5,
    )


@router.get(
    "/tools",
    summary="List available agent tools",
    responses={200: {"description": "List of agent tools"}},
)
async def list_agent_tools() -> dict[str, list[AgentToolInfo]]:
    """List all tools available to the EcoTrack agent system.

    Each tool represents a capability that specialist agents can
    invoke during query processing.
    """
    return {
        "tools": [
            AgentToolInfo(
                name="climate_observation_query",
                description="Query climate observations from the data lake",
                domains=["climate"],
                input_schema={"variable": "str", "bbox": "BBox", "time_range": "TimeRange"},
            ),
            AgentToolInfo(
                name="climate_forecast",
                description="Generate climate forecasts using ML models",
                domains=["climate"],
                input_schema={"variable": "str", "bbox": "BBox", "horizon_hours": "int"},
            ),
            AgentToolInfo(
                name="species_search",
                description="Search species observations and distributions",
                domains=["biodiversity"],
                input_schema={"name": "str", "bbox": "BBox", "status_filter": "str"},
            ),
            AgentToolInfo(
                name="ecosystem_health",
                description="Compute ecosystem health indices",
                domains=["biodiversity"],
                input_schema={"lat": "float", "lon": "float", "radius_km": "float"},
            ),
            AgentToolInfo(
                name="air_quality_query",
                description="Query real-time air quality data",
                domains=["health"],
                input_schema={"bbox": "BBox", "pollutant": "str"},
            ),
            AgentToolInfo(
                name="disease_risk_assessment",
                description="Assess vector-borne disease risk",
                domains=["health"],
                input_schema={"lat": "float", "lon": "float", "disease": "str"},
            ),
            AgentToolInfo(
                name="crop_yield_prediction",
                description="Predict crop yields for a region",
                domains=["food_security"],
                input_schema={"crop_type": "str", "lat": "float", "lon": "float"},
            ),
            AgentToolInfo(
                name="drought_monitor",
                description="Monitor drought conditions",
                domains=["food_security"],
                input_schema={"bbox": "BBox", "severity": "str"},
            ),
            AgentToolInfo(
                name="water_stress_index",
                description="Compute water stress indicators",
                domains=["resources"],
                input_schema={"lat": "float", "lon": "float"},
            ),
            AgentToolInfo(
                name="ej_assessment",
                description="Environmental justice assessment",
                domains=["resources"],
                input_schema={"lat": "float", "lon": "float"},
            ),
            AgentToolInfo(
                name="causal_analysis",
                description="Run causal analysis between environmental variables",
                domains=["climate", "biodiversity", "health"],
                input_schema={"variables": "list[str]", "bbox": "BBox", "time_range": "TimeRange"},
            ),
            AgentToolInfo(
                name="knowledge_graph_query",
                description="Query the EcoTrack environmental knowledge graph",
                domains=["climate", "biodiversity", "health", "food_security", "resources"],
                input_schema={"query": "str", "entity_types": "list[str]"},
            ),
        ]
    }


@router.websocket("/ws")
async def agent_websocket(websocket: WebSocket) -> None:
    """Real-time agent interaction via WebSocket.

    Clients send JSON messages with ``{"query": "...", "domains": [...]}``
    and receive streaming responses as the agent system processes them.
    """
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
                continue

            query = data.get("query", "")
            if not query:
                await websocket.send_json({"error": "Missing 'query' field"})
                continue

            query_id = f"ws-{uuid.uuid4().hex[:8]}"

            # Stream status updates
            await websocket.send_json({
                "type": "status",
                "query_id": query_id,
                "message": "Query received. Routing to specialist agents...",
            })

            await asyncio.sleep(0.3)  # Simulate processing

            await websocket.send_json({
                "type": "status",
                "query_id": query_id,
                "message": "Climate specialist responding...",
            })

            await asyncio.sleep(0.3)

            await websocket.send_json({
                "type": "status",
                "query_id": query_id,
                "message": "Synthesising responses...",
            })

            await asyncio.sleep(0.2)

            # Final answer
            await websocket.send_json({
                "type": "answer",
                "query_id": query_id,
                "answer": f"Analysis of '{query}': Environmental conditions in the queried region show moderate stress levels. Climate trends indicate warming, biodiversity is stable but declining, and resource allocation needs optimisation.",
                "confidence": 0.82,
                "agents_consulted": ["climate_specialist", "biodiversity_specialist"],
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            })

    except WebSocketDisconnect:
        pass
