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


class UserAdminCreate(BaseModel):
    """Admin/CFO user creation payload"""
    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=200)
    password: str = Field(..., min_length=8)
    employee_id: Optional[str] = None
    department: Optional[str] = None
    branch: Optional[str] = None
    is_active: bool = True
    roles: List[str] = []


class UserAdminUpdate(BaseModel):
    """Admin/CFO user update payload"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    password: Optional[str] = Field(default=None, min_length=8)
    employee_id: Optional[str] = None
    department: Optional[str] = None
    branch: Optional[str] = None
    is_active: Optional[bool] = None
    roles: Optional[List[str]] = None


class RoleResponse(BaseModel):
    """Role list item"""
    id: int
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True
