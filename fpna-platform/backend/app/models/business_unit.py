"""
Business Unit models for Uzbek Banking FP&A System
Defines organizational structure and account responsibilities
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class BusinessUnitType(str, enum.Enum):
    """Types of business units"""
    REVENUE_CENTER = "REVENUE_CENTER"      # Generates revenue (Corporate, Retail, SME)
    COST_CENTER = "COST_CENTER"            # Cost only (HR, IT, Admin)
    PROFIT_CENTER = "PROFIT_CENTER"        # Both revenue and cost (Treasury)
    SUPPORT_CENTER = "SUPPORT_CENTER"      # Support functions (Risk, Operations)


class BusinessUnit(Base):
    """
    Business Units / Departments
    Examples: Corporate Banking, Retail Banking, SME, Treasury, HR, Risk, IT, Operations, Admin
    """
    __tablename__ = "business_units"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)  # CORP, RETAIL, SME, etc.
    
    name_en = Column(String(150), nullable=False)
    name_uz = Column(String(150), nullable=False)
    description = Column(Text)
    
    unit_type = Column(SQLEnum(BusinessUnitType), nullable=False)
    
    parent_id = Column(Integer, ForeignKey("business_units.id", ondelete="NO ACTION"), nullable=True)
    
    head_user_id = Column(Integer, ForeignKey("users.id", ondelete="NO ACTION"), nullable=True)
    
    is_active = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    parent = relationship("BusinessUnit", remote_side=[id], backref="children")
    responsibilities = relationship("AccountResponsibility", back_populates="business_unit", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<BusinessUnit(code={self.code}, name={self.name_en})>"


class AccountResponsibility(Base):
    """
    Maps accounts to responsible business units
    Example: 12100 (Loans) -> Corporate Banking, Retail Banking, SME
    """
    __tablename__ = "account_responsibilities"

    id = Column(Integer, primary_key=True, index=True)
    
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    business_unit_id = Column(Integer, ForeignKey("business_units.id", ondelete="CASCADE"), nullable=False)
    
    is_primary = Column(Boolean, default=False)
    can_budget = Column(Boolean, default=True)
    can_view = Column(Boolean, default=True)
    
    notes = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    account = relationship("Account", back_populates="responsibilities")
    business_unit = relationship("BusinessUnit", back_populates="responsibilities")

    def __repr__(self):
        return f"<AccountResponsibility(account={self.account_id}, unit={self.business_unit_id})>"
