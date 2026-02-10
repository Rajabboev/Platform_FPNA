"""Approval workflow API routes"""

from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.budget import Budget, BudgetApproval, BudgetStatus
from app.models.user import User
from app.schemas.budget import BudgetResponse, BudgetSummary
from app.schemas.approval import ApproveRejectRequest, ApprovalRecordResponse
from app.utils.dependencies import get_current_active_user
from app.services.approval_service import (
    get_pending_for_user,
    approve_budget,
    reject_budget,
    submit_budget,
    get_current_level,
)

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("/pending", response_model=list)
def list_pending_approvals(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List budgets pending at a level the current user can approve."""
    budgets = get_pending_for_user(current_user, db)
    return [
        {
            "id": b.id,
            "budget_code": b.budget_code,
            "fiscal_year": b.fiscal_year,
            "department": b.department,
            "branch": b.branch,
            "total_amount": float(b.total_amount),
            "status": b.status.value,
            "current_level": get_current_level(b.status),
            "line_items_count": len(b.line_items),
        }
        for b in budgets
    ]


@router.post("/{budget_id}/approve", response_model=BudgetResponse)
def approve(
    budget_id: int,
    body: ApproveRejectRequest = Body(default=ApproveRejectRequest()),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Approve budget at current level."""
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    return approve_budget(budget, current_user, body.comment, db)


@router.post("/{budget_id}/reject", response_model=BudgetResponse)
def reject(
    budget_id: int,
    body: ApproveRejectRequest = Body(default=ApproveRejectRequest()),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Reject budget at current level."""
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    return reject_budget(budget, current_user, body.comment, db)


@router.get("/{budget_id}/history")
def get_approval_history(
    budget_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get approval history for a budget."""
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    records = db.query(BudgetApproval).filter(BudgetApproval.budget_id == budget_id).order_by(BudgetApproval.created_at).all()
    return [{"user_username": r.user_username, "level": r.level, "action": r.action, "comment": r.comment, "created_at": r.created_at} for r in records]
