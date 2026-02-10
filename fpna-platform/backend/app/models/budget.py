"""
Budget models for Excel upload and data storage
"""

from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class BudgetStatus(str, enum.Enum):
    """Budget status enum"""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    PENDING_L1 = "PENDING_L1"
    PENDING_L2 = "PENDING_L2"
    PENDING_L3 = "PENDING_L3"
    PENDING_L4 = "PENDING_L4"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Budget(Base):
    """Main budget table"""
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    budget_code = Column(String(50), unique=True, nullable=False, index=True)

    # Budget details
    fiscal_year = Column(Integer, nullable=False, index=True)
    department = Column(String(100))
    branch = Column(String(100))

    # Financial summary
    total_amount = Column(Numeric(18, 2), nullable=False, default=0)
    currency = Column(String(3), default='USD')

    # Metadata
    description = Column(Text)
    notes = Column(Text)
    status = Column(SQLEnum(BudgetStatus), default=BudgetStatus.DRAFT, index=True)

    # File tracking
    source_file = Column(String(500))  # Original filename
    uploaded_by = Column(String(100))
    submitted_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    line_items = relationship("BudgetLineItem", back_populates="budget", cascade="all, delete-orphan")
    approvals = relationship("BudgetApproval", back_populates="budget", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Budget(code={self.budget_code}, year={self.fiscal_year})>"


class BudgetApproval(Base):
    """Approval audit trail for budget workflow"""
    __tablename__ = "budget_approvals"

    id = Column(Integer, primary_key=True, index=True)
    budget_id = Column(Integer, ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user_username = Column(String(100))  # Denormalized for audit
    level = Column(Integer, nullable=False)  # 1-4
    action = Column(String(20), nullable=False)  # APPROVED, REJECTED
    comment = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    budget = relationship("Budget", back_populates="approvals")


class BudgetLineItem(Base):
    """Budget line items from Excel"""
    __tablename__ = "budget_line_items"

    id = Column(Integer, primary_key=True, index=True)
    budget_id = Column(Integer, ForeignKey('budgets.id', ondelete='CASCADE'), nullable=False)

    # Account information
    account_code = Column(String(50), nullable=False, index=True)
    account_name = Column(String(200), nullable=False)
    category = Column(String(100))  # Revenue, Expense, etc.

    # Period
    month = Column(Integer)  # 1-12
    quarter = Column(Integer)  # 1-4
    year = Column(Integer)

    # Financial data
    amount = Column(Numeric(18, 2), nullable=False)
    quantity = Column(Numeric(18, 4))
    unit_price = Column(Numeric(18, 2))

    # Additional info
    notes = Column(Text)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    budget = relationship("Budget", back_populates="line_items")

    def __repr__(self):
        return f"<LineItem(account={self.account_code}, amount={self.amount})>"
