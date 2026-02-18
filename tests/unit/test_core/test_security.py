"""Tests for security utilities."""
from __future__ import annotations

from ecotrack.security import (
    generate_api_key,
    hash_api_key,
    verify_api_key,
    sanitize_input,
    validate_bbox,
    validate_cypher_input,
    RateLimiter,
)


class TestAPIKeyManagement:
    def test_generate_api_key(self) -> None:
        key = generate_api_key()
        assert key.startswith("eco_")
        assert len(key) > 20

    def test_generate_api_key_custom_prefix(self) -> None:
        key = generate_api_key(prefix="test")
        assert key.startswith("test_")

    def test_hash_and_verify(self) -> None:
        key = generate_api_key()
        hashed = hash_api_key(key)
        assert verify_api_key(key, hashed)
        assert not verify_api_key("wrong_key", hashed)


class TestInputSanitization:
    def test_sanitize_normal_input(self) -> None:
        assert sanitize_input("hello world") == "hello world"

    def test_sanitize_null_bytes(self) -> None:
        assert "\x00" not in sanitize_input("hello\x00world")

    def test_sanitize_truncation(self) -> None:
        result = sanitize_input("a" * 2000, max_length=100)
        assert len(result) == 100

    def test_validate_bbox_valid(self) -> None:
        assert validate_bbox(-122.5, 37.7, -122.3, 37.9)

    def test_validate_bbox_invalid(self) -> None:
        assert not validate_bbox(-200, 0, 0, 0)
        assert not validate_bbox(0, 0, -10, 10)  # min_lon > max_lon


class TestCypherValidation:
    def test_valid_input(self) -> None:
        assert validate_cypher_input("temperature")
        assert validate_cypher_input("San Francisco")

    def test_dangerous_input(self) -> None:
        assert not validate_cypher_input("MATCH (n) DETACH DELETE n")
        assert not validate_cypher_input("DROP something")


class TestRateLimiter:
    def test_allows_within_limit(self) -> None:
        limiter = RateLimiter(rate=10.0, burst=5)
        for _ in range(5):
            assert limiter.allow("test-key")

    def test_blocks_over_limit(self) -> None:
        limiter = RateLimiter(rate=0.0, burst=2)
        assert limiter.allow("test-key")
        assert limiter.allow("test-key")
        assert not limiter.allow("test-key")
