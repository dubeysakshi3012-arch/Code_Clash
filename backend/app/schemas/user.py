"""User-related Pydantic schemas."""

from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional
from app.db.models.user import ProgrammingLanguage


class UserCreate(BaseModel):
    """Schema for user registration."""
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Schema for user response."""
    id: int
    email: str
    elo_rating: int
    wins: int = 0
    losses: int = 0
    selected_language: Optional[ProgrammingLanguage]
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Schema for token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    """Schema for token refresh request."""
    refresh_token: str
