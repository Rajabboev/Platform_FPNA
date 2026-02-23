"""
Data Upload API - Excel uploads for balance snapshots and budget planned

Supports two upload types:
1. Balance Snapshots - Monthly balance data for baseline calculation
2. Budget Planned - Ready budget plans for approval workflow
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import os
from datetime import datetime
import uuid

from app.database import get_db
from app.models.snapshot import BalanceSnapshot, SnapshotImportLog
from app.models.baseline import BudgetPlanned
from app.models.user import User
from app.utils.dependencies import get_current_active_user
from app.services.excel_service import ExcelProcessor, ExcelUploadType
from app.config import settings

router = APIRouter(prefix="/data-upload", tags=["data-upload"])

os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)


# ============================================================================
# Balance Snapshot Upload
# ============================================================================

@router.post("/balance-snapshot/upload")
async def upload_balance_snapshot(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Upload balance snapshot data from Excel file
    
    Expected format:
    - Account Code (required)
    - Snapshot Date (required)
    - Balance (required)
    - Currency, Balance UZS, FX Rate, Branch (optional)
    """
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided")
    
    file_ext = file.filename.split('.')[-1].lower()
    if file_ext not in ['xlsx', 'xls']:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only Excel files (.xlsx, .xls) are supported")
    
    contents = await file.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large")
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    temp_filename = f"snapshot_{timestamp}_{file.filename}"
    temp_filepath = os.path.join(settings.UPLOAD_FOLDER, temp_filename)
    
    with open(temp_filepath, 'wb') as f:
        f.write(contents)
    
    try:
        result = ExcelProcessor.parse_balance_snapshot_excel(temp_filepath)
        
        import_log = SnapshotImportLog(
            import_batch_id=result['import_batch_id'],
            source_type='EXCEL_UPLOAD',
            start_date=datetime.fromisoformat(result['summary']['date_range']['start']).date(),
            end_date=datetime.fromisoformat(result['summary']['date_range']['end']).date(),
            status='IN_PROGRESS',
            total_records=result['summary']['valid_records'],
            created_by_user_id=current_user.id
        )
        db.add(import_log)
        db.flush()
        
        imported_count = 0
        for record in result['records']:
            snapshot = BalanceSnapshot(
                snapshot_date=record['snapshot_date'],
                account_code=record['account_code'],
                currency=record['currency'],
                balance=record['balance'],
                balance_uzs=record['balance_uzs'],
                fx_rate=record['fx_rate'],
                data_source=record['data_source'],
                import_batch_id=record['import_batch_id'],
                is_validated=False,
            )
            db.add(snapshot)
            imported_count += 1
        
        import_log.imported_records = imported_count
        import_log.status = 'COMPLETED'
        import_log.completed_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "status": "success",
            "import_batch_id": result['import_batch_id'],
            "summary": result['summary'],
            "message": f"Successfully imported {imported_count} balance snapshot records"
        }
        
    except ValueError as ve:
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Upload failed: {str(e)}")


