"""
Budget Template models for FP&A System
Manages template definitions, sections, and assignments
"""

from sqlalchemy import Column, Integer, String, Numeric, DateTime, Date, ForeignKey, Text, Boolean, Enum as SQLEnum, Index, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class TemplateType(str, enum.Enum):
    """Types of budget templates"""
    STANDARD = "standard"
    MIXED = "mixed"
    CUSTOM = "custom"
    REVENUE = "revenue"
    EXPENSE = "expense"
    BALANCE_SHEET = "balance_sheet"


class TemplateStatus(str, enum.Enum):
    """Template lifecycle status"""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


template_drivers = Table(
    'template_section_drivers',
    Base.metadata,
    Column('section_id', Integer, ForeignKey('template_sections.id', ondelete='CASCADE'), primary_key=True),
    Column('driver_id', Integer, ForeignKey('drivers.id', ondelete='CASCADE'), primary_key=True)
)


class BudgetTemplate(Base):
    """
    Budget template definition
    Defines structure and content for department budget forms
    """
    __tablename__ = "budget_templates"

    id = Column(Integer, primary_key=True, index=True)
    
    code = Column(String(50), unique=True, nullable=False, index=True)
    name_en = Column(String(200), nullable=False)
    name_uz = Column(String(200), nullable=False)
    description = Column(Text)
    
    template_type = Column(SQLEnum(TemplateType), default=TemplateType.STANDARD)
    status = Column(SQLEnum(TemplateStatus), default=TemplateStatus.DRAFT)
    
    fiscal_year = Column(Integer, index=True)
    
    version = Column(Integer, default=1)
    
    include_baseline = Column(Boolean, default=True)
    include_prior_year = Column(Boolean, default=True)
    include_variance = Column(Boolean, default=True)
    
    instructions = Column(Text)
    
    is_active = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    sections = relationship("TemplateSection", back_populates="template", cascade="all, delete-orphan", order_by="TemplateSection.display_order")
    assignments = relationship("TemplateAssignment", back_populates="template", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<BudgetTemplate(code={self.code}, type={self.template_type})>"


class TemplateSection(Base):
    """
    Section within a budget template
    Groups related accounts and defines editability
    """
    __tablename__ = "template_sections"

    id = Column(Integer, primary_key=True, index=True)
    
    template_id = Column(Integer, ForeignKey("budget_templates.id", ondelete="CASCADE"), nullable=False)
    
    code = Column(String(50), nullable=False)
    name_en = Column(String(200), nullable=False)
    name_uz = Column(String(200), nullable=False)
    description = Column(Text)
    
    section_type = Column(String(50), default="accounts")
    
    account_pattern = Column(String(10))
    account_codes = Column(Text)
    
    is_editable = Column(Boolean, default=True)
    is_required = Column(Boolean, default=True)
    is_collapsed = Column(Boolean, default=False)
    
    show_subtotals = Column(Boolean, default=True)
    show_monthly = Column(Boolean, default=True)
    show_quarterly = Column(Boolean, default=False)
    show_annual = Column(Boolean, default=True)
    
    validation_rules = Column(Text)
    
    display_order = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    template = relationship("BudgetTemplate", back_populates="sections")

    __table_args__ = (
        Index('ix_template_section_template', 'template_id', 'code'),
    )

    def __repr__(self):
        return f"<TemplateSection(code={self.code}, template={self.template_id})>"

    @property
    def account_codes_list(self) -> list:
        """Parse account codes from comma-separated string"""
        if self.account_codes:
            return [c.strip() for c in self.account_codes.split(",")]
        return []


class TemplateAssignment(Base):
    """
    Assignment of template to business unit for specific fiscal year
    """
    __tablename__ = "template_assignments"

    id = Column(Integer, primary_key=True, index=True)
    
    template_id = Column(Integer, ForeignKey("budget_templates.id", ondelete="CASCADE"), nullable=False)
    business_unit_id = Column(Integer, ForeignKey("business_units.id", ondelete="CASCADE"), nullable=False)
    
    fiscal_year = Column(Integer, nullable=False, index=True)
    
    deadline = Column(Date)
    reminder_date = Column(Date)
    
    status = Column(String(20), default="pending")
    
    assigned_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="NO ACTION"), nullable=True)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    
    submitted_at = Column(DateTime(timezone=True))
    submitted_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="NO ACTION"), nullable=True)
    
    notes = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    template = relationship("BudgetTemplate", back_populates="assignments")

    __table_args__ = (
        Index('ix_assignment_bu_year', 'business_unit_id', 'fiscal_year'),
    )

    def __repr__(self):
        return f"<TemplateAssignment(template={self.template_id}, bu={self.business_unit_id}, year={self.fiscal_year})>"


