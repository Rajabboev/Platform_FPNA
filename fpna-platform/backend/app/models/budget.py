"""
Budget models for Excel upload and data storage
Enhanced with template support and multi-currency
"""

from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Text, Boolean, Enum as SQLEnum, Index
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


class BudgetType(str, enum.Enum):
    """Budget type enum"""
    BASELINE = "BASELINE"
    ADJUSTMENT = "ADJUSTMENT"
    FORECAST = "FORECAST"
    ACTUAL = "ACTUAL"


class Budget(Base):
    """Main budget table - enhanced with template and baseline support"""
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    budget_code = Column(String(50), unique=True, nullable=False, index=True)

    # Budget details
    fiscal_year = Column(Integer, nullable=False, index=True)
    department = Column(String(100))
    branch = Column(String(100))
    
    # Business unit link
    business_unit_id = Column(Integer, ForeignKey("business_units.id", ondelete="SET NULL"), nullable=True, index=True)

    # Financial summary
    total_amount = Column(Numeric(18, 2), nullable=False, default=0)
    total_amount_uzs = Column(Numeric(20, 2), default=0)
    currency = Column(String(3), default='UZS')

    # Metadata
    description = Column(Text)
    notes = Column(Text)
    status = Column(SQLEnum(BudgetStatus), default=BudgetStatus.DRAFT, index=True)
    
    # Template and baseline support
    template_id = Column(Integer, ForeignKey("budget_templates.id", ondelete="SET NULL"), nullable=True, index=True)
    template_assignment_id = Column(Integer, ForeignKey("template_assignments.id", ondelete="SET NULL"), nullable=True)
    baseline_version = Column(Integer)
    budget_type = Column(SQLEnum(BudgetType), default=BudgetType.BASELINE)
    is_baseline = Column(Boolean, default=False)
    parent_budget_id = Column(Integer, ForeignKey("budgets.id", ondelete="SET NULL"), nullable=True)
    
    # Version control
    version = Column(Integer, default=1)
    is_current_version = Column(Boolean, default=True)

    # File tracking
    source_file = Column(String(500))
    uploaded_by = Column(String(100))
    submitted_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    line_items = relationship("BudgetLineItem", back_populates="budget", cascade="all, delete-orphan")
    approvals = relationship("BudgetApproval", back_populates="budget", cascade="all, delete-orphan")
    currency_details = relationship("BudgetLineItemCurrency", back_populates="budget", cascade="all, delete-orphan")
    
    # Self-referential for adjustment budgets
    parent_budget = relationship("Budget", remote_side=[id], backref="adjustments")

    __table_args__ = (
        Index('ix_budget_year_bu', 'fiscal_year', 'business_unit_id'),
    )

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
    """Budget line items from Excel - enhanced with multi-currency support"""
    __tablename__ = "budget_line_items"

    id = Column(Integer, primary_key=True, index=True)
    budget_id = Column(Integer, ForeignKey('budgets.id', ondelete='CASCADE'), nullable=False)

    # Account information
    account_code = Column(String(50), nullable=False, index=True)
    account_name = Column(String(200), nullable=False)
    category = Column(String(100))

    # Period
    month = Column(Integer)
    quarter = Column(Integer)
    year = Column(Integer)

    # Financial data - primary currency
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), default='UZS')
    
    # UZS equivalent (for reporting)
    amount_uzs = Column(Numeric(20, 2))
    fx_rate_used = Column(Numeric(18, 6))
    
    # Baseline comparison
    baseline_amount = Column(Numeric(18, 2))
    baseline_amount_uzs = Column(Numeric(20, 2))
    variance = Column(Numeric(18, 2))
    variance_percent = Column(Numeric(8, 4))
    
    # Driver-calculated flag
    is_driver_calculated = Column(Boolean, default=False)
    driver_code = Column(String(50))

    quantity = Column(Numeric(18, 4))
    unit_price = Column(Numeric(18, 2))

    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    budget = relationship("Budget", back_populates="line_items")
    currency_breakdowns = relationship("BudgetLineItemCurrency", back_populates="line_item", cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_line_item_account_month', 'budget_id', 'account_code', 'month'),
    )

    def __repr__(self):
        return f"<LineItem(account={self.account_code}, amount={self.amount})>"


class BudgetLineItemCurrency(Base):
    """
    Multi-currency breakdown for budget line items
    Stores amounts in multiple currencies for the same line item
    """
    __tablename__ = "budget_line_item_currencies"

    id = Column(Integer, primary_key=True, index=True)
    
    budget_id = Column(Integer, ForeignKey('budgets.id', ondelete='CASCADE'), nullable=False)
    line_item_id = Column(Integer, ForeignKey('budget_line_items.id', ondelete='NO ACTION'), nullable=False)
    
    currency = Column(String(3), nullable=False)
    amount_original = Column(Numeric(20, 2), nullable=False)
    amount_uzs = Column(Numeric(20, 2), nullable=False)
    fx_rate_used = Column(Numeric(18, 6), nullable=False)
    fx_rate_date = Column(DateTime(timezone=True))
    fx_rate_source = Column(String(50))
    
    is_budget_rate = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    budget = relationship("Budget", back_populates="currency_details")
    line_item = relationship("BudgetLineItem", back_populates="currency_breakdowns")

    __table_args__ = (
        Index('ix_currency_line_item', 'line_item_id', 'currency'),
    )

    def __repr__(self):
        return f"<BudgetLineItemCurrency(item={self.line_item_id}, currency={self.currency}, amount={self.amount_original})>"
