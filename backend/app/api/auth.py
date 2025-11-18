"""Authentication API endpoints and dependencies."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

__all__ = ["CurrentUser", "get_current_user", "router"]

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from backend.app.db.models.user import User
from backend.app.db.models.org import Org
from backend.app.db.session import get_session
from backend.app.security import (
    verify_access_token,
    verify_refresh_token,
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    check_and_update_lockout,
    AuthenticationError,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


# Pydantic models
class LoginRequest(BaseModel):
    """Login request payload."""
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    """Authentication response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900  # 15 minutes in seconds


class RefreshRequest(BaseModel):
    """Refresh token request."""
    refresh_token: str


class CurrentUser(BaseModel):
    """Current authenticated user context."""
    org_id: UUID
    user_id: UUID
    email: str


class CreateUserRequest(BaseModel):
    """Create user request (admin only)."""
    email: EmailStr
    password: str
    role: str = "MEMBER"


# HTTP Bearer token security scheme
bearer_scheme = HTTPBearer()


# Updated dependency with real JWT verification
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_session)
) -> CurrentUser:
    """Get current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Authorization header with Bearer token
        db: Database session
        
    Returns:
        CurrentUser with org_id, user_id, and email
        
    Raises:
        HTTPException: If token is missing, invalid, or user not found
    """
    try:
        if not credentials or not credentials.credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authorization token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verify JWT token
        payload = verify_access_token(credentials.credentials)
        
        # Verify user still exists
        user = db.query(User).filter(User.user_id == payload.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if user is locked
        if user.locked_until and user.locked_until > datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account locked",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return CurrentUser(
            org_id=user.org_id,
            user_id=user.user_id,
            email=user.email
        )
        
    except AuthenticationError as e:
        # Handle specific auth errors
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Handle any other errors
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_session)
) -> AuthResponse:
    """Authenticate user and return JWT tokens.
    
    Returns:
        AuthResponse with access and refresh tokens
        
    Raises:
        HTTPException: If authentication fails or account is locked
    """
    try:
        # Find user by email
        user = db.query(User).filter(User.email == request.email).first()
        if not user:
            # Don't reveal whether email exists
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Check account lockout status  
        lockout_status = await check_and_update_lockout(user.user_id, False)
        if lockout_status.locked:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail={
                    "error": "Account temporarily locked",
                    "locked_until": lockout_status.locked_until.isoformat(),
                    "reason": "Too many failed login attempts"
                }
            )
        
        # Check if user is currently locked (database lockout)
        if user.locked_until and user.locked_until > datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail={
                    "error": "Account locked",
                    "locked_until": user.locked_until.isoformat(),
                    "contact": "Contact administrator to unlock"
                }
            )
        
        # Verify password
        password_valid = verify_password(request.password, user.password_hash)
        
        if not password_valid:
            # Update lockout for failed attempt
            await check_and_update_lockout(user.user_id, True)
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Success - clear any lockout and create tokens
        await check_and_update_lockout(user.user_id, False)
        
        access_token = create_access_token(user.user_id, user.org_id)
        refresh_token = create_refresh_token(user.user_id, user.org_id)
        
        return AuthResponse(
            access_token=access_token,
            refresh_token=refresh_token
        )
        
    except HTTPException:
        raise
    except Exception as e:
        # Log the actual error for debugging
        print(f"❌ Login error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication service error: {str(e)}"
        )


@router.post("/signup", response_model=AuthResponse)
async def signup(
    request: CreateUserRequest,
    db: Session = Depends(get_session)
) -> AuthResponse:
    """Create a new user account and return JWT tokens.
    
    Returns:
        AuthResponse with access and refresh tokens
        
    Raises:
        HTTPException: If email already exists or signup fails
    """
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == request.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Get or create default org
        org = db.query(Org).first()
        if not org:
            org = Org(
                org_id=uuid4(),
                name="Default Organization", 
                created_at=datetime.now(timezone.utc)
            )
            db.add(org)
            db.flush()
        
        # Hash password and create user
        password_hash = hash_password(request.password)
        user = User(
            user_id=uuid4(),
            org_id=org.org_id,
            email=request.email,
            password_hash=password_hash,
            created_at=datetime.now(timezone.utc)
        )
        
        db.add(user)
        db.commit()
        
        # Create tokens for immediate login
        access_token = create_access_token(user.user_id, user.org_id)
        refresh_token = create_refresh_token(user.user_id, user.org_id)
        
        return AuthResponse(
            access_token=access_token,
            refresh_token=refresh_token
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Signup error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Signup service error: {str(e)}"
        )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(
    request: RefreshRequest,
    db: Session = Depends(get_session)
) -> AuthResponse:
    """Refresh access token using refresh token.
    
    Returns:
        New AuthResponse with fresh tokens
        
    Raises:
        HTTPException: If refresh token is invalid or user not found
    """
    try:
        # Verify refresh token
        payload = verify_refresh_token(request.refresh_token)
        
        # Verify user still exists and is active
        user = db.query(User).filter(User.user_id == payload.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        # Check if user is locked
        if user.locked_until and user.locked_until > datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account locked"
            )
        
        # Create new tokens
        access_token = create_access_token(user.user_id, user.org_id)
        refresh_token = create_refresh_token(user.user_id, user.org_id)
        
        # TODO: Store new refresh token hash and invalidate old one
        
        return AuthResponse(
            access_token=access_token,
            refresh_token=refresh_token
        )
        
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh service temporarily unavailable"
        )


@router.post("/logout")
async def logout() -> dict[str, str]:
    """Logout user by invalidating tokens.
    
    Note: In a complete implementation, this would add the token JTI
    to a blacklist in Redis to prevent reuse.
    
    Returns:
        Success message
    """
    # TODO: Extract JTI from token and add to blacklist
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=CurrentUser)
async def get_current_user_info(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_session)
) -> CurrentUser:
    """Get current user information.
    
    Returns:
        Current user details
    """
    user = db.query(User).filter(User.user_id == current_user.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return CurrentUser(
        org_id=user.org_id,
        user_id=user.user_id,
        email=user.email
    )
