"""
API endpoints for BudgetPlanned approval workflow

Provides endpoints for:
- Listing pending budget plans for approval
- Approving/rejecting individual or bulk budget plans
- Viewing approval history
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.models.baseline import BudgetPlanned
from app.models.user import User
from app.utils.dependencies import get_current_active_user
from app.services.planned_approval_service import (
    submit_planned_budget,
    approve_planned_budget,
    reject_planned_budget,
    get_pending_planned_for_user,
    bulk_approve_planned,
    bulk_reject_planned,
    can_approve_planned,
)

router = APIRouter(prefix="/planned-approvals", tags=["planned-approvals"])


class ApprovalAction(BaseModel):
    comment: Optional[str] = None


class BulkApprovalRequest(BaseModel):
    budget_ids: List[int]
    comment: Optional[str] = None


class BulkRejectionRequest(BaseModel):
    budget_ids: List[int]
    comment: str


@router.get("/pending")
def list_pending_approvals(
    fiscal_year: int = Query(None),
    department: str = Query(None),
    account_code: str = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List budget plans pending approval for the current user"""
    budgets = get_pending_planned_for_user(current_user, db)
    
    # Apply filters
    if fiscal_year:
        budgets = [b for b in budgets if b.fiscal_year == fiscal_year]
    if department:
        budgets = [b for b in budgets if b.department and department.lower() in b.department.lower()]
    if account_code:
        budgets = [b for b in budgets if b.account_code == account_code]
    
    return {
        "total": len(budgets),
        "can_approve": can_approve_planned(current_user),
        "budgets": [
            {
                "id": b.id,
                "budget_code": b.budget_code,
                "fiscal_year": b.fiscal_year,
                "account_code": b.account_code,
                "department": b.department,
                "branch": b.branch,
                "currency": b.currency,
                "annual_total": float(b.annual_total) if b.annual_total else 0,
                "scenario": b.scenario,
                "status": b.status,
                "submitted_at": b.submitted_at.isoformat() if b.submitted_at else None,
                "notes": b.notes,
            }
            for b in budgets
        ]
    }


@router.get("/stats")
def get_approval_stats(
    fiscal_year: int = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get approval statistics"""
    from sqlalchemy import func
    
    query = db.query(BudgetPlanned)
    if fiscal_year:
        query = query.filter(BudgetPlanned.fiscal_year == fiscal_year)
    
    status_counts = query.with_entities(
        BudgetPlanned.status,
        func.count(BudgetPlanned.id),
        func.sum(BudgetPlanned.annual_total)
    ).group_by(BudgetPlanned.status).all()
    
    return {
        "by_status": {
            s: {"count": c, "total_amount": float(t) if t else 0}
            for s, c, t in status_counts
        },
        "can_approve": can_approve_planned(current_user),
    }


@router.post("/{budget_id}/approve")
def approve_budget(
    budget_id: int,
    action: ApprovalAction = Body(default=ApprovalAction()),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Approve a submitted budget plan"""
    budget = db.query(BudgetPlanned).filter(BudgetPlanned.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    
    approved = approve_planned_budget(budget, current_user, action.comment, db)
    
    return {
        "status": "success",
        "message": f"Budget {approved.budget_code} approved",
        "budget": {
            "id": approved.id,
            "budget_code": approved.budget_code,
            "status": approved.status,
            "approved_at": approved.approved_at.isoformat() if approved.approved_at else None,
        }
    }


@router.post("/{budget_id}/reject")
def reject_budget(
    budget_id: int,
    action: ApprovalAction = Body(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Reject a submitted budget plan"""
    budget = db.query(BudgetPlanned).filter(BudgetPlanned.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    
    rejected = reject_planned_budget(budget, current_user, action.comment, db)
    
    return {
        "status": "success",
        "message": f"Budget {rejected.budget_code} rejected",
        "budget": {
            "id": rejected.id,
            "budget_code": rejected.budget_code,
            "status": rejected.status,
        }
    }


@router.post("/{budget_id}/submit")
def submit_budget(
    budget_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Submit a draft budget plan for approval"""
    budget = db.query(BudgetPlanned).filter(BudgetPlanned.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    
    submitted = submit_planned_budget(budget, current_user, db)
    
    return {
        "status": "success",
        "message": f"Budget {submitted.budget_code} submitted for approval",
        "budget": {
            "id": submitted.id,
            "budget_code": submitted.budget_code,
            "status": submitted.status,
            "submitted_at": submitted.submitted_at.isoformat() if submitted.submitted_at else None,
        }
    }


@router.post("/bulk-approve")
def bulk_approve(
    request: BulkApprovalRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Bulk approve multiple budget plans"""
    result = bulk_approve_planned(request.budget_ids, current_user, request.comment, db)
    return result


@router.post("/bulk-reject")
def bulk_reject(
    request: BulkRejectionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Bulk reject multiple budget plans"""
    result = bulk_reject_planned(request.budget_ids, current_user, request.comment, db)
    return result


@router.post("/bulk-submit")
def bulk_submit(
    request: BulkApprovalRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Bulk submit multiple draft budget plans for approval"""
    from app.services.planned_approval_service import can_submit_planned
    
    if not can_submit_planned(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permission to submit budget plans"
        )
    
    submitted = 0
    skipped = 0
    
    for budget_id in request.budget_ids:
        budget = db.query(BudgetPlanned).filter(BudgetPlanned.id == budget_id).first()
        if budget and budget.status in ('DRAFT', 'REJECTED'):
            budget.status = 'SUBMITTED'
            budget.submitted_at = __import__('datetime').datetime.utcnow()
            budget.submitted_by_user_id = current_user.id
            submitted += 1
        else:
            skipped += 1
    
    db.commit()
    
    return {
        "submitted": submitted,
        "skipped": skipped,
        "message": f"Submitted {submitted} budget plans for approval"
    }


@router.get("/{budget_id}")
def get_budget_details(
    budget_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get detailed budget plan information for approval review"""
    budget = db.query(BudgetPlanned).filter(BudgetPlanned.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    
    # Get submitter info
    submitter = None
    if budget.submitted_by_user_id:
        from app.models.user import User
        user = db.query(User).filter(User.id == budget.submitted_by_user_id).first()
        if user:
            submitter = {"id": user.id, "username": user.username, "full_name": user.full_name}
    
    # Get approver info
    approver = None
    if budget.approved_by_user_id:
        user = db.query(User).filter(User.id == budget.approved_by_user_id).first()
        if user:
            approver = {"id": user.id, "username": user.username, "full_name": user.full_name}
    
    return {
        "id": budget.id,
        "budget_code": budget.budget_code,
        "fiscal_year": budget.fiscal_year,
        "account_code": budget.account_code,
        "department": budget.department,
        "branch": budget.branch,
        "currency": budget.currency,
        "monthly": {
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
        },
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
        "submitter": submitter,
        "approver": approver,
        "submitted_at": budget.submitted_at.isoformat() if budget.submitted_at else None,
        "approved_at": budget.approved_at.isoformat() if budget.approved_at else None,
        "created_at": budget.created_at.isoformat() if budget.created_at else None,
        "can_approve": can_approve_planned(current_user),
    }
