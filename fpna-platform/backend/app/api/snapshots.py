"""
Snapshot and Baseline API endpoints
Handles balance snapshot import and baseline calculation
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date

from app.database import get_db
from app.models.snapshot import BalanceSnapshot, BaselineBudget, SnapshotImportLog
from app.models.coa import Account
from app.services.baseline_service import BaselineService
from app.schemas.snapshot import (
    BalanceSnapshotCreate, BalanceSnapshotResponse, BulkSnapshotCreate,
    BaselineBudgetCreate, BaselineBudgetResponse, BaselineBudgetDetail,
    BaselineCalculationRequest, BaselineCalculationResponse,
    SnapshotImportLogResponse, SnapshotSummary, SnapshotTimeSeries,
    SnapshotTimeSeriesPoint, AggregatedSnapshot
)

router = APIRouter(prefix="/snapshots", tags=["Balance Snapshots"])


@router.get("", response_model=List[BalanceSnapshotResponse])
def list_snapshots(
    account_code: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    currency: Optional[str] = None,
    import_batch_id: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """List balance snapshots with filters"""
    query = db.query(BalanceSnapshot)

    if account_code:
        query = query.filter(BalanceSnapshot.account_code == account_code)
    if start_date:
        query = query.filter(BalanceSnapshot.snapshot_date >= start_date)
    if end_date:
        query = query.filter(BalanceSnapshot.snapshot_date <= end_date)
    if currency:
        query = query.filter(BalanceSnapshot.currency == currency)
    if import_batch_id:
        query = query.filter(BalanceSnapshot.import_batch_id == import_batch_id)

    return query.order_by(BalanceSnapshot.snapshot_date.desc()).offset(offset).limit(limit).all()


@router.post("", response_model=BalanceSnapshotResponse, status_code=201)
def create_snapshot(
    data: BalanceSnapshotCreate,
    db: Session = Depends(get_db)
):
    """Create a single balance snapshot"""
    snapshot = BalanceSnapshot(**data.model_dump())
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


@router.post("/bulk", response_model=dict, status_code=201)
def bulk_create_snapshots(
    data: BulkSnapshotCreate,
    db: Session = Depends(get_db)
):
    """Bulk import balance snapshots"""
    service = BaselineService(db)
    
    snapshots_data = [s.model_dump() for s in data.snapshots]
    batch_id, imported, failed, errors = service.import_snapshots_from_data(
        snapshots_data,
        source_type="api"
    )

    return {
        "import_batch_id": batch_id,
        "imported": imported,
        "failed": failed,
        "errors": errors[:10]
    }


@router.get("/summary", response_model=List[SnapshotSummary])
def get_snapshot_summary(
    class_code: Optional[str] = None,
    group_code: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get summary statistics for snapshots by account"""
    query = db.query(
        BalanceSnapshot.account_code,
        BalanceSnapshot.currency,
        func.count(BalanceSnapshot.id).label("snapshot_count"),
        func.min(BalanceSnapshot.snapshot_date).label("earliest_date"),
        func.max(BalanceSnapshot.snapshot_date).label("latest_date"),
        func.min(BalanceSnapshot.balance).label("min_balance"),
        func.max(BalanceSnapshot.balance).label("max_balance"),
        func.avg(BalanceSnapshot.balance).label("avg_balance")
    ).group_by(BalanceSnapshot.account_code, BalanceSnapshot.currency)

    if group_code:
        query = query.filter(BalanceSnapshot.account_code.startswith(group_code))
    elif class_code:
        query = query.filter(BalanceSnapshot.account_code.startswith(class_code))

    results = query.all()

    summaries = []
    for r in results:
        account = db.query(Account).filter(Account.code == r.account_code).first()
        summaries.append(SnapshotSummary(
            account_code=r.account_code,
            account_name=account.name_en if account else None,
            currency=r.currency,
            snapshot_count=r.snapshot_count,
            earliest_date=r.earliest_date,
            latest_date=r.latest_date,
            min_balance=r.min_balance,
            max_balance=r.max_balance,
            avg_balance=r.avg_balance
        ))

    return summaries


