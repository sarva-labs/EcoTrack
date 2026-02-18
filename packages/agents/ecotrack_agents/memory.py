"""Shared memory system for agent coordination.

Provides an in-memory key-value store with optional TTL expiry,
keyword search, and conversation history management.  Designed as
a lightweight coordination substrate that can be backed by Redis
in production.
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class _MemoryEntry:
    """Internal wrapper that pairs a value with an optional expiry."""

    value: Any
    expires_at: float | None = None  # epoch seconds; *None* = never expires


@dataclass
class ConversationTurn:
    """A single turn in a conversation.

    Attributes:
        role: ``user``, ``agent``, or ``system``.
        content: The message content (string or dict).
        agent_id: ID of the agent that produced the turn (if applicable).
        timestamp: Epoch-seconds timestamp.
    """

    role: str
    content: Any
    agent_id: str | None = None
    timestamp: float = field(default_factory=time.time)


class SharedMemory:
    """In-memory shared store for multi-agent coordination.

    Features
    --------
    * Key-value storage with optional TTL.
    * Simple keyword search across stored values.
    * Per-session conversation history tracking.

    In production, swap the internal dicts for a Redis backend by
    subclassing and overriding the storage methods.
    """

    def __init__(self, max_conversation_length: int = 200) -> None:
        """Initialise the shared memory.

        Args:
            max_conversation_length: Maximum number of turns kept per
                conversation session.
        """
        self._store: dict[str, _MemoryEntry] = {}
        self._conversations: dict[str, list[ConversationTurn]] = defaultdict(list)
        self._max_conv_len = max_conversation_length
        self._log = logger.bind(component="shared_memory")

    # ------------------------------------------------------------------
    # Key-value operations
    # ------------------------------------------------------------------

    def store(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Store a value with an optional time-to-live.

        Args:
            key: Storage key.
            value: Arbitrary value to store.
            ttl_seconds: If set, the entry expires after this many seconds.
        """
        expires_at = (time.time() + ttl_seconds) if ttl_seconds else None
        self._store[key] = _MemoryEntry(value=value, expires_at=expires_at)
        self._log.debug("stored", key=key, ttl=ttl_seconds)

    def retrieve(self, key: str) -> Any | None:
        """Retrieve a value by key.

        Returns *None* if the key does not exist or has expired.

        Args:
            key: Storage key.

        Returns:
            The stored value, or *None*.
        """
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.expires_at is not None and time.time() > entry.expires_at:
            del self._store[key]
            self._log.debug("entry_expired", key=key)
            return None
        return entry.value

    def delete(self, key: str) -> bool:
        """Delete a key from the store.

        Args:
            key: Storage key.

        Returns:
            ``True`` if the key existed and was removed.
        """
        if key in self._store:
            del self._store[key]
            return True
        return False

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Search stored values by keyword matching.

        Performs a case-insensitive substring match against the string
        representation of each stored value.

        Args:
            query: The search query string.
            top_k: Maximum number of results to return.

        Returns:
            List of dicts with ``key`` and ``value`` for matching entries.
        """
        self._evict_expired()
        query_lower = query.lower()
        results: list[dict[str, Any]] = []
        for key, entry in self._store.items():
            value_str = str(entry.value).lower()
            if query_lower in value_str:
                results.append({"key": key, "value": entry.value})
                if len(results) >= top_k:
                    break
        return results

    # ------------------------------------------------------------------
    # Conversation history
    # ------------------------------------------------------------------

    def get_conversation_history(self, session_id: str) -> list[dict[str, Any]]:
        """Retrieve the conversation history for a session.

        Args:
            session_id: Unique session identifier.

        Returns:
            List of turn dictionaries with ``role``, ``content``,
            ``agent_id``, and ``timestamp``.
        """
        return [
            {
                "role": turn.role,
                "content": turn.content,
                "agent_id": turn.agent_id,
                "timestamp": turn.timestamp,
            }
            for turn in self._conversations.get(session_id, [])
        ]

    def add_to_conversation(
        self,
        session_id: str,
        message: dict[str, Any],
    ) -> None:
        """Add a message to a conversation session.

        The *message* dict should contain at least a ``role`` and
        ``content`` key.

        Args:
            session_id: Unique session identifier.
            message: Message dictionary to append.
        """
        turn = ConversationTurn(
            role=message.get("role", "system"),
            content=message.get("content", ""),
            agent_id=message.get("agent_id"),
        )
        conv = self._conversations[session_id]
        conv.append(turn)
        if len(conv) > self._max_conv_len:
            self._conversations[session_id] = conv[-self._max_conv_len:]
        self._log.debug(
            "conversation_updated",
            session_id=session_id,
            length=len(self._conversations[session_id]),
        )

    def clear_conversation(self, session_id: str) -> None:
        """Clear conversation history for a session.

        Args:
            session_id: Unique session identifier.
        """
        self._conversations.pop(session_id, None)

    # ------------------------------------------------------------------
    # Housekeeping
    # ------------------------------------------------------------------

    def _evict_expired(self) -> None:
        """Remove all expired entries from the store."""
        now = time.time()
        expired_keys = [
            k for k, e in self._store.items()
            if e.expires_at is not None and now > e.expires_at
        ]
        for k in expired_keys:
            del self._store[k]

    def clear(self) -> None:
        """Clear all data from the shared memory."""
        self._store.clear()
        self._conversations.clear()

    @property
    def size(self) -> int:
        """Number of non-expired entries in the key-value store."""
        self._evict_expired()
        return len(self._store)

    def __repr__(self) -> str:
        return (
            f"<SharedMemory(entries={len(self._store)}, "
            f"conversations={len(self._conversations)})>"
        )


__all__ = ["SharedMemory", "ConversationTurn"]
