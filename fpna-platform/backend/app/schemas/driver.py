"""
Pydantic schemas for Driver API
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from enum import Enum


class DriverType(str, Enum):
    YIELD_RATE = "yield_rate"
    COST_RATE = "cost_rate"
    GROWTH_RATE = "growth_rate"
    PROVISION_RATE = "provision_rate"
    FX_RATE = "fx_rate"
    INFLATION_RATE = "inflation_rate"
    HEADCOUNT = "headcount"
    CUSTOM = "custom"


class DriverScope(str, Enum):
    ACCOUNT = "account"
    CATEGORY = "category"
    GROUP = "group"
    CLASS = "class"
    BUSINESS_UNIT = "business_unit"
    GLOBAL = "global"


class DriverBase(BaseModel):
    code: str = Field(..., max_length=50)
    name_en: str = Field(..., max_length=200)
    name_uz: str = Field(..., max_length=200)
    description: Optional[str] = None
    driver_type: DriverType
    scope: DriverScope = DriverScope.ACCOUNT
    source_account_pattern: Optional[str] = None
    target_account_pattern: Optional[str] = None
    formula: Optional[str] = None
    formula_description: Optional[str] = None
    default_value: Optional[Decimal] = None
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    unit: str = Field(default="%")
    decimal_places: int = Field(default=2)
    is_active: bool = True
    display_order: int = 0


class DriverCreate(DriverBase):
    pass


class DriverUpdate(BaseModel):
    name_en: Optional[str] = None
    name_uz: Optional[str] = None
    description: Optional[str] = None
    scope: Optional[DriverScope] = None
    source_account_pattern: Optional[str] = None
    target_account_pattern: Optional[str] = None
    formula: Optional[str] = None
    formula_description: Optional[str] = None
    default_value: Optional[Decimal] = None
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    unit: Optional[str] = None
    decimal_places: Optional[int] = None
    is_active: Optional[bool] = None
    display_order: Optional[int] = None


class DriverResponse(DriverBase):
    id: int
    is_system: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DriverValueBase(BaseModel):
    driver_id: int
    fiscal_year: int
    month: Optional[int] = None
    quarter: Optional[int] = None
    account_code: Optional[str] = None
    business_unit_code: Optional[str] = None
    currency: str = Field(default="UZS")
    value: Decimal
    value_type: str = Field(default="planned")
    notes: Optional[str] = None


class DriverValueCreate(DriverValueBase):
    pass


class DriverValueUpdate(BaseModel):
    value: Optional[Decimal] = None
    value_type: Optional[str] = None
    notes: Optional[str] = None
    is_approved: Optional[bool] = None


class DriverValueResponse(DriverValueBase):
    id: int
    is_approved: bool
    approved_by_user_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BulkDriverValueCreate(BaseModel):
    values: List[DriverValueCreate]


class DriverValueMatrix(BaseModel):
    driver_id: int
    driver_code: str
    driver_name: str
    fiscal_year: int
    monthly_values: dict


class GoldenRuleBase(BaseModel):
    code: str = Field(..., max_length=50)
    name_en: str = Field(..., max_length=200)
    name_uz: str = Field(..., max_length=200)
    description: Optional[str] = None
    rule_type: str
    source_account_pattern: str
    target_account_pattern: str
    driver_code: Optional[str] = None
    calculation_formula: str
    priority: int = Field(default=100)
    is_active: bool = True


class GoldenRuleCreate(GoldenRuleBase):
    pass


class GoldenRuleUpdate(BaseModel):
    name_en: Optional[str] = None
    name_uz: Optional[str] = None
    description: Optional[str] = None
    driver_code: Optional[str] = None
    calculation_formula: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class GoldenRuleResponse(GoldenRuleBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DriverCalculationRequest(BaseModel):
    fiscal_year: int
    months: Optional[List[int]] = None
    driver_codes: Optional[List[str]] = None
    account_codes: Optional[List[str]] = None
    apply_golden_rules: bool = True


class DriverCalculationResult(BaseModel):
    source_account_code: str
    target_account_code: str
    month: int
    source_balance: Decimal
    driver_value: Decimal
    calculated_amount: Decimal
    driver_code: str


class DriverCalculationResponse(BaseModel):
    calculation_batch_id: str
    fiscal_year: int
    total_calculations: int
    successful: int
    failed: int
    results: List[DriverCalculationResult]
    errors: List[str]


class ValidationResult(BaseModel):
    is_valid: bool
    total_assets: Decimal
    total_liabilities: Decimal
    total_equity: Decimal
    difference: Decimal
    message: str


class SpreadAnalysis(BaseModel):
    account_code: str
    account_name: Optional[str] = None
    yield_rate: Optional[Decimal] = None
    cost_rate: Optional[Decimal] = None
    spread: Optional[Decimal] = None
    balance: Decimal
    interest_income: Optional[Decimal] = None
    interest_expense: Optional[Decimal] = None
    net_interest: Decimal
