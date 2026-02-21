"""
Currency and FX Rate API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from decimal import Decimal

from app.database import get_db
from app.models.currency import Currency, CurrencyRate, BudgetFXRate
from app.services.fx_service import FXService
from app.schemas.currency import (
    CurrencyCreate, CurrencyUpdate, CurrencyResponse,
    CurrencyRateCreate, CurrencyRateResponse, BulkCurrencyRateCreate,
    BudgetFXRateCreate, BudgetFXRateUpdate, BudgetFXRateResponse,
    FXConversionRequest, FXConversionResponse,
    FXRateTimeSeries, BudgetFXRatePlan
)

router = APIRouter(prefix="/currencies", tags=["Currencies & FX Rates"])


@router.get("", response_model=List[CurrencyResponse])
def list_currencies(
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """List all currencies"""
    query = db.query(Currency)
    if is_active is not None:
        query = query.filter(Currency.is_active == is_active)
    return query.order_by(Currency.display_order).all()


@router.post("", response_model=CurrencyResponse, status_code=201)
def create_currency(
    data: CurrencyCreate,
    db: Session = Depends(get_db)
):
    """Create a new currency"""
    existing = db.query(Currency).filter(Currency.code == data.code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Currency {data.code} already exists")

    currency = Currency(**data.model_dump())
    db.add(currency)
    db.commit()
    db.refresh(currency)
    return currency


@router.get("/{code}", response_model=CurrencyResponse)
def get_currency(code: str, db: Session = Depends(get_db)):
    """Get currency by code"""
    currency = db.query(Currency).filter(Currency.code == code.upper()).first()
    if not currency:
        raise HTTPException(status_code=404, detail="Currency not found")
    return currency


@router.patch("/{code}", response_model=CurrencyResponse)
def update_currency(
    code: str,
    data: CurrencyUpdate,
    db: Session = Depends(get_db)
):
    """Update currency"""
    currency = db.query(Currency).filter(Currency.code == code.upper()).first()
    if not currency:
        raise HTTPException(status_code=404, detail="Currency not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(currency, field, value)

    db.commit()
    db.refresh(currency)
    return currency


@router.post("/seed", response_model=dict)
def seed_currencies(db: Session = Depends(get_db)):
    """Seed default currencies"""
    service = FXService(db)
    created = service.seed_default_currencies()
    return {"created": created}


rates_router = APIRouter(prefix="/rates", tags=["FX Rates"])


@rates_router.get("", response_model=List[CurrencyRateResponse])
def list_rates(
    from_currency: Optional[str] = None,
    to_currency: str = "UZS",
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = Query(default=100, le=1000),
    db: Session = Depends(get_db)
):
    """List exchange rates"""
    query = db.query(CurrencyRate).filter(CurrencyRate.to_currency == to_currency)

    if from_currency:
        query = query.filter(CurrencyRate.from_currency == from_currency.upper())
    if start_date:
        query = query.filter(CurrencyRate.rate_date >= start_date)
    if end_date:
        query = query.filter(CurrencyRate.rate_date <= end_date)

    return query.order_by(CurrencyRate.rate_date.desc()).limit(limit).all()


@rates_router.post("", response_model=CurrencyRateResponse, status_code=201)
def create_rate(
    data: CurrencyRateCreate,
    db: Session = Depends(get_db)
):
    """Create or update exchange rate"""
    service = FXService(db)
    rate = service.save_rate(
        from_currency=data.from_currency.upper(),
        to_currency=data.to_currency.upper(),
        rate=data.rate,
        rate_date=data.rate_date,
        rate_source=data.rate_source,
        is_official=data.is_official
    )
    return rate


@rates_router.post("/bulk", response_model=dict, status_code=201)
def bulk_create_rates(
    data: BulkCurrencyRateCreate,
    db: Session = Depends(get_db)
):
    """Bulk import exchange rates"""
    service = FXService(db)
    created = 0
    for rate_data in data.rates:
        service.save_rate(
            from_currency=rate_data.from_currency.upper(),
            to_currency=rate_data.to_currency.upper(),
            rate=rate_data.rate,
            rate_date=rate_data.rate_date,
            rate_source=rate_data.rate_source,
            is_official=rate_data.is_official
        )
        created += 1
    return {"created": created}


@rates_router.get("/latest/{from_currency}")
def get_latest_rate(
    from_currency: str,
    to_currency: str = "UZS",
    db: Session = Depends(get_db)
):
    """Get latest exchange rate for currency pair"""
    service = FXService(db)
    rate = service.get_rate(from_currency.upper(), to_currency.upper())

    if rate is None:
        raise HTTPException(status_code=404, detail="Rate not found")

    latest = db.query(CurrencyRate).filter(
        CurrencyRate.from_currency == from_currency.upper(),
        CurrencyRate.to_currency == to_currency.upper()
    ).order_by(CurrencyRate.rate_date.desc()).first()

    return {
        "from_currency": from_currency.upper(),
        "to_currency": to_currency.upper(),
        "rate": rate,
        "rate_date": latest.rate_date if latest else None,
        "rate_source": latest.rate_source if latest else None
    }


@rates_router.get("/history/{from_currency}", response_model=FXRateTimeSeries)
def get_rate_history(
    from_currency: str,
    to_currency: str = "UZS",
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Get historical exchange rates"""
    service = FXService(db)
    rates = service.get_rate_history(
        from_currency.upper(),
        to_currency.upper(),
        start_date,
        end_date
    )

    return FXRateTimeSeries(
        from_currency=from_currency.upper(),
        to_currency=to_currency.upper(),
        data_points=rates
    )


@rates_router.post("/convert", response_model=FXConversionResponse)
def convert_currency(
    request: FXConversionRequest,
    db: Session = Depends(get_db)
):
    """Convert amount between currencies"""
    service = FXService(db)

    try:
        converted, rate, source = service.convert(
            amount=request.amount,
            from_currency=request.from_currency.upper(),
            to_currency=request.to_currency.upper(),
            rate_date=request.rate_date,
            use_budget_rate=request.use_budget_rate,
            fiscal_year=request.fiscal_year,
            month=request.month
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return FXConversionResponse(
        original_amount=request.amount,
        converted_amount=converted,
        from_currency=request.from_currency.upper(),
        to_currency=request.to_currency.upper(),
        rate_used=rate,
        rate_date=request.rate_date or date.today(),
        rate_source=source
    )


@rates_router.post("/seed", response_model=dict)
def seed_sample_rates(db: Session = Depends(get_db)):
    """Seed sample exchange rates for testing"""
    service = FXService(db)
    created = service.seed_sample_rates()
    return {"created": created}


budget_rates_router = APIRouter(prefix="/budget-rates", tags=["Budget FX Rates"])


@budget_rates_router.get("", response_model=List[BudgetFXRateResponse])
def list_budget_rates(
    fiscal_year: int,
    from_currency: Optional[str] = None,
    to_currency: str = "UZS",
    is_approved: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """List budget FX rates"""
    query = db.query(BudgetFXRate).filter(
        BudgetFXRate.fiscal_year == fiscal_year,
        BudgetFXRate.to_currency == to_currency
    )

    if from_currency:
        query = query.filter(BudgetFXRate.from_currency == from_currency.upper())
    if is_approved is not None:
        query = query.filter(BudgetFXRate.is_approved == is_approved)

    return query.order_by(BudgetFXRate.from_currency, BudgetFXRate.month).all()


@budget_rates_router.post("", response_model=BudgetFXRateResponse, status_code=201)
def create_budget_rate(
    data: BudgetFXRateCreate,
    db: Session = Depends(get_db)
):
    """Create or update budget FX rate"""
    service = FXService(db)
    rate = service.save_budget_rate(
        from_currency=data.from_currency.upper(),
        to_currency=data.to_currency.upper(),
        fiscal_year=data.fiscal_year,
        month=data.month,
        planned_rate=data.planned_rate,
        assumption_type=data.assumption_type,
        notes=data.notes
    )
    return rate


@budget_rates_router.post("/generate", response_model=dict)
def generate_budget_rates(
    fiscal_year: int,
    from_currency: str,
    to_currency: str = "UZS",
    assumption_type: str = "flat",
    base_rate: Decimal = Query(...),
    growth_rate: Optional[Decimal] = None,
    notes: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Generate 12 monthly budget rates based on assumption"""
    service = FXService(db)
    rates = service.generate_budget_rates_from_assumption(
        from_currency=from_currency.upper(),
        to_currency=to_currency.upper(),
        fiscal_year=fiscal_year,
        assumption_type=assumption_type,
        base_rate=base_rate,
        growth_rate=growth_rate,
        notes=notes
    )
    return {"generated": len(rates), "fiscal_year": fiscal_year}


@budget_rates_router.get("/plan/{fiscal_year}/{from_currency}", response_model=BudgetFXRatePlan)
def get_budget_rate_plan(
    fiscal_year: int,
    from_currency: str,
    to_currency: str = "UZS",
    db: Session = Depends(get_db)
):
    """Get complete budget FX rate plan for currency pair"""
    rates = db.query(BudgetFXRate).filter(
        BudgetFXRate.fiscal_year == fiscal_year,
        BudgetFXRate.from_currency == from_currency.upper(),
        BudgetFXRate.to_currency == to_currency.upper()
    ).order_by(BudgetFXRate.month).all()

    if not rates:
        raise HTTPException(status_code=404, detail="Budget rate plan not found")

    avg_rate = sum(r.planned_rate for r in rates) / len(rates) if rates else Decimal("0")
    is_fully_approved = all(r.is_approved for r in rates)

    return BudgetFXRatePlan(
        fiscal_year=fiscal_year,
        from_currency=from_currency.upper(),
        to_currency=to_currency.upper(),
        monthly_rates=rates,
        average_rate=avg_rate,
        is_fully_approved=is_fully_approved
    )


@budget_rates_router.post("/approve")
def approve_budget_rates(
    fiscal_year: int,
    from_currency: str,
    to_currency: str = "UZS",
    approved_by_user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """Approve budget FX rates for a currency pair"""
    service = FXService(db)
    count = service.approve_budget_rates(
        fiscal_year=fiscal_year,
        from_currency=from_currency.upper(),
        to_currency=to_currency.upper(),
        approved_by_user_id=approved_by_user_id
    )
    return {"approved": count}


router.include_router(rates_router)
router.include_router(budget_rates_router)
