"""
Baseline API Endpoints
Handles the complete budget workflow: Ingest → Calculate → Plan → Export
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime

from app.database import get_db
from app.services.baseline_service import BaselineService
from app.models.baseline import BaselineData, BudgetBaseline, BudgetPlanned
from app.models.user import User
from app.utils.dependencies import get_current_active_user

router = APIRouter(prefix="/baseline", tags=["Baseline & Budget Planning"])


# ============================================
# Pydantic Schemas
# ============================================

class IngestRequest(BaseModel):
    connection_id: int
    start_year: int = 2023
    end_year: int = 2025


class CalculateBaselineRequest(BaseModel):
    fiscal_year: int
    method: str = Field(default="simple_average", description="simple_average, weighted_average, trend")
    source_years: Optional[List[int]] = None


class CreatePlannedRequest(BaseModel):
    fiscal_year: int
    account_code: str
    driver_adjustment_pct: float = 0
    driver_code: Optional[str] = None
    department: Optional[str] = None
    scenario: str = "BASE"


class BulkCreatePlannedRequest(BaseModel):
    fiscal_year: int
    driver_adjustment_pct: float = 0
    driver_code: Optional[str] = None
    account_codes: Optional[List[str]] = None
    scenario: str = "BASE"


class ExportRequest(BaseModel):
    connection_id: int
    fiscal_year: int
    target_table: str = "fpna_budget_planned"
    status_filter: str = "APPROVED"


# ============================================
# STEP 1: INGEST ENDPOINTS
# ============================================

@router.post("/ingest", response_model=dict)
def ingest_baseline_data(
    request: IngestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Import snapshot data from DWH balans_ato into baseline_data table.
    This is the first step in the budget planning workflow.
    """
    service = BaselineService(db)
    
    try:
        result = service.ingest_baseline_data(
            connection_id=request.connection_id,
            start_year=request.start_year,
            end_year=request.end_year,
            user_id=current_user.id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@router.get("/data", response_model=dict)
def get_baseline_data(
    fiscal_year: Optional[int] = None,
    account_code: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get imported baseline data with optional filters"""
    query = db.query(BaselineData)
    
    if fiscal_year:
        query = query.filter(BaselineData.fiscal_year == fiscal_year)
    if account_code:
        query = query.filter(BaselineData.account_code.like(f"{account_code}%"))
    
    total = query.count()
    data = query.order_by(
        BaselineData.fiscal_year.desc(),
        BaselineData.fiscal_month.desc(),
        BaselineData.account_code
    ).offset(skip).limit(limit).all()
    
    return {
        "total": total,
        "data": [
            {
                "id": d.id,
                "account_code": d.account_code,
                "snapshot_date": str(d.snapshot_date),
                "fiscal_year": d.fiscal_year,
                "fiscal_month": d.fiscal_month,
                "currency": d.currency,
                "balance": float(d.balance or 0),
                "balance_uzs": float(d.balance_uzs or 0),
                "debit_turnover": float(d.debit_turnover or 0),
                "credit_turnover": float(d.credit_turnover or 0)
            }
            for d in data
        ]
    }


@router.get("/data/summary", response_model=dict)
def get_baseline_data_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get summary of imported baseline data"""
    from sqlalchemy import func, text
    
    result = db.execute(text("""
        SELECT 
            fiscal_year,
            COUNT(DISTINCT account_code) as accounts,
            COUNT(*) as records,
            SUM(balance_uzs) as total_balance
        FROM baseline_data
        GROUP BY fiscal_year
        ORDER BY fiscal_year
    """)).fetchall()
    
    return {
        "by_year": [
            {
                "year": row[0],
                "accounts": row[1],
                "records": row[2],
                "total_balance": float(row[3] or 0)
            }
            for row in result
        ]
    }


# ============================================
# STEP 2: CALCULATE BASELINE ENDPOINTS
# ============================================

@router.post("/calculate", response_model=dict)
def calculate_baseline(
    request: CalculateBaselineRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Calculate baseline budget from historical data.
    Uses simple average of same month across source years.
    """
    service = BaselineService(db)
    
    try:
        result = service.calculate_baseline(
            fiscal_year=request.fiscal_year,
            method=request.method,
            source_years=request.source_years,
            user_id=current_user.id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calculation failed: {str(e)}")


@router.get("/baselines", response_model=dict)
def list_baselines(
    fiscal_year: int,
    account_code: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List calculated baselines for a fiscal year"""
    query = db.query(BudgetBaseline).filter(
        BudgetBaseline.fiscal_year == fiscal_year,
        BudgetBaseline.is_active == True
    )
    
    if account_code:
        query = query.filter(BudgetBaseline.account_code.like(f"{account_code}%"))
    
    total = query.count()
    baselines = query.order_by(BudgetBaseline.account_code).offset(skip).limit(limit).all()
    
    return {
        "fiscal_year": fiscal_year,
        "total": total,
        "data": [
            {
                "id": b.id,
                "account_code": b.account_code,
                "currency": b.currency,
                "monthly": {
                    "jan": float(b.jan or 0),
                    "feb": float(b.feb or 0),
                    "mar": float(b.mar or 0),
                    "apr": float(b.apr or 0),
                    "may": float(b.may or 0),
                    "jun": float(b.jun or 0),
                    "jul": float(b.jul or 0),
                    "aug": float(b.aug or 0),
                    "sep": float(b.sep or 0),
                    "oct": float(b.oct or 0),
                    "nov": float(b.nov or 0),
                    "dec": float(b.dec or 0)
                },
                "annual_total": float(b.annual_total or 0),
                "calculation_method": b.calculation_method,
                "source_years": b.source_years,
                "yoy_growth_rate": float(b.yoy_growth_rate) if b.yoy_growth_rate else None
            }
            for b in baselines
        ]
    }


@router.get("/baselines/summary", response_model=dict)
def get_baseline_summary(
    fiscal_year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get summary statistics for baselines"""
    service = BaselineService(db)
    return service.get_baseline_summary(fiscal_year)


# ============================================
# STEP 3: PLANNED BUDGET ENDPOINTS
# ============================================

@router.post("/planned", response_model=dict)
def create_planned_budget(
    request: CreatePlannedRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a planned budget from baseline with driver adjustments.
    """
    service = BaselineService(db)
    
    try:
        result = service.create_planned_budget(
            fiscal_year=request.fiscal_year,
            account_code=request.account_code,
            driver_adjustment_pct=request.driver_adjustment_pct,
            driver_code=request.driver_code,
            department=request.department,
            scenario=request.scenario,
            user_id=current_user.id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Creation failed: {str(e)}")


@router.post("/planned/bulk", response_model=dict)
def bulk_create_planned_budgets(
    request: BulkCreatePlannedRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Create planned budgets for all baselines with a uniform driver adjustment.
    """
    service = BaselineService(db)
    
    try:
        result = service.bulk_create_planned_budgets(
            fiscal_year=request.fiscal_year,
            driver_adjustment_pct=request.driver_adjustment_pct,
            driver_code=request.driver_code,
            account_codes=request.account_codes,
            scenario=request.scenario,
            user_id=current_user.id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk creation failed: {str(e)}")


@router.get("/planned", response_model=dict)
def list_planned_budgets(
    fiscal_year: int,
    status: Optional[str] = None,
    account_code: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List planned budgets with filters"""
    query = db.query(BudgetPlanned).filter(
        BudgetPlanned.fiscal_year == fiscal_year,
        BudgetPlanned.is_current == True
    )
    
    if status:
        query = query.filter(BudgetPlanned.status == status)
    if account_code:
        query = query.filter(BudgetPlanned.account_code.like(f"{account_code}%"))
    
    total = query.count()
    budgets = query.order_by(BudgetPlanned.account_code).offset(skip).limit(limit).all()
    
    return {
        "fiscal_year": fiscal_year,
        "total": total,
        "data": [
            {
                "id": b.id,
                "budget_code": b.budget_code,
                "account_code": b.account_code,
                "department": b.department,
                "currency": b.currency,
                "monthly": {
                    "jan": float(b.jan or 0),
                    "feb": float(b.feb or 0),
                    "mar": float(b.mar or 0),
                    "apr": float(b.apr or 0),
                    "may": float(b.may or 0),
                    "jun": float(b.jun or 0),
                    "jul": float(b.jul or 0),
                    "aug": float(b.aug or 0),
                    "sep": float(b.sep or 0),
                    "oct": float(b.oct or 0),
                    "nov": float(b.nov or 0),
                    "dec": float(b.dec or 0)
                },
                "annual_total": float(b.annual_total or 0),
                "baseline_amount": float(b.baseline_amount or 0),
                "driver_adjustment_pct": float(b.driver_adjustment_pct or 0),
                "variance_from_baseline": float(b.variance_from_baseline or 0),
                "variance_pct": float(b.variance_pct or 0),
                "scenario": b.scenario,
                "status": b.status,
                "submitted_at": b.submitted_at.isoformat() if b.submitted_at else None,
                "approved_at": b.approved_at.isoformat() if b.approved_at else None
            }
            for b in budgets
        ]
    }


@router.post("/planned/{budget_code}/submit", response_model=dict)
def submit_planned_budget(
    budget_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Submit a planned budget for approval"""
    service = BaselineService(db)
    
    try:
        return service.submit_planned_budget(budget_code, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/planned/{budget_code}/approve", response_model=dict)
def approve_planned_budget(
    budget_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Approve a submitted budget"""
    service = BaselineService(db)
    
    try:
        return service.approve_planned_budget(budget_code, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/planned/summary", response_model=dict)
def get_planned_summary(
    fiscal_year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get summary of planned budgets by status"""
    service = BaselineService(db)
    return service.get_planned_summary(fiscal_year)


# ============================================
# STEP 4: EXPORT ENDPOINTS
# ============================================

@router.post("/export", response_model=dict)
def export_to_dwh(
    request: ExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Export approved planned budgets to DWH.
    Creates fpna_budget_planned table in DWH if not exists.
    """
    service = BaselineService(db)
    
    try:
        result = service.export_to_dwh(
            connection_id=request.connection_id,
            fiscal_year=request.fiscal_year,
            target_table=request.target_table,
            status_filter=request.status_filter,
            user_id=current_user.id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


# ============================================
# WORKFLOW STATUS ENDPOINT
# ============================================

@router.get("/workflow-status/{fiscal_year}", response_model=dict)
def get_workflow_status(
    fiscal_year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get complete workflow status for a fiscal year.
    Shows progress through: Ingest → Calculate → Plan → Export
    """
    from sqlalchemy import text
    
    # Check baseline data
    data_result = db.execute(text("""
        SELECT COUNT(DISTINCT account_code), COUNT(*), MIN(snapshot_date), MAX(snapshot_date)
        FROM baseline_data
        WHERE fiscal_year BETWEEN :year - 3 AND :year - 1
    """), {"year": fiscal_year}).fetchone()
    
    # Check baselines
    baseline_result = db.execute(text("""
        SELECT COUNT(*), SUM(annual_total)
        FROM budget_baseline
        WHERE fiscal_year = :year AND is_active = 1
    """), {"year": fiscal_year}).fetchone()
    
    # Check planned budgets
    planned_result = db.execute(text("""
        SELECT status, COUNT(*), SUM(annual_total)
        FROM budget_planned
        WHERE fiscal_year = :year AND is_current = 1
        GROUP BY status
    """), {"year": fiscal_year}).fetchall()
    
    planned_by_status = {row[0]: {"count": row[1], "amount": float(row[2] or 0)} for row in planned_result}
    
    return {
        "fiscal_year": fiscal_year,
        "steps": {
            "1_ingest": {
                "status": "COMPLETED" if data_result[0] > 0 else "PENDING",
                "accounts": data_result[0] or 0,
                "records": data_result[1] or 0,
                "date_range": f"{data_result[2]} to {data_result[3]}" if data_result[2] else None
            },
            "2_calculate": {
                "status": "COMPLETED" if baseline_result[0] > 0 else "PENDING",
                "baselines": baseline_result[0] or 0,
                "total_amount": float(baseline_result[1] or 0)
            },
            "3_plan": {
                "status": "COMPLETED" if planned_by_status else "PENDING",
                "by_status": planned_by_status
            },
            "4_export": {
                "status": "COMPLETED" if planned_by_status.get("EXPORTED", {}).get("count", 0) > 0 else "PENDING",
                "exported": planned_by_status.get("EXPORTED", {}).get("count", 0)
            }
        }
    }
