"""Notification service for manager-worker workflow"""

from sqlalchemy.orm import Session
from app.models.notification import Notification
from app.models.budget import Budget, BudgetStatus
from app.models.user import User, PermissionEnum
from app.utils.permissions import get_user_permissions

LEVEL_PERMISSION = {
    1: PermissionEnum.APPROVE_L1,
    2: PermissionEnum.APPROVE_L2,
    3: PermissionEnum.APPROVE_L3,
    4: PermissionEnum.APPROVE_L4,
}


def _get_users_with_permission(perm: PermissionEnum, db: Session) -> list[User]:
    """Get all users who have a specific permission."""
    from app.utils.permissions import get_user_permissions
    users = db.query(User).filter(User.is_active == True).all()
    result = []
    for u in users:
        roles = [r.name for r in u.roles]
        perms = get_user_permissions(roles)
        if perm.value in perms:
            result.append(u)
    return result


def notify_managers_pending(budget: Budget, actor: User, db: Session) -> None:
    """Notify managers that a budget is awaiting their approval (L1)."""
    level = 1
    perm = LEVEL_PERMISSION.get(level)
    if not perm:
        return
    managers = _get_users_with_permission(perm, db)
    msg = f"{actor.username} submitted budget {budget.budget_code} for your approval."
    for m in managers:
        db.add(Notification(
            recipient_id=m.id,
            type="PENDING_APPROVAL",
            budget_id=budget.id,
            budget_code=budget.budget_code,
            actor_username=actor.username,
            message=msg,
        ))
    db.commit()


def notify_worker_approved(budget: Budget, actor: User, worker_user_id: int | None, db: Session) -> None:
    """Notify worker that their budget was approved."""
    if not worker_user_id:
        return
    msg = f"Your budget {budget.budget_code} has been approved."
    db.add(Notification(
        recipient_id=worker_user_id,
        type="APPROVED",
        budget_id=budget.id,
        budget_code=budget.budget_code,
        actor_username=actor.username,
        message=msg,
    ))
    db.commit()


def notify_worker_rejected(budget: Budget, actor: User, worker_user_id: int | None, db: Session) -> None:
    """Notify worker that their budget was rejected - please revise."""
    if not worker_user_id:
        return
    msg = f"Your budget {budget.budget_code} was rejected. Please revise the budget items and resubmit."
    db.add(Notification(
        recipient_id=worker_user_id,
        type="REJECTED",
        budget_id=budget.id,
        budget_code=budget.budget_code,
        actor_username=actor.username,
        message=msg,
    ))
    db.commit()


def notify_managers_uploaded(budget: Budget, uploaded_by_username: str, db: Session) -> None:
    """Notify managers when a new budget is uploaded (for approval)."""
    perm = LEVEL_PERMISSION.get(1)
    if not perm:
        return
    managers = _get_users_with_permission(perm, db)
    msg = f"{uploaded_by_username} uploaded budget {budget.budget_code}. It is awaiting your approval."
    for m in managers:
        db.add(Notification(
            recipient_id=m.id,
            type="PENDING_APPROVAL",
            budget_id=budget.id,
            budget_code=budget.budget_code,
            actor_username=uploaded_by_username,
            message=msg,
        ))
    db.commit()
