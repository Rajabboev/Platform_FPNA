"""
User, Role, and Authentication models
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum

# Association table for many-to-many relationship
user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('role_id', Integer, ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True)
)


class RoleEnum(str, enum.Enum):
    """Predefined roles"""
    ADMIN = "ADMIN"
    CEO = "CEO"
    CFO = "CFO"
    FINANCE_MANAGER = "FINANCE_MANAGER"
    DEPARTMENT_MANAGER = "DEPARTMENT_MANAGER"
    BRANCH_MANAGER = "BRANCH_MANAGER"
    ANALYST = "ANALYST"
    DATA_ENTRY = "DATA_ENTRY"
    VIEWER = "VIEWER"


class PermissionEnum(str, enum.Enum):
    """System permissions"""
    # Budget permissions
    CREATE_BUDGET = "create_budget"
    VIEW_BUDGET = "view_budget"
    EDIT_BUDGET = "edit_budget"
    DELETE_BUDGET = "delete_budget"
    SUBMIT_BUDGET = "submit_budget"

    # Approval permissions
    APPROVE_L1 = "approve_level_1"
    APPROVE_L2 = "approve_level_2"
    APPROVE_L3 = "approve_level_3"
    APPROVE_L4 = "approve_level_4"

    # Data permissions
    UPLOAD_DATA = "upload_data"
    EXPORT_DATA = "export_data"

    # User management
    MANAGE_USERS = "manage_users"
    MANAGE_ROLES = "manage_roles"

    # System
    VIEW_ALL = "view_all"
    VIEW_DEPARTMENT = "view_department"
    VIEW_OWN = "view_own"


class Role(Base):
    """Role definition"""
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    display_name = Column(String(100), nullable=False)
    description = Column(String(500))
    permissions = Column(String(2000))  # Comma-separated permissions
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    users = relationship("User", secondary=user_roles, back_populates="roles")

    def __repr__(self):
        return f"<Role(name={self.name})>"


class User(Base):
    """User account"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(200), nullable=False)
    hashed_password = Column(String(255), nullable=False)

    # Organizational info
    employee_id = Column(String(50), unique=True, index=True)
    department = Column(String(100))
    branch = Column(String(100))

    # Status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))

    # Relationships
    roles = relationship("Role", secondary=user_roles, back_populates="users")

    def __repr__(self):
        return f"<User(username={self.username})>"