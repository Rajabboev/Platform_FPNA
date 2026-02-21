"""
Driver API endpoints
Handles driver configuration and calculations
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from decimal import Decimal

from app.database import get_db
from app.models.driver import Driver, DriverValue, DriverCalculationLog, GoldenRule, DriverType as ModelDriverType
from app.services.driver_engine import DriverEngine
from app.schemas.driver import (
    DriverCreate, DriverUpdate, DriverResponse,
    DriverValueCreate, DriverValueUpdate, DriverValueResponse, BulkDriverValueCreate,
    DriverValueMatrix,
    GoldenRuleCreate, GoldenRuleUpdate, GoldenRuleResponse,
    DriverCalculationRequest, DriverCalculationResponse, DriverCalculationResult,
    ValidationResult, SpreadAnalysis, DriverType
)

router = APIRouter(prefix="/drivers", tags=["Drivers"])


@router.get("", response_model=List[DriverResponse])
def list_drivers(
    driver_type: Optional[DriverType] = None,
    is_active: Optional[bool] = None,
    is_system: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """List all drivers with optional filters"""
    query = db.query(Driver)

    if driver_type:
        query = query.filter(Driver.driver_type == driver_type.value)
    if is_active is not None:
        query = query.filter(Driver.is_active == is_active)
    if is_system is not None:
        query = query.filter(Driver.is_system == is_system)

    return query.order_by(Driver.display_order, Driver.code).all()


@router.post("", response_model=DriverResponse, status_code=201)
def create_driver(
    data: DriverCreate,
    db: Session = Depends(get_db)
):
    """Create a new driver"""
    existing = db.query(Driver).filter(Driver.code == data.code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Driver with code {data.code} already exists")

    driver = Driver(**data.model_dump())
    db.add(driver)
    db.commit()
    db.refresh(driver)
    return driver


@router.post("/seed", response_model=dict)
def seed_drivers(db: Session = Depends(get_db)):
    """Seed default drivers"""
    engine = DriverEngine(db)
    created = engine.seed_default_drivers()
    return {"created": created}


values_router = APIRouter(prefix="/values", tags=["Driver Values"])


@values_router.get("", response_model=List[DriverValueResponse])
def list_driver_values(
    driver_code: Optional[str] = None,
    fiscal_year: Optional[int] = None,
    month: Optional[int] = None,
    account_code: Optional[str] = None,
    is_approved: Optional[bool] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """List driver values with filters"""
    query = db.query(DriverValue)

    if driver_code:
        driver = db.query(Driver).filter(Driver.code == driver_code).first()
        if driver:
            query = query.filter(DriverValue.driver_id == driver.id)

    if fiscal_year:
        query = query.filter(DriverValue.fiscal_year == fiscal_year)
    if month:
        query = query.filter(DriverValue.month == month)
    if account_code:
        query = query.filter(DriverValue.account_code == account_code)
    if is_approved is not None:
        query = query.filter(DriverValue.is_approved == is_approved)

    return query.order_by(DriverValue.fiscal_year, DriverValue.month).offset(offset).limit(limit).all()


@values_router.post("", response_model=DriverValueResponse, status_code=201)
def create_driver_value(
    data: DriverValueCreate,
    db: Session = Depends(get_db)
):
    """Create or update driver value"""
    existing = db.query(DriverValue).filter(
        DriverValue.driver_id == data.driver_id,
        DriverValue.fiscal_year == data.fiscal_year,
        DriverValue.month == data.month,
        DriverValue.account_code == data.account_code,
        DriverValue.business_unit_code == data.business_unit_code
    ).first()

    if existing:
        existing.value = data.value
        existing.value_type = data.value_type
        existing.notes = data.notes
        db.commit()
        db.refresh(existing)
        return existing

    value = DriverValue(**data.model_dump())
    db.add(value)
    db.commit()
    db.refresh(value)
    return value


@values_router.post("/bulk", response_model=dict, status_code=201)
def bulk_create_driver_values(
    data: BulkDriverValueCreate,
    db: Session = Depends(get_db)
):
    """Bulk create/update driver values"""
    created = 0
    updated = 0

    for value_data in data.values:
        existing = db.query(DriverValue).filter(
            DriverValue.driver_id == value_data.driver_id,
            DriverValue.fiscal_year == value_data.fiscal_year,
            DriverValue.month == value_data.month,
            DriverValue.account_code == value_data.account_code,
            DriverValue.business_unit_code == value_data.business_unit_code
        ).first()

        if existing:
            existing.value = value_data.value
            existing.value_type = value_data.value_type
            existing.notes = value_data.notes
            updated += 1
        else:
            db.add(DriverValue(**value_data.model_dump()))
            created += 1

    db.commit()
    return {"created": created, "updated": updated}


@values_router.get("/matrix/{driver_code}", response_model=DriverValueMatrix)
def get_driver_value_matrix(
    driver_code: str,
    fiscal_year: int,
    account_code: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get driver values as monthly matrix"""
    driver = db.query(Driver).filter(Driver.code == driver_code).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    query = db.query(DriverValue).filter(
        DriverValue.driver_id == driver.id,
        DriverValue.fiscal_year == fiscal_year
    )

    if account_code:
        query = query.filter(DriverValue.account_code == account_code)

    values = query.all()

    monthly_values = {m: None for m in range(1, 13)}
    for v in values:
        if v.month:
            monthly_values[v.month] = float(v.value)

    return DriverValueMatrix(
        driver_id=driver.id,
        driver_code=driver.code,
        driver_name=driver.name_en,
        fiscal_year=fiscal_year,
        monthly_values=monthly_values
    )


@values_router.post("/approve")
def approve_driver_values(
    driver_code: str,
    fiscal_year: int,
    approved_by_user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """Approve all driver values for a driver and year"""
    from datetime import datetime

    driver = db.query(Driver).filter(Driver.code == driver_code).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    count = db.query(DriverValue).filter(
        DriverValue.driver_id == driver.id,
        DriverValue.fiscal_year == fiscal_year,
        DriverValue.is_approved == False
    ).update({
        "is_approved": True,
        "approved_by_user_id": approved_by_user_id,
        "approved_at": datetime.utcnow()
    })

    db.commit()
    return {"approved": count}


router.include_router(values_router)


rules_router = APIRouter(prefix="/golden-rules", tags=["Golden Rules"])


@rules_router.get("", response_model=List[GoldenRuleResponse])
def list_golden_rules(
    rule_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """List golden rules"""
    query = db.query(GoldenRule)

    if rule_type:
        query = query.filter(GoldenRule.rule_type == rule_type)
    if is_active is not None:
        query = query.filter(GoldenRule.is_active == is_active)

    return query.order_by(GoldenRule.priority).all()


@rules_router.post("", response_model=GoldenRuleResponse, status_code=201)
def create_golden_rule(
    data: GoldenRuleCreate,
    db: Session = Depends(get_db)
):
    """Create a golden rule"""
    existing = db.query(GoldenRule).filter(GoldenRule.code == data.code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Golden rule with code {data.code} already exists")

    rule = GoldenRule(**data.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@rules_router.get("/{code}", response_model=GoldenRuleResponse)
def get_golden_rule(code: str, db: Session = Depends(get_db)):
    """Get golden rule by code"""
    rule = db.query(GoldenRule).filter(GoldenRule.code == code).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Golden rule not found")
    return rule


@rules_router.patch("/{code}", response_model=GoldenRuleResponse)
def update_golden_rule(
    code: str,
    data: GoldenRuleUpdate,
    db: Session = Depends(get_db)
):
    """Update golden rule"""
    rule = db.query(GoldenRule).filter(GoldenRule.code == code).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Golden rule not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rule, field, value)

    db.commit()
    db.refresh(rule)
    return rule


@rules_router.delete("/{code}")
def delete_golden_rule(code: str, db: Session = Depends(get_db)):
    """Delete golden rule"""
    rule = db.query(GoldenRule).filter(GoldenRule.code == code).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Golden rule not found")

    db.delete(rule)
    db.commit()
    return {"message": "Golden rule deleted"}


@rules_router.post("/seed", response_model=dict)
def seed_golden_rules(db: Session = Depends(get_db)):
    """Seed default golden rules"""
    engine = DriverEngine(db)
    created = engine.seed_golden_rules()
    return {"created": created}


router.include_router(rules_router)


calculations_router = APIRouter(prefix="/calculations", tags=["Driver Calculations"])


@calculations_router.post("/run", response_model=DriverCalculationResponse)
def run_calculations(
    request: DriverCalculationRequest,
    db: Session = Depends(get_db)
):
    """Run driver calculations"""
    engine = DriverEngine(db)

    batch_id, successful, failed, results, errors = engine.run_driver_calculations(
        fiscal_year=request.fiscal_year,
        months=request.months,
        driver_codes=request.driver_codes,
        account_codes=request.account_codes,
        apply_golden_rules=request.apply_golden_rules
    )

    return DriverCalculationResponse(
        calculation_batch_id=batch_id,
        fiscal_year=request.fiscal_year,
        total_calculations=successful + failed,
        successful=successful,
        failed=failed,
        results=[DriverCalculationResult(**r) for r in results[:100]],
        errors=errors[:20]
    )


@calculations_router.get("/logs")
def list_calculation_logs(
    batch_id: Optional[str] = None,
    fiscal_year: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    db: Session = Depends(get_db)
):
    """List calculation logs"""
    query = db.query(DriverCalculationLog)

    if batch_id:
        query = query.filter(DriverCalculationLog.calculation_batch_id == batch_id)
    if fiscal_year:
        query = query.filter(DriverCalculationLog.fiscal_year == fiscal_year)
    if status:
        query = query.filter(DriverCalculationLog.status == status)

    return query.order_by(DriverCalculationLog.created_at.desc()).limit(limit).all()


@calculations_router.post("/validate", response_model=ValidationResult)
def validate_balance_equation(
    fiscal_year: int,
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db)
):
    """Validate accounting equation (Assets = Liabilities + Equity)"""
    engine = DriverEngine(db)
    is_valid, difference, message = engine.validate_balance_equation(fiscal_year, month)

    from app.models.snapshot import BaselineBudget
    
    baselines = db.query(BaselineBudget).filter(
        BaselineBudget.fiscal_year == fiscal_year,
        BaselineBudget.is_active == True
    ).all()

    month_attr = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                  'jul', 'aug', 'sep', 'oct', 'nov', 'dec'][month - 1]

    assets = Decimal("0")
    liabilities = Decimal("0")
    equity = Decimal("0")

    for baseline in baselines:
        value = getattr(baseline, month_attr) or Decimal("0")
        class_code = baseline.account_code[0]
        if class_code == "1":
            assets += value
        elif class_code == "2":
            liabilities += value
        elif class_code == "3":
            equity += value

    return ValidationResult(
        is_valid=is_valid,
        total_assets=assets,
        total_liabilities=liabilities,
        total_equity=equity,
        difference=difference,
        message=message
    )


router.include_router(calculations_router)


@router.get("/{code}", response_model=DriverResponse)
def get_driver(code: str, db: Session = Depends(get_db)):
    """Get driver by code"""
    driver = db.query(Driver).filter(Driver.code == code).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    return driver


@router.patch("/{code}", response_model=DriverResponse)
def update_driver(
    code: str,
    data: DriverUpdate,
    db: Session = Depends(get_db)
):
    """Update driver"""
    driver = db.query(Driver).filter(Driver.code == code).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    if driver.is_system:
        allowed_fields = {"default_value", "min_value", "max_value", "is_active"}
        update_data = {k: v for k, v in data.model_dump(exclude_unset=True).items() if k in allowed_fields}
    else:
        update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(driver, field, value)

    db.commit()
    db.refresh(driver)
    return driver


@router.delete("/{code}")
def delete_driver(code: str, db: Session = Depends(get_db)):
    """Delete driver (only non-system drivers)"""
    driver = db.query(Driver).filter(Driver.code == code).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    if driver.is_system:
        raise HTTPException(status_code=400, detail="Cannot delete system driver")

    db.delete(driver)
    db.commit()
    return {"message": "Driver deleted"}
