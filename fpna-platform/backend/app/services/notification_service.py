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


def notify_template_assigned(
    recipient_id: int,
    template_name: str,
    fiscal_year: int,
    deadline: str | None,
    assigned_by: str,
    db: Session
) -> None:
    """Notify user that a budget template has been assigned to them."""
    deadline_str = f" Deadline: {deadline}." if deadline else ""
    msg = f"You have been assigned the '{template_name}' budget template for fiscal year {fiscal_year}.{deadline_str} Please complete your budget entries."
    db.add(Notification(
        recipient_id=recipient_id,
        type="TEMPLATE_ASSIGNED",
        message=msg,
        actor_username=assigned_by,
    ))
    db.commit()


def notify_department_users_template_assigned(
    department_id: int,
    template_name: str,
    fiscal_year: int,
    deadline: str | None,
    assigned_by: str,
    db: Session
) -> None:
    """Notify all users in a department that a template has been assigned."""
    from app.models.department import Department
    
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept or not dept.manager_user_id:
        return
    
    deadline_str = f" Deadline: {deadline}." if deadline else ""
    msg = f"Department '{dept.name_en}' has been assigned the '{template_name}' budget template for fiscal year {fiscal_year}.{deadline_str}"
    
    # Notify the department manager
    db.add(Notification(
        recipient_id=dept.manager_user_id,
        type="TEMPLATE_ASSIGNED",
        message=msg,
        actor_username=assigned_by,
    ))
    db.commit()


def notify_budget_plan_created(
    department_id: int,
    fiscal_year: int,
    created_by: str,
    db: Session
) -> None:
    """Notify department manager that a budget plan has been created for their department."""
    from app.models.department import Department
    
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept or not dept.manager_user_id:
        return
    
    msg = f"A budget plan for fiscal year {fiscal_year} has been created for your department '{dept.name_en}'. Please review and make adjustments."
    
    db.add(Notification(
        recipient_id=dept.manager_user_id,
        type="BUDGET_PLAN_CREATED",
        message=msg,
        actor_username=created_by,
    ))
    db.commit()


def notify_budget_plan_submitted(
    plan_id: int,
    department_name: str,
    fiscal_year: int,
    submitted_by: str,
    db: Session
) -> None:
    """Notify CFO/managers that a department has submitted their budget plan."""
    perm = LEVEL_PERMISSION.get(1)  # L1 approvers
    if not perm:
        return
    
    managers = _get_users_with_permission(perm, db)
    msg = f"Department '{department_name}' has submitted their budget plan for fiscal year {fiscal_year}. Please review and approve."
    
    for m in managers:
        db.add(Notification(
            recipient_id=m.id,
            type="BUDGET_PLAN_SUBMITTED",
            message=msg,
            actor_username=submitted_by,
        ))
    db.commit()


def notify_budget_plan_approved(
    department_id: int,
    fiscal_year: int,
    approved_by: str,
    approval_level: str,
    db: Session
) -> None:
    """Notify department manager that their budget plan has been approved."""
    from app.models.department import Department
    
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept or not dept.manager_user_id:
        return
    
    msg = f"Your budget plan for fiscal year {fiscal_year} has been approved ({approval_level})."
    
    db.add(Notification(
        recipient_id=dept.manager_user_id,
        type="BUDGET_PLAN_APPROVED",
        message=msg,
        actor_username=approved_by,
    ))
    db.commit()


def notify_budget_plan_rejected(
    department_id: int,
    fiscal_year: int,
    rejected_by: str,
    reason: str | None,
    db: Session
) -> None:
    """Notify department manager that their budget plan has been rejected."""
    from app.models.department import Department
    
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept or not dept.manager_user_id:
        return
    
    reason_str = f" Reason: {reason}" if reason else ""
    msg = f"Your budget plan for fiscal year {fiscal_year} has been rejected.{reason_str} Please revise and resubmit."
    
    db.add(Notification(
        recipient_id=dept.manager_user_id,
        type="BUDGET_PLAN_REJECTED",
        message=msg,
        actor_username=rejected_by,
    ))
    db.commit()
