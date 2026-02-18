"""Authentication and authorization for EcoTrack API."""
from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel


class UserRole(str, Enum):
    """User role hierarchy."""

    PUBLIC = "public"
    RESEARCHER = "researcher"
    ADMIN = "admin"


class TokenPayload(BaseModel):
    """JWT token payload."""

    sub: str  # user ID
    role: UserRole
    exp: datetime
    iat: datetime


class APIUser(BaseModel):
    """Authenticated API user context."""

    id: str
    email: str
    role: UserRole
    permissions: list[str] = []


# ---------------------------------------------------------------------------
# Security schemes
# ---------------------------------------------------------------------------
bearer_scheme = HTTPBearer(auto_error=False)
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)

SECRET_KEY = "ecotrack-dev-secret-change-in-production"  # From env in production
ALGORITHM = "HS256"


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def create_access_token(
    user_id: str,
    role: UserRole,
    expires_delta: timedelta = timedelta(hours=24),
) -> str:
    """Create a JWT access token."""
    now = datetime.utcnow()
    payload = {
        "sub": user_id,
        "role": role.value,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ---------------------------------------------------------------------------
# Dependency: extract current user
# ---------------------------------------------------------------------------

async def get_current_user(
    bearer: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    api_key: str | None = Security(api_key_scheme),
) -> APIUser:
    """Extract the current user from a JWT bearer token or API key.

    Falls back to an anonymous public user when no credentials are provided.
    """
    if bearer:
        try:
            payload = jwt.decode(bearer.credentials, SECRET_KEY, algorithms=[ALGORITHM])
            return APIUser(
                id=payload["sub"],
                email=f"{payload['sub']}@ecotrack.earth",
                role=UserRole(payload["role"]),
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

    if api_key:
        # Simple API key validation — in production, look up in database
        if api_key.startswith("eco_"):
            return APIUser(
                id="api-user",
                email="api@ecotrack.earth",
                role=UserRole.RESEARCHER,
            )
        raise HTTPException(status_code=401, detail="Invalid API key")

    # No credentials supplied — anonymous / public access
    return APIUser(id="anonymous", email="", role=UserRole.PUBLIC)


# ---------------------------------------------------------------------------
# Dependency: role guard
# ---------------------------------------------------------------------------

_ROLE_HIERARCHY = {UserRole.PUBLIC: 0, UserRole.RESEARCHER: 1, UserRole.ADMIN: 2}


def require_role(minimum_role: UserRole):
    """FastAPI dependency that enforces a minimum user role."""

    async def _check_role(user: APIUser = Depends(get_current_user)) -> APIUser:
        if _ROLE_HIERARCHY.get(user.role, 0) < _ROLE_HIERARCHY[minimum_role]:
            raise HTTPException(
                status_code=403,
                detail=f"Requires {minimum_role.value} role or higher",
            )
        return user

    return _check_role
