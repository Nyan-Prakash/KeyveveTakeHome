"""JWT token creation and verification."""

import jwt
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from backend.app.config import get_settings


class TokenPayload(BaseModel):
    """JWT token payload."""
    user_id: UUID
    org_id: UUID
    token_type: Literal["access", "refresh"]
    issued_at: datetime
    expires_at: datetime


class AuthenticationError(Exception):
    """Authentication-related errors."""
    pass


def get_jwt_private_key() -> str:
    """Get JWT private key from settings."""
    settings = get_settings()
    key = settings.jwt_private_key_pem.strip()
    
    if key.startswith("dummy-"):
        raise AuthenticationError(
            "JWT private key not configured. Set JWT_PRIVATE_KEY_PEM in environment."
        )
    
    return key


def get_jwt_public_key() -> str:
    """Get JWT public key from settings.""" 
    settings = get_settings()
    key = settings.jwt_public_key_pem.strip()
    
    if key.startswith("dummy-"):
        raise AuthenticationError(
            "JWT public key not configured. Set JWT_PUBLIC_KEY_PEM in environment."
        )
    
    return key


def create_access_token(user_id: UUID, org_id: UUID) -> str:
    """Create JWT access token with 15min expiry.
    
    Args:
        user_id: User UUID
        org_id: Organization UUID
        
    Returns:
        Encoded JWT token string
        
    Raises:
        AuthenticationError: If JWT keys not configured
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=settings.jwt_access_ttl_minutes)
    
    payload = {
        "sub": str(user_id),
        "org_id": str(org_id),
        "iat": now,
        "exp": expires,
        "type": "access",
        "jti": f"acc_{user_id}_{int(now.timestamp())}"  # Unique token ID
    }
    
    return jwt.encode(payload, get_jwt_private_key(), algorithm="RS256")


def create_refresh_token(user_id: UUID, org_id: UUID) -> str:
    """Create JWT refresh token with 7day expiry.
    
    Args:
        user_id: User UUID
        org_id: Organization UUID
        
    Returns:
        Encoded JWT refresh token string
        
    Raises:
        AuthenticationError: If JWT keys not configured
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=settings.jwt_refresh_ttl_days)
    
    payload = {
        "sub": str(user_id),
        "org_id": str(org_id),
        "iat": now,
        "exp": expires,
        "type": "refresh",
        "jti": f"ref_{user_id}_{int(now.timestamp())}"  # Unique token ID
    }
    
    return jwt.encode(payload, get_jwt_private_key(), algorithm="RS256")


def verify_access_token(token: str) -> TokenPayload:
    """Verify and decode JWT access token.
    
    Args:
        token: JWT token string
        
    Returns:
        TokenPayload with user and org info
        
    Raises:
        AuthenticationError: If token is invalid, expired, or wrong type
    """
    try:
        payload = jwt.decode(token, get_jwt_public_key(), algorithms=["RS256"])
        
        # Verify token type
        if payload.get("type") != "access":
            raise AuthenticationError("Invalid token type")
        
        return TokenPayload(
            user_id=UUID(payload["sub"]),
            org_id=UUID(payload["org_id"]),
            token_type=payload["type"],
            issued_at=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        )
        
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise AuthenticationError(f"Invalid token: {e}")
    except (KeyError, ValueError) as e:
        raise AuthenticationError(f"Malformed token payload: {e}")


def verify_refresh_token(token: str) -> TokenPayload:
    """Verify and decode JWT refresh token.
    
    Args:
        token: JWT refresh token string
        
    Returns:
        TokenPayload with user and org info
        
    Raises:
        AuthenticationError: If token is invalid, expired, or wrong type
    """
    try:
        payload = jwt.decode(token, get_jwt_public_key(), algorithms=["RS256"])
        
        # Verify token type
        if payload.get("type") != "refresh":
            raise AuthenticationError("Invalid token type")
        
        return TokenPayload(
            user_id=UUID(payload["sub"]),
            org_id=UUID(payload["org_id"]),
            token_type=payload["type"],
            issued_at=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        )
        
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Refresh token has expired")
    except jwt.InvalidTokenError as e:
        raise AuthenticationError(f"Invalid refresh token: {e}")
    except (KeyError, ValueError) as e:
        raise AuthenticationError(f"Malformed refresh token payload: {e}")


def extract_token_jti(token: str) -> str:
    """Extract JTI (token ID) from token without verification.
    
    Used for token revocation tracking.
    
    Args:
        token: JWT token string
        
    Returns:
        Token JTI string
        
    Raises:
        AuthenticationError: If token format is invalid
    """
    try:
        # Decode without verification to get JTI for revocation
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload.get("jti", "")
    except Exception as e:
        raise AuthenticationError(f"Could not extract token ID: {e}")
