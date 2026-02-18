"""Multi-agent orchestrator for coordinating EcoTrack agents.

The orchestrator is the central coordination point: it receives user
queries, classifies them to determine relevant specialist agents,
dispatches sub-tasks in parallel, and aggregates results into a
unified response.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any

import structlog

from ecotrack_agents.base import (
    AgentMessage,
    AgentRole,
    BaseAgent,
    MessageType,
    ToolDefinition,
)

logger = structlog.get_logger(__name__)

# Keyword → AgentRole mapping used by the lightweight classifier
_DOMAIN_KEYWORDS: dict[AgentRole, list[str]] = {
    AgentRole.CLIMATE_ANALYST: [
        "climate", "temperature", "precipitation", "weather", "forecast",
        "warming", "rainfall", "drought", "heat", "storm", "hurricane",
        "el niño", "la niña", "greenhouse", "co2", "carbon dioxide",
    ],
    AgentRole.BIODIVERSITY_MONITOR: [
        "species", "biodiversity", "ecosystem", "habitat", "wildlife",
        "conservation", "endangered", "migration", "bird", "plant",
        "forest", "coral", "reef", "invasive", "extinction",
    ],
    AgentRole.HEALTH_SENTINEL: [
        "health", "air quality", "pollution", "disease", "dengue",
        "malaria", "respiratory", "heat stress", "vulnerability",
        "water quality", "contamination", "epidemiology",
    ],
    AgentRole.FOOD_SECURITY_ADVISOR: [
        "food", "crop", "agriculture", "yield", "famine", "hunger",
        "irrigation", "soil", "livestock", "grain", "rice", "wheat",
        "maize", "supply chain", "food price",
    ],
    AgentRole.RESOURCE_OPTIMIZER: [
        "resource", "water allocation", "energy", "optimization",
        "equity", "justice", "distribution", "sustainability",
        "renewable", "infrastructure", "budget",
    ],
}


class AgentOrchestrator:
    """Orchestrates multiple EcoTrack specialist agents.

    Routes queries to appropriate domain agents, manages inter-agent
    communication, coordinates parallel execution, and aggregates
    results across domains.
    """

    def __init__(self) -> None:
        """Initialize the orchestrator with an empty agent registry."""
        self._agents: dict[str, BaseAgent] = {}
        self._role_index: dict[AgentRole, list[str]] = {}
        self._log = logger.bind(component="orchestrator")

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_agent(self, agent: BaseAgent) -> None:
        """Register an agent with the orchestrator.

        Args:
            agent: Agent instance to register.
        """
        self._agents[agent.agent_id] = agent
        self._role_index.setdefault(agent.role, []).append(agent.agent_id)
        self._log.info("agent_registered", agent_id=agent.agent_id, role=agent.role.value)

    def get_agent(self, agent_id: str) -> BaseAgent | None:
        """Get a registered agent by ID.

        Args:
            agent_id: The agent's unique identifier.

        Returns:
            Agent instance or *None*.
        """
        return self._agents.get(agent_id)

    # ------------------------------------------------------------------
    # Message routing
    # ------------------------------------------------------------------

    async def route_message(self, message: AgentMessage) -> AgentMessage | None:
        """Route a message to the appropriate agent.

        Args:
            message: The message to route.

        Returns:
            Response from the target agent, or *None* if the recipient
            is not found.
        """
        if not message.recipient:
            return await self.broadcast(message)

        agent = self._agents.get(message.recipient)
        if agent is None:
            self._log.warning("recipient_not_found", recipient=message.recipient)
            return None
        return await agent.process_message(message)

    async def broadcast(self, message: AgentMessage) -> AgentMessage | None:
        """Broadcast a message to all registered agents.

        Args:
            message: The message to broadcast (``recipient`` ignored).

        Returns:
            An aggregated response message, or *None* when there are
            no agents.
        """
        if not self._agents:
            return None

        tasks = [
            agent.process_message(message) for agent in self._agents.values()
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        valid = [
            r.content
            for r in responses
            if isinstance(r, AgentMessage)
        ]
        return AgentMessage(
            sender="orchestrator",
            recipient=message.sender,
            type=MessageType.RESPONSE,
            content={"responses": valid, "agent_count": len(valid)},
            correlation_id=message.id,
        )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def execute_query(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a user query across the multi-agent system.

        Workflow:
        1. Classify the query to determine relevant domains.
        2. Create sub-tasks for the corresponding specialist agents.
        3. Execute tasks in parallel.
        4. Aggregate and synthesise results.

        Args:
            query: Natural-language user query.
            context: Optional context dictionary.

        Returns:
            Aggregated result dictionary.
        """
        ctx = context or {}
        correlation_id = str(uuid.uuid4())
        self._log.info("execute_query", query=query[:120], correlation_id=correlation_id)

        # Step 1 — classify
        relevant_roles = self._classify_query(query)
        if not relevant_roles:
            # Fallback: send to all agents
            relevant_roles = list(self._role_index.keys())

        self._log.info("query_classified", roles=[r.value for r in relevant_roles])

        # Step 2 — dispatch sub-tasks
        tasks: list[asyncio.Task[AgentMessage | None]] = []
        agent_ids_dispatched: list[str] = []
        for role in relevant_roles:
            for agent_id in self._role_index.get(role, []):
                agent = self._agents[agent_id]
                msg = AgentMessage(
                    sender="orchestrator",
                    recipient=agent_id,
                    type=MessageType.TASK,
                    content={"task": query, "context": ctx},
                    correlation_id=correlation_id,
                )
                tasks.append(asyncio.ensure_future(agent.process_message(msg)))
                agent_ids_dispatched.append(agent_id)

        if not tasks:
            return {
                "status": "no_agents_available",
                "query": query,
                "correlation_id": correlation_id,
            }

        # Step 3 — parallel execution
        raw_responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Step 4 — aggregate
        results: list[dict[str, Any]] = []
        for idx, resp in enumerate(raw_responses):
            if isinstance(resp, AgentMessage):
                results.append({
                    "agent_id": agent_ids_dispatched[idx],
                    "content": resp.content,
                })
            elif isinstance(resp, Exception):
                results.append({
                    "agent_id": agent_ids_dispatched[idx],
                    "error": str(resp),
                })

        aggregated = self._aggregate_results(results)
        aggregated["correlation_id"] = correlation_id
        aggregated["query"] = query
        aggregated["agents_consulted"] = agent_ids_dispatched
        aggregated["timestamp"] = datetime.utcnow().isoformat()
        return aggregated

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def _classify_query(self, query: str) -> list[AgentRole]:
        """Determine which agent roles should handle the query.

        Uses keyword matching as a lightweight classifier. In production
        this could be replaced by an LLM-based intent classifier.

        Args:
            query: The user query.

        Returns:
            Sorted list of relevant :class:`AgentRole` values.
        """
        query_lower = query.lower()
        scores: dict[AgentRole, int] = {}
        for role, keywords in _DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in query_lower)
            if score > 0:
                scores[role] = score

        if not scores:
            return []

        # Return roles sorted by descending score
        return sorted(scores, key=lambda r: scores[r], reverse=True)

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    @staticmethod
    def _aggregate_results(results: list[dict[str, Any]]) -> dict[str, Any]:
        """Merge results from multiple specialist agents.

        Args:
            results: List of per-agent result dictionaries.

        Returns:
            Aggregated response dictionary.
        """
        if not results:
            return {"status": "no_results", "results": []}

        errors = [r for r in results if "error" in r]
        successes = [r for r in results if "error" not in r]

        return {
            "status": "completed" if successes else "error",
            "results": successes,
            "errors": errors if errors else None,
            "total_agents": len(results),
            "successful_agents": len(successes),
        }

    # ------------------------------------------------------------------
    # Status / introspection
    # ------------------------------------------------------------------

    def get_system_status(self) -> dict[str, Any]:
        """Get status of all registered agents.

        Returns:
            Dictionary with per-agent status and overall summary.
        """
        agents_status = {}
        for agent_id, agent in self._agents.items():
            agents_status[agent_id] = {
                "role": agent.role.value,
                "status": agent.state.status,
                "current_task": agent.state.current_task,
                "last_active": agent.state.last_active.isoformat(),
                "tools_available": list(agent.tools.keys()),
            }
        return {
            "total_agents": len(self._agents),
            "agents": agents_status,
            "roles_covered": [r.value for r in self._role_index],
        }

    @property
    def registered_agents(self) -> list[str]:
        """List IDs of all registered agents."""
        return list(self._agents.keys())


__all__ = ["AgentOrchestrator"]
