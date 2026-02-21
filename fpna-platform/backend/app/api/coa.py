"""
Chart of Accounts (COA) API endpoints
Provides CRUD operations for account hierarchy and business unit management
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from app.database import get_db
from app.models.coa import (
    AccountClass, AccountGroup, AccountCategory, Account, AccountMapping,
    AccountClassType, AccountNature
)
from app.models.business_unit import BusinessUnit, AccountResponsibility, BusinessUnitType
from app.schemas.coa import (
    AccountClassCreate, AccountClassUpdate, AccountClassResponse,
    AccountGroupCreate, AccountGroupUpdate, AccountGroupResponse,
    AccountCategoryCreate, AccountCategoryUpdate, AccountCategoryResponse,
    AccountCreate, AccountUpdate, AccountResponse, AccountDetail,
    AccountMappingCreate, AccountMappingUpdate, AccountMappingResponse,
    BusinessUnitCreate, BusinessUnitUpdate, BusinessUnitResponse, BusinessUnitDetail,
    AccountResponsibilityCreate, AccountResponsibilityUpdate, AccountResponsibilityResponse,
    AccountResponsibilityDetail, AccountHierarchyNode, COAHierarchyResponse,
    BulkAccountCreate, BulkResponsibilityCreate
)

router = APIRouter(prefix="/coa", tags=["Chart of Accounts"])


# ============== Account Classes ==============

@router.get("/classes", response_model=List[AccountClassResponse])
def list_account_classes(
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """List all account classes (1-digit level)"""
    query = db.query(AccountClass)
    if is_active is not None:
        query = query.filter(AccountClass.is_active == is_active)
    return query.order_by(AccountClass.display_order, AccountClass.code).all()


@router.post("/classes", response_model=AccountClassResponse, status_code=201)
def create_account_class(
    data: AccountClassCreate,
    db: Session = Depends(get_db)
):
    """Create a new account class"""
    existing = db.query(AccountClass).filter(AccountClass.code == data.code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Account class with code {data.code} already exists")
    
    account_class = AccountClass(**data.model_dump())
    db.add(account_class)
    db.commit()
    db.refresh(account_class)
    return account_class


@router.get("/classes/{code}", response_model=AccountClassResponse)
def get_account_class(code: str, db: Session = Depends(get_db)):
    """Get account class by code"""
    account_class = db.query(AccountClass).filter(AccountClass.code == code).first()
    if not account_class:
        raise HTTPException(status_code=404, detail="Account class not found")
    return account_class


@router.patch("/classes/{code}", response_model=AccountClassResponse)
def update_account_class(
    code: str,
    data: AccountClassUpdate,
    db: Session = Depends(get_db)
):
    """Update account class"""
    account_class = db.query(AccountClass).filter(AccountClass.code == code).first()
    if not account_class:
        raise HTTPException(status_code=404, detail="Account class not found")
    
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(account_class, field, value)
    
    db.commit()
    db.refresh(account_class)
    return account_class


# ============== Account Groups ==============

@router.get("/groups", response_model=List[AccountGroupResponse])
def list_account_groups(
    class_code: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """List account groups (2-digit level)"""
    query = db.query(AccountGroup)
    
    if class_code:
        account_class = db.query(AccountClass).filter(AccountClass.code == class_code).first()
        if account_class:
            query = query.filter(AccountGroup.class_id == account_class.id)
    
    if is_active is not None:
        query = query.filter(AccountGroup.is_active == is_active)
    
    return query.order_by(AccountGroup.code).all()


@router.post("/groups", response_model=AccountGroupResponse, status_code=201)
def create_account_group(
    data: AccountGroupCreate,
    db: Session = Depends(get_db)
):
    """Create a new account group"""
    existing = db.query(AccountGroup).filter(AccountGroup.code == data.code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Account group with code {data.code} already exists")
    
    account_class = db.query(AccountClass).filter(AccountClass.id == data.class_id).first()
    if not account_class:
        raise HTTPException(status_code=400, detail="Account class not found")
    
    group = AccountGroup(**data.model_dump())
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@router.get("/groups/{code}", response_model=AccountGroupResponse)
def get_account_group(code: str, db: Session = Depends(get_db)):
    """Get account group by code"""
    group = db.query(AccountGroup).filter(AccountGroup.code == code).first()
    if not group:
        raise HTTPException(status_code=404, detail="Account group not found")
    return group


@router.patch("/groups/{code}", response_model=AccountGroupResponse)
def update_account_group(
    code: str,
    data: AccountGroupUpdate,
    db: Session = Depends(get_db)
):
    """Update account group"""
    group = db.query(AccountGroup).filter(AccountGroup.code == code).first()
    if not group:
        raise HTTPException(status_code=404, detail="Account group not found")
    
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(group, field, value)
    
    db.commit()
    db.refresh(group)
    return group


# ============== Account Categories ==============

@router.get("/categories", response_model=List[AccountCategoryResponse])
def list_account_categories(
    group_code: Optional[str] = None,
    class_code: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """List account categories (3-digit level)"""
    query = db.query(AccountCategory)
    
    if group_code:
        group = db.query(AccountGroup).filter(AccountGroup.code == group_code).first()
        if group:
            query = query.filter(AccountCategory.group_id == group.id)
    elif class_code:
        account_class = db.query(AccountClass).filter(AccountClass.code == class_code).first()
        if account_class:
            groups = db.query(AccountGroup.id).filter(AccountGroup.class_id == account_class.id)
            query = query.filter(AccountCategory.group_id.in_(groups))
    
    if is_active is not None:
        query = query.filter(AccountCategory.is_active == is_active)
    
    return query.order_by(AccountCategory.code).all()


@router.post("/categories", response_model=AccountCategoryResponse, status_code=201)
def create_account_category(
    data: AccountCategoryCreate,
    db: Session = Depends(get_db)
):
    """Create a new account category"""
    existing = db.query(AccountCategory).filter(AccountCategory.code == data.code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Account category with code {data.code} already exists")
    
    group = db.query(AccountGroup).filter(AccountGroup.id == data.group_id).first()
    if not group:
        raise HTTPException(status_code=400, detail="Account group not found")
    
    category = AccountCategory(**data.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.get("/categories/{code}", response_model=AccountCategoryResponse)
def get_account_category(code: str, db: Session = Depends(get_db)):
    """Get account category by code"""
    category = db.query(AccountCategory).filter(AccountCategory.code == code).first()
    if not category:
        raise HTTPException(status_code=404, detail="Account category not found")
    return category


@router.patch("/categories/{code}", response_model=AccountCategoryResponse)
def update_account_category(
    code: str,
    data: AccountCategoryUpdate,
    db: Session = Depends(get_db)
):
    """Update account category"""
    category = db.query(AccountCategory).filter(AccountCategory.code == code).first()
    if not category:
        raise HTTPException(status_code=404, detail="Account category not found")
    
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(category, field, value)
    
    db.commit()
    db.refresh(category)
    return category


# ============== Accounts (5-digit) ==============

@router.get("/accounts", response_model=List[AccountResponse])
def list_accounts(
    category_code: Optional[str] = None,
    group_code: Optional[str] = None,
    class_code: Optional[str] = None,
    is_active: Optional[bool] = None,
    is_budgetable: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """List accounts (5-digit level) with filters"""
    query = db.query(Account)
    
    if category_code:
        category = db.query(AccountCategory).filter(AccountCategory.code == category_code).first()
        if category:
            query = query.filter(Account.category_id == category.id)
    elif group_code:
        group = db.query(AccountGroup).filter(AccountGroup.code == group_code).first()
        if group:
            categories = db.query(AccountCategory.id).filter(AccountCategory.group_id == group.id)
            query = query.filter(Account.category_id.in_(categories))
    elif class_code:
        account_class = db.query(AccountClass).filter(AccountClass.code == class_code).first()
        if account_class:
            groups = db.query(AccountGroup.id).filter(AccountGroup.class_id == account_class.id)
            categories = db.query(AccountCategory.id).filter(AccountCategory.group_id.in_(groups))
            query = query.filter(Account.category_id.in_(categories))
    
    if is_active is not None:
        query = query.filter(Account.is_active == is_active)
    
    if is_budgetable is not None:
        query = query.filter(Account.is_budgetable == is_budgetable)
    
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (Account.code.ilike(search_filter)) |
            (Account.name_en.ilike(search_filter)) |
            (Account.name_uz.ilike(search_filter))
        )
    
    return query.order_by(Account.code).offset(offset).limit(limit).all()


@router.post("/accounts", response_model=AccountResponse, status_code=201)
def create_account(
    data: AccountCreate,
    db: Session = Depends(get_db)
):
    """Create a new account"""
    existing = db.query(Account).filter(Account.code == data.code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Account with code {data.code} already exists")
    
    category = db.query(AccountCategory).filter(AccountCategory.id == data.category_id).first()
    if not category:
        raise HTTPException(status_code=400, detail="Account category not found")
    
    account = Account(**data.model_dump())
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.post("/accounts/bulk", response_model=dict, status_code=201)
def bulk_create_accounts(
    data: BulkAccountCreate,
    db: Session = Depends(get_db)
):
    """Bulk create accounts"""
    created = 0
    skipped = 0
    errors = []
    
    for account_data in data.accounts:
        existing = db.query(Account).filter(Account.code == account_data.code).first()
        if existing:
            skipped += 1
            continue
        
        category = db.query(AccountCategory).filter(AccountCategory.id == account_data.category_id).first()
        if not category:
            errors.append(f"Category not found for account {account_data.code}")
            continue
        
        account = Account(**account_data.model_dump())
        db.add(account)
        created += 1
    
    db.commit()
    return {"created": created, "skipped": skipped, "errors": errors}


@router.get("/accounts/{code}", response_model=AccountDetail)
def get_account(code: str, db: Session = Depends(get_db)):
    """Get account by code with hierarchy info"""
    account = db.query(Account).filter(Account.code == code).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    category = account.account_category
    group = category.account_group if category else None
    account_class = group.account_class if group else None
    
    return AccountDetail(
        **{c.name: getattr(account, c.name) for c in account.__table__.columns},
        class_code=account.class_code,
        group_code=account.group_code,
        category_code=account.category_code,
        category_name=category.name_en if category else None,
        group_name=group.name_en if group else None,
        class_name=account_class.name_en if account_class else None
    )


@router.patch("/accounts/{code}", response_model=AccountResponse)
def update_account(
    code: str,
    data: AccountUpdate,
    db: Session = Depends(get_db)
):
    """Update account"""
    account = db.query(Account).filter(Account.code == code).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(account, field, value)
    
    db.commit()
    db.refresh(account)
    return account


@router.get("/accounts/{code}/children", response_model=List[AccountResponse])
def get_account_children(code: str, db: Session = Depends(get_db)):
    """Get child accounts for a given code prefix"""
    return db.query(Account).filter(Account.code.startswith(code)).order_by(Account.code).all()


# ============== Account Mappings ==============

@router.get("/mappings", response_model=List[AccountMappingResponse])
def list_account_mappings(
    balance_code: Optional[str] = None,
    pnl_code: Optional[str] = None,
    mapping_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """List account mappings (Balance -> P&L)"""
    query = db.query(AccountMapping)
    
    if balance_code:
        query = query.filter(AccountMapping.balance_account_code.startswith(balance_code))
    if pnl_code:
        query = query.filter(AccountMapping.pnl_account_code.startswith(pnl_code))
    if mapping_type:
        query = query.filter(AccountMapping.mapping_type == mapping_type)
    if is_active is not None:
        query = query.filter(AccountMapping.is_active == is_active)
    
    return query.all()


@router.post("/mappings", response_model=AccountMappingResponse, status_code=201)
def create_account_mapping(
    data: AccountMappingCreate,
    db: Session = Depends(get_db)
):
    """Create account mapping"""
    mapping = AccountMapping(**data.model_dump())
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping


@router.delete("/mappings/{mapping_id}")
def delete_account_mapping(mapping_id: int, db: Session = Depends(get_db)):
    """Delete account mapping"""
    mapping = db.query(AccountMapping).filter(AccountMapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")
    
    db.delete(mapping)
    db.commit()
    return {"message": "Mapping deleted"}


# ============== Hierarchy ==============

@router.get("/hierarchy", response_model=COAHierarchyResponse)
def get_coa_hierarchy(
    is_active: Optional[bool] = True,
    db: Session = Depends(get_db)
):
    """Get full COA hierarchy as tree structure"""
    classes = db.query(AccountClass).order_by(AccountClass.display_order, AccountClass.code).all()
    
    hierarchy = []
    total_accounts = 0
    active_accounts = 0
    
    for acc_class in classes:
        if is_active is not None and acc_class.is_active != is_active:
            continue
            
        class_node = AccountHierarchyNode(
            code=acc_class.code,
            name_en=acc_class.name_en,
            name_uz=acc_class.name_uz,
            level=1,
            is_active=acc_class.is_active,
            children=[]
        )
        
        groups = db.query(AccountGroup).filter(AccountGroup.class_id == acc_class.id).order_by(AccountGroup.code).all()
        
        for group in groups:
            if is_active is not None and group.is_active != is_active:
                continue
                
            group_node = AccountHierarchyNode(
                code=group.code,
                name_en=group.name_en,
                name_uz=group.name_uz,
                level=2,
                is_active=group.is_active,
                children=[]
            )
            
            categories = db.query(AccountCategory).filter(AccountCategory.group_id == group.id).order_by(AccountCategory.code).all()
            
            for category in categories:
                if is_active is not None and category.is_active != is_active:
                    continue
                    
                category_node = AccountHierarchyNode(
                    code=category.code,
                    name_en=category.name_en,
                    name_uz=category.name_uz,
                    level=3,
                    is_active=category.is_active,
                    children=[]
                )
                
                accounts = db.query(Account).filter(Account.category_id == category.id).order_by(Account.code).all()
                
                for account in accounts:
                    total_accounts += 1
                    if account.is_active:
                        active_accounts += 1
                    
                    if is_active is not None and account.is_active != is_active:
                        continue
                    
                    account_node = AccountHierarchyNode(
                        code=account.code,
                        name_en=account.name_en,
                        name_uz=account.name_uz,
                        level=4,
                        is_active=account.is_active,
                        children=[]
                    )
                    category_node.children.append(account_node)
                
                group_node.children.append(category_node)
            
            class_node.children.append(group_node)
        
        hierarchy.append(class_node)
    
    return COAHierarchyResponse(
        classes=hierarchy,
        total_accounts=total_accounts,
        active_accounts=active_accounts
    )


# ============== Business Units ==============

@router.get("/business-units", response_model=List[BusinessUnitResponse])
def list_business_units(
    unit_type: Optional[BusinessUnitType] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """List all business units"""
    query = db.query(BusinessUnit)
    
    if unit_type:
        query = query.filter(BusinessUnit.unit_type == unit_type)
    if is_active is not None:
        query = query.filter(BusinessUnit.is_active == is_active)
    
    return query.order_by(BusinessUnit.display_order, BusinessUnit.code).all()


@router.post("/business-units", response_model=BusinessUnitResponse, status_code=201)
def create_business_unit(
    data: BusinessUnitCreate,
    db: Session = Depends(get_db)
):
    """Create a new business unit"""
    existing = db.query(BusinessUnit).filter(BusinessUnit.code == data.code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Business unit with code {data.code} already exists")
    
    unit = BusinessUnit(**data.model_dump())
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit


@router.get("/business-units/{code}", response_model=BusinessUnitDetail)
def get_business_unit(code: str, db: Session = Depends(get_db)):
    """Get business unit by code"""
    unit = db.query(BusinessUnit).filter(BusinessUnit.code == code).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Business unit not found")
    
    account_count = db.query(func.count(AccountResponsibility.id)).filter(
        AccountResponsibility.business_unit_id == unit.id
    ).scalar()
    
    return BusinessUnitDetail(
        **{c.name: getattr(unit, c.name) for c in unit.__table__.columns},
        children=[],
        account_count=account_count
    )


@router.patch("/business-units/{code}", response_model=BusinessUnitResponse)
def update_business_unit(
    code: str,
    data: BusinessUnitUpdate,
    db: Session = Depends(get_db)
):
    """Update business unit"""
    unit = db.query(BusinessUnit).filter(BusinessUnit.code == code).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Business unit not found")
    
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(unit, field, value)
    
    db.commit()
    db.refresh(unit)
    return unit


@router.delete("/business-units/{code}")
def delete_business_unit(code: str, db: Session = Depends(get_db)):
    """Delete business unit"""
    unit = db.query(BusinessUnit).filter(BusinessUnit.code == code).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Business unit not found")
    
    db.delete(unit)
    db.commit()
    return {"message": "Business unit deleted"}


# ============== Account Responsibilities ==============

@router.get("/responsibilities", response_model=List[AccountResponsibilityDetail])
def list_responsibilities(
    account_code: Optional[str] = None,
    business_unit_code: Optional[str] = None,
    is_primary: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """List account responsibilities"""
    query = db.query(AccountResponsibility)
    
    if account_code:
        account = db.query(Account).filter(Account.code == account_code).first()
        if account:
            query = query.filter(AccountResponsibility.account_id == account.id)
    
    if business_unit_code:
        unit = db.query(BusinessUnit).filter(BusinessUnit.code == business_unit_code).first()
        if unit:
            query = query.filter(AccountResponsibility.business_unit_id == unit.id)
    
    if is_primary is not None:
        query = query.filter(AccountResponsibility.is_primary == is_primary)
    
    responsibilities = query.all()
    
    result = []
    for resp in responsibilities:
        account = db.query(Account).filter(Account.id == resp.account_id).first()
        unit = db.query(BusinessUnit).filter(BusinessUnit.id == resp.business_unit_id).first()
        
        result.append(AccountResponsibilityDetail(
            **{c.name: getattr(resp, c.name) for c in resp.__table__.columns},
            account_code=account.code if account else "",
            account_name=account.name_en if account else "",
            business_unit_code=unit.code if unit else "",
            business_unit_name=unit.name_en if unit else ""
        ))
    
    return result


@router.post("/responsibilities", response_model=AccountResponsibilityResponse, status_code=201)
def create_responsibility(
    data: AccountResponsibilityCreate,
    db: Session = Depends(get_db)
):
    """Create account responsibility"""
    account = db.query(Account).filter(Account.id == data.account_id).first()
    if not account:
        raise HTTPException(status_code=400, detail="Account not found")
    
    unit = db.query(BusinessUnit).filter(BusinessUnit.id == data.business_unit_id).first()
    if not unit:
        raise HTTPException(status_code=400, detail="Business unit not found")
    
    existing = db.query(AccountResponsibility).filter(
        AccountResponsibility.account_id == data.account_id,
        AccountResponsibility.business_unit_id == data.business_unit_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Responsibility already exists")
    
    resp = AccountResponsibility(**data.model_dump())
    db.add(resp)
    db.commit()
    db.refresh(resp)
    return resp


@router.post("/responsibilities/bulk", response_model=dict, status_code=201)
def bulk_create_responsibilities(
    data: BulkResponsibilityCreate,
    db: Session = Depends(get_db)
):
    """Bulk create responsibilities"""
    created = 0
    skipped = 0
    
    for assignment in data.assignments:
        existing = db.query(AccountResponsibility).filter(
            AccountResponsibility.account_id == assignment.account_id,
            AccountResponsibility.business_unit_id == assignment.business_unit_id
        ).first()
        if existing:
            skipped += 1
            continue
        
        resp = AccountResponsibility(**assignment.model_dump())
        db.add(resp)
        created += 1
    
    db.commit()
    return {"created": created, "skipped": skipped}


@router.delete("/responsibilities/{responsibility_id}")
def delete_responsibility(responsibility_id: int, db: Session = Depends(get_db)):
    """Delete responsibility"""
    resp = db.query(AccountResponsibility).filter(AccountResponsibility.id == responsibility_id).first()
    if not resp:
        raise HTTPException(status_code=404, detail="Responsibility not found")
    
    db.delete(resp)
    db.commit()
    return {"message": "Responsibility deleted"}


# ============== Seed Data ==============

@router.post("/seed", response_model=dict)
def seed_coa_data(db: Session = Depends(get_db)):
    """Seed default Uzbek Banking COA data"""
    results = {
        "classes": 0,
        "groups": 0,
        "categories": 0,
        "accounts": 0,
        "business_units": 0
    }
    
    # Seed Account Classes
    classes_data = [
        {"code": "1", "name_en": "Assets", "name_uz": "Aktivlar", "class_type": AccountClassType.ASSETS, "nature": AccountNature.DEBIT, "display_order": 1},
        {"code": "2", "name_en": "Liabilities", "name_uz": "Majburiyatlar", "class_type": AccountClassType.LIABILITIES, "nature": AccountNature.CREDIT, "display_order": 2},
        {"code": "3", "name_en": "Equity", "name_uz": "Xususiy kapital", "class_type": AccountClassType.EQUITY, "nature": AccountNature.CREDIT, "display_order": 3},
        {"code": "4", "name_en": "Revenue", "name_uz": "Daromadlar", "class_type": AccountClassType.REVENUE, "nature": AccountNature.CREDIT, "display_order": 4},
        {"code": "5", "name_en": "Expenses", "name_uz": "Xarajatlar", "class_type": AccountClassType.EXPENSES, "nature": AccountNature.DEBIT, "display_order": 5},
    ]
    
    for cls_data in classes_data:
        existing = db.query(AccountClass).filter(AccountClass.code == cls_data["code"]).first()
        if not existing:
            db.add(AccountClass(**cls_data))
            results["classes"] += 1
    db.commit()
    
    # Get class map for groups
    class_map = {c.code: c.id for c in db.query(AccountClass).all()}
    
    # Seed Account Groups (2-digit)
    groups_data = [
        {"code": "10", "class_id": class_map.get("1"), "name_en": "Cash and Cash Equivalents", "name_uz": "Naqd pul va ekvivalentlar", "display_order": 1},
        {"code": "11", "class_id": class_map.get("1"), "name_en": "Due from Central Bank", "name_uz": "Markaziy bankdagi mablag'lar", "display_order": 2},
        {"code": "12", "class_id": class_map.get("1"), "name_en": "Loans to Customers", "name_uz": "Mijozlarga kreditlar", "display_order": 3},
        {"code": "14", "class_id": class_map.get("1"), "name_en": "Consumer Loans", "name_uz": "Iste'mol kreditlari", "display_order": 5},
        {"code": "15", "class_id": class_map.get("1"), "name_en": "Mortgage Loans", "name_uz": "Ipoteka kreditlari", "display_order": 6},
        {"code": "17", "class_id": class_map.get("1"), "name_en": "Investment Securities", "name_uz": "Investitsiya qimmatli qog'ozlari", "display_order": 8},
        {"code": "18", "class_id": class_map.get("1"), "name_en": "Fixed Assets", "name_uz": "Asosiy vositalar", "display_order": 9},
        {"code": "20", "class_id": class_map.get("2"), "name_en": "Customer Deposits", "name_uz": "Mijozlar depozitlari", "display_order": 1},
        {"code": "21", "class_id": class_map.get("2"), "name_en": "Due to Other Banks", "name_uz": "Boshqa banklarga qarz", "display_order": 2},
        {"code": "22", "class_id": class_map.get("2"), "name_en": "Borrowed Funds", "name_uz": "Qarz mablag'lari", "display_order": 3},
        {"code": "30", "class_id": class_map.get("3"), "name_en": "Share Capital", "name_uz": "Ustav kapitali", "display_order": 1},
        {"code": "31", "class_id": class_map.get("3"), "name_en": "Reserves", "name_uz": "Zaxiralar", "display_order": 2},
        {"code": "32", "class_id": class_map.get("3"), "name_en": "Retained Earnings", "name_uz": "Taqsimlanmagan foyda", "display_order": 3},
        {"code": "40", "class_id": class_map.get("4"), "name_en": "Interest Income", "name_uz": "Foiz daromadlari", "display_order": 1},
        {"code": "41", "class_id": class_map.get("4"), "name_en": "Fee and Commission Income", "name_uz": "Komissiya daromadlari", "display_order": 2},
        {"code": "42", "class_id": class_map.get("4"), "name_en": "Trading Income", "name_uz": "Savdo daromadlari", "display_order": 3},
        {"code": "50", "class_id": class_map.get("5"), "name_en": "Interest Expense", "name_uz": "Foiz xarajatlari", "display_order": 1},
        {"code": "51", "class_id": class_map.get("5"), "name_en": "Fee and Commission Expense", "name_uz": "Komissiya xarajatlari", "display_order": 2},
        {"code": "52", "class_id": class_map.get("5"), "name_en": "Personnel Expense", "name_uz": "Xodimlar xarajatlari", "display_order": 3},
        {"code": "53", "class_id": class_map.get("5"), "name_en": "Administrative Expense", "name_uz": "Ma'muriy xarajatlar", "display_order": 4},
        {"code": "56", "class_id": class_map.get("5"), "name_en": "Provision Expense", "name_uz": "Zaxira xarajatlari", "display_order": 7},
    ]
    
    for grp_data in groups_data:
        if grp_data["class_id"]:
            existing = db.query(AccountGroup).filter(AccountGroup.code == grp_data["code"]).first()
            if not existing:
                db.add(AccountGroup(**grp_data))
                results["groups"] += 1
    db.commit()
    
    # Get group map for categories
    group_map = {g.code: g.id for g in db.query(AccountGroup).all()}
    
    # Seed Account Categories (3-digit)
    categories_data = [
        {"code": "101", "group_id": group_map.get("10"), "name_en": "Cash on Hand", "name_uz": "Kassadagi naqd pul"},
        {"code": "102", "group_id": group_map.get("10"), "name_en": "Cash in ATMs", "name_uz": "Bankomatdagi pul"},
        {"code": "121", "group_id": group_map.get("12"), "name_en": "Corporate Loans", "name_uz": "Korporativ kreditlar"},
        {"code": "122", "group_id": group_map.get("12"), "name_en": "SME Loans", "name_uz": "KOB kreditlari"},
        {"code": "141", "group_id": group_map.get("14"), "name_en": "Personal Loans", "name_uz": "Shaxsiy kreditlar"},
        {"code": "142", "group_id": group_map.get("14"), "name_en": "Credit Cards", "name_uz": "Kredit kartalari"},
        {"code": "201", "group_id": group_map.get("20"), "name_en": "Current Accounts", "name_uz": "Joriy hisoblar"},
        {"code": "202", "group_id": group_map.get("20"), "name_en": "Savings Deposits", "name_uz": "Jamg'arma depozitlari"},
        {"code": "203", "group_id": group_map.get("20"), "name_en": "Term Deposits", "name_uz": "Muddatli depozitlar"},
        {"code": "401", "group_id": group_map.get("40"), "name_en": "Loan Interest Income", "name_uz": "Kredit foiz daromadi"},
        {"code": "402", "group_id": group_map.get("40"), "name_en": "Investment Interest Income", "name_uz": "Investitsiya foiz daromadi"},
        {"code": "501", "group_id": group_map.get("50"), "name_en": "Deposit Interest Expense", "name_uz": "Depozit foiz xarajati"},
        {"code": "521", "group_id": group_map.get("52"), "name_en": "Salaries", "name_uz": "Ish haqi"},
        {"code": "522", "group_id": group_map.get("52"), "name_en": "Benefits", "name_uz": "Imtiyozlar"},
        {"code": "561", "group_id": group_map.get("56"), "name_en": "Loan Loss Provision", "name_uz": "Kredit yo'qotish zaxirasi"},
    ]
    
    for cat_data in categories_data:
        if cat_data["group_id"]:
            existing = db.query(AccountCategory).filter(AccountCategory.code == cat_data["code"]).first()
            if not existing:
                db.add(AccountCategory(**cat_data))
                results["categories"] += 1
    db.commit()
    
    # Get category map for accounts
    category_map = {c.code: c.id for c in db.query(AccountCategory).all()}
    
    # Seed some sample accounts (5-digit)
    accounts_data = [
        {"code": "10100", "category_id": category_map.get("101"), "name_en": "Cash in Main Vault", "name_uz": "Asosiy kassadagi pul", "is_budgetable": False},
        {"code": "10101", "category_id": category_map.get("101"), "name_en": "Cash in Branch Vaults", "name_uz": "Filial kassalaridagi pul", "is_budgetable": False},
        {"code": "12100", "category_id": category_map.get("121"), "name_en": "Corporate Loans - UZS", "name_uz": "Korporativ kreditlar - UZS", "is_budgetable": True},
        {"code": "12101", "category_id": category_map.get("121"), "name_en": "Corporate Loans - USD", "name_uz": "Korporativ kreditlar - USD", "is_budgetable": True},
        {"code": "12200", "category_id": category_map.get("122"), "name_en": "SME Loans - UZS", "name_uz": "KOB kreditlari - UZS", "is_budgetable": True},
        {"code": "14100", "category_id": category_map.get("141"), "name_en": "Personal Loans - UZS", "name_uz": "Shaxsiy kreditlar - UZS", "is_budgetable": True},
        {"code": "20100", "category_id": category_map.get("201"), "name_en": "Current Accounts - Individuals", "name_uz": "Joriy hisoblar - Jismoniy", "is_budgetable": True},
        {"code": "20101", "category_id": category_map.get("201"), "name_en": "Current Accounts - Legal Entities", "name_uz": "Joriy hisoblar - Yuridik", "is_budgetable": True},
        {"code": "20200", "category_id": category_map.get("202"), "name_en": "Savings Deposits - UZS", "name_uz": "Jamg'arma - UZS", "is_budgetable": True},
        {"code": "20300", "category_id": category_map.get("203"), "name_en": "Term Deposits - UZS", "name_uz": "Muddatli depozit - UZS", "is_budgetable": True},
        {"code": "40100", "category_id": category_map.get("401"), "name_en": "Corporate Loan Interest", "name_uz": "Korporativ kredit foizi", "is_budgetable": True},
        {"code": "40101", "category_id": category_map.get("401"), "name_en": "SME Loan Interest", "name_uz": "KOB kredit foizi", "is_budgetable": True},
        {"code": "40102", "category_id": category_map.get("401"), "name_en": "Consumer Loan Interest", "name_uz": "Iste'mol kredit foizi", "is_budgetable": True},
        {"code": "50100", "category_id": category_map.get("501"), "name_en": "Current Account Interest", "name_uz": "Joriy hisob foizi", "is_budgetable": True},
        {"code": "50101", "category_id": category_map.get("501"), "name_en": "Savings Interest Expense", "name_uz": "Jamg'arma foiz xarajati", "is_budgetable": True},
        {"code": "50102", "category_id": category_map.get("501"), "name_en": "Term Deposit Interest", "name_uz": "Muddatli depozit foizi", "is_budgetable": True},
        {"code": "52100", "category_id": category_map.get("521"), "name_en": "Base Salaries", "name_uz": "Asosiy ish haqi", "is_budgetable": True},
        {"code": "52101", "category_id": category_map.get("521"), "name_en": "Bonuses", "name_uz": "Bonuslar", "is_budgetable": True},
        {"code": "56100", "category_id": category_map.get("561"), "name_en": "Corporate Loan Provisions", "name_uz": "Korporativ kredit zaxirasi", "is_budgetable": True},
        {"code": "56101", "category_id": category_map.get("561"), "name_en": "Consumer Loan Provisions", "name_uz": "Iste'mol kredit zaxirasi", "is_budgetable": True},
    ]
    
    for acc_data in accounts_data:
        if acc_data["category_id"]:
            existing = db.query(Account).filter(Account.code == acc_data["code"]).first()
            if not existing:
                db.add(Account(**acc_data))
                results["accounts"] += 1
    db.commit()
    
    # Seed Business Units
    bu_data = [
        {"code": "CORP", "name_en": "Corporate Banking", "name_uz": "Korporativ bank", "unit_type": BusinessUnitType.REVENUE_CENTER, "display_order": 1},
        {"code": "RETAIL", "name_en": "Retail Banking", "name_uz": "Chakana bank", "unit_type": BusinessUnitType.REVENUE_CENTER, "display_order": 2},
        {"code": "SME", "name_en": "SME Banking", "name_uz": "KOB bank", "unit_type": BusinessUnitType.REVENUE_CENTER, "display_order": 3},
        {"code": "TREASURY", "name_en": "Treasury", "name_uz": "G'aznachilik", "unit_type": BusinessUnitType.PROFIT_CENTER, "display_order": 4},
        {"code": "HR", "name_en": "Human Resources", "name_uz": "Kadrlar bo'limi", "unit_type": BusinessUnitType.COST_CENTER, "display_order": 5},
        {"code": "IT", "name_en": "Information Technology", "name_uz": "AT bo'limi", "unit_type": BusinessUnitType.COST_CENTER, "display_order": 6},
        {"code": "RISK", "name_en": "Risk Management", "name_uz": "Risk boshqaruvi", "unit_type": BusinessUnitType.COST_CENTER, "display_order": 7},
        {"code": "OPS", "name_en": "Operations", "name_uz": "Operatsiyalar", "unit_type": BusinessUnitType.COST_CENTER, "display_order": 8},
        {"code": "ADMIN", "name_en": "Administration", "name_uz": "Ma'muriyat", "unit_type": BusinessUnitType.COST_CENTER, "display_order": 9},
    ]
    
    for bu in bu_data:
        existing = db.query(BusinessUnit).filter(BusinessUnit.code == bu["code"]).first()
        if not existing:
            db.add(BusinessUnit(**bu))
            results["business_units"] += 1
    db.commit()
    
    return results
