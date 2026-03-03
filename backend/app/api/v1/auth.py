"""Authentication API routes."""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.rate_limit import limiter
from app.schemas.user import UserCreate, UserLogin, UserResponse, TokenResponse, TokenRefresh
from app.services.auth_service import (
    register_user,
    authenticate_user,
    create_tokens,
    refresh_access_token,
    get_current_user
)
from app.core.jwt import get_user_id_from_token
from app.db.models import User

router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()


def get_current_user_from_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get current user from JWT token.
    
    Args:
        credentials: HTTP Bearer token credentials
        db: Database session
        
    Returns:
        Current user object
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    
    # Decode token to check what we have
    from app.core.jwt import decode_token
    from app.core.config import settings
    from jose import jwt, JWTError
    
    # Try to decode manually to get better error info
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
    except JWTError as e:
        # Token decode failed
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check token type
    token_type = payload.get("type")
    if token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token type: {token_type}. Access token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user ID
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing user ID",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: invalid user ID format: {user_id}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return get_current_user(db, user_id)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def register(
    request: Request,
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """
    Register a new user.
    
    Args:
        user_data: User registration data
        db: Database session
        
    Returns:
        Access and refresh tokens
    """
    user = register_user(db, user_data)
    tokens = create_tokens(user)
    return tokens


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(
    request: Request,
    login_data: UserLogin,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return tokens.
    
    Args:
        login_data: User login credentials
        db: Database session
        
    Returns:
        Access and refresh tokens
    """
    user = authenticate_user(db, login_data)
    tokens = create_tokens(user)
    return tokens


@router.post("/refresh", response_model=dict)
def refresh_token(
    token_data: TokenRefresh
):
    """
    Refresh access token using refresh token.
    
    Args:
        token_data: Refresh token data
        
    Returns:
        New access token
    """
    return refresh_access_token(token_data.refresh_token)


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user_from_token)
):
    """
    Get current authenticated user.
    
    Args:
        current_user: Current user from token
        
    Returns:
        User information
    """
    return current_user


@router.get("/debug")
def debug_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Debug endpoint to check if token is being received.
    """
    token = credentials.credentials
    from app.core.jwt import decode_token
    payload = decode_token(token)
    
    return {
        "token_received": bool(token),
        "token_length": len(token) if token else 0,
        "token_preview": token[:50] + "..." if token and len(token) > 50 else token,
        "payload": payload,
        "decoded": bool(payload)
    }
