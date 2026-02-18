"""Tool registry for EcoTrack agents."""
from __future__ import annotations

from typing import Any

import structlog

from ecotrack_agents.base import AgentRole, ToolDefinition

logger = structlog.get_logger(__name__)


class ToolRegistry:
    """Singleton registry of all available tools for EcoTrack agents.

    Provides centralised registration, lookup, and role-based filtering
    of :class:`ToolDefinition` instances used across the multi-agent system.

    Usage::

        registry = ToolRegistry()
        registry.register(my_tool)
        tools = registry.list_tools()
    """

    _instance: ToolRegistry | None = None
    _tools: dict[str, ToolDefinition]

    def __new__(cls) -> ToolRegistry:
        """Ensure only one registry instance exists (singleton)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
        return cls._instance

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool definition.

        Args:
            tool: The tool to register. If a tool with the same name
                  already exists it will be overwritten with a warning.
        """
        if tool.name in self._tools:
            logger.warning("tool_overwritten", tool=tool.name)
        self._tools[tool.name] = tool
        logger.debug("tool_registered", tool=tool.name)

    def get(self, name: str) -> ToolDefinition:
        """Retrieve a tool by name.

        Args:
            name: Unique tool name.

        Returns:
            The matching :class:`ToolDefinition`.

        Raises:
            KeyError: If no tool with the given name is registered.
        """
        if name not in self._tools:
            raise KeyError(
                f"Tool '{name}' not found. Available: {list(self._tools.keys())}"
            )
        return self._tools[name]

    def list_tools(self, role: AgentRole | None = None) -> list[ToolDefinition]:
        """List registered tools, optionally filtered by role.

        Args:
            role: If provided, return only tools that either have no
                  ``required_role`` restriction **or** whose
                  ``required_role`` matches the given role.

        Returns:
            List of matching tool definitions.
        """
        if role is None:
            return list(self._tools.values())
        return [
            t
            for t in self._tools.values()
            if t.required_role is None or t.required_role == role
        ]

    def get_tools_for_role(self, role: AgentRole) -> list[ToolDefinition]:
        """Get all tools accessible to a specific agent role.

        Convenience wrapper around :meth:`list_tools` with a role filter.

        Args:
            role: The agent role to filter for.

        Returns:
            List of tool definitions available to that role.
        """
        return self.list_tools(role=role)

    def reset(self) -> None:
        """Clear all registered tools. Useful in tests."""
        self._tools.clear()

    @property
    def tool_names(self) -> list[str]:
        """Return a sorted list of all registered tool names."""
        return sorted(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __repr__(self) -> str:
        return f"<ToolRegistry(tools={len(self._tools)})>"


__all__ = ["ToolRegistry"]
