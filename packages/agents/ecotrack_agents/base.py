"""Base agent abstractions for the EcoTrack multi-agent system."""
from __future__ import annotations

import abc
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

import structlog

logger = structlog.get_logger(__name__)


class AgentRole(str, Enum):
    """Specialized agent roles."""

    CLIMATE_ANALYST = "climate_analyst"
    BIODIVERSITY_MONITOR = "biodiversity_monitor"
    HEALTH_SENTINEL = "health_sentinel"
    FOOD_SECURITY_ADVISOR = "food_security_advisor"
    RESOURCE_OPTIMIZER = "resource_optimizer"
    DATA_CURATOR = "data_curator"
    ORCHESTRATOR = "orchestrator"


class MessageType(str, Enum):
    """Inter-agent message types."""

    QUERY = "query"
    RESPONSE = "response"
    TASK = "task"
    RESULT = "result"
    ALERT = "alert"
    BROADCAST = "broadcast"
    HEARTBEAT = "heartbeat"


@dataclass
class AgentMessage:
    """Message passed between agents.

    Attributes:
        id: Unique message identifier.
        sender: Agent ID of the sender.
        recipient: Agent ID of the recipient (empty string for broadcast).
        type: The message type classification.
        content: Arbitrary payload dictionary.
        timestamp: UTC timestamp when the message was created.
        correlation_id: Optional ID for request-response tracking.
        priority: Priority level where 1 is highest and 10 is lowest.
        metadata: Additional metadata for the message.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender: str = ""
    recipient: str = ""  # Empty = broadcast
    type: MessageType = MessageType.QUERY
    content: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    correlation_id: str | None = None  # For request-response tracking
    priority: int = 5  # 1=highest, 10=lowest
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentState:
    """Current state of an agent.

    Attributes:
        agent_id: Unique identifier for the agent.
        role: The agent's assigned role.
        status: Current operational status (idle, processing, waiting, error).
        current_task: Description of the task currently being processed.
        memory: Rolling list of memory entries (bounded to 100).
        context: Contextual information for the current session.
        last_active: Timestamp of the last activity.
    """

    agent_id: str
    role: AgentRole
    status: str = "idle"  # idle, processing, waiting, error
    current_task: str | None = None
    memory: list[dict[str, Any]] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    last_active: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ToolDefinition:
    """Definition of a tool available to agents.

    Attributes:
        name: Unique tool name.
        description: Human-readable description of what the tool does.
        parameters: JSON Schema dictionary describing expected parameters.
        handler: Optional callable that executes the tool logic.
        required_role: If set, only agents with this role may use the tool.
    """

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema for parameters
    handler: Callable[..., Any] | None = None
    required_role: AgentRole | None = None


class BaseAgent(abc.ABC):
    """Abstract base class for all EcoTrack agents.

    Provides common infrastructure for message processing, tool usage,
    memory management, and planning/execution lifecycle.

    Subclasses must implement:
        - :meth:`process_message` — Handle incoming messages.
        - :meth:`plan` — Decompose a task into executable steps.
        - :meth:`execute_step` — Run a single step from a plan.
    """

    def __init__(
        self,
        agent_id: str,
        role: AgentRole,
        tools: list[ToolDefinition] | None = None,
    ) -> None:
        """Initialize the base agent.

        Args:
            agent_id: Unique identifier for this agent.
            role: The role this agent fulfills.
            tools: Optional list of tool definitions available to the agent.
        """
        self.agent_id = agent_id
        self.role = role
        self.tools: dict[str, ToolDefinition] = {t.name: t for t in (tools or [])}
        self.state = AgentState(agent_id=agent_id, role=role)
        self._message_handlers: dict[MessageType, Callable[..., Any]] = {}
        self._inbox: list[AgentMessage] = []
        self._log = logger.bind(agent_id=agent_id, role=role.value)

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abc.abstractmethod
    async def process_message(self, message: AgentMessage) -> AgentMessage | None:
        """Process an incoming message and optionally return a response.

        Args:
            message: The inbound :class:`AgentMessage`.

        Returns:
            An optional response message, or ``None`` if no reply is needed.
        """
        ...

    @abc.abstractmethod
    async def plan(self, task: str, context: dict[str, Any]) -> list[dict[str, Any]]:
        """Create an execution plan for a given task.

        Args:
            task: Natural-language task description.
            context: Contextual data that may inform planning.

        Returns:
            Ordered list of step dictionaries, each containing at minimum
            ``action`` and ``params`` keys.
        """
        ...

    @abc.abstractmethod
    async def execute_step(self, step: dict[str, Any]) -> dict[str, Any]:
        """Execute a single step from the plan.

        Args:
            step: Step dictionary with ``action`` and ``params``.

        Returns:
            Result dictionary with at minimum a ``status`` key.
        """
        ...

    # ------------------------------------------------------------------
    # Tool usage
    # ------------------------------------------------------------------

    async def use_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Use a registered tool.

        Args:
            tool_name: Name of the tool to invoke.
            **kwargs: Keyword arguments forwarded to the tool handler.

        Returns:
            The tool handler's return value.

        Raises:
            ValueError: If the tool is not registered.
            RuntimeError: If the tool has no handler attached.
        """
        if tool_name not in self.tools:
            raise ValueError(
                f"Tool '{tool_name}' not available. Available: {list(self.tools.keys())}"
            )
        tool = self.tools[tool_name]
        if tool.handler is None:
            raise RuntimeError(f"Tool '{tool_name}' has no handler registered")

        self._log.debug("using_tool", tool=tool_name, kwargs=list(kwargs.keys()))
        if asyncio.iscoroutinefunction(tool.handler):
            return await tool.handler(**kwargs)
        return tool.handler(**kwargs)

    # ------------------------------------------------------------------
    # Memory management
    # ------------------------------------------------------------------

    def add_to_memory(self, entry: dict[str, Any]) -> None:
        """Add an entry to agent memory (bounded to 100 entries).

        Args:
            entry: Arbitrary dictionary to store in memory.
        """
        self.state.memory.append(
            {**entry, "timestamp": datetime.utcnow().isoformat()}
        )
        if len(self.state.memory) > 100:
            self.state.memory = self.state.memory[-100:]

    # ------------------------------------------------------------------
    # Messaging helpers
    # ------------------------------------------------------------------

    def send_message(
        self,
        recipient: str,
        msg_type: MessageType,
        content: dict[str, Any],
        correlation_id: str | None = None,
    ) -> AgentMessage:
        """Create a message to send.

        Args:
            recipient: Target agent ID (empty string for broadcast).
            msg_type: The type of message.
            content: Payload dictionary.
            correlation_id: Optional correlation ID for request-response flows.

        Returns:
            A fully populated :class:`AgentMessage` ready for dispatch.
        """
        return AgentMessage(
            sender=self.agent_id,
            recipient=recipient,
            type=msg_type,
            content=content,
            correlation_id=correlation_id,
        )

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    async def run_task(self, task: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Plan and execute a full task end-to-end.

        Convenience method that calls :meth:`plan` followed by
        :meth:`execute_step` for each step, collecting results.

        Args:
            task: Natural-language task description.
            context: Optional contextual data.

        Returns:
            Dictionary containing ``steps`` (list of results) and ``status``.
        """
        ctx = context or {}
        self.state.status = "processing"
        self.state.current_task = task
        self.state.last_active = datetime.utcnow()
        self._log.info("running_task", task=task)

        try:
            steps = await self.plan(task, ctx)
            results: list[dict[str, Any]] = []
            for step in steps:
                self._log.debug("executing_step", step=step.get("action"))
                result = await self.execute_step(step)
                results.append(result)
                self.add_to_memory({"step": step, "result": result})

            self.state.status = "idle"
            self.state.current_task = None
            return {"status": "completed", "steps": results}
        except Exception as exc:
            self.state.status = "error"
            self._log.error("task_failed", error=str(exc))
            return {"status": "error", "error": str(exc)}

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.agent_id!r}, role={self.role.value!r})>"


__all__ = [
    "AgentRole",
    "MessageType",
    "AgentMessage",
    "AgentState",
    "ToolDefinition",
    "BaseAgent",
]
