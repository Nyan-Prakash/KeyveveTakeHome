"""Authentication dependencies for FastAPI.

In PR4, this is a stub implementation that returns a fixed org/user.
Real JWT authentication will be implemented in PR10.
"""

from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel


class CurrentUser(BaseModel):
    """Current authenticated user context."""

    org_id: UUID
    user_id: UUID


# HTTP Bearer token security scheme
bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentUser:
    """Get current authenticated user from JWT token.

    In PR4, this is a stub that returns a fixed org/user for testing.
    Real JWT verification will be added in PR10.

    Args:
        credentials: HTTP Authorization header with Bearer token

    Returns:
        CurrentUser with org_id and user_id

    Raises:
        HTTPException: If token is missing or invalid
    """
    # For PR4, accept any non-empty token and return fixed test user
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Stub: return fixed test org/user
    # In PR10, this will verify JWT and extract real org_id/user_id
    return CurrentUser(
        org_id=UUID("00000000-0000-0000-0000-000000000001"),
        user_id=UUID("00000000-0000-0000-0000-000000000002"),
    )
