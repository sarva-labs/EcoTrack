"""Tests for agent orchestrator."""
from __future__ import annotations

import pytest

from ecotrack_agents.base import AgentRole, MessageType, AgentMessage
from ecotrack_agents.memory import SharedMemory


class TestAgentMessage:
    def test_create_message(self) -> None:
        msg = AgentMessage(
            sender="agent_1",
            recipient="agent_2",
            type=MessageType.QUERY,
            content={"query": "What is the current temperature?"},
        )
        assert msg.sender == "agent_1"
        assert msg.type == MessageType.QUERY

    def test_broadcast_message(self) -> None:
        msg = AgentMessage(sender="orchestrator", type=MessageType.BROADCAST, content={"alert": "test"})
        assert msg.recipient == ""


class TestSharedMemory:
    def test_store_and_retrieve(self) -> None:
        memory = SharedMemory()
        memory.store("key1", {"data": "test"})
        result = memory.retrieve("key1")
        assert result == {"data": "test"}

    def test_retrieve_missing(self) -> None:
        memory = SharedMemory()
        result = memory.retrieve("nonexistent")
        assert result is None

    def test_conversation_history(self) -> None:
        memory = SharedMemory()
        memory.add_to_conversation("session1", {"role": "user", "content": "hello"})
        memory.add_to_conversation("session1", {"role": "assistant", "content": "hi"})
        history = memory.get_conversation_history("session1")
        assert len(history) == 2
