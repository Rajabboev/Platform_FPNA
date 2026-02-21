"""
Balance Snapshot models for DWH data import
Stores 36 monthly snapshots for baseline calculation
"""

from sqlalchemy import Column, Integer, String, Numeric, DateTime, Date, ForeignKey, Text, Boolean, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class BalanceSnapshot(Base):
    """
    Monthly balance snapshots imported from DWH
    Stores end-of-month balances for each account
    """
    __tablename__ = "balance_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    
    snapshot_date = Column(Date, nullable=False, index=True)
    account_code = Column(String(5), nullable=False, index=True)
    
    currency = Column(String(3), nullable=False, default="UZS")
    balance = Column(Numeric(20, 2), nullable=False, default=0)
    balance_uzs = Column(Numeric(20, 2), nullable=False, default=0)
    fx_rate = Column(Numeric(18, 6), nullable=False, default=1.0)
    
    data_source = Column(String(100))
    import_batch_id = Column(String(50), index=True)
    
    is_validated = Column(Boolean, default=False)
    validation_notes = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index('ix_snapshot_date_account', 'snapshot_date', 'account_code'),
        Index('ix_snapshot_account_currency', 'account_code', 'currency'),
    )

    def __repr__(self):
        return f"<BalanceSnapshot(date={self.snapshot_date}, account={self.account_code}, balance={self.balance})>"


class BaselineBudget(Base):
    """
    Calculated baseline budgets from historical snapshots
    Used as starting point for budget planning
    """
    __tablename__ = "baseline_budgets"

    id = Column(Integer, primary_key=True, index=True)
    
    fiscal_year = Column(Integer, nullable=False, index=True)
    account_code = Column(String(5), nullable=False, index=True)
    
    currency = Column(String(3), nullable=False, default="UZS")
    
    jan = Column(Numeric(20, 2), default=0)
    feb = Column(Numeric(20, 2), default=0)
    mar = Column(Numeric(20, 2), default=0)
    apr = Column(Numeric(20, 2), default=0)
    may = Column(Numeric(20, 2), default=0)
    jun = Column(Numeric(20, 2), default=0)
    jul = Column(Numeric(20, 2), default=0)
    aug = Column(Numeric(20, 2), default=0)
    sep = Column(Numeric(20, 2), default=0)
    oct = Column(Numeric(20, 2), default=0)
    nov = Column(Numeric(20, 2), default=0)
    dec = Column(Numeric(20, 2), default=0)
    
    annual_total = Column(Numeric(20, 2), default=0)
    
    calculation_method = Column(String(50), default="average")
    yoy_growth_rate = Column(Numeric(8, 4))
    trend_factor = Column(Numeric(8, 4))
    
    baseline_version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    notes = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index('ix_baseline_year_account', 'fiscal_year', 'account_code'),
    )

    def __repr__(self):
        return f"<BaselineBudget(year={self.fiscal_year}, account={self.account_code})>"

    @property
    def monthly_values(self) -> list:
        """Return monthly values as list"""
        return [
            self.jan, self.feb, self.mar, self.apr,
            self.may, self.jun, self.jul, self.aug,
            self.sep, self.oct, self.nov, self.dec
        ]


class SnapshotImportLog(Base):
    """
    Log of snapshot import operations
    Tracks import batches and their status
    """
    __tablename__ = "snapshot_import_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    import_batch_id = Column(String(50), unique=True, nullable=False, index=True)
    source_type = Column(String(50), nullable=False)
    source_connection_id = Column(Integer, ForeignKey("dwh_connections.id", ondelete="SET NULL"), nullable=True)
    
    start_date = Column(Date)
    end_date = Column(Date)
    
    status = Column(String(20), default="PENDING")
    
    total_records = Column(Integer, default=0)
    imported_records = Column(Integer, default=0)
    failed_records = Column(Integer, default=0)
    
    error_message = Column(Text)
    
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    def __repr__(self):
        return f"<SnapshotImportLog(batch={self.import_batch_id}, status={self.status})>"
