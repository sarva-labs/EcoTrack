"""Shared test fixtures for EcoTrack."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import AsyncIterator

import numpy as np
import pytest


@pytest.fixture
def sample_bbox() -> tuple[float, float, float, float]:
    """Sample bounding box (San Francisco area)."""
    return (-122.5, 37.7, -122.3, 37.9)


@pytest.fixture
def sample_time_range() -> tuple[datetime, datetime]:
    """Sample time range (last 30 days)."""
    end = datetime.utcnow()
    start = end - timedelta(days=30)
    return (start, end)


@pytest.fixture
def sample_uuid() -> str:
    return str(uuid.uuid4())