class TemplateLineItem(Base):
    """
    Pre-filled line items for template
    Stores baseline values and allows adjustments
    """
    __tablename__ = "template_line_items"

    id = Column(Integer, primary_key=True, index=True)
    
    assignment_id = Column(Integer, ForeignKey("template_assignments.id", ondelete="CASCADE"), nullable=False)
    section_id = Column(Integer, ForeignKey("template_sections.id", ondelete="NO ACTION"), nullable=False)
    
    account_code = Column(String(5), nullable=False, index=True)
    
    baseline_jan = Column(Numeric(20, 2), default=0)
    baseline_feb = Column(Numeric(20, 2), default=0)
    baseline_mar = Column(Numeric(20, 2), default=0)
    baseline_apr = Column(Numeric(20, 2), default=0)
    baseline_may = Column(Numeric(20, 2), default=0)
    baseline_jun = Column(Numeric(20, 2), default=0)
    baseline_jul = Column(Numeric(20, 2), default=0)
    baseline_aug = Column(Numeric(20, 2), default=0)
    baseline_sep = Column(Numeric(20, 2), default=0)
    baseline_oct = Column(Numeric(20, 2), default=0)
    baseline_nov = Column(Numeric(20, 2), default=0)
    baseline_dec = Column(Numeric(20, 2), default=0)
    
    adjusted_jan = Column(Numeric(20, 2))
    adjusted_feb = Column(Numeric(20, 2))
    adjusted_mar = Column(Numeric(20, 2))
    adjusted_apr = Column(Numeric(20, 2))
    adjusted_may = Column(Numeric(20, 2))
    adjusted_jun = Column(Numeric(20, 2))
    adjusted_jul = Column(Numeric(20, 2))
    adjusted_aug = Column(Numeric(20, 2))
    adjusted_sep = Column(Numeric(20, 2))
    adjusted_oct = Column(Numeric(20, 2))
    adjusted_nov = Column(Numeric(20, 2))
    adjusted_dec = Column(Numeric(20, 2))
    
    adjustment_notes = Column(Text)
    
    is_locked = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index('ix_template_line_assignment', 'assignment_id', 'account_code'),
    )

    def __repr__(self):
        return f"<TemplateLineItem(assignment={self.assignment_id}, account={self.account_code})>"

    @property
    def baseline_total(self):
        """Calculate baseline annual total"""
        from decimal import Decimal
        return sum([
            self.baseline_jan or Decimal("0"),
            self.baseline_feb or Decimal("0"),
            self.baseline_mar or Decimal("0"),
            self.baseline_apr or Decimal("0"),
            self.baseline_may or Decimal("0"),
            self.baseline_jun or Decimal("0"),
            self.baseline_jul or Decimal("0"),
            self.baseline_aug or Decimal("0"),
            self.baseline_sep or Decimal("0"),
            self.baseline_oct or Decimal("0"),
            self.baseline_nov or Decimal("0"),
            self.baseline_dec or Decimal("0"),
        ])

    @property
    def adjusted_total(self):
        """Calculate adjusted annual total"""
        from decimal import Decimal
        return sum([
            self.adjusted_jan or self.baseline_jan or Decimal("0"),
            self.adjusted_feb or self.baseline_feb or Decimal("0"),
            self.adjusted_mar or self.baseline_mar or Decimal("0"),
            self.adjusted_apr or self.baseline_apr or Decimal("0"),
            self.adjusted_may or self.baseline_may or Decimal("0"),
            self.adjusted_jun or self.baseline_jun or Decimal("0"),
            self.adjusted_jul or self.baseline_jul or Decimal("0"),
            self.adjusted_aug or self.baseline_aug or Decimal("0"),
            self.adjusted_sep or self.baseline_sep or Decimal("0"),
            self.adjusted_oct or self.baseline_oct or Decimal("0"),
            self.adjusted_nov or self.baseline_nov or Decimal("0"),
            self.adjusted_dec or self.baseline_dec or Decimal("0"),
        ])
