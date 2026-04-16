"""
Department model — product-line owners for FP&A budget planning.

Each department typically owns one FP&A taxonomy product (Loans, Deposits, …).
`primary_product_key` is the planning level; `department_product_access` lists
which product buckets the plan UI may edit (usually the same as primary).
Legacy org-style naming is optional; prefer product owner naming.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Table, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class DepartmentProductAccess(Base):
    """
    Which FP&A product buckets (Loans, Deposits, …) a department may budget.
    Replaces reliance on CBU budgeting_groups for access control.
    """
    __tablename__ = "department_product_access"

    department_id = Column(Integer, ForeignKey("departments.id", ondelete="CASCADE"), primary_key=True)
    product_key = Column(String(50), primary_key=True)
    can_edit = Column(Boolean, default=True)
    can_submit = Column(Boolean, default=True)
    assigned_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="NO ACTION"), nullable=True)
    assigned_at = Column(DateTime(timezone=True), nullable=True)

    department = relationship("Department", back_populates="product_access_rows")


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
    Column('can_edit', Boolean, default=True),
    Column('can_submit', Boolean, default=True),
    Column('assigned_by_user_id', Integer, nullable=True),
    Column('assigned_at', DateTime(timezone=True), nullable=True),
)


class Department(Base):
    """
    Product owner unit: submits budget plans for one FP&A product line (taxonomy key)
    and optional DWH segment slice; two-level approval (manager → head / CFO).
    """
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    # FP&A taxonomy key (e.g. LOANS, DEPOSITS) — one “owner” per active department
    primary_product_key = Column(String(50), nullable=True, index=True)
    name_en = Column(String(255), nullable=False)
    name_uz = Column(String(255))
    name_ru = Column(String(255))
    description = Column(String(1000))
    
    # Hierarchy (optional parent department)
    parent_id = Column(Integer, ForeignKey('departments.id', ondelete='NO ACTION'), nullable=True)
    
    # Department head (user who approves at dept level — L1 approval)
    head_user_id = Column(Integer, ForeignKey('users.id', ondelete='NO ACTION'), nullable=True)

    # Department manager (user who manages budget entry and submits — different from head)
    manager_user_id = Column(Integer, ForeignKey('users.id', ondelete='NO ACTION'), nullable=True)
    
    # Settings
    is_active = Column(Boolean, default=True)
    is_baseline_only = Column(Boolean, default=False)  # If True, no adjustments allowed
    display_order = Column(Integer, default=0)
    # When DWH ingest includes a segment column, set this to the value for this unit (e.g. RETAIL).
    # NULL = use consolidated baseline (sum across all segment_key values for each account/month).
    dwh_segment_value = Column(String(100), nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by_user_id = Column(Integer, ForeignKey('users.id', ondelete='NO ACTION'), nullable=True)
    
    # Relationships
    parent = relationship("Department", remote_side=[id], backref="children")
    head_user = relationship("User", foreign_keys=[head_user_id])
    manager_user = relationship("User", foreign_keys=[manager_user_id])
    assignments = relationship("DepartmentAssignment", back_populates="department", cascade="all, delete-orphan")
    budget_plans = relationship("BudgetPlan", back_populates="department", cascade="all, delete-orphan")
    budgeting_groups = relationship("BudgetingGroup", secondary=department_budgeting_groups, backref="departments")
    product_access_rows = relationship(
        "DepartmentProductAccess", back_populates="department", cascade="all, delete-orphan"
    )
    
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