@router.get("/timeseries/{account_code}", response_model=SnapshotTimeSeries)
def get_snapshot_timeseries(
    account_code: str,
    currency: str = "UZS",
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Get time series data for an account"""
    query = db.query(BalanceSnapshot).filter(
        BalanceSnapshot.account_code == account_code,
        BalanceSnapshot.currency == currency
    )

    if start_date:
        query = query.filter(BalanceSnapshot.snapshot_date >= start_date)
    if end_date:
        query = query.filter(BalanceSnapshot.snapshot_date <= end_date)

    snapshots = query.order_by(BalanceSnapshot.snapshot_date).all()

    account = db.query(Account).filter(Account.code == account_code).first()

    return SnapshotTimeSeries(
        account_code=account_code,
        account_name=account.name_en if account else None,
        currency=currency,
        data_points=[
            SnapshotTimeSeriesPoint(
                snapshot_date=s.snapshot_date,
                balance=s.balance,
                balance_uzs=s.balance_uzs,
                fx_rate=s.fx_rate
            ) for s in snapshots
        ]
    )


@router.get("/import-logs", response_model=List[SnapshotImportLogResponse])
def list_import_logs(
    status: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db)
):
    """List snapshot import logs"""
    query = db.query(SnapshotImportLog)

    if status:
        query = query.filter(SnapshotImportLog.status == status)

    return query.order_by(SnapshotImportLog.started_at.desc()).limit(limit).all()


@router.get("/import-logs/{batch_id}", response_model=SnapshotImportLogResponse)
def get_import_log(batch_id: str, db: Session = Depends(get_db)):
    """Get import log by batch ID"""
    log = db.query(SnapshotImportLog).filter(
        SnapshotImportLog.import_batch_id == batch_id
    ).first()

    if not log:
        raise HTTPException(status_code=404, detail="Import log not found")

    return log


baselines_router = APIRouter(prefix="/baselines", tags=["Baseline Budgets"])


@baselines_router.get("", response_model=List[BaselineBudgetResponse])
def list_baselines(
    fiscal_year: int,
    account_code: Optional[str] = None,
    class_code: Optional[str] = None,
    group_code: Optional[str] = None,
    is_active: bool = True,
    baseline_version: Optional[int] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """List baseline budgets with filters"""
    query = db.query(BaselineBudget).filter(
        BaselineBudget.fiscal_year == fiscal_year,
        BaselineBudget.is_active == is_active
    )

    if account_code:
        query = query.filter(BaselineBudget.account_code == account_code)
    elif group_code:
        query = query.filter(BaselineBudget.account_code.startswith(group_code))
    elif class_code:
        query = query.filter(BaselineBudget.account_code.startswith(class_code))

    if baseline_version:
        query = query.filter(BaselineBudget.baseline_version == baseline_version)

    return query.order_by(BaselineBudget.account_code).offset(offset).limit(limit).all()


@baselines_router.get("/{account_code}", response_model=BaselineBudgetDetail)
def get_baseline(
    account_code: str,
    fiscal_year: int,
    baseline_version: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get baseline budget for specific account"""
    query = db.query(BaselineBudget).filter(
        BaselineBudget.fiscal_year == fiscal_year,
        BaselineBudget.account_code == account_code,
        BaselineBudget.is_active == True
    )

    if baseline_version:
        query = query.filter(BaselineBudget.baseline_version == baseline_version)
    else:
        query = query.order_by(BaselineBudget.baseline_version.desc())

    baseline = query.first()

    if not baseline:
        raise HTTPException(status_code=404, detail="Baseline not found")

    account = db.query(Account).filter(Account.code == account_code).first()

    return BaselineBudgetDetail(
        **{c.name: getattr(baseline, c.name) for c in baseline.__table__.columns},
        account_name=account.name_en if account else None,
        class_code=account_code[0] if account_code else None,
        group_code=account_code[:2] if len(account_code) >= 2 else None
    )


@baselines_router.post("/calculate", response_model=BaselineCalculationResponse)
def calculate_baselines(
    request: BaselineCalculationRequest,
    db: Session = Depends(get_db)
):
    """Calculate baseline budgets from historical snapshots"""
    service = BaselineService(db)

    total, calculated, skipped, errors = service.calculate_baseline(
        fiscal_year=request.fiscal_year,
        account_codes=request.account_codes,
        class_code=request.class_code,
        group_code=request.group_code,
        calculation_method=request.calculation_method,
        lookback_months=request.lookback_months,
        apply_trend=request.apply_trend,
        apply_seasonality=request.apply_seasonality
    )

    latest_version = db.query(func.max(BaselineBudget.baseline_version)).filter(
        BaselineBudget.fiscal_year == request.fiscal_year
    ).scalar() or 1

    return BaselineCalculationResponse(
        fiscal_year=request.fiscal_year,
        total_accounts=total,
        calculated_accounts=calculated,
        skipped_accounts=skipped,
        errors=errors[:20],
        baseline_version=latest_version
    )


@baselines_router.get("/summary/{fiscal_year}")
def get_baseline_summary(
    fiscal_year: int,
    class_code: Optional[str] = None,
    group_code: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get summary of baseline budgets for fiscal year"""
    service = BaselineService(db)
    return service.get_baseline_summary(fiscal_year, class_code, group_code)


@baselines_router.get("/aggregated/{fiscal_year}")
def get_aggregated_baselines(
    fiscal_year: int,
    level: int = Query(..., ge=1, le=3, description="1=class, 2=group, 3=category"),
    baseline_version: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get aggregated baseline budgets at specified hierarchy level"""
    service = BaselineService(db)
    return service.aggregate_to_level(fiscal_year, level, baseline_version)


@baselines_router.delete("/{fiscal_year}")
def deactivate_baselines(
    fiscal_year: int,
    baseline_version: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Deactivate baseline budgets (soft delete)"""
    query = db.query(BaselineBudget).filter(
        BaselineBudget.fiscal_year == fiscal_year,
        BaselineBudget.is_active == True
    )

    if baseline_version:
        query = query.filter(BaselineBudget.baseline_version == baseline_version)

    count = query.update({"is_active": False})
    db.commit()

    return {"deactivated": count}


router.include_router(baselines_router)
