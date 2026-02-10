"""
Pydantic schemas for Budget API
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from decimal import Decimal


class BudgetLineItemCreate(BaseModel):
    """Create line item"""
    account_code: str
    account_name: str
    category: Optional[str] = None
    month: Optional[int] = None
    quarter: Optional[int] = None
    year: Optional[int] = None
    amount: Decimal = Field(..., ge=0)
    quantity: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    notes: Optional[str] = None


class BudgetLineItemUpdate(BaseModel):
    """Update line item (all optional)"""
    account_code: Optional[str] = None
    account_name: Optional[str] = None
    category: Optional[str] = None
    month: Optional[int] = None
    quarter: Optional[int] = None
    year: Optional[int] = None
    amount: Optional[Decimal] = Field(None, ge=0)
    quantity: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    notes: Optional[str] = None


class BudgetLineItemResponse(BaseModel):
    """Line item response schema"""
    id: int
    account_code: str
    account_name: str
    category: Optional[str]
    month: Optional[int]
    quarter: Optional[int]
    year: Optional[int]
    amount: Decimal
    quantity: Optional[Decimal]
    unit_price: Optional[Decimal]
    notes: Optional[str]

    class Config:
        from_attributes = True


class BudgetResponse(BaseModel):
    """Budget response schema"""
    id: int
    budget_code: str
    fiscal_year: int
    department: Optional[str]
    branch: Optional[str]
    total_amount: Decimal
    currency: str
    description: Optional[str]
    notes: Optional[str]
    status: str
    source_file: Optional[str]
    uploaded_by: Optional[str]
    created_at: datetime
    line_items: List[BudgetLineItemResponse] = []

    class Config:
        from_attributes = True


class BudgetUpdate(BaseModel):
    """Update budget header (all optional)"""
    department: Optional[str] = None
    branch: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None


class ScaleSectionRequest(BaseModel):
    """Scale a section (category or month) to new total"""
    group_by: str = "category"  # "category" or "month"
    group_value: str  # category name or month number as string
    new_amount: Optional[Decimal] = Field(None, ge=0)
    new_quantity: Optional[Decimal] = Field(None, ge=0)


class LineItemBatchUpdate(BaseModel):
    """Single line item update in batch"""
    id: int
    amount: Optional[Decimal] = Field(None, ge=0)
    quantity: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    account_code: Optional[str] = None
    account_name: Optional[str] = None
    category: Optional[str] = None
    month: Optional[int] = None


class BatchUpdateRequest(BaseModel):
    """Batch update multiple line items"""
    updates: List[LineItemBatchUpdate]


class BudgetSummary(BaseModel):
    """Budget summary (without line items)"""
    id: int
    budget_code: str
    fiscal_year: int
    department: Optional[str]
    branch: Optional[str]
    total_amount: Decimal
    status: str
    created_at: datetime
    line_items_count: int

    class Config:
        from_attributes = True

