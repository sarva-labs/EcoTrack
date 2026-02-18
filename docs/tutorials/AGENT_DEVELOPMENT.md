# Tutorial: Creating an EcoTrack Agent

**Prerequisites:** [Quickstart Guide](./QUICKSTART.md) completed, Python 3.11+, `ecotrack-agents` package installed
**Time:** ~30 minutes
**Difficulty:** Intermediate

---

## Table of Contents

- [1. Overview](#1-overview)
- [2. Understanding the BaseAgent Class](#2-understanding-the-baseagent-class)
- [3. Creating a Specialist Agent](#3-creating-a-specialist-agent)
- [4. Implementing the Core Methods](#4-implementing-the-core-methods)
- [5. Creating and Registering Tools](#5-creating-and-registering-tools)
- [6. Registering with the Orchestrator](#6-registering-with-the-orchestrator)
- [7. Testing the Agent](#7-testing-the-agent)
- [8. Next Steps](#8-next-steps)

---

## 1. Overview

EcoTrack's multi-agent system coordinates five specialist AI agents—each covering a distinct environmental domain—through a central orchestrator. Agents process natural-language queries by planning a sequence of tool-based steps, executing them, and aggregating results.

### Agent Architecture

```
                        ┌─────────────────────┐
                        │  AgentOrchestrator   │
  User Query ──────────▶│  ─ classify query    │
                        │  ─ dispatch agents   │
                        │  ─ aggregate results │
                        └────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                   │
     ┌────────▼───────┐ ┌───────▼────────┐ ┌───────▼────────┐
     │ ClimateAnalyst │ │ BiodiversityMon│ │ HealthSentinel │ ...
     │  plan()        │ │  plan()        │ │  plan()        │
     │  execute_step()│ │  execute_step()│ │  execute_step()│
     │  tools: [...]  │ │  tools: [...]  │ │  tools: [...]  │
     └────────────────┘ └────────────────┘ └────────────────┘
```

### Existing Agents

| Agent | Role | Module |
|-------|------|--------|
| [`ClimateAnalystAgent`](../../packages/agents/ecotrack_agents/specialists.py:29) | `CLIMATE_ANALYST` | Climate data, forecasting, trends |
| [`BiodiversityMonitorAgent`](../../packages/agents/ecotrack_agents/specialists.py:209) | `BIODIVERSITY_MONITOR` | Species, ecosystems, hotspots |
| [`HealthSentinelAgent`](../../packages/agents/ecotrack_agents/specialists.py:384) | `HEALTH_SENTINEL` | Air quality, disease risk, heat |
| [`FoodSecurityAdvisorAgent`](../../packages/agents/ecotrack_agents/specialists.py:554) | `FOOD_SECURITY_ADVISOR` | Crop yields, drought, food prices |
| [`ResourceOptimizerAgent`](../../packages/agents/ecotrack_agents/specialists.py:728) | `RESOURCE_OPTIMIZER` | Water allocation, energy, equity |

---

## 2. Understanding the BaseAgent Class

All agents extend [`BaseAgent`](../../packages/agents/ecotrack_agents/base.py:110), which provides infrastructure for message processing, tool usage, memory management, and the plan-execute lifecycle.

### Abstract Methods

Every agent **must** implement three methods:

```python
class BaseAgent(abc.ABC):

    @abc.abstractmethod
    async def process_message(self, message: AgentMessage) -> AgentMessage | None:
        """Handle an incoming message and optionally return a response."""
        ...

    @abc.abstractmethod
    async def plan(self, task: str, context: dict[str, Any]) -> list[dict[str, Any]]:
        """Decompose a task into an ordered list of executable steps."""
        ...

    @abc.abstractmethod
    async def execute_step(self, step: dict[str, Any]) -> dict[str, Any]:
        """Execute a single step from the plan."""
        ...
```

### Built-In Capabilities

`BaseAgent` provides these out of the box:

| Method | Description |
|--------|-------------|
| [`use_tool()`](../../packages/agents/ecotrack_agents/base.py:189) | Invoke a registered tool by name |
| [`add_to_memory()`](../../packages/agents/ecotrack_agents/base.py:220) | Store an entry in bounded memory (100 items) |
| [`send_message()`](../../packages/agents/ecotrack_agents/base.py:236) | Create a structured message to another agent |
| [`run_task()`](../../packages/agents/ecotrack_agents/base.py:266) | Convenience: `plan()` → `execute_step()` for each step |

### Key Supporting Types

**[`AgentRole`](../../packages/agents/ecotrack_agents/base.py:17)** — Enum of agent roles:

```python
class AgentRole(str, Enum):
    CLIMATE_ANALYST = "climate_analyst"
    BIODIVERSITY_MONITOR = "biodiversity_monitor"
    HEALTH_SENTINEL = "health_sentinel"
    FOOD_SECURITY_ADVISOR = "food_security_advisor"
    RESOURCE_OPTIMIZER = "resource_optimizer"
    DATA_CURATOR = "data_curator"
    ORCHESTRATOR = "orchestrator"
```

**[`MessageType`](../../packages/agents/ecotrack_agents/base.py:29)** — Message classification:

| Type | Usage |
|------|-------|
| `QUERY` | Direct data/analysis request |
| `RESPONSE` | Reply to a query |
| `TASK` | Full task for plan-execute lifecycle |
| `RESULT` | Final result of a task |
| `ALERT` | Urgent notification |
| `BROADCAST` | System-wide message |
| `HEARTBEAT` | Liveness check |

**[`AgentMessage`](../../packages/agents/ecotrack_agents/base.py:42)** — Structured message with `sender`, `recipient`, `type`, `content`, `correlation_id`, `priority`, and `metadata`.

**[`ToolDefinition`](../../packages/agents/ecotrack_agents/base.py:91)** — Tool specification with `name`, `description`, `parameters` (JSON Schema), `handler`, and optional `required_role`.

---

## 3. Creating a Specialist Agent

Let's build a **Water Quality Monitor** agent that analyses water quality data, detects contamination, and assesses risks to aquatic ecosystems.

### Step 1: Define the Agent Class

Create `packages/agents/ecotrack_agents/water_quality_agent.py`:

```python
"""Water Quality Monitor agent for EcoTrack.

Analyses water quality data from sensor networks, detects
contamination events, and assesses risks to aquatic ecosystems
and downstream human populations.
"""
from __future__ import annotations

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


class WaterQualityMonitorAgent(BaseAgent):
    """Specialist agent for water quality monitoring and contamination detection.

    Handles water quality queries, contamination alerts, trend analysis,
    and ecosystem impact assessment for freshwater and coastal systems.
    """

    SYSTEM_PROMPT: str = (
        "You are a Water Quality Monitor agent for the EcoTrack platform. "
        "Your expertise covers water chemistry, contamination detection, "
        "aquatic ecosystem health, and water safety assessment. You monitor "
        "pH, dissolved oxygen, turbidity, heavy metals, and biological "
        "indicators to provide early warnings of water quality threats."
    )

    def __init__(
        self,
        agent_id: str = "water_quality_monitor",
        tools: list[ToolDefinition] | None = None,
    ) -> None:
        """Initialize the water quality monitor agent.

        Args:
            agent_id: Unique agent identifier.
            tools: Optional list of tool definitions.
        """
        # Use DATA_CURATOR role (or add a custom role)
        super().__init__(
            agent_id=agent_id,
            role=AgentRole.DATA_CURATOR,
            tools=tools,
        )
        self._log = logger.bind(agent_id=agent_id, role=self.role.value)
```

---

## 4. Implementing the Core Methods

### Implement `process_message()`

This is the entry point for all incoming messages. Route based on [`MessageType`](../../packages/agents/ecotrack_agents/base.py:29):

```python
    async def process_message(self, message: AgentMessage) -> AgentMessage | None:
        """Process water-quality-related messages.

        Routes to appropriate handlers based on message type:
        - QUERY → direct data query
        - ALERT → contamination alert check
        - TASK  → full analysis pipeline via plan/execute

        Args:
            message: Incoming agent message.

        Returns:
            Response message or None.
        """
        self._log.info("processing_message", msg_type=message.type.value)
        self.state.status = "processing"
        self.state.last_active = message.timestamp

        content = message.content
        result: dict[str, Any]

        if message.type == MessageType.QUERY:
            result = await self._handle_query(content)
        elif message.type == MessageType.ALERT:
            result = await self._handle_contamination_alert(content)
        elif message.type == MessageType.TASK:
            result = await self.run_task(
                content.get("task", "water quality assessment"),
                content.get("context", {}),
            )
        else:
            result = {"status": "unhandled", "message_type": message.type.value}

        self.state.status = "idle"
        return self.send_message(
            recipient=message.sender,
            msg_type=MessageType.RESPONSE,
            content=result,
            correlation_id=message.correlation_id or message.id,
        )
```

### Implement `plan()`

Decompose tasks into ordered steps. Each step is a dictionary with `action`, `params`, and `description` keys:

```python
    async def plan(self, task: str, context: dict[str, Any]) -> list[dict[str, Any]]:
        """Create a plan for water quality analysis tasks.

        Standard pipeline:
          1. Query current water quality data
          2. Detect contamination events
          3. Assess ecosystem impact
          4. Generate water quality report

        Args:
            task: Natural-language task description.
            context: Contextual information (bbox, parameters, etc.).

        Returns:
            Ordered list of execution steps.
        """
        self._log.info("planning", task=task)
        bbox = context.get("bbox", [-180, -90, 180, 90])
        water_body = context.get("water_body", "river")

        steps: list[dict[str, Any]] = [
            {
                "action": "query_water_quality",
                "params": {
                    "bbox": bbox,
                    "water_body_type": water_body,
                    "parameters": context.get("parameters", ["pH", "DO", "turbidity"]),
                    "start_date": context.get("start_date", "2024-01-01"),
                    "end_date": context.get("end_date", "2025-01-01"),
                },
                "description": "Query current water quality sensor data",
            },
            {
                "action": "detect_contamination",
                "params": {
                    "bbox": bbox,
                    "lookback_days": context.get("lookback_days", 7),
                    "thresholds": context.get("thresholds", {}),
                },
                "description": "Detect contamination events in recent data",
            },
            {
                "action": "assess_ecosystem_impact",
                "params": {
                    "bbox": bbox,
                    "water_body_type": water_body,
                },
                "description": "Assess impact on aquatic ecosystems",
            },
            {
                "action": "generate_water_report",
                "params": {
                    "bbox": bbox,
                    "include_recommendations": True,
                },
                "description": "Generate comprehensive water quality report",
            },
        ]
        return steps
```

### Implement `execute_step()`

Execute each step by invoking the corresponding tool:

```python
    async def execute_step(self, step: dict[str, Any]) -> dict[str, Any]:
        """Execute a single water quality analysis step.

        Attempts to invoke the tool matching the step's action.
        Falls back to a synthetic result when the tool is not registered.

        Args:
            step: Step dictionary with 'action' and 'params'.

        Returns:
            Result dictionary with 'action', 'status', and 'result'.
        """
        action = step.get("action", "")
        params = step.get("params", {})
        self._log.debug("executing_step", action=action)

        if action in self.tools:
            try:
                result = await self.use_tool(action, **params)
                return {"action": action, "status": "success", "result": result}
            except (ValueError, RuntimeError) as exc:
                self._log.warning("step_failed", action=action, error=str(exc))
                return {"action": action, "status": "error", "error": str(exc)}

        # Fallback for unregistered tools
        return self._synthetic_result(action, params)

    @staticmethod
    def _synthetic_result(action: str, params: dict[str, Any]) -> dict[str, Any]:
        """Return a placeholder result when tools aren't registered."""
        return {
            "action": action,
            "status": "synthetic",
            "params": params,
            "note": "Tool not yet registered; returning placeholder result",
            "result": {"quality_index": 0.75, "risk_level": "low"},
        }
```

### Add Private Helper Methods

```python
    async def _handle_query(self, content: dict[str, Any]) -> dict[str, Any]:
        """Handle a direct water quality query."""
        if "query_water_quality" in self.tools:
            return await self.use_tool("query_water_quality", **content)
        return {
            "status": "success",
            "bbox": content.get("bbox", []),
            "pH": 7.2,
            "dissolved_oxygen_mg_l": 8.5,
            "turbidity_ntu": 12.3,
            "quality_index": 0.82,
            "classification": "good",
        }

    async def _handle_contamination_alert(self, content: dict[str, Any]) -> dict[str, Any]:
        """Handle a contamination alert request."""
        if "detect_contamination" in self.tools:
            return await self.use_tool("detect_contamination", **content)
        return {
            "status": "success",
            "contamination_detected": False,
            "alert_level": "none",
            "parameters_checked": ["pH", "DO", "turbidity", "heavy_metals"],
        }


__all__ = ["WaterQualityMonitorAgent"]
```

---

## 5. Creating and Registering Tools

Tools give agents the ability to perform specific actions. Create tool functions and wrap them in [`ToolDefinition`](../../packages/agents/ecotrack_agents/base.py:91) objects.

### Step 1: Implement Tool Functions

Create `packages/agents/ecotrack_agents/tools/water_quality_tools.py`:

```python
"""Water quality analysis tools for EcoTrack agents."""
from __future__ import annotations

from typing import Any

import structlog

from ecotrack_agents.base import AgentRole, ToolDefinition

logger = structlog.get_logger(__name__)


async def query_water_quality(
    bbox: list[float],
    water_body_type: str = "river",
    parameters: list[str] | None = None,
    start_date: str = "2024-01-01",
    end_date: str = "2025-01-01",
) -> dict[str, Any]:
    """Query water quality observations for a region.

    Args:
        bbox: Bounding box [min_lon, min_lat, max_lon, max_lat].
        water_body_type: Type of water body (river, lake, coastal).
        parameters: Water quality parameters to query.
        start_date: Start date (ISO-8601).
        end_date: End date (ISO-8601).

    Returns:
        Dictionary with water quality data and summary statistics.
    """
    logger.info("query_water_quality", bbox=bbox, water_body=water_body_type)
    params = parameters or ["pH", "DO", "turbidity"]
    return {
        "bbox": bbox,
        "water_body_type": water_body_type,
        "time_range": {"start": start_date, "end": end_date},
        "stations": 12,
        "measurements": 4380,
        "summary": {
            "pH": {"mean": 7.2, "min": 6.5, "max": 8.1},
            "dissolved_oxygen_mg_l": {"mean": 8.5, "min": 5.2, "max": 11.8},
            "turbidity_ntu": {"mean": 12.3, "min": 2.1, "max": 45.6},
        },
        "quality_index": 0.82,
        "classification": "good",
        "status": "success",
    }


async def detect_contamination(
    bbox: list[float],
    lookback_days: int = 7,
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Detect contamination events in recent water quality data.

    Args:
        bbox: Bounding box [min_lon, min_lat, max_lon, max_lat].
        lookback_days: Days to look back for anomalies.
        thresholds: Parameter-specific alert thresholds.

    Returns:
        Dictionary with contamination detection results.
    """
    logger.info("detect_contamination", bbox=bbox, lookback_days=lookback_days)
    return {
        "bbox": bbox,
        "lookback_days": lookback_days,
        "events_detected": 0,
        "alert_level": "none",
        "stations_monitored": 12,
        "parameters_checked": ["pH", "DO", "turbidity", "nitrates", "phosphates"],
        "status": "success",
    }
```

### Step 2: Define ToolDefinition Objects

```python
WATER_QUALITY_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="query_water_quality",
        description="Query water quality observations for a bounding box and time range.",
        parameters={
            "type": "object",
            "properties": {
                "bbox": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Bounding box [min_lon, min_lat, max_lon, max_lat]",
                },
                "water_body_type": {"type": "string", "enum": ["river", "lake", "coastal"]},
                "parameters": {"type": "array", "items": {"type": "string"}},
                "start_date": {"type": "string", "format": "date"},
                "end_date": {"type": "string", "format": "date"},
            },
            "required": ["bbox"],
        },
        handler=query_water_quality,
        required_role=None,  # Available to any agent
    ),
    ToolDefinition(
        name="detect_contamination",
        description="Detect contamination events in recent water quality data.",
        parameters={
            "type": "object",
            "properties": {
                "bbox": {"type": "array", "items": {"type": "number"}},
                "lookback_days": {"type": "integer", "default": 7},
                "thresholds": {"type": "object"},
            },
            "required": ["bbox"],
        },
        handler=detect_contamination,
        required_role=None,
    ),
]

__all__ = ["query_water_quality", "detect_contamination", "WATER_QUALITY_TOOLS"]
```

### Step 3: Pass Tools to the Agent

```python
from ecotrack_agents.tools.water_quality_tools import WATER_QUALITY_TOOLS

agent = WaterQualityMonitorAgent(
    agent_id="water_quality_monitor",
    tools=WATER_QUALITY_TOOLS,
)

# Verify tools are registered
print(f"Available tools: {list(agent.tools.keys())}")
# ['query_water_quality', 'detect_contamination']
```

---

## 6. Registering with the Orchestrator

The [`AgentOrchestrator`](../../packages/agents/ecotrack_agents/orchestrator.py:57) coordinates multi-agent interactions.

### Basic Registration

```python
import asyncio
from ecotrack_agents.orchestrator import AgentOrchestrator
from ecotrack_agents.specialists import ClimateAnalystAgent
from ecotrack_agents.tools.climate_tools import CLIMATE_TOOLS
from ecotrack_agents.tools.water_quality_tools import WATER_QUALITY_TOOLS

async def main():
    # Create the orchestrator
    orchestrator = AgentOrchestrator()

    # Register existing agents
    climate_agent = ClimateAnalystAgent(tools=CLIMATE_TOOLS)
    orchestrator.register_agent(climate_agent)

    # Register our new agent
    water_agent = WaterQualityMonitorAgent(tools=WATER_QUALITY_TOOLS)
    orchestrator.register_agent(water_agent)

    # Check system status
    status = orchestrator.get_system_status()
    print(f"Total agents: {status['total_agents']}")
    print(f"Roles covered: {status['roles_covered']}")
    for agent_id, info in status["agents"].items():
        print(f"  {agent_id}: {info['role']} — tools: {info['tools_available']}")

asyncio.run(main())
```

### Executing Multi-Agent Queries

```python
async def run_query():
    orchestrator = AgentOrchestrator()

    # Register agents...
    water_agent = WaterQualityMonitorAgent(tools=WATER_QUALITY_TOOLS)
    orchestrator.register_agent(water_agent)

    # Execute a query — the orchestrator classifies and dispatches
    result = await orchestrator.execute_query(
        query="What is the water quality in the Mississippi River basin?",
        context={"bbox": [-95, 29, -88, 43]},
    )

    print(f"Status: {result['status']}")
    print(f"Agents consulted: {result['agents_consulted']}")
    for r in result.get("results", []):
        print(f"  Agent {r['agent_id']}: {r['content'].get('status')}")

asyncio.run(run_query())
```

### Adding Query Classification Keywords

To ensure the orchestrator routes water quality queries to your agent, you may need to extend the keyword classifier. The classification logic is in [`AgentOrchestrator._classify_query()`](../../packages/agents/ecotrack_agents/orchestrator.py:236), which maps keywords to [`AgentRole`](../../packages/agents/ecotrack_agents/base.py:17) values. Since our agent uses `DATA_CURATOR`, add keywords for that role or modify the `_DOMAIN_KEYWORDS` mapping:

```python
# In orchestrator.py or via monkey-patching for customisation:
from ecotrack_agents.orchestrator import _DOMAIN_KEYWORDS
from ecotrack_agents.base import AgentRole

_DOMAIN_KEYWORDS[AgentRole.DATA_CURATOR] = [
    "water quality", "contamination", "pH", "dissolved oxygen",
    "turbidity", "water pollution", "aquatic", "river quality",
    "lake quality", "drinking water", "wastewater",
]
```

---

## 7. Testing the Agent

### Unit Tests

Create `tests/unit/test_water_quality_agent.py`:

```python
"""Tests for the WaterQualityMonitorAgent."""
from __future__ import annotations

import pytest
from datetime import datetime

from ecotrack_agents.base import AgentMessage, MessageType, ToolDefinition
from ecotrack_agents.tools.water_quality_tools import WATER_QUALITY_TOOLS

# Import your agent
from ecotrack_agents.water_quality_agent import WaterQualityMonitorAgent


@pytest.fixture
def agent() -> WaterQualityMonitorAgent:
    """Create an agent with tools for testing."""
    return WaterQualityMonitorAgent(tools=WATER_QUALITY_TOOLS)


@pytest.fixture
def agent_no_tools() -> WaterQualityMonitorAgent:
    """Create an agent without tools (tests fallback behaviour)."""
    return WaterQualityMonitorAgent(tools=None)


class TestProcessMessage:
    """Tests for process_message()."""

    @pytest.mark.asyncio
    async def test_handles_query(self, agent):
        message = AgentMessage(
            sender="test_user",
            recipient=agent.agent_id,
            type=MessageType.QUERY,
            content={
                "bbox": [-90, 30, -80, 40],
                "water_body_type": "river",
            },
        )
        response = await agent.process_message(message)

        assert response is not None
        assert response.type == MessageType.RESPONSE
        assert response.recipient == "test_user"
        assert "quality_index" in response.content

    @pytest.mark.asyncio
    async def test_handles_alert(self, agent):
        message = AgentMessage(
            sender="orchestrator",
            recipient=agent.agent_id,
            type=MessageType.ALERT,
            content={"bbox": [-90, 30, -80, 40]},
        )
        response = await agent.process_message(message)

        assert response is not None
        assert "alert_level" in response.content

    @pytest.mark.asyncio
    async def test_handles_task(self, agent):
        message = AgentMessage(
            sender="orchestrator",
            recipient=agent.agent_id,
            type=MessageType.TASK,
            content={
                "task": "Assess water quality in the region",
                "context": {"bbox": [-90, 30, -80, 40]},
            },
        )
        response = await agent.process_message(message)

        assert response is not None
        assert response.content["status"] in ("completed", "error")

    @pytest.mark.asyncio
    async def test_returns_idle_after_processing(self, agent):
        message = AgentMessage(
            sender="test", recipient=agent.agent_id,
            type=MessageType.QUERY, content={},
        )
        await agent.process_message(message)
        assert agent.state.status == "idle"


class TestPlan:
    """Tests for plan()."""

    @pytest.mark.asyncio
    async def test_returns_ordered_steps(self, agent):
        steps = await agent.plan(
            task="Check water quality",
            context={"bbox": [-90, 30, -80, 40]},
        )
        assert len(steps) == 4
        assert steps[0]["action"] == "query_water_quality"
        assert steps[1]["action"] == "detect_contamination"

    @pytest.mark.asyncio
    async def test_uses_context_parameters(self, agent):
        steps = await agent.plan(
            task="Check water quality",
            context={
                "bbox": [-100, 25, -90, 35],
                "water_body": "lake",
                "parameters": ["pH", "nitrates"],
            },
        )
        assert steps[0]["params"]["water_body_type"] == "lake"
        assert steps[0]["params"]["parameters"] == ["pH", "nitrates"]


class TestExecuteStep:
    """Tests for execute_step()."""

    @pytest.mark.asyncio
    async def test_invokes_registered_tool(self, agent):
        step = {
            "action": "query_water_quality",
            "params": {"bbox": [-90, 30, -80, 40]},
        }
        result = await agent.execute_step(step)
        assert result["status"] == "success"
        assert "result" in result

    @pytest.mark.asyncio
    async def test_fallback_for_unregistered_tool(self, agent_no_tools):
        step = {
            "action": "query_water_quality",
            "params": {"bbox": [-90, 30, -80, 40]},
        }
        result = await agent_no_tools.execute_step(step)
        assert result["status"] == "synthetic"


class TestToolUsage:
    """Tests for tool integration."""

    @pytest.mark.asyncio
    async def test_use_tool_success(self, agent):
        result = await agent.use_tool(
            "query_water_quality",
            bbox=[-90, 30, -80, 40],
        )
        assert result["status"] == "success"
        assert "quality_index" in result

    @pytest.mark.asyncio
    async def test_use_tool_not_found(self, agent):
        with pytest.raises(ValueError, match="not available"):
            await agent.use_tool("nonexistent_tool")


class TestMemory:
    """Tests for memory management."""

    @pytest.mark.asyncio
    async def test_adds_to_memory_during_task(self, agent):
        message = AgentMessage(
            sender="test", recipient=agent.agent_id,
            type=MessageType.TASK,
            content={
                "task": "quick check",
                "context": {"bbox": [-90, 30, -80, 40]},
            },
        )
        await agent.process_message(message)
        assert len(agent.state.memory) > 0
```

### Run Tests

```bash
pytest tests/unit/test_water_quality_agent.py -v
```

### Integration Test with Orchestrator

```python
"""Integration test: agent + orchestrator."""

@pytest.mark.asyncio
async def test_orchestrator_routes_to_water_agent():
    from ecotrack_agents.orchestrator import AgentOrchestrator, _DOMAIN_KEYWORDS
    from ecotrack_agents.base import AgentRole

    # Add classification keywords
    _DOMAIN_KEYWORDS[AgentRole.DATA_CURATOR] = ["water quality", "contamination"]

    orchestrator = AgentOrchestrator()
    agent = WaterQualityMonitorAgent(tools=WATER_QUALITY_TOOLS)
    orchestrator.register_agent(agent)

    result = await orchestrator.execute_query(
        query="Check water quality in the river basin",
    )

    assert result["status"] == "completed"
    assert "water_quality_monitor" in result["agents_consulted"]
```

---

## 8. Next Steps

- **Add LLM-based planning** — Replace keyword-based planning with LangChain/LangGraph using the optional `llm` dependency in [`pyproject.toml`](../../packages/agents/pyproject.toml:12)
- **Implement shared memory** — Use the [`memory.py`](../../packages/agents/ecotrack_agents/memory.py) module for persistent cross-agent context
- **Create more tools** — Add tools for knowledge graph queries, causal analysis, or ML inference
- **Connect to the API** — Expose agent queries through the [`agents router`](../../apps/api-python/ecotrack_api/routers/agents.py)
- **Train supporting models** — Follow the [Model Training Tutorial](./MODEL_TRAINING.md) to create models your agent can invoke
- **Read the whitepaper** — See Section 8 of the [Research Whitepaper](../whitepaper/WHITEPAPER.md) for multi-agent design rationale

---

*See also: [Data Ingestion Tutorial](./DATA_INGESTION.md) · [Model Training Tutorial](./MODEL_TRAINING.md) · [API Documentation](../../API.md)*
