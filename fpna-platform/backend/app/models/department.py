"""
Department Model - Organizational units for budget planning

Departments are the primary organizational units that receive budget templates
and submit budget plans for approval.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class DepartmentRole(str, enum.Enum):
    """Roles for department assignments"""
    ANALYST = "analyst"
    MANAGER = "manager"
    HEAD = "head"


# Association table for department budgeting groups
department_budgeting_groups = Table(
    'department_budgeting_groups',
    Base.metadata,
    Column('department_id', Integer, ForeignKey('departments.id', ondelete='CASCADE'), primary_key=True),
    Column('budgeting_group_id', Integer, ForeignKey('budgeting_groups.id', ondelete='CASCADE'), primary_key=True),
)


class Department(Base):
    """
    Department/Business Unit for budget planning
    
    Each department is assigned specific budgeting groups and submits
    budget plans that go through a two-level approval workflow.
    """
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name_en = Column(String(255), nullable=False)
    name_uz = Column(String(255))
    name_ru = Column(String(255))
    description = Column(String(1000))
    
    # Hierarchy (optional parent department)
    parent_id = Column(Integer, ForeignKey('departments.id', ondelete='NO ACTION'), nullable=True)
    
    # Department head (user who approves at L1)
    head_user_id = Column(Integer, ForeignKey('users.id', ondelete='NO ACTION'), nullable=True)
    
    # Settings
    is_active = Column(Boolean, default=True)
    is_baseline_only = Column(Boolean, default=False)  # If True, no adjustments allowed
    display_order = Column(Integer, default=0)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by_user_id = Column(Integer, ForeignKey('users.id', ondelete='NO ACTION'), nullable=True)
    
    # Relationships
    parent = relationship("Department", remote_side=[id], backref="children")
    head_user = relationship("User", foreign_keys=[head_user_id])
    assignments = relationship("DepartmentAssignment", back_populates="department", cascade="all, delete-orphan")
    budget_plans = relationship("BudgetPlan", back_populates="department", cascade="all, delete-orphan")
    budgeting_groups = relationship("BudgetingGroup", secondary=department_budgeting_groups, backref="departments")
    
    def __repr__(self):
        return f"<Department(code={self.code}, name={self.name_en})>"


class DepartmentAssignment(Base):
    """
    User assignments to departments with roles
    
    Roles:
    - ANALYST: Can edit budget data
    - MANAGER: Can edit and review
    - HEAD: Can approve at department level
    """
    __tablename__ = "department_assignments"

    id = Column(Integer, primary_key=True, index=True)
    department_id = Column(Integer, ForeignKey('departments.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    role = Column(Enum(DepartmentRole), default=DepartmentRole.ANALYST, nullable=False)
    
    # Metadata
    is_active = Column(Boolean, default=True)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    assigned_by_user_id = Column(Integer, ForeignKey('users.id', ondelete='NO ACTION'), nullable=True)
    
    # Relationships
    department = relationship("Department", back_populates="assignments")
    user = relationship("User", foreign_keys=[user_id])
    assigned_by = relationship("User", foreign_keys=[assigned_by_user_id])
    
    def __repr__(self):
        return f"<DepartmentAssignment(dept={self.department_id}, user={self.user_id}, role={self.role})>"
