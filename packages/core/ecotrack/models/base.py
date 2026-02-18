"""Base domain models for EcoTrack."""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Domain(str, Enum):
    """Core EcoTrack domains."""

    CLIMATE = "climate"
    BIODIVERSITY = "biodiversity"
    HEALTH = "health"
    FOOD_SECURITY = "food_security"
    RESOURCE_EQUITY = "resource_equity"


class Severity(str, Enum):
    """Alert/event severity levels."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EcoTrackModel(BaseModel):
    """Base model with common fields."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


__all__ = [
    "Domain",
    "Severity",
    "EcoTrackModel",
]
