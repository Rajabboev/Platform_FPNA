"""
Approval service for BudgetPlanned records

Handles approval workflow for budget plans uploaded via Excel or generated from baseline.
Uses a simpler status flow: DRAFT → SUBMITTED → APPROVED/REJECTED → EXPORTED
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from datetime import datetime

from app.models.baseline import BudgetPlanned
from app.models.user import User, PermissionEnum
from app.utils.permissions import get_user_permissions


# Status flow for BudgetPlanned
PLANNED_STATUS_FLOW = {
    'DRAFT': ['SUBMITTED'],
    'SUBMITTED': ['APPROVED', 'REJECTED'],
    'REJECTED': ['SUBMITTED'],  # Can resubmit after rejection
    'APPROVED': ['EXPORTED'],
    'EXPORTED': [],  # Terminal state
}


def _user_permissions(user: User) -> List[str]:
    """Get all permissions for a user"""
    perms = set()
    for role in user.roles:
        if role.permissions:
            perms.update(p.strip() for p in role.permissions.split(",") if p.strip())
    role_names = [r.name for r in user.roles]
    perms.update(get_user_permissions(role_names))
    return list(perms)


def can_submit_planned(user: User) -> bool:
    """Check if user can submit budget plans"""
    submit_roles = {"ANALYST", "CFO", "BRANCH_MANAGER", "FINANCE_MANAGER", "ADMIN"}
    role_names = {r.name.upper() for r in user.roles}
    if role_names & submit_roles:
        return True
    return PermissionEnum.SUBMIT_BUDGET.value in _user_permissions(user)


def can_approve_planned(user: User) -> bool:
    """Check if user can approve budget plans (requires at least L1 approval permission)"""
    perms = _user_permissions(user)
    approval_perms = [
        PermissionEnum.APPROVE_L1.value,
        PermissionEnum.APPROVE_L2.value,
        PermissionEnum.APPROVE_L3.value,
        PermissionEnum.APPROVE_L4.value,
    ]
    return any(p in perms for p in approval_perms)


def submit_planned_budget(budget: BudgetPlanned, user: User, db: Session) -> BudgetPlanned:
    """Submit a DRAFT or REJECTED budget plan for approval"""
    if budget.status not in ('DRAFT', 'REJECTED'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only DRAFT or REJECTED budgets can be submitted"
        )
    
    if not can_submit_planned(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permission to submit budget plans"
        )
    
    budget.status = 'SUBMITTED'
    budget.submitted_at = datetime.utcnow()
    budget.submitted_by_user_id = user.id
    db.commit()
    db.refresh(budget)
    
    # Send notification to approvers
    try:
        from app.services.notification_service import create_notification
        create_notification(
            db=db,
            title="Budget Plan Submitted",
            message=f"Budget plan {budget.budget_code} for account {budget.account_code} has been submitted for approval",
            notification_type="APPROVAL_REQUIRED",
            related_entity_type="budget_planned",
            related_entity_id=budget.id,
        )
    except Exception:
        pass
    
    return budget


def approve_planned_budget(budget: BudgetPlanned, user: User, comment: Optional[str], db: Session) -> BudgetPlanned:
    """Approve a submitted budget plan"""
    if budget.status != 'SUBMITTED':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only SUBMITTED budgets can be approved"
        )
    
    if not can_approve_planned(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permission to approve budget plans"
        )
    
    budget.status = 'APPROVED'
    budget.approved_at = datetime.utcnow()
    budget.approved_by_user_id = user.id
    if comment:
        budget.notes = f"{budget.notes or ''}\n[Approval: {comment}]".strip()
    
    db.commit()
    db.refresh(budget)
    
    # Notify submitter
    try:
        from app.services.notification_service import create_notification
        if budget.submitted_by_user_id:
            create_notification(
                db=db,
                user_id=budget.submitted_by_user_id,
                title="Budget Plan Approved",
                message=f"Your budget plan {budget.budget_code} has been approved",
                notification_type="APPROVAL_COMPLETE",
                related_entity_type="budget_planned",
                related_entity_id=budget.id,
            )
    except Exception:
        pass
    
    return budget


def reject_planned_budget(budget: BudgetPlanned, user: User, comment: Optional[str], db: Session) -> BudgetPlanned:
    """Reject a submitted budget plan"""
    if budget.status != 'SUBMITTED':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only SUBMITTED budgets can be rejected"
        )
    
    if not can_approve_planned(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permission to reject budget plans"
        )
    
    budget.status = 'REJECTED'
    if comment:
        budget.notes = f"{budget.notes or ''}\n[Rejection: {comment}]".strip()
    
    db.commit()
    db.refresh(budget)
    
    # Notify submitter
    try:
        from app.services.notification_service import create_notification
        if budget.submitted_by_user_id:
            create_notification(
                db=db,
                user_id=budget.submitted_by_user_id,
                title="Budget Plan Rejected",
                message=f"Your budget plan {budget.budget_code} has been rejected. Reason: {comment or 'No reason provided'}",
                notification_type="APPROVAL_REJECTED",
                related_entity_type="budget_planned",
                related_entity_id=budget.id,
            )
    except Exception:
        pass
    
    return budget


def get_pending_planned_for_user(user: User, db: Session) -> List[BudgetPlanned]:
    """Get budget plans pending approval that the user can approve"""
    if not can_approve_planned(user):
        return []
    
    return db.query(BudgetPlanned).filter(
        BudgetPlanned.status == 'SUBMITTED'
    ).order_by(BudgetPlanned.submitted_at).all()


def bulk_approve_planned(budget_ids: List[int], user: User, comment: Optional[str], db: Session) -> dict:
    """Bulk approve multiple budget plans"""
    if not can_approve_planned(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permission to approve budget plans"
        )
    
    approved = 0
    skipped = 0
    
    for budget_id in budget_ids:
        budget = db.query(BudgetPlanned).filter(BudgetPlanned.id == budget_id).first()
        if budget and budget.status == 'SUBMITTED':
            budget.status = 'APPROVED'
            budget.approved_at = datetime.utcnow()
            budget.approved_by_user_id = user.id
            if comment:
                budget.notes = f"{budget.notes or ''}\n[Bulk Approval: {comment}]".strip()
            approved += 1
        else:
            skipped += 1
    
    db.commit()
    
    return {
        "approved": approved,
        "skipped": skipped,
        "message": f"Approved {approved} budget plans"
    }


def bulk_reject_planned(budget_ids: List[int], user: User, comment: str, db: Session) -> dict:
    """Bulk reject multiple budget plans"""
    if not can_approve_planned(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permission to reject budget plans"
        )
    
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rejection comment is required"
        )
    
    rejected = 0
    skipped = 0
    
    for budget_id in budget_ids:
        budget = db.query(BudgetPlanned).filter(BudgetPlanned.id == budget_id).first()
        if budget and budget.status == 'SUBMITTED':
            budget.status = 'REJECTED'
            budget.notes = f"{budget.notes or ''}\n[Bulk Rejection: {comment}]".strip()
            rejected += 1
        else:
            skipped += 1
    
    db.commit()
    
    return {
        "rejected": rejected,
        "skipped": skipped,
        "message": f"Rejected {rejected} budget plans"
    }
