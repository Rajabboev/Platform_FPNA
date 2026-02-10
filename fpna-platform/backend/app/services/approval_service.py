"""Approval service logic - role-based approval workflow"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Tuple

from app.models.budget import Budget, BudgetApproval, BudgetStatus
from app.models.user import User, PermissionEnum
from app.utils.permissions import get_user_permissions

# Level -> required permission
LEVEL_PERMISSION = {
    1: PermissionEnum.APPROVE_L1,
    2: PermissionEnum.APPROVE_L2,
    3: PermissionEnum.APPROVE_L3,
    4: PermissionEnum.APPROVE_L4,
}

# Status -> current approval level (which level can act next)
STATUS_LEVEL = {
    BudgetStatus.SUBMITTED: 1,
    BudgetStatus.PENDING_L1: 1,
    BudgetStatus.PENDING_L2: 2,
    BudgetStatus.PENDING_L3: 3,
    BudgetStatus.PENDING_L4: 4,
}


def _user_permissions(user: User) -> List[str]:
    perms = set()
    # From database Role.permissions
    for role in user.roles:
        if role.permissions:
            perms.update(p.strip() for p in role.permissions.split(",") if p.strip())
    # From ROLE_PERMISSIONS (source of truth, in case DB is stale)
    role_names = [r.name for r in user.roles]
    perms.update(get_user_permissions(role_names))
    return list(perms)


# Roles that can submit budgets (fallback if permission loading fails)
SUBMIT_ROLES = {"ANALYST", "CFO", "BRANCH_MANAGER", "FINANCE_MANAGER", "ADMIN"}


def can_submit(user: User) -> bool:
    # Direct role check (most reliable)
    role_names = {r.name.upper() for r in user.roles}
    if role_names & SUBMIT_ROLES:
        return True
    # Permission-based check
    return PermissionEnum.SUBMIT_BUDGET.value in _user_permissions(user)


def can_approve_at_level(user: User, level: int) -> bool:
    perm = LEVEL_PERMISSION.get(level)
    return perm and perm.value in _user_permissions(user) if perm else False


def get_current_level(status: BudgetStatus) -> Optional[int]:
    return STATUS_LEVEL.get(status)


def _status_str(s) -> str:
    """Normalize status for comparison (handles enum or string from DB)."""
    return (s.value if hasattr(s, 'value') else str(s)) if s else ""


def submit_budget(budget: Budget, user: User, db: Session) -> Budget:
    """Submit DRAFT or REJECTED budget to start approval workflow (DRAFT/REJECTED → PENDING_L1)."""
    if _status_str(budget.status) not in ("DRAFT", "REJECTED"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only DRAFT or REJECTED budgets can be submitted")
    if not can_submit(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to submit budgets")
    budget.status = BudgetStatus.PENDING_L1
    budget.submitted_by_user_id = user.id
    db.commit()
    db.refresh(budget)
    try:
        from app.services.notification_service import notify_managers_pending
        notify_managers_pending(budget, user, db)
    except Exception:
        pass
    return budget


def approve_budget(budget: Budget, user: User, comment: Optional[str], db: Session) -> Budget:
    """Approve at current level. Moves to next level or APPROVED."""
    level = get_current_level(budget.status)
    if level is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Budget is not pending approval")
    if not can_approve_at_level(user, level):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"No permission to approve at level {level}")

    # Record approval
    db.add(BudgetApproval(
        budget_id=budget.id,
        user_id=user.id,
        user_username=user.username,
        level=level,
        action="APPROVED",
        comment=comment,
    ))

    if level == 4:
        budget.status = BudgetStatus.APPROVED
    else:
        budget.status = getattr(BudgetStatus, f"PENDING_L{level + 1}")

    db.commit()
    db.refresh(budget)
    worker_id = getattr(budget, "submitted_by_user_id", None) or _worker_id_from_uploaded_by(budget.uploaded_by, db)
    if budget.status == BudgetStatus.APPROVED and worker_id:
        from app.services.notification_service import notify_worker_approved
        notify_worker_approved(budget, user, worker_id, db)
    return budget


def _worker_id_from_uploaded_by(uploaded_by: Optional[str], db: Session) -> Optional[int]:
    """Look up user id by uploaded_by username."""
    if not uploaded_by:
        return None
    from app.models.user import User
    u = db.query(User).filter(User.username == uploaded_by).first()
    return u.id if u else None


def reject_budget(budget: Budget, user: User, comment: Optional[str], db: Session) -> Budget:
    """Reject at current level."""
    level = get_current_level(budget.status)
    if level is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Budget is not pending approval")
    if not can_approve_at_level(user, level):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"No permission to reject at level {level}")

    db.add(BudgetApproval(
        budget_id=budget.id,
        user_id=user.id,
        user_username=user.username,
        level=level,
        action="REJECTED",
        comment=comment,
    ))
    budget.status = BudgetStatus.REJECTED
    db.commit()
    db.refresh(budget)
    worker_id = getattr(budget, "submitted_by_user_id", None) or _worker_id_from_uploaded_by(budget.uploaded_by, db)
    if worker_id:
        from app.services.notification_service import notify_worker_rejected
        notify_worker_rejected(budget, user, worker_id, db)
    return budget


def get_pending_for_user(user: User, db: Session) -> List[Budget]:
    """Budgets pending at a level the user can approve."""
    perms = _user_permissions(user)
    pending = []
    for status_name, level in STATUS_LEVEL.items():
        perm = LEVEL_PERMISSION.get(level)
        if perm and perm.value in perms:
            budgets = db.query(Budget).filter(Budget.status == status_name).order_by(Budget.id).all()
            pending.extend(budgets)
    return pending
