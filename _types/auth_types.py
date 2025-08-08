from pydantic import BaseModel, Field, EmailStr
from typing import Optional


class UserAuthRequest(BaseModel):
    """Request model for user authentication"""
    email: EmailStr = Field(..., description="User's email address")


class User(BaseModel):
    """User model returned from authentication"""
    id: str = Field(..., description="User's unique identifier")
    displayName: Optional[str] = Field(None, description="User's display name")
    email: str = Field(..., description="User's email address")
    createdOn: Optional[str] = Field(None, description="User creation timestamp")
    status: str = Field(..., description="User account status (active/inactive)")


class AuthResponse(BaseModel):
    """Response model for authentication operations"""
    success: bool = Field(..., description="Whether the authentication was successful")
    user: Optional[User] = Field(None, description="User data if authentication successful")
    error: Optional[str] = Field(None, description="Error message if authentication failed") 