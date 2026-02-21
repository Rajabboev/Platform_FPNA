"""
Baseline and Budget Planning Models
Handles the flow: DWH Snapshots → Baseline Data → Baseline Budget → Planned Budget
"""

from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, Boolean, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class BaselineData(Base):
    """
    Raw snapshot data imported from DWH balans_ato
    Stores monthly ending balances for baseline calculation
    """
    __tablename__ = "baseline_data"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Source identification
    import_batch_id = Column(String(50), index=True)
    source_connection_id = Column(Integer, ForeignKey("dwh_connections.id"))
    
    # Account and period
    account_code = Column(String(10), nullable=False, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    fiscal_year = Column(Integer, nullable=False, index=True)
    fiscal_month = Column(Integer, nullable=False)  # 1-12
    
    # Balance data
    currency_code = Column(Integer, default=0)  # ISO numeric (0=UZS, 840=USD, etc.)
    currency = Column(String(3), default='UZS')  # ISO alpha
    balance = Column(Numeric(22, 2), default=0)  # Balance in original currency
    balance_uzs = Column(Numeric(22, 2), default=0)  # Balance in UZS equivalent
    
    # Turnover data (for trend analysis)
    debit_turnover = Column(Numeric(22, 2), default=0)
    credit_turnover = Column(Numeric(22, 2), default=0)
    net_change = Column(Numeric(22, 2), default=0)  # credit - debit
    
    # Branch aggregation
    branch_code = Column(String(10), default='ALL')
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_baseline_data_account_period', 'account_code', 'fiscal_year', 'fiscal_month'),
        Index('ix_baseline_data_year_month', 'fiscal_year', 'fiscal_month'),
    )


class BudgetBaseline(Base):
    """
    Calculated baseline budget for a fiscal year
    Generated from historical snapshot data using averaging methods
    """
    __tablename__ = "budget_baseline"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Budget identification
    fiscal_year = Column(Integer, nullable=False, index=True)
    account_code = Column(String(10), nullable=False, index=True)
    currency = Column(String(3), default='UZS')
    
    # Monthly baseline amounts (calculated from historical averages)
    jan = Column(Numeric(22, 2), default=0)
    feb = Column(Numeric(22, 2), default=0)
    mar = Column(Numeric(22, 2), default=0)
    apr = Column(Numeric(22, 2), default=0)
    may = Column(Numeric(22, 2), default=0)
    jun = Column(Numeric(22, 2), default=0)
    jul = Column(Numeric(22, 2), default=0)
    aug = Column(Numeric(22, 2), default=0)
    sep = Column(Numeric(22, 2), default=0)
    oct = Column(Numeric(22, 2), default=0)
    nov = Column(Numeric(22, 2), default=0)
    dec = Column(Numeric(22, 2), default=0)
    
    # Annual totals
    annual_total = Column(Numeric(22, 2), default=0)
    annual_total_uzs = Column(Numeric(22, 2), default=0)
    
    # Calculation metadata
    calculation_method = Column(String(50), default='simple_average')  # simple_average, weighted_average, trend
    source_years = Column(String(50))  # e.g., "2023,2024,2025"
    yoy_growth_rate = Column(Numeric(10, 4))  # Year-over-year growth rate
    
    # Status
    is_active = Column(Boolean, default=True)
    version = Column(Integer, default=1)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by_user_id = Column(Integer, ForeignKey("users.id"))
    
    __table_args__ = (
        Index('ix_budget_baseline_year_account', 'fiscal_year', 'account_code', unique=True),
    )


class BudgetPlanned(Base):
    """
    Planned budget after template/driver adjustments
    This is what gets submitted for approval and exported to DWH
    """
    __tablename__ = "budget_planned"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Budget identification
    budget_code = Column(String(50), nullable=False, unique=True, index=True)
    fiscal_year = Column(Integer, nullable=False, index=True)
    account_code = Column(String(10), nullable=False, index=True)
    currency = Column(String(3), default='UZS')
    
    # Department/Branch assignment
    department = Column(String(100))
    branch = Column(String(100))
    
    # Monthly planned amounts (after driver adjustments)
    jan = Column(Numeric(22, 2), default=0)
    feb = Column(Numeric(22, 2), default=0)
    mar = Column(Numeric(22, 2), default=0)
    apr = Column(Numeric(22, 2), default=0)
    may = Column(Numeric(22, 2), default=0)
    jun = Column(Numeric(22, 2), default=0)
    jul = Column(Numeric(22, 2), default=0)
    aug = Column(Numeric(22, 2), default=0)
    sep = Column(Numeric(22, 2), default=0)
    oct = Column(Numeric(22, 2), default=0)
    nov = Column(Numeric(22, 2), default=0)
    dec = Column(Numeric(22, 2), default=0)
    
    # Totals
    annual_total = Column(Numeric(22, 2), default=0)
    annual_total_uzs = Column(Numeric(22, 2), default=0)
    
    # Driver adjustments applied
    driver_code = Column(String(50))
    driver_adjustment_pct = Column(Numeric(10, 4), default=0)  # e.g., 0.05 for 5% increase
    
    # Baseline reference
    baseline_id = Column(Integer, ForeignKey("budget_baseline.id"))
    baseline_amount = Column(Numeric(22, 2), default=0)  # Original baseline before adjustment
    variance_from_baseline = Column(Numeric(22, 2), default=0)
    variance_pct = Column(Numeric(10, 4), default=0)
    
    # Workflow status
    status = Column(String(20), default='DRAFT')  # DRAFT, SUBMITTED, APPROVED, REJECTED, EXPORTED
    submitted_at = Column(DateTime)
    submitted_by_user_id = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(DateTime)
    approved_by_user_id = Column(Integer, ForeignKey("users.id"))
    exported_at = Column(DateTime)
    export_batch_id = Column(String(50))
    
    # Version control
    version = Column(Integer, default=1)
    is_current = Column(Boolean, default=True)
    parent_version_id = Column(Integer, ForeignKey("budget_planned.id"))
    
    # Scenario type
    scenario = Column(String(20), default='BASE')  # BASE, OPTIMISTIC, PESSIMISTIC
    
    # Metadata
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    created_by_user_id = Column(Integer, ForeignKey("users.id"))
    
    __table_args__ = (
        Index('ix_budget_planned_year_account', 'fiscal_year', 'account_code'),
        Index('ix_budget_planned_status', 'status'),
    )
