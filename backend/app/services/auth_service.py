"""Authentication service for user registration, login, and token management."""

from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.db.models import User
from app.core.security import hash_password, verify_password
from app.core.jwt import create_access_token, create_refresh_token, decode_token
from app.schemas.user import UserCreate, UserLogin
from app.utils.validators import validate_email, validate_password_strength
from datetime import timedelta


def register_user(db: Session, user_data: UserCreate) -> User:
    """
    Register a new user.
    
    Args:
        db: Database session
        user_data: User registration data
        
    Returns:
        Created user object
        
    Raises:
        HTTPException: If email already exists or validation fails
    """
    # Validate email format
    if not validate_email(user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format"
        )
    
    # Validate password strength
    is_valid, error_msg = validate_password_strength(user_data.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = hash_password(user_data.password)
    new_user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        elo_rating=0  # Initialize ELO to 0
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user


def authenticate_user(db: Session, login_data: UserLogin) -> User:
    """
    Authenticate a user with email and password.
    
    Args:
        db: Database session
        login_data: User login credentials
        
    Returns:
        Authenticated user object
        
    Raises:
        HTTPException: If credentials are invalid
    """
    user = db.query(User).filter(User.email == login_data.email).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    if not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    return user


def create_tokens(user: User) -> dict:
    """
    Create access and refresh tokens for a user.
    
    Args:
        user: User object
        
    Returns:
        Dictionary with access_token and refresh_token
    """
    # JWT 'sub' claim must be a string according to JWT spec. Include elo/wins/losses for matchmaking.
    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "elo": getattr(user, "elo_rating", 1000),
        "wins": getattr(user, "wins", 0),
        "losses": getattr(user, "losses", 0),
    }
    
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


def refresh_access_token(refresh_token: str) -> dict:
    """
    Refresh an access token using a refresh token.
    
    Args:
        refresh_token: Refresh token string
        
    Returns:
        Dictionary with new access_token
        
    Raises:
        HTTPException: If refresh token is invalid
    """
    payload = decode_token(refresh_token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type"
        )
    
    user_id = payload.get("sub")
    email = payload.get("email")
    
    if not user_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    # Create new access token (sub should remain as string)
    token_data = {"sub": str(user_id), "email": email}
    access_token = create_access_token(data=token_data)
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


def get_current_user(db: Session, user_id: int) -> User:
    """
    Get current user by ID.
    
    Args:
        db: Database session
        user_id: User ID from token
        
    Returns:
        User object
        
    Raises:
        HTTPException: If user not found
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user
