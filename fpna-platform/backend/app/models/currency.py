"""
Currency and FX Rate models for multi-currency support
"""

from sqlalchemy import Column, Integer, String, Numeric, DateTime, Date, Boolean, Text, Index
from sqlalchemy.sql import func
from app.database import Base


class Currency(Base):
    """
    Supported currencies in the system
    """
    __tablename__ = "currencies"

    id = Column(Integer, primary_key=True, index=True)
    
    code = Column(String(3), unique=True, nullable=False, index=True)
    name_en = Column(String(100), nullable=False)
    name_uz = Column(String(100), nullable=False)
    symbol = Column(String(10))
    
    decimal_places = Column(Integer, default=2)
    
    is_active = Column(Boolean, default=True)
    is_base_currency = Column(Boolean, default=False)
    
    display_order = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Currency(code={self.code}, name={self.name_en})>"


class CurrencyRate(Base):
    """
    Daily exchange rates
    Stores rates from Central Bank of Uzbekistan
    """
    __tablename__ = "currency_rates"

    id = Column(Integer, primary_key=True, index=True)
    
    rate_date = Column(Date, nullable=False, index=True)
    from_currency = Column(String(3), nullable=False, index=True)
    to_currency = Column(String(3), nullable=False, default="UZS")
    
    rate = Column(Numeric(18, 6), nullable=False)
    inverse_rate = Column(Numeric(18, 10))
    
    rate_source = Column(String(50), default="CBU")
    
    is_official = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('ix_rate_date_currencies', 'rate_date', 'from_currency', 'to_currency'),
    )

    def __repr__(self):
        return f"<CurrencyRate({self.from_currency}/{self.to_currency}={self.rate} on {self.rate_date})>"


class BudgetFXRate(Base):
    """
    FX rates used for budget planning
    May differ from actual rates (planning assumptions)
    """
    __tablename__ = "budget_fx_rates"

    id = Column(Integer, primary_key=True, index=True)
    
    fiscal_year = Column(Integer, nullable=False, index=True)
    month = Column(Integer, nullable=False)
    
    from_currency = Column(String(3), nullable=False, index=True)
    to_currency = Column(String(3), nullable=False, default="UZS")
    
    planned_rate = Column(Numeric(18, 6), nullable=False)
    
    assumption_type = Column(String(50), default="flat")
    notes = Column(Text)
    
    is_approved = Column(Boolean, default=False)
    approved_by_user_id = Column(Integer)
    approved_at = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index('ix_budget_fx_year_month', 'fiscal_year', 'month', 'from_currency'),
    )

    def __repr__(self):
        return f"<BudgetFXRate({self.from_currency}/{self.to_currency}={self.planned_rate} for {self.fiscal_year}/{self.month})>"
