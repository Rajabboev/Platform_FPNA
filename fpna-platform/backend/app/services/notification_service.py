"""
Notification service for FP&A budget workflow.

Workflow events:
  1. CFO initializes budget cycle → dept managers/heads get notified (step 4)
  2. CFO assigns groups to department → dept head + all dept users notified (step 4)
  3. Department submits plan → CFO notified (step 6)
  4. All depts submitted → CFO gets aggregate notification (step 6)
  5. CFO approves dept plan → dept head + manager notified (step 5)
  6. CFO rejects dept plan → dept head + manager notified with reason (step 4)
  7. CFO approves all → CEO notified (step 7)
  8. CEO approves → CFO notified to export (step 7)
  9. CEO rejects → CFO notified (step 6)
"""

from sqlalchemy.orm import Session
from app.models.notification import Notification
from app.models.user import User, PermissionEnum
from app.utils.permissions import get_user_permissions


LEVEL_PERMISSION = {
    1: PermissionEnum.APPROVE_L1,   # CFO
    2: PermissionEnum.APPROVE_L2,
    3: PermissionEnum.APPROVE_L3,
    4: PermissionEnum.APPROVE_L4,   # CEO
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_users_with_permission(perm: PermissionEnum, db: Session) -> list:
    """Return all active users who hold the given permission."""
    users = db.query(User).filter(User.is_active == True).all()
    result = []
    for u in users:
        roles = [r.name for r in u.roles]
        perms = get_user_permissions(roles)
        if perm.value in perms:
            result.append(u)
    return result


def _get_dept_recipients(department_id: int, db: Session) -> set:
    """
    Return user IDs to notify for a department.
    Includes: head_user_id, manager_user_id, and all active DepartmentAssignment users.
    """
    from app.models.department import Department, DepartmentAssignment

    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        return set()

    recipients: set = set()
    if dept.head_user_id:
        recipients.add(dept.head_user_id)
    if dept.manager_user_id:
        recipients.add(dept.manager_user_id)

    assignments = db.query(DepartmentAssignment).filter(
        DepartmentAssignment.department_id == department_id,
        DepartmentAssignment.is_active == True,
    ).all()
    for a in assignments:
        recipients.add(a.user_id)

    return recipients


def _add_notification(
    db: Session,
    recipient_id: int,
    notif_type: str,
    message: str,
    actor_username: str = None,
    plan_id: int = None,
    plan_code: str = None,
    link_step: int = None,
) -> None:
    db.add(Notification(
        recipient_id=recipient_id,
        type=notif_type,
        message=message,
        actor_username=actor_username,
        plan_id=plan_id,
        plan_code=plan_code,
        link_step=link_step,
    ))


# ---------------------------------------------------------------------------
# Workflow notification functions
# ---------------------------------------------------------------------------

def notify_budget_cycle_initialized(
    fiscal_year: int,
    initialized_by: str,
    db: Session,
) -> None:
    """
    CFO started a new budget cycle → notify all department heads/managers
    so they know their budget templates will be coming.
    """
    from app.models.department import Department

    depts = db.query(Department).filter(Department.is_active == True).all()
    msg = (
        f"{initialized_by} has started the budget planning cycle for FY {fiscal_year}. "
        f"Budget baselines are being calculated. You will be notified when your "
        f"department template is ready for input."
    )
    notified: set = set()
    for dept in depts:
        for uid in _get_dept_recipients(dept.id, db):
            if uid not in notified:
                _add_notification(db, uid, "BUDGET_CYCLE_STARTED", msg,
                                  actor_username=initialized_by, link_step=4)
                notified.add(uid)
    db.commit()


def notify_department_assigned(
    department_id: int,
    fiscal_year: int,
    group_count: int,
    assigned_by: str,
    can_edit: bool,
    db: Session,
    plan_id: int = None,
) -> None:
    """
    CFO assigned budgeting groups to a department → notify all dept users.
    Step 4: Department Budget Entry.
    """
    from app.models.department import Department

    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        return

    perm = "edit" if can_edit else "view-only"
    msg = (
        f"{assigned_by} assigned {group_count} budgeting group(s) to '{dept.name_en}' "
        f"for FY {fiscal_year} ({perm} access). "
        f"Please open your budget template and adjust the driver values for your section."
    )

    for uid in _get_dept_recipients(department_id, db):
        _add_notification(db, uid, "DEPT_GROUPS_ASSIGNED", msg,
                          actor_username=assigned_by,
                          plan_id=plan_id, link_step=4)
    db.commit()


def notify_department_users_template_assigned(
    department_id: int,
    template_name: str,
    fiscal_year: int,
    deadline: str | None,
    assigned_by: str,
    db: Session,
) -> None:
    """Notify all users in a department that a budget template has been assigned."""
    from app.models.department import Department

    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        return

    deadline_str = f" Deadline: {deadline}." if deadline else ""
    msg = (
        f"Department '{dept.name_en}' has been assigned the '{template_name}' "
        f"budget template for FY {fiscal_year}.{deadline_str} "
        f"Please review and complete your budget entries."
    )

    for uid in _get_dept_recipients(department_id, db):
        _add_notification(db, uid, "TEMPLATE_ASSIGNED", msg,
                          actor_username=assigned_by, link_step=4)
    db.commit()


def notify_budget_plan_created(
    department_id: int,
    fiscal_year: int,
    created_by: str,
    db: Session,
    plan_id: int = None,
) -> None:
    """
    A budget plan was created for a department → notify dept head and manager.
    """
    from app.models.department import Department

    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        return

    msg = (
        f"A budget plan for FY {fiscal_year} has been created for '{dept.name_en}'. "
        f"Please review the baseline, adjust driver values for your section, "
        f"and submit when ready."
    )

    for uid in _get_dept_recipients(department_id, db):
        _add_notification(db, uid, "BUDGET_PLAN_CREATED", msg,
                          actor_username=created_by,
                          plan_id=plan_id, link_step=4)
    db.commit()


def notify_budget_plan_submitted(
    plan_id: int,
    department_name: str,
    fiscal_year: int,
    submitted_by: str,
    db: Session,
) -> None:
    """
    Department submitted their budget plan → notify CFO (L1 approvers).
    Step 6: CFO Review.
    """
    managers = _get_users_with_permission(LEVEL_PERMISSION[1], db)
    msg = (
        f"'{department_name}' has submitted their budget plan for FY {fiscal_year}. "
        f"Please review in the CFO dashboard and approve or return for revision."
    )
    plan_code = f"{department_name} / FY{fiscal_year}"
    for m in managers:
        _add_notification(db, m.id, "BUDGET_PLAN_SUBMITTED", msg,
                          actor_username=submitted_by,
                          plan_id=plan_id, plan_code=plan_code, link_step=6)
    db.commit()


def notify_all_departments_submitted(fiscal_year: int, db: Session) -> None:
    """
    All departments have submitted → aggregate notification to CFO.
    """
    managers = _get_users_with_permission(LEVEL_PERMISSION[1], db)
    msg = (
        f"All departments have submitted their budget plans for FY {fiscal_year}. "
        f"You may now proceed to the CFO Review step to approve or reject."
    )
    for m in managers:
        _add_notification(db, m.id, "ALL_SUBMITTED", msg, link_step=6)
    db.commit()


def notify_budget_plan_approved(
    department_id: int,
    fiscal_year: int,
    approved_by: str,
    approval_level: str,
    db: Session,
    plan_id: int = None,
) -> None:
    """
    CFO approved dept budget plan → notify dept head and manager.
    """
    from app.models.department import Department

    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        return

    msg = (
        f"Your department's budget plan for FY {fiscal_year} has been approved "
        f"({approval_level}) by {approved_by}. "
        f"No further action required from your side."
    )

    for uid in _get_dept_recipients(department_id, db):
        _add_notification(db, uid, "BUDGET_PLAN_APPROVED", msg,
                          actor_username=approved_by,
                          plan_id=plan_id, link_step=5)
    db.commit()


def notify_budget_plan_rejected(
    department_id: int,
    fiscal_year: int,
    rejected_by: str,
    reason: str | None,
    db: Session,
    plan_id: int = None,
) -> None:
    """
    CFO rejected dept budget plan → notify dept head and manager with reason.
    """
    from app.models.department import Department

    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        return

    reason_str = f" Reason: {reason}" if reason else ""
    msg = (
        f"Your department's budget plan for FY {fiscal_year} was returned for revision "
        f"by {rejected_by}.{reason_str} "
        f"Please review the feedback, adjust your driver values, and resubmit."
    )

    for uid in _get_dept_recipients(department_id, db):
        _add_notification(db, uid, "BUDGET_PLAN_REJECTED", msg,
                          actor_username=rejected_by,
                          plan_id=plan_id, link_step=4)
    db.commit()


def notify_ceo_ready(fiscal_year: int, approved_by: str, db: Session) -> None:
    """
    All plans are CFO-approved → notify CEO (L4 or L3 approvers) for final sign-off.
    Step 7: CEO Approval.
    """
    perm = LEVEL_PERMISSION.get(4) or LEVEL_PERMISSION.get(3)
    if not perm:
        return
    ceo_users = _get_users_with_permission(perm, db)
    msg = (
        f"All department budget plans for FY {fiscal_year} have been CFO-approved by "
        f"{approved_by}. Please review the consolidated budget and provide your sign-off."
    )
    for u in ceo_users:
        _add_notification(db, u.id, "CEO_REVIEW_READY", msg,
                          actor_username=approved_by, link_step=7)
    db.commit()


def notify_cfo_ceo_approved(fiscal_year: int, approved_by: str, db: Session) -> None:
    """
    CEO approved consolidated budget → notify CFO to proceed with DWH export.
    """
    managers = _get_users_with_permission(LEVEL_PERMISSION[1], db)
    msg = (
        f"CEO ({approved_by}) has approved the consolidated budget for FY {fiscal_year}. "
        f"You may now proceed with the DWH export to write Budget_{fiscal_year} to the warehouse."
    )
    for m in managers:
        _add_notification(db, m.id, "CEO_APPROVED", msg,
                          actor_username=approved_by, link_step=7)
    db.commit()


def notify_cfo_ceo_rejected(fiscal_year: int, rejected_by: str, reason: str, db: Session) -> None:
    """
    CEO rejected the consolidated plan → notify CFO to revise.
    """
    managers = _get_users_with_permission(LEVEL_PERMISSION[1], db)
    reason_str = f" Reason: {reason}" if reason else ""
    msg = (
        f"CEO ({rejected_by}) has rejected the consolidated budget plan for "
        f"FY {fiscal_year}.{reason_str} Please coordinate with departments and revise."
    )
    for m in managers:
        _add_notification(db, m.id, "CEO_REJECTED", msg,
                          actor_username=rejected_by, link_step=6)
    db.commit()


def notify_budget_exported(fiscal_year: int, exported_by: str, db: Session) -> None:
    """
    Budget exported to DWH → notify all stakeholders.
    """
    from app.models.department import Department

    msg = (
        f"Budget_{fiscal_year} has been exported to the Data Warehouse by {exported_by}. "
        f"The budget is now available for reporting and analysis."
    )
    # Notify CFO/CEO level users
    managers = _get_users_with_permission(LEVEL_PERMISSION[1], db)
    ceo_perm = LEVEL_PERMISSION.get(4) or LEVEL_PERMISSION.get(3)
    if ceo_perm:
        managers += _get_users_with_permission(ceo_perm, db)

    notified: set = set()
    for m in managers:
        if m.id not in notified:
            _add_notification(db, m.id, "BUDGET_EXPORTED", msg, actor_username=exported_by, link_step=7)
            notified.add(m.id)

    # Also notify all department heads
    depts = db.query(Department).filter(Department.is_active == True).all()
    for dept in depts:
        for uid in _get_dept_recipients(dept.id, db):
            if uid not in notified:
                _add_notification(db, uid, "BUDGET_EXPORTED", msg, actor_username=exported_by, link_step=7)
                notified.add(uid)

    db.commit()


# ---------------------------------------------------------------------------
# Legacy helpers (kept for backward compatibility with old budget module)
# ---------------------------------------------------------------------------

def notify_managers_pending(budget, actor: User, db: Session) -> None:
    """Legacy: Notify L1 approvers that a budget is pending approval."""
    perm = LEVEL_PERMISSION.get(1)
    if not perm:
        return
    managers = _get_users_with_permission(perm, db)
    msg = f"{actor.username} submitted budget {budget.budget_code} for your approval."
    for m in managers:
        _add_notification(db, m.id, "PENDING_APPROVAL", msg,
                          actor_username=actor.username)
    db.commit()


def notify_worker_approved(budget, actor: User, worker_user_id: int | None, db: Session) -> None:
    """Legacy: Notify worker that their budget was approved."""
    if not worker_user_id:
        return
    msg = f"Your budget {budget.budget_code} has been approved."
    _add_notification(db, worker_user_id, "APPROVED", msg, actor_username=actor.username)
    db.commit()


def notify_worker_rejected(budget, actor: User, worker_user_id: int | None, db: Session) -> None:
    """Legacy: Notify worker that their budget was rejected."""
    if not worker_user_id:
        return
    msg = f"Your budget {budget.budget_code} was rejected. Please revise and resubmit."
    _add_notification(db, worker_user_id, "REJECTED", msg, actor_username=actor.username)
    db.commit()


def notify_managers_uploaded(budget, uploaded_by_username: str, db: Session) -> None:
    """Legacy: Notify managers when a new budget is uploaded."""
    perm = LEVEL_PERMISSION.get(1)
    if not perm:
        return
    managers = _get_users_with_permission(perm, db)
    msg = f"{uploaded_by_username} uploaded budget {budget.budget_code}. Awaiting approval."
    for m in managers:
        _add_notification(db, m.id, "PENDING_APPROVAL", msg,
                          actor_username=uploaded_by_username)
    db.commit()


def notify_template_assigned(
    recipient_id: int,
    template_name: str,
    fiscal_year: int,
    deadline: str | None,
    assigned_by: str,
    db: Session,
) -> None:
    """Legacy: Notify a single user that a template has been assigned."""
    deadline_str = f" Deadline: {deadline}." if deadline else ""
    msg = (
        f"You have been assigned the '{template_name}' budget template "
        f"for FY {fiscal_year}.{deadline_str} Please complete your budget entries."
    )
    _add_notification(db, recipient_id, "TEMPLATE_ASSIGNED", msg,
                      actor_username=assigned_by)
    db.commit()
