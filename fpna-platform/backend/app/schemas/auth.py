"""
Authentication schemas
"""

from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime


class UserBase(BaseModel):
    """Base user schema"""
    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=200)


class UserCreate(UserBase):
    """Schema for creating a user"""
    password: str = Field(..., min_length=8)
    employee_id: Optional[str] = None
    department: Optional[str] = None
    branch: Optional[str] = None


class UserResponse(UserBase):
    """Schema for user responses"""
    id: int
    employee_id: Optional[str]
    department: Optional[str]
    branch: Optional[str]
    is_active: bool
    is_verified: bool
    created_at: datetime
    roles: List[str] = []

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Token response"""
    access_token: str
    token_type: str
    user: dict


class LoginRequest(BaseModel):
    """Login request"""
    username: str
    password: str
