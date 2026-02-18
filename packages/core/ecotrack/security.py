"""Security utilities for EcoTrack."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def generate_api_key(prefix: str = "eco") -> str:
    """Generate a secure API key."""
    random_part = secrets.token_urlsafe(32)
    return f"{prefix}_{random_part}"


def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(api_key: str, hashed: str) -> bool:
    """Verify API key against stored hash."""
    return hmac.compare_digest(hash_api_key(api_key), hashed)


def sanitize_input(value: str, max_length: int = 1000) -> str:
    """Sanitize user input to prevent injection attacks."""
    # Truncate
    value = value[:max_length]
    # Remove null bytes
    value = value.replace("\x00", "")
    # Strip leading/trailing whitespace
    value = value.strip()
    return value


def validate_bbox(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> bool:
    """Validate bounding box coordinates."""
    if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180):
        return False
    if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90):
        return False
    if min_lon > max_lon or min_lat > max_lat:
        return False
    return True


def validate_cypher_input(value: str) -> bool:
    """Validate input used in Cypher queries to prevent injection."""
    dangerous_patterns = [
        r"(?i)\bDROP\b",
        r"(?i)\bDELETE\b",
        r"(?i)\bDETACH\b",
        r"(?i)\bCALL\b.*\bdbms\b",
        r"(?i)\bLOAD\s+CSV\b",
    ]
    for pattern in dangerous_patterns:
        if re.search(pattern, value):
            logger.warning("security.cypher_injection_attempt", value=value[:100])
            return False
    return True


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, rate: float, burst: int) -> None:
        self.rate = rate
        self.burst = burst
        self._tokens: dict[str, float] = {}
        self._last_refill: dict[str, float] = {}

    def allow(self, key: str) -> bool:
        """Check if request is allowed."""
        import time

        now = time.time()

        if key not in self._tokens:
            self._tokens[key] = float(self.burst)
            self._last_refill[key] = now

        elapsed = now - self._last_refill[key]
        self._tokens[key] = min(self.burst, self._tokens[key] + elapsed * self.rate)
        self._last_refill[key] = now

        if self._tokens[key] >= 1:
            self._tokens[key] -= 1
            return True
        return False


class ContentSecurityPolicy:
    """Generate Content-Security-Policy headers."""

    @staticmethod
    def get_headers() -> dict[str, str]:
        return {
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' http://localhost:* https://*",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        }