@router.get("/balance-snapshot/template")
def download_balance_snapshot_template():
    """Download Excel template for balance snapshot upload"""
    template_path = os.path.join(settings.UPLOAD_FOLDER, "balance_snapshot_template.xlsx")
    if not os.path.exists(template_path):
        ExcelProcessor.create_balance_snapshot_template(template_path)
    return FileResponse(
        path=template_path,
        filename="balance_snapshot_template.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@router.get("/balance-snapshot/imports")
def list_snapshot_imports(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List balance snapshot import history"""
    imports = db.query(SnapshotImportLog).order_by(
        SnapshotImportLog.started_at.desc()
    ).offset(skip).limit(limit).all()
    
    return [
        {
            "id": imp.id,
            "import_batch_id": imp.import_batch_id,
            "source_type": imp.source_type,
            "start_date": imp.start_date.isoformat() if imp.start_date else None,
            "end_date": imp.end_date.isoformat() if imp.end_date else None,
            "status": imp.status,
            "total_records": imp.total_records,
            "imported_records": imp.imported_records,
            "failed_records": imp.failed_records,
            "started_at": imp.started_at.isoformat() if imp.started_at else None,
            "completed_at": imp.completed_at.isoformat() if imp.completed_at else None,
        }
        for imp in imports
    ]


@router.delete("/balance-snapshot/imports/{batch_id}")
def delete_snapshot_import(
    batch_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a balance snapshot import batch and all its records"""
    import_log = db.query(SnapshotImportLog).filter(
        SnapshotImportLog.import_batch_id == batch_id
    ).first()
    
    if not import_log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import batch not found")
    
    deleted_count = db.query(BalanceSnapshot).filter(
        BalanceSnapshot.import_batch_id == batch_id
    ).delete()
    
    db.delete(import_log)
    db.commit()
    
    return {"status": "success", "deleted_records": deleted_count}


# ============================================================================
# Budget Planned Upload
# ============================================================================

@router.post("/budget-planned/upload")
async def upload_budget_planned(
    file: UploadFile = File(...),
    fiscal_year: int = Query(..., description="Fiscal year for the budget"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Upload budget planned data from Excel file
    
    Expected format:
    - Account Code (required)
    - Jan-Dec monthly amounts
    - Department, Branch, Currency, Scenario, Notes (optional)
    
    All records are created in DRAFT status for review and approval workflow.
    """
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided")
    
    file_ext = file.filename.split('.')[-1].lower()
    if file_ext not in ['xlsx', 'xls']:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only Excel files (.xlsx, .xls) are supported")
    
    contents = await file.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large")
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    temp_filename = f"budget_planned_{timestamp}_{file.filename}"
    temp_filepath = os.path.join(settings.UPLOAD_FOLDER, temp_filename)
    
    with open(temp_filepath, 'wb') as f:
        f.write(contents)
    
    try:
        result = ExcelProcessor.parse_budget_planned_excel(temp_filepath, fiscal_year)
        
        imported_count = 0
        for record in result['records']:
            budget = BudgetPlanned(
                budget_code=record['budget_code'],
                fiscal_year=record['fiscal_year'],
                account_code=record['account_code'],
                department=record['department'],
                branch=record['branch'],
                currency=record['currency'],
                jan=record['jan'],
                feb=record['feb'],
                mar=record['mar'],
                apr=record['apr'],
                may=record['may'],
                jun=record['jun'],
                jul=record['jul'],
                aug=record['aug'],
                sep=record['sep'],
                oct=record['oct'],
                nov=record['nov'],
                dec=record['dec'],
                annual_total=record['annual_total'],
                annual_total_uzs=record['annual_total_uzs'],
                scenario=record['scenario'],
                notes=record['notes'],
                status='DRAFT',
                created_by_user_id=current_user.id,
            )
            db.add(budget)
            imported_count += 1
        
        db.commit()
        
        return {
            "status": "success",
            "fiscal_year": fiscal_year,
            "summary": result['summary'],
            "message": f"Successfully imported {imported_count} budget planned records in DRAFT status"
        }
        
    except ValueError as ve:
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Upload failed: {str(e)}")


@router.get("/budget-planned/template")
def download_budget_planned_template(
    fiscal_year: int = Query(None, description="Fiscal year for template")
):
    """Download Excel template for budget planned upload"""
    if fiscal_year is None:
        fiscal_year = datetime.now().year + 1
    
    template_path = os.path.join(settings.UPLOAD_FOLDER, f"budget_planned_template_{fiscal_year}.xlsx")
    if not os.path.exists(template_path):
        ExcelProcessor.create_budget_planned_template(template_path, fiscal_year)
    return FileResponse(
        path=template_path,
        filename=f"budget_planned_template_{fiscal_year}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@router.get("/budget-planned/list")
def list_budget_planned(
    fiscal_year: int = Query(None),
    status: str = Query(None),
    department: str = Query(None),
    account_code: str = Query(None),
    scenario: str = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """List budget planned records with filtering"""
    query = db.query(BudgetPlanned)
    
    if fiscal_year:
        query = query.filter(BudgetPlanned.fiscal_year == fiscal_year)
    if status:
        query = query.filter(BudgetPlanned.status == status)
    if department:
        query = query.filter(BudgetPlanned.department.ilike(f"%{department}%"))
    if account_code:
        query = query.filter(BudgetPlanned.account_code == account_code)
    if scenario:
        query = query.filter(BudgetPlanned.scenario == scenario)
    
    total = query.count()
    records = query.order_by(BudgetPlanned.account_code).offset(skip).limit(limit).all()
    
    return {
        "total": total,
        "records": [
            {
                "id": r.id,
                "budget_code": r.budget_code,
                "fiscal_year": r.fiscal_year,
                "account_code": r.account_code,
                "department": r.department,
                "branch": r.branch,
                "currency": r.currency,
                "jan": float(r.jan) if r.jan else 0,
                "feb": float(r.feb) if r.feb else 0,
                "mar": float(r.mar) if r.mar else 0,
                "apr": float(r.apr) if r.apr else 0,
                "may": float(r.may) if r.may else 0,
                "jun": float(r.jun) if r.jun else 0,
                "jul": float(r.jul) if r.jul else 0,
                "aug": float(r.aug) if r.aug else 0,
                "sep": float(r.sep) if r.sep else 0,
                "oct": float(r.oct) if r.oct else 0,
                "nov": float(r.nov) if r.nov else 0,
                "dec": float(r.dec) if r.dec else 0,
                "annual_total": float(r.annual_total) if r.annual_total else 0,
                "scenario": r.scenario,
                "status": r.status,
                "notes": r.notes,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ]
    }


@router.get("/budget-planned/{budget_id}")
def get_budget_planned(
    budget_id: int,
    db: Session = Depends(get_db)
):
    """Get a single budget planned record"""
    budget = db.query(BudgetPlanned).filter(BudgetPlanned.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    
    return {
        "id": budget.id,
        "budget_code": budget.budget_code,
        "fiscal_year": budget.fiscal_year,
        "account_code": budget.account_code,
        "department": budget.department,
        "branch": budget.branch,
        "currency": budget.currency,
        "jan": float(budget.jan) if budget.jan else 0,
        "feb": float(budget.feb) if budget.feb else 0,
        "mar": float(budget.mar) if budget.mar else 0,
        "apr": float(budget.apr) if budget.apr else 0,
        "may": float(budget.may) if budget.may else 0,
        "jun": float(budget.jun) if budget.jun else 0,
        "jul": float(budget.jul) if budget.jul else 0,
        "aug": float(budget.aug) if budget.aug else 0,
        "sep": float(budget.sep) if budget.sep else 0,
        "oct": float(budget.oct) if budget.oct else 0,
        "nov": float(budget.nov) if budget.nov else 0,
        "dec": float(budget.dec) if budget.dec else 0,
        "annual_total": float(budget.annual_total) if budget.annual_total else 0,
        "annual_total_uzs": float(budget.annual_total_uzs) if budget.annual_total_uzs else 0,
        "driver_code": budget.driver_code,
        "driver_adjustment_pct": float(budget.driver_adjustment_pct) if budget.driver_adjustment_pct else 0,
        "baseline_amount": float(budget.baseline_amount) if budget.baseline_amount else 0,
        "variance_from_baseline": float(budget.variance_from_baseline) if budget.variance_from_baseline else 0,
        "variance_pct": float(budget.variance_pct) if budget.variance_pct else 0,
        "scenario": budget.scenario,
        "status": budget.status,
        "notes": budget.notes,
        "version": budget.version,
        "created_at": budget.created_at.isoformat() if budget.created_at else None,
        "submitted_at": budget.submitted_at.isoformat() if budget.submitted_at else None,
        "approved_at": budget.approved_at.isoformat() if budget.approved_at else None,
    }


@router.patch("/budget-planned/{budget_id}")
def update_budget_planned(
    budget_id: int,
    updates: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a budget planned record (DRAFT or REJECTED only)"""
    budget = db.query(BudgetPlanned).filter(BudgetPlanned.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    
    if budget.status not in ('DRAFT', 'REJECTED'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only DRAFT or REJECTED budgets can be updated")
    
    allowed_fields = [
        'department', 'branch', 'currency', 'jan', 'feb', 'mar', 'apr', 'may', 'jun',
        'jul', 'aug', 'sep', 'oct', 'nov', 'dec', 'scenario', 'notes',
        'driver_code', 'driver_adjustment_pct'
    ]
    
    for key, value in updates.items():
        if key in allowed_fields:
            setattr(budget, key, value)
    
    months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
    annual_total = sum(float(getattr(budget, m) or 0) for m in months)
    budget.annual_total = annual_total
    if budget.currency == 'UZS':
        budget.annual_total_uzs = annual_total
    
    if budget.status == 'REJECTED':
        budget.status = 'DRAFT'
    
    budget.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(budget)
    
    return {"status": "success", "message": "Budget updated"}


@router.delete("/budget-planned/{budget_id}")
def delete_budget_planned(
    budget_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a budget planned record (DRAFT or REJECTED only)"""
    budget = db.query(BudgetPlanned).filter(BudgetPlanned.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    
    if budget.status not in ('DRAFT', 'REJECTED'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only DRAFT or REJECTED budgets can be deleted")
    
    db.delete(budget)
    db.commit()
    
    return {"status": "success", "message": "Budget deleted"}


@router.post("/budget-planned/{budget_id}/submit")
def submit_budget_planned(
    budget_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Submit a budget planned record for approval"""
    budget = db.query(BudgetPlanned).filter(BudgetPlanned.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    
    if budget.status not in ('DRAFT', 'REJECTED'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only DRAFT or REJECTED budgets can be submitted")
    
    budget.status = 'SUBMITTED'
    budget.submitted_at = datetime.utcnow()
    budget.submitted_by_user_id = current_user.id
    db.commit()
    
    return {"status": "success", "message": "Budget submitted for approval", "new_status": "SUBMITTED"}


@router.post("/budget-planned/bulk-submit")
def bulk_submit_budget_planned(
    budget_ids: List[int],
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Submit multiple budget planned records for approval"""
    submitted = 0
    skipped = 0
    
    for budget_id in budget_ids:
        budget = db.query(BudgetPlanned).filter(BudgetPlanned.id == budget_id).first()
        if budget and budget.status in ('DRAFT', 'REJECTED'):
            budget.status = 'SUBMITTED'
            budget.submitted_at = datetime.utcnow()
            budget.submitted_by_user_id = current_user.id
            submitted += 1
        else:
            skipped += 1
    
    db.commit()
    
    return {
        "status": "success",
        "submitted": submitted,
        "skipped": skipped,
        "message": f"Submitted {submitted} budgets for approval"
    }


# ============================================================================
# Upload Statistics
# ============================================================================

@router.get("/stats")
def get_upload_stats(
    fiscal_year: int = Query(None),
    db: Session = Depends(get_db)
):
    """Get statistics for uploaded data"""
    snapshot_count = db.query(func.count(BalanceSnapshot.id)).scalar()
    snapshot_date_range = db.query(
        func.min(BalanceSnapshot.snapshot_date),
        func.max(BalanceSnapshot.snapshot_date)
    ).first()
    
    budget_query = db.query(BudgetPlanned)
    if fiscal_year:
        budget_query = budget_query.filter(BudgetPlanned.fiscal_year == fiscal_year)
    
    budget_stats = budget_query.with_entities(
        func.count(BudgetPlanned.id),
        func.sum(BudgetPlanned.annual_total),
    ).first()
    
    status_breakdown = db.query(
        BudgetPlanned.status,
        func.count(BudgetPlanned.id)
    ).group_by(BudgetPlanned.status).all()
    
    return {
        "balance_snapshots": {
            "total_records": snapshot_count,
            "date_range": {
                "start": snapshot_date_range[0].isoformat() if snapshot_date_range[0] else None,
                "end": snapshot_date_range[1].isoformat() if snapshot_date_range[1] else None,
            }
        },
        "budget_planned": {
            "total_records": budget_stats[0] or 0,
            "total_annual_amount": float(budget_stats[1]) if budget_stats[1] else 0,
            "by_status": {s: c for s, c in status_breakdown}
        }
    }
