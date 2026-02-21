"""
Driver models for FP&A calculation engine
Handles yield rates, cost rates, growth rates, provisions, and custom formulas
"""

from sqlalchemy import Column, Integer, String, Numeric, DateTime, Date, ForeignKey, Text, Boolean, Enum as SQLEnum, Index, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class DriverType(str, enum.Enum):
    """Types of drivers for budget calculations"""
    YIELD_RATE = "yield_rate"
    COST_RATE = "cost_rate"
    GROWTH_RATE = "growth_rate"
    PROVISION_RATE = "provision_rate"
    FX_RATE = "fx_rate"
    INFLATION_RATE = "inflation_rate"
    HEADCOUNT = "headcount"
    CUSTOM = "custom"


class DriverScope(str, enum.Enum):
    """Scope of driver application"""
    ACCOUNT = "account"
    CATEGORY = "category"
    GROUP = "group"
    CLASS = "class"
    BUSINESS_UNIT = "business_unit"
    GLOBAL = "global"


driver_accounts = Table(
    'driver_accounts',
    Base.metadata,
    Column('driver_id', Integer, ForeignKey('drivers.id', ondelete='CASCADE'), primary_key=True),
    Column('account_code', String(5), primary_key=True)
)


class Driver(Base):
    """
    Driver definition for budget calculations
    Examples: Loan yield rate, Deposit cost rate, Growth rate
    """
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True, index=True)
    
    code = Column(String(50), unique=True, nullable=False, index=True)
    name_en = Column(String(200), nullable=False)
    name_uz = Column(String(200), nullable=False)
    description = Column(Text)
    
    driver_type = Column(SQLEnum(DriverType), nullable=False)
    scope = Column(SQLEnum(DriverScope), default=DriverScope.ACCOUNT)
    
    source_account_pattern = Column(String(10))
    target_account_pattern = Column(String(10))
    
    formula = Column(Text)
    formula_description = Column(Text)
    
    default_value = Column(Numeric(18, 6))
    min_value = Column(Numeric(18, 6))
    max_value = Column(Numeric(18, 6))
    
    unit = Column(String(20), default="%")
    decimal_places = Column(Integer, default=2)
    
    is_active = Column(Boolean, default=True)
    is_system = Column(Boolean, default=False)
    display_order = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    values = relationship("DriverValue", back_populates="driver", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Driver(code={self.code}, type={self.driver_type})>"


class DriverValue(Base):
    """
    Driver values by period
    Stores monthly/quarterly/annual driver values
    """
    __tablename__ = "driver_values"

    id = Column(Integer, primary_key=True, index=True)
    
    driver_id = Column(Integer, ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False)
    
    fiscal_year = Column(Integer, nullable=False, index=True)
    month = Column(Integer)
    quarter = Column(Integer)
    
    account_code = Column(String(5), index=True)
    business_unit_code = Column(String(20), index=True)
    currency = Column(String(3), default="UZS")
    
    value = Column(Numeric(18, 6), nullable=False)
    
    value_type = Column(String(20), default="planned")
    
    is_approved = Column(Boolean, default=False)
    approved_by_user_id = Column(Integer)
    approved_at = Column(DateTime(timezone=True))
    
    notes = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    driver = relationship("Driver", back_populates="values")

    __table_args__ = (
        Index('ix_driver_value_lookup', 'driver_id', 'fiscal_year', 'month', 'account_code'),
    )

    def __repr__(self):
        return f"<DriverValue(driver={self.driver_id}, year={self.fiscal_year}, month={self.month}, value={self.value})>"


class DriverCalculationLog(Base):
    """
    Log of driver calculations for audit trail
    """
    __tablename__ = "driver_calculation_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    calculation_batch_id = Column(String(50), nullable=False, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True)
    
    fiscal_year = Column(Integer, nullable=False)
    month = Column(Integer)
    
    source_account_code = Column(String(5))
    target_account_code = Column(String(5))
    
    source_balance = Column(Numeric(20, 2))
    driver_value = Column(Numeric(18, 6))
    calculated_amount = Column(Numeric(20, 2))
    
    calculation_formula = Column(Text)
    
    status = Column(String(20), default="SUCCESS")
    error_message = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<DriverCalculationLog(batch={self.calculation_batch_id}, driver={self.driver_id})>"


class GoldenRule(Base):
    """
    Golden rules for automatic P&L impact calculation
    Defines relationships between balance sheet and P&L accounts
    """
    __tablename__ = "golden_rules"

    id = Column(Integer, primary_key=True, index=True)
    
    code = Column(String(50), unique=True, nullable=False, index=True)
    name_en = Column(String(200), nullable=False)
    name_uz = Column(String(200), nullable=False)
    description = Column(Text)
    
    rule_type = Column(String(50), nullable=False)
    
    source_account_pattern = Column(String(10), nullable=False)
    target_account_pattern = Column(String(10), nullable=False)
    
    driver_code = Column(String(50))
    
    calculation_formula = Column(Text, nullable=False)
    
    priority = Column(Integer, default=100)
    
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<GoldenRule(code={self.code}, type={self.rule_type})>"
