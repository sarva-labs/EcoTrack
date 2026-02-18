"""EcoTrack Agents — Multi-agent coordination for environmental intelligence."""
from __future__ import annotations

from ecotrack_agents.base import (
    AgentMessage,
    AgentRole,
    AgentState,
    BaseAgent,
    MessageType,
    ToolDefinition,
)
from ecotrack_agents.memory import SharedMemory
from ecotrack_agents.orchestrator import AgentOrchestrator
from ecotrack_agents.specialists import (
    BiodiversityMonitorAgent,
    ClimateAnalystAgent,
    FoodSecurityAdvisorAgent,
    HealthSentinelAgent,
    ResourceOptimizerAgent,
)
from ecotrack_agents.tools import ToolRegistry

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # Base abstractions
    "AgentMessage",
    "AgentRole",
    "AgentState",
    "BaseAgent",
    "MessageType",
    "ToolDefinition",
    # Orchestrator
    "AgentOrchestrator",
    # Specialists
    "ClimateAnalystAgent",
    "BiodiversityMonitorAgent",
    "HealthSentinelAgent",
    "FoodSecurityAdvisorAgent",
    "ResourceOptimizerAgent",
    # Memory
    "SharedMemory",
    # Tools
    "ToolRegistry",
]
