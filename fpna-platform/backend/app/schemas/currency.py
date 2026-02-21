"""
Pydantic schemas for Currency and FX Rate API
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal


class CurrencyBase(BaseModel):
    code: str = Field(..., min_length=3, max_length=3)
    name_en: str = Field(..., max_length=100)
    name_uz: str = Field(..., max_length=100)
    symbol: Optional[str] = None
    decimal_places: int = Field(default=2)
    is_active: bool = True
    is_base_currency: bool = False
    display_order: int = 0


class CurrencyCreate(CurrencyBase):
    pass


class CurrencyUpdate(BaseModel):
    name_en: Optional[str] = None
    name_uz: Optional[str] = None
    symbol: Optional[str] = None
    decimal_places: Optional[int] = None
    is_active: Optional[bool] = None
    display_order: Optional[int] = None


class CurrencyResponse(CurrencyBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CurrencyRateBase(BaseModel):
    rate_date: date
    from_currency: str = Field(..., max_length=3)
    to_currency: str = Field(default="UZS", max_length=3)
    rate: Decimal
    rate_source: str = Field(default="CBU")
    is_official: bool = True


class CurrencyRateCreate(CurrencyRateBase):
    pass


class CurrencyRateResponse(CurrencyRateBase):
    id: int
    inverse_rate: Optional[Decimal] = None
    created_at: datetime

    class Config:
        from_attributes = True


class BulkCurrencyRateCreate(BaseModel):
    rates: List[CurrencyRateCreate]


class BudgetFXRateBase(BaseModel):
    fiscal_year: int
    month: int = Field(..., ge=1, le=12)
    from_currency: str = Field(..., max_length=3)
    to_currency: str = Field(default="UZS", max_length=3)
    planned_rate: Decimal
    assumption_type: str = Field(default="flat")
    notes: Optional[str] = None


class BudgetFXRateCreate(BudgetFXRateBase):
    pass


class BudgetFXRateUpdate(BaseModel):
    planned_rate: Optional[Decimal] = None
    assumption_type: Optional[str] = None
    notes: Optional[str] = None
    is_approved: Optional[bool] = None


class BudgetFXRateResponse(BudgetFXRateBase):
    id: int
    is_approved: bool
    approved_by_user_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FXConversionRequest(BaseModel):
    amount: Decimal
    from_currency: str
    to_currency: str = Field(default="UZS")
    rate_date: Optional[date] = None
    use_budget_rate: bool = False
    fiscal_year: Optional[int] = None
    month: Optional[int] = None


class FXConversionResponse(BaseModel):
    original_amount: Decimal
    converted_amount: Decimal
    from_currency: str
    to_currency: str
    rate_used: Decimal
    rate_date: date
    rate_source: str


class FXRateTimeSeries(BaseModel):
    from_currency: str
    to_currency: str
    data_points: List[CurrencyRateResponse]


class BudgetFXRatePlan(BaseModel):
    fiscal_year: int
    from_currency: str
    to_currency: str
    monthly_rates: List[BudgetFXRateResponse]
    average_rate: Decimal
    is_fully_approved: bool
