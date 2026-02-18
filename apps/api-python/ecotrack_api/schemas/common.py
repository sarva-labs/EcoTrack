"""Common API schemas shared across domains."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=50, ge=1, le=1000, description="Items per page")


class BBoxQuery(BaseModel):
    """Bounding box spatial query."""

    min_lon: float = Field(ge=-180, le=180, description="Minimum longitude")
    min_lat: float = Field(ge=-90, le=90, description="Minimum latitude")
    max_lon: float = Field(ge=-180, le=180, description="Maximum longitude")
    max_lat: float = Field(ge=-90, le=90, description="Maximum latitude")


class TimeRangeQuery(BaseModel):
    """Temporal range query."""

    start_time: datetime = Field(description="Start of the time range (ISO 8601)")
    end_time: datetime = Field(description="End of the time range (ISO 8601)")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""

    items: list[T]
    total: int = Field(description="Total number of items matching the query")
    page: int = Field(description="Current page number")
    page_size: int = Field(description="Number of items per page")
    has_next: bool = Field(description="Whether more pages are available")


class ErrorResponse(BaseModel):
    """Standardised API error response."""

    error: str = Field(description="Short error identifier")
    detail: str = Field(description="Human-readable error description")
    status_code: int = Field(description="HTTP status code")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SuccessResponse(BaseModel):
    """Generic success response."""

    message: str = Field(description="Success message")
    data: dict[str, Any] = Field(default_factory=dict, description="Optional payload")
