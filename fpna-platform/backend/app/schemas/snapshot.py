"""
Pydantic schemas for Snapshot and Baseline API
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal


class BalanceSnapshotBase(BaseModel):
    snapshot_date: date
    account_code: str = Field(..., min_length=5, max_length=5)
    currency: str = Field(default="UZS", max_length=3)
    balance: Decimal
    balance_uzs: Decimal
    fx_rate: Decimal = Field(default=Decimal("1.0"))
    data_source: Optional[str] = None


class BalanceSnapshotCreate(BalanceSnapshotBase):
    pass


class BalanceSnapshotResponse(BalanceSnapshotBase):
    id: int
    import_batch_id: Optional[str] = None
    is_validated: bool
    validation_notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BulkSnapshotCreate(BaseModel):
    snapshots: List[BalanceSnapshotCreate]
    import_batch_id: Optional[str] = None


class BaselineBudgetBase(BaseModel):
    fiscal_year: int
    account_code: str = Field(..., min_length=5, max_length=5)
    currency: str = Field(default="UZS", max_length=3)


class BaselineBudgetCreate(BaselineBudgetBase):
    jan: Decimal = Field(default=Decimal("0"))
    feb: Decimal = Field(default=Decimal("0"))
    mar: Decimal = Field(default=Decimal("0"))
    apr: Decimal = Field(default=Decimal("0"))
    may: Decimal = Field(default=Decimal("0"))
    jun: Decimal = Field(default=Decimal("0"))
    jul: Decimal = Field(default=Decimal("0"))
    aug: Decimal = Field(default=Decimal("0"))
    sep: Decimal = Field(default=Decimal("0"))
    oct: Decimal = Field(default=Decimal("0"))
    nov: Decimal = Field(default=Decimal("0"))
    dec: Decimal = Field(default=Decimal("0"))
    calculation_method: str = Field(default="average")
    notes: Optional[str] = None


class BaselineBudgetResponse(BaselineBudgetBase):
    id: int
    jan: Decimal
    feb: Decimal
    mar: Decimal
    apr: Decimal
    may: Decimal
    jun: Decimal
    jul: Decimal
    aug: Decimal
    sep: Decimal
    oct: Decimal
    nov: Decimal
    dec: Decimal
    annual_total: Decimal
    calculation_method: str
    yoy_growth_rate: Optional[Decimal] = None
    trend_factor: Optional[Decimal] = None
    baseline_version: int
    is_active: bool
    notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BaselineBudgetDetail(BaselineBudgetResponse):
    account_name: Optional[str] = None
    class_code: Optional[str] = None
    group_code: Optional[str] = None


class BaselineCalculationRequest(BaseModel):
    fiscal_year: int
    account_codes: Optional[List[str]] = None
    class_code: Optional[str] = None
    group_code: Optional[str] = None
    calculation_method: str = Field(default="average")
    lookback_months: int = Field(default=36, ge=12, le=60)
    apply_trend: bool = Field(default=False)
    apply_seasonality: bool = Field(default=False)


class BaselineCalculationResponse(BaseModel):
    fiscal_year: int
    total_accounts: int
    calculated_accounts: int
    skipped_accounts: int
    errors: List[str]
    baseline_version: int


class SnapshotImportRequest(BaseModel):
    source_type: str = Field(..., description="dwh, file, api")
    source_connection_id: Optional[int] = None
    start_date: date
    end_date: date
    account_codes: Optional[List[str]] = None


class SnapshotImportLogResponse(BaseModel):
    id: int
    import_batch_id: str
    source_type: str
    source_connection_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: str
    total_records: int
    imported_records: int
    failed_records: int
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SnapshotSummary(BaseModel):
    account_code: str
    account_name: Optional[str] = None
    currency: str
    snapshot_count: int
    earliest_date: date
    latest_date: date
    min_balance: Decimal
    max_balance: Decimal
    avg_balance: Decimal


class SnapshotTimeSeriesPoint(BaseModel):
    snapshot_date: date
    balance: Decimal
    balance_uzs: Decimal
    fx_rate: Decimal


class SnapshotTimeSeries(BaseModel):
    account_code: str
    account_name: Optional[str] = None
    currency: str
    data_points: List[SnapshotTimeSeriesPoint]


class AggregatedSnapshot(BaseModel):
    level: int
    code: str
    name: Optional[str] = None
    snapshot_date: date
    currency: str
    total_balance: Decimal
    total_balance_uzs: Decimal
    account_count: int
