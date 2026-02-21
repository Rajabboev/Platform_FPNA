"""
Pydantic schemas for Chart of Accounts (COA) API
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class AccountNature(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class AccountClassType(str, Enum):
    ASSETS = "ASSETS"
    LIABILITIES = "LIABILITIES"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSES = "EXPENSES"


class BusinessUnitType(str, Enum):
    REVENUE_CENTER = "REVENUE_CENTER"
    COST_CENTER = "COST_CENTER"
    PROFIT_CENTER = "PROFIT_CENTER"
    SUPPORT_CENTER = "SUPPORT_CENTER"


# ============== Account Class Schemas ==============

class AccountClassBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=1)
    name_en: str = Field(..., max_length=100)
    name_uz: str = Field(..., max_length=100)
    class_type: AccountClassType
    nature: AccountNature
    description: Optional[str] = None
    is_active: bool = True
    display_order: int = 0


class AccountClassCreate(AccountClassBase):
    pass


class AccountClassUpdate(BaseModel):
    name_en: Optional[str] = None
    name_uz: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    display_order: Optional[int] = None


class AccountClassResponse(AccountClassBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============== Account Group Schemas ==============

class AccountGroupBase(BaseModel):
    code: str = Field(..., min_length=2, max_length=2)
    class_id: int
    name_en: str = Field(..., max_length=150)
    name_uz: str = Field(..., max_length=150)
    description: Optional[str] = None
    is_active: bool = True
    display_order: int = 0


class AccountGroupCreate(AccountGroupBase):
    pass


class AccountGroupUpdate(BaseModel):
    name_en: Optional[str] = None
    name_uz: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    display_order: Optional[int] = None


class AccountGroupResponse(AccountGroupBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============== Account Category Schemas ==============

class AccountCategoryBase(BaseModel):
    code: str = Field(..., min_length=3, max_length=3)
    group_id: int
    name_en: str = Field(..., max_length=200)
    name_uz: str = Field(..., max_length=200)
    description: Optional[str] = None
    is_active: bool = True
    display_order: int = 0


class AccountCategoryCreate(AccountCategoryBase):
    pass


class AccountCategoryUpdate(BaseModel):
    name_en: Optional[str] = None
    name_uz: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    display_order: Optional[int] = None


class AccountCategoryResponse(AccountCategoryBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============== Account Schemas ==============

class AccountBase(BaseModel):
    code: str = Field(..., min_length=5, max_length=5)
    category_id: int
    name_en: str = Field(..., max_length=250)
    name_uz: str = Field(..., max_length=250)
    description: Optional[str] = None
    is_active: bool = True
    is_budgetable: bool = True
    display_order: int = 0


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    name_en: Optional[str] = None
    name_uz: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    is_budgetable: Optional[bool] = None
    display_order: Optional[int] = None


class AccountResponse(AccountBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AccountDetail(AccountResponse):
    """Account with hierarchy info"""
    class_code: str
    group_code: str
    category_code: str
    category_name: Optional[str] = None
    group_name: Optional[str] = None
    class_name: Optional[str] = None


# ============== Account Mapping Schemas ==============

class AccountMappingBase(BaseModel):
    balance_account_code: str = Field(..., max_length=5)
    pnl_account_code: str = Field(..., max_length=5)
    mapping_type: str = Field(..., max_length=50)
    description: Optional[str] = None
    is_active: bool = True


class AccountMappingCreate(AccountMappingBase):
    pass


class AccountMappingUpdate(BaseModel):
    pnl_account_code: Optional[str] = None
    mapping_type: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class AccountMappingResponse(AccountMappingBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============== Business Unit Schemas ==============

class BusinessUnitBase(BaseModel):
    code: str = Field(..., max_length=20)
    name_en: str = Field(..., max_length=150)
    name_uz: str = Field(..., max_length=150)
    description: Optional[str] = None
    unit_type: BusinessUnitType
    parent_id: Optional[int] = None
    head_user_id: Optional[int] = None
    is_active: bool = True
    display_order: int = 0


class BusinessUnitCreate(BusinessUnitBase):
    pass


class BusinessUnitUpdate(BaseModel):
    name_en: Optional[str] = None
    name_uz: Optional[str] = None
    description: Optional[str] = None
    unit_type: Optional[BusinessUnitType] = None
    parent_id: Optional[int] = None
    head_user_id: Optional[int] = None
    is_active: Optional[bool] = None
    display_order: Optional[int] = None


class BusinessUnitResponse(BusinessUnitBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BusinessUnitDetail(BusinessUnitResponse):
    """Business unit with children"""
    children: List["BusinessUnitDetail"] = []
    account_count: int = 0


# ============== Account Responsibility Schemas ==============

class AccountResponsibilityBase(BaseModel):
    account_id: int
    business_unit_id: int
    is_primary: bool = False
    can_budget: bool = True
    can_view: bool = True
    notes: Optional[str] = None


class AccountResponsibilityCreate(AccountResponsibilityBase):
    pass


class AccountResponsibilityUpdate(BaseModel):
    is_primary: Optional[bool] = None
    can_budget: Optional[bool] = None
    can_view: Optional[bool] = None
    notes: Optional[str] = None


class AccountResponsibilityResponse(AccountResponsibilityBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AccountResponsibilityDetail(AccountResponsibilityResponse):
    """With account and business unit info"""
    account_code: str
    account_name: str
    business_unit_code: str
    business_unit_name: str


# ============== Hierarchy Schemas ==============

class AccountHierarchyNode(BaseModel):
    """Node in account hierarchy tree"""
    code: str
    name_en: str
    name_uz: str
    level: int  # 1=class, 2=group, 3=category, 4=account
    is_active: bool
    children: List["AccountHierarchyNode"] = []

    class Config:
        from_attributes = True


class COAHierarchyResponse(BaseModel):
    """Full COA hierarchy"""
    classes: List[AccountHierarchyNode]
    total_accounts: int
    active_accounts: int


# ============== Bulk Operations ==============

class BulkAccountCreate(BaseModel):
    """For bulk importing accounts"""
    accounts: List[AccountCreate]


class BulkResponsibilityCreate(BaseModel):
    """For bulk assigning responsibilities"""
    assignments: List[AccountResponsibilityCreate]


# Update forward references
AccountHierarchyNode.model_rebuild()
BusinessUnitDetail.model_rebuild()
