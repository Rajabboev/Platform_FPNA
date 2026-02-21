"""
Chart of Accounts (COA) models for Uzbek Banking FP&A System
Supports hierarchical account structure: Class -> Group -> Category -> Account
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class AccountNature(str, enum.Enum):
    """Account nature - Debit or Credit"""
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class AccountClassType(str, enum.Enum):
    """Standard account class types for banking"""
    ASSETS = "ASSETS"           # 1xxxx - Aktivlar
    LIABILITIES = "LIABILITIES" # 2xxxx - Majburiyatlar
    EQUITY = "EQUITY"           # 3xxxx - Kapital
    REVENUE = "REVENUE"         # 4xxxx - Daromadlar
    EXPENSES = "EXPENSES"       # 5xxxx - Xarajatlar


class AccountClass(Base):
    """
    1-digit level: Account Classes (1-5)
    Examples: 1-Assets, 2-Liabilities, 3-Equity, 4-Revenue, 5-Expenses
    """
    __tablename__ = "account_classes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(1), unique=True, nullable=False, index=True)  # 1, 2, 3, 4, 5
    name_en = Column(String(100), nullable=False)
    name_uz = Column(String(100), nullable=False)
    class_type = Column(SQLEnum(AccountClassType), nullable=False)
    nature = Column(SQLEnum(AccountNature), nullable=False)
    description = Column(Text)
    
    is_active = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    groups = relationship("AccountGroup", back_populates="account_class", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<AccountClass(code={self.code}, name={self.name_en})>"


class AccountGroup(Base):
    """
    2-digit level: Account Groups (10-59)
    Examples: 10-Cash, 12-Loans, 20-Deposits, 40-Interest Income
    """
    __tablename__ = "account_groups"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(2), unique=True, nullable=False, index=True)  # 10, 12, 20, etc.
    class_id = Column(Integer, ForeignKey("account_classes.id", ondelete="CASCADE"), nullable=False)
    
    name_en = Column(String(150), nullable=False)
    name_uz = Column(String(150), nullable=False)
    description = Column(Text)
    
    is_active = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    account_class = relationship("AccountClass", back_populates="groups")
    categories = relationship("AccountCategory", back_populates="account_group", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<AccountGroup(code={self.code}, name={self.name_en})>"


class AccountCategory(Base):
    """
    3-digit level: Account Categories (101-599)
    Examples: 101-Cash on hand, 121-Short-term loans, 202-Demand deposits
    """
    __tablename__ = "account_categories"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(3), unique=True, nullable=False, index=True)  # 101, 121, 202, etc.
    group_id = Column(Integer, ForeignKey("account_groups.id", ondelete="CASCADE"), nullable=False)
    
    name_en = Column(String(200), nullable=False)
    name_uz = Column(String(200), nullable=False)
    description = Column(Text)
    
    is_active = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    account_group = relationship("AccountGroup", back_populates="categories")
    accounts = relationship("Account", back_populates="account_category", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<AccountCategory(code={self.code}, name={self.name_en})>"


class Account(Base):
    """
    5-digit level: Full Account Codes (10100-59999)
    Examples: 10101-Cash in vault UZS, 12101-Short-term corporate loans
    """
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(5), unique=True, nullable=False, index=True)  # 10101, 12101, etc.
    category_id = Column(Integer, ForeignKey("account_categories.id", ondelete="CASCADE"), nullable=False)
    
    name_en = Column(String(250), nullable=False)
    name_uz = Column(String(250), nullable=False)
    description = Column(Text)
    
    is_active = Column(Boolean, default=True)
    is_budgetable = Column(Boolean, default=True)  # Can be used in budgeting
    display_order = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    account_category = relationship("AccountCategory", back_populates="accounts")
    responsibilities = relationship("AccountResponsibility", back_populates="account", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Account(code={self.code}, name={self.name_en})>"

    @property
    def class_code(self) -> str:
        """Get 1-digit class code"""
        return self.code[0] if self.code else ""
    
    @property
    def group_code(self) -> str:
        """Get 2-digit group code"""
        return self.code[:2] if self.code and len(self.code) >= 2 else ""
    
    @property
    def category_code(self) -> str:
        """Get 3-digit category code"""
        return self.code[:3] if self.code and len(self.code) >= 3 else ""


class AccountMapping(Base):
    """
    Maps Balance Sheet accounts to P&L accounts
    Example: Loans (12xxx) -> Interest Income (401xx)
    """
    __tablename__ = "account_mappings"

    id = Column(Integer, primary_key=True, index=True)
    
    balance_account_code = Column(String(5), nullable=False, index=True)  # Source: Balance account
    pnl_account_code = Column(String(5), nullable=False, index=True)      # Target: P&L account
    
    mapping_type = Column(String(50), nullable=False)  # interest_income, interest_expense, provision, etc.
    description = Column(Text)
    
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<AccountMapping({self.balance_account_code} -> {self.pnl_account_code})>"
