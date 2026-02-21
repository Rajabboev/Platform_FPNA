"""
Pydantic schemas for Budget Template API
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


class TemplateType(str, Enum):
    STANDARD = "standard"
    MIXED = "mixed"
    CUSTOM = "custom"
    REVENUE = "revenue"
    EXPENSE = "expense"
    BALANCE_SHEET = "balance_sheet"


class TemplateStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class TemplateSectionBase(BaseModel):
    code: str = Field(..., max_length=50)
    name_en: str = Field(..., max_length=200)
    name_uz: str = Field(..., max_length=200)
    description: Optional[str] = None
    section_type: str = Field(default="accounts")
    account_pattern: Optional[str] = None
    account_codes: Optional[str] = None
    is_editable: bool = True
    is_required: bool = True
    is_collapsed: bool = False
    show_subtotals: bool = True
    show_monthly: bool = True
    show_quarterly: bool = False
    show_annual: bool = True
    validation_rules: Optional[str] = None
    display_order: int = 0


class TemplateSectionCreate(TemplateSectionBase):
    template_id: int


class TemplateSectionUpdate(BaseModel):
    name_en: Optional[str] = None
    name_uz: Optional[str] = None
    description: Optional[str] = None
    account_pattern: Optional[str] = None
    account_codes: Optional[str] = None
    is_editable: Optional[bool] = None
    is_required: Optional[bool] = None
    is_collapsed: Optional[bool] = None
    show_subtotals: Optional[bool] = None
    show_monthly: Optional[bool] = None
    show_quarterly: Optional[bool] = None
    show_annual: Optional[bool] = None
    validation_rules: Optional[str] = None
    display_order: Optional[int] = None


class TemplateSectionResponse(TemplateSectionBase):
    id: int
    template_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BudgetTemplateBase(BaseModel):
    code: str = Field(..., max_length=50)
    name_en: str = Field(..., max_length=200)
    name_uz: str = Field(..., max_length=200)
    description: Optional[str] = None
    template_type: TemplateType = TemplateType.STANDARD
    fiscal_year: Optional[int] = None
    include_baseline: bool = True
    include_prior_year: bool = True
    include_variance: bool = True
    instructions: Optional[str] = None
    is_active: bool = True
    display_order: int = 0


class BudgetTemplateCreate(BudgetTemplateBase):
    sections: Optional[List[TemplateSectionBase]] = None


class BudgetTemplateUpdate(BaseModel):
    name_en: Optional[str] = None
    name_uz: Optional[str] = None
    description: Optional[str] = None
    template_type: Optional[TemplateType] = None
    status: Optional[TemplateStatus] = None
    fiscal_year: Optional[int] = None
    include_baseline: Optional[bool] = None
    include_prior_year: Optional[bool] = None
    include_variance: Optional[bool] = None
    instructions: Optional[str] = None
    is_active: Optional[bool] = None
    display_order: Optional[int] = None


class BudgetTemplateResponse(BudgetTemplateBase):
    id: int
    status: TemplateStatus
    version: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by_user_id: Optional[int] = None

    class Config:
        from_attributes = True


class BudgetTemplateDetail(BudgetTemplateResponse):
    sections: List[TemplateSectionResponse] = []
    assignment_count: int = 0


class TemplateAssignmentBase(BaseModel):
    template_id: int
    business_unit_id: int
    fiscal_year: int
    deadline: Optional[date] = None
    reminder_date: Optional[date] = None
    notes: Optional[str] = None


class TemplateAssignmentCreate(TemplateAssignmentBase):
    pass


class TemplateAssignmentUpdate(BaseModel):
    deadline: Optional[date] = None
    reminder_date: Optional[date] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class TemplateAssignmentResponse(TemplateAssignmentBase):
    id: int
    status: str
    assigned_by_user_id: Optional[int] = None
    assigned_at: datetime
    submitted_at: Optional[datetime] = None
    submitted_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TemplateAssignmentDetail(TemplateAssignmentResponse):
    template_code: str
    template_name: str
    business_unit_code: str
    business_unit_name: str


class BulkAssignmentCreate(BaseModel):
    template_id: int
    business_unit_ids: List[int]
    fiscal_year: int
    deadline: Optional[date] = None
    reminder_date: Optional[date] = None


class MonthlyValues(BaseModel):
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


class TemplateLineItemBase(BaseModel):
    account_code: str = Field(..., max_length=5)
    adjustment_notes: Optional[str] = None


class TemplateLineItemCreate(TemplateLineItemBase):
    assignment_id: int
    section_id: int
    baseline: Optional[MonthlyValues] = None
    adjusted: Optional[MonthlyValues] = None


class TemplateLineItemUpdate(BaseModel):
    adjusted: Optional[MonthlyValues] = None
    adjustment_notes: Optional[str] = None
    is_locked: Optional[bool] = None


class TemplateLineItemResponse(TemplateLineItemBase):
    id: int
    assignment_id: int
    section_id: int
    baseline_jan: Decimal
    baseline_feb: Decimal
    baseline_mar: Decimal
    baseline_apr: Decimal
    baseline_may: Decimal
    baseline_jun: Decimal
    baseline_jul: Decimal
    baseline_aug: Decimal
    baseline_sep: Decimal
    baseline_oct: Decimal
    baseline_nov: Decimal
    baseline_dec: Decimal
    adjusted_jan: Optional[Decimal] = None
    adjusted_feb: Optional[Decimal] = None
    adjusted_mar: Optional[Decimal] = None
    adjusted_apr: Optional[Decimal] = None
    adjusted_may: Optional[Decimal] = None
    adjusted_jun: Optional[Decimal] = None
    adjusted_jul: Optional[Decimal] = None
    adjusted_aug: Optional[Decimal] = None
    adjusted_sep: Optional[Decimal] = None
    adjusted_oct: Optional[Decimal] = None
    adjusted_nov: Optional[Decimal] = None
    adjusted_dec: Optional[Decimal] = None
    is_locked: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TemplateLineItemDetail(TemplateLineItemResponse):
    account_name: Optional[str] = None
    baseline_total: Decimal
    adjusted_total: Decimal
    variance: Decimal
    variance_percent: Optional[Decimal] = None


class PrefilledTemplateRequest(BaseModel):
    assignment_id: int
    baseline_version: Optional[int] = None
    apply_drivers: bool = True


class PrefilledTemplateResponse(BaseModel):
    assignment_id: int
    template_code: str
    business_unit_code: str
    fiscal_year: int
    sections: List[Dict]
    total_baseline: Decimal
    total_adjusted: Decimal
    line_items_count: int


class TemplateSubmissionRequest(BaseModel):
    assignment_id: int
    submitted_by_user_id: int
    notes: Optional[str] = None


class TemplateSubmissionResponse(BaseModel):
    assignment_id: int
    status: str
    submitted_at: datetime
    submitted_by_user_id: int
    validation_passed: bool
    validation_errors: List[str]
