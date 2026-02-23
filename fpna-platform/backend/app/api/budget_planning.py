"""
Budget Planning API

Endpoints for the budget planning workflow:
1. Initialize (Ingest + Calculate Baseline)
2. Assign Departments
3. Department Entry (Templates)
4. Approval Workflow
5. Export to DWH
"""

from typing import List, Optional, Dict, Any
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.department import Department
from app.models.budget_plan import (
    BudgetPlan, BudgetPlanGroup, BudgetPlanDetail, BudgetPlanApproval,
    BudgetPlanStatus, ApprovalLevel
)
from app.models.user import User
from app.services.budget_planning_service import BudgetPlanningService
from app.utils.dependencies import get_current_active_user

router = APIRouter(prefix="/budget-planning", tags=["Budget Planning"])


# ============================================================================
# Pydantic Schemas
# ============================================================================

class InitializeRequest(BaseModel):
    connection_id: int
    source_table: str = "balans_ato"
    source_years: Optional[List[int]] = None
    calculation_method: str = "simple_average"


class AssignDepartmentsRequest(BaseModel):
    assignments: List[Dict[str, Any]]  # [{department_id, budgeting_group_ids}]


class GroupAdjustmentRequest(BaseModel):
    driver_code: Optional[str] = None
    driver_name: Optional[str] = None
    driver_rate: Optional[float] = None
    monthly_adjustments: Optional[Dict[str, float]] = None
    notes: Optional[str] = None


class ApprovalRequest(BaseModel):
    comment: Optional[str] = None


class RejectRequest(BaseModel):
    reason: str


class ExportRequest(BaseModel):
    connection_id: int
    target_table: str = "fpna_budget_final"


class PlanSummaryResponse(BaseModel):
    id: int
    fiscal_year: int
    department_id: int
    department_code: str
    department_name: str
    status: str
    version: int
    total_baseline: float
    total_adjusted: float
    total_variance: float
    total_variance_pct: float
    groups_count: int


class GroupResponse(BaseModel):
    id: int
    budgeting_group_id: int
    budgeting_group_name: str
    bs_flag: int
    bs_class_name: str
    baseline_total: float
    adjusted_total: float
    variance: float
    variance_pct: float
    driver_code: Optional[str]
    driver_rate: Optional[float]
    is_locked: bool
    monthly_baseline: Dict[str, float]
    monthly_adjusted: Dict[str, float]


# ============================================================================
# Step 1: Initialize Budget Cycle
# ============================================================================

@router.post("/initialize/{fiscal_year}")
def initialize_budget_cycle(
    fiscal_year: int,
    data: InitializeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Initialize budget cycle for a fiscal year.
    
    1. Ingest data from DWH
    2. Calculate baseline by budgeting groups
    3. Create budget plans for all departments
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        service = BudgetPlanningService(db)
        
        # Step 1: Ingest from DWH
        logger.info(f"Starting DWH ingestion for FY {fiscal_year}, connection {data.connection_id}")
        ingest_result = service.ingest_from_dwh(
            connection_id=data.connection_id,
            source_table=data.source_table,
            fiscal_years=data.source_years,
        )
        logger.info(f"Ingestion result: {ingest_result}")
        
        if ingest_result.get('status') == 'warning':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ingest_result.get('message')
            )
        
        # Step 2: Calculate baseline
        logger.info(f"Calculating baseline for FY {fiscal_year}")
        baseline_result = service.calculate_baseline_by_groups(
            target_fiscal_year=fiscal_year,
            source_years=data.source_years,
            method=data.calculation_method,
        )
        logger.info(f"Baseline result: {baseline_result.get('group_count')} groups calculated")
        
        if baseline_result.get('status') == 'warning':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=baseline_result.get('message')
            )
        
        # Step 3: Create department plans
        logger.info(f"Creating department plans for FY {fiscal_year}")
        plans_result = service.create_department_plans(
            fiscal_year=fiscal_year,
            baseline_data=baseline_result,
            user_id=current_user.id,
        )
        logger.info(f"Plans result: {plans_result}")
        
        return {
            "status": "success",
            "fiscal_year": fiscal_year,
            "ingest": {
                "rows_inserted": ingest_result.get('rows_inserted'),
                "batch_id": ingest_result.get('batch_id'),
            },
            "baseline": {
                "groups_calculated": baseline_result.get('group_count'),
                "method": data.calculation_method,
            },
            "plans": plans_result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Initialize budget cycle failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Initialize failed: {str(e)}"
        )


@router.post("/calculate-baseline/{fiscal_year}")
def calculate_baseline_only(
    fiscal_year: int,
    source_years: Optional[List[int]] = Query(None),
    method: str = "simple_average",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Calculate baseline without creating plans (for preview)"""
    service = BudgetPlanningService(db)
    
    result = service.calculate_baseline_by_groups(
        target_fiscal_year=fiscal_year,
        source_years=source_years,
        method=method,
    )
    
    return result


# ============================================================================
# Step 2: Department Assignment
# ============================================================================

@router.post("/assign-departments")
def assign_departments_to_groups(
    data: AssignDepartmentsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Bulk assign budgeting groups to departments"""
    from app.models.coa_dimension import BudgetingGroup
    
    results = []
    for assignment in data.assignments:
        dept_id = assignment.get('department_id')
        group_ids = assignment.get('budgeting_group_ids', [])
        
        dept = db.query(Department).filter(Department.id == dept_id).first()
        if not dept:
            results.append({
                'department_id': dept_id,
                'status': 'error',
                'message': 'Department not found'
            })
            continue
        
        groups = db.query(BudgetingGroup).filter(
            BudgetingGroup.group_id.in_(group_ids)
        ).all()
        
        dept.budgeting_groups = groups
        results.append({
            'department_id': dept_id,
            'status': 'success',
            'assigned_groups': len(groups)
        })
    
    db.commit()
    return {"status": "success", "results": results}


# ============================================================================
# Step 3: Department Budget Templates
# ============================================================================

@router.get("/department/{dept_id}/template")
def get_department_template(
    dept_id: int,
    fiscal_year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get department's budget template with 4-level hierarchy:
    Level 1: BS Class (Assets, Liabilities, Capital)
    Level 2: BS Group (3-digit code)
    Level 3: Budgeting Group (FP&A grouping) - editable level
    Level 4: COA Account (drill-down only)
    """
    plan = db.query(BudgetPlan).filter(
        BudgetPlan.department_id == dept_id,
        BudgetPlan.fiscal_year == fiscal_year,
        BudgetPlan.is_current == True
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Budget plan not found for this department and year")
    
    dept = plan.department
    months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
    
    # Build 4-level hierarchical structure
    # {bs_flag: {bs_group: [groups]}}
    hierarchy_data = {}
    
    for group in plan.groups:
        bs_flag = group.bs_flag or 0
        bs_group = group.bs_group or '000'
        
        if bs_flag not in hierarchy_data:
            hierarchy_data[bs_flag] = {
                'bs_class_name': group.bs_class_name or f"Class {bs_flag}",
                'bs_groups': {}
            }
        
        if bs_group not in hierarchy_data[bs_flag]['bs_groups']:
            hierarchy_data[bs_flag]['bs_groups'][bs_group] = {
                'bs_group_name': group.bs_group_name or f"Group {bs_group}",
                'groups': [],
                'total_baseline': 0,
                'total_adjusted': 0,
            }
        
        monthly_baseline = {m: float(getattr(group, f'baseline_{m}', 0) or 0) for m in months}
        monthly_adjusted = {m: float(getattr(group, f'adjusted_{m}', 0) or 0) for m in months}
        
        # Determine effective lock status (is_locked OR locked_by_cfo)
        effective_locked = group.is_locked or group.locked_by_cfo
        
        group_data = {
            'id': group.id,
            'budgeting_group_id': group.budgeting_group_id,
            'budgeting_group_name': group.budgeting_group_name,
            'baseline_total': float(group.baseline_total or 0),
            'adjusted_total': float(group.adjusted_total or 0),
            'variance': float(group.variance or 0),
            'variance_pct': float(group.variance_pct or 0),
            'driver_code': group.driver_code,
            'driver_name': group.driver_name,
            'driver_rate': float(group.driver_rate) if group.driver_rate else None,
            'is_locked': effective_locked,
            'locked_by_cfo': group.locked_by_cfo or False,
            'cfo_lock_reason': group.cfo_lock_reason,
            'monthly_baseline': monthly_baseline,
            'monthly_adjusted': monthly_adjusted,
            'adjustment_notes': group.adjustment_notes,
        }
        
        hierarchy_data[bs_flag]['bs_groups'][bs_group]['groups'].append(group_data)
        hierarchy_data[bs_flag]['bs_groups'][bs_group]['total_baseline'] += float(group.baseline_total or 0)
        hierarchy_data[bs_flag]['bs_groups'][bs_group]['total_adjusted'] += float(group.adjusted_total or 0)
    
    # Convert to list structure
    bs_classes = []
    for bs_flag in sorted(hierarchy_data.keys()):
        bs_data = hierarchy_data[bs_flag]
        bs_groups_list = []
        bs_class_baseline = 0
        bs_class_adjusted = 0
        
        for bs_group in sorted(bs_data['bs_groups'].keys()):
            bs_group_data = bs_data['bs_groups'][bs_group]
            bs_groups_list.append({
                'bs_group': bs_group,
                'bs_group_name': bs_group_data['bs_group_name'],
                'groups': sorted(bs_group_data['groups'], key=lambda x: x['budgeting_group_name'] or ''),
                'total_baseline': bs_group_data['total_baseline'],
                'total_adjusted': bs_group_data['total_adjusted'],
            })
            bs_class_baseline += bs_group_data['total_baseline']
            bs_class_adjusted += bs_group_data['total_adjusted']
        
        bs_classes.append({
            'bs_flag': bs_flag,
            'bs_class_name': bs_data['bs_class_name'],
            'bs_groups': bs_groups_list,
            'total_baseline': bs_class_baseline,
            'total_adjusted': bs_class_adjusted,
        })
    
    return {
        'plan_id': plan.id,
        'fiscal_year': plan.fiscal_year,
        'department': {
            'id': dept.id,
            'code': dept.code,
            'name': dept.name_en,
            'is_baseline_only': dept.is_baseline_only,
        },
        'status': plan.status.value,
        'version': plan.version,
        'total_baseline': float(plan.total_baseline or 0),
        'total_adjusted': float(plan.total_adjusted or 0),
        'total_variance': float(plan.total_variance or 0),
        'total_variance_pct': float(plan.total_variance_pct or 0),
        'hierarchy': bs_classes,  # New 4-level structure
    }


@router.get("/department/{dept_id}/group/{group_id}/details")
def get_group_details(
    dept_id: int,
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get drill-down details for a budget plan group (individual accounts)"""
    group = db.query(BudgetPlanGroup).filter(BudgetPlanGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Verify department ownership
    if group.plan.department_id != dept_id:
        raise HTTPException(status_code=403, detail="Group does not belong to this department")
    
    months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
    
    details = []
    for detail in group.details:
        monthly = {m: float(getattr(detail, f'baseline_{m}', 0) or 0) for m in months}
        details.append({
            'id': detail.id,
            'coa_code': detail.coa_code,
            'coa_name': detail.coa_name,
            'bs_group': detail.bs_group,
            'bs_group_name': detail.bs_group_name,
            'baseline_total': float(detail.baseline_total or 0),
            'monthly_baseline': monthly,
        })
    
    return {
        'group_id': group.id,
        'budgeting_group_id': group.budgeting_group_id,
        'budgeting_group_name': group.budgeting_group_name,
        'details': details,
    }


@router.patch("/department/{dept_id}/group/{group_id}")
def update_group_adjustment(
    dept_id: int,
    group_id: int,
    data: GroupAdjustmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update adjustments for a budget plan group"""
    group = db.query(BudgetPlanGroup).filter(BudgetPlanGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    plan = group.plan
    if plan.department_id != dept_id:
        raise HTTPException(status_code=403, detail="Group does not belong to this department")
    
    service = BudgetPlanningService(db)
    
    try:
        updated_group = service.update_group_adjustment(
            plan_id=plan.id,
            group_id=group_id,
            driver_code=data.driver_code,
            driver_name=data.driver_name,
            driver_rate=Decimal(str(data.driver_rate)) if data.driver_rate is not None else None,
            monthly_adjustments={k: Decimal(str(v)) for k, v in data.monthly_adjustments.items()} if data.monthly_adjustments else None,
            notes=data.notes,
            user_id=current_user.id,
        )
        
        months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
        
        return {
            'id': updated_group.id,
            'budgeting_group_id': updated_group.budgeting_group_id,
            'baseline_total': float(updated_group.baseline_total or 0),
            'adjusted_total': float(updated_group.adjusted_total or 0),
            'variance': float(updated_group.variance or 0),
            'variance_pct': float(updated_group.variance_pct or 0),
            'driver_code': updated_group.driver_code,
            'driver_rate': float(updated_group.driver_rate) if updated_group.driver_rate else None,
            'monthly_adjusted': {m: float(getattr(updated_group, f'adjusted_{m}', 0) or 0) for m in months},
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Step 4: Approval Workflow
# ============================================================================

@router.post("/department/{dept_id}/submit")
def submit_plan(
    dept_id: int,
    fiscal_year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Submit department's budget plan for approval"""
    from app.services.notification_service import notify_budget_plan_submitted
    from app.models.department import Department
    
    plan = db.query(BudgetPlan).filter(
        BudgetPlan.department_id == dept_id,
        BudgetPlan.fiscal_year == fiscal_year,
        BudgetPlan.is_current == True
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Budget plan not found")
    
    service = BudgetPlanningService(db)
    
    try:
        updated_plan = service.submit_plan(plan.id, current_user.id)
        
        # Send notification to approvers
        dept = db.query(Department).filter(Department.id == dept_id).first()
        if dept:
            notify_budget_plan_submitted(
                plan_id=updated_plan.id,
                department_name=dept.name_en,
                fiscal_year=fiscal_year,
                submitted_by=current_user.username,
                db=db
            )
        
        return {
            'status': 'success',
            'plan_id': updated_plan.id,
            'new_status': updated_plan.status.value,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/department/{dept_id}/approve")
def approve_plan_dept_head(
    dept_id: int,
    fiscal_year: int,
    data: ApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Department head approves the budget plan"""
    from app.services.notification_service import notify_budget_plan_approved
    
    plan = db.query(BudgetPlan).filter(
        BudgetPlan.department_id == dept_id,
        BudgetPlan.fiscal_year == fiscal_year,
        BudgetPlan.is_current == True
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Budget plan not found")
    
    service = BudgetPlanningService(db)
    
    try:
        updated_plan = service.approve_plan_dept(plan.id, current_user.id, data.comment)
        
        # Send notification to department
        notify_budget_plan_approved(
            department_id=dept_id,
            fiscal_year=fiscal_year,
            approved_by=current_user.username,
            approval_level="Department Head Approval",
            db=db
        )
        
        return {
            'status': 'success',
            'plan_id': updated_plan.id,
            'new_status': updated_plan.status.value,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cfo-approve/{fiscal_year}")
def cfo_approve_all(
    fiscal_year: int,
    data: ApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """CFO approves all department-approved plans for a fiscal year"""
    plans = db.query(BudgetPlan).filter(
        BudgetPlan.fiscal_year == fiscal_year,
        BudgetPlan.status == BudgetPlanStatus.DEPT_APPROVED,
        BudgetPlan.is_current == True
    ).all()
    
    if not plans:
        raise HTTPException(status_code=404, detail="No plans pending CFO approval")
    
    service = BudgetPlanningService(db)
    results = []
    
    for plan in plans:
        try:
            updated_plan = service.approve_plan_cfo(plan.id, current_user.id, data.comment)
            results.append({
                'plan_id': updated_plan.id,
                'department_id': updated_plan.department_id,
                'status': 'approved',
            })
        except ValueError as e:
            results.append({
                'plan_id': plan.id,
                'department_id': plan.department_id,
                'status': 'error',
                'message': str(e),
            })
    
    return {
        'status': 'success',
        'fiscal_year': fiscal_year,
        'plans_approved': len([r for r in results if r['status'] == 'approved']),
        'results': results,
    }


@router.post("/department/{dept_id}/reject")
def reject_plan(
    dept_id: int,
    fiscal_year: int,
    data: RejectRequest,
    level: ApprovalLevel = ApprovalLevel.DEPT_HEAD,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Reject a budget plan"""
    plan = db.query(BudgetPlan).filter(
        BudgetPlan.department_id == dept_id,
        BudgetPlan.fiscal_year == fiscal_year,
        BudgetPlan.is_current == True
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Budget plan not found")
    
    service = BudgetPlanningService(db)
    
    try:
        updated_plan = service.reject_plan(plan.id, current_user.id, data.reason, level)
        return {
            'status': 'success',
            'plan_id': updated_plan.id,
            'new_status': updated_plan.status.value,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Step 5: Export
# ============================================================================

@router.post("/export/{fiscal_year}")
def export_to_dwh(
    fiscal_year: int,
    data: ExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Export approved budget plans to DWH"""
    service = BudgetPlanningService(db)
    
    try:
        result = service.export_to_dwh(
            fiscal_year=fiscal_year,
            connection_id=data.connection_id,
            target_table=data.target_table,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


# ============================================================================
# CFO Locking Controls
# ============================================================================

@router.post("/lock-group/{group_id}")
def cfo_lock_group(
    group_id: int,
    fiscal_year: int,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    CFO locks a budgeting group to prevent adjustments.
    Locked groups will use baseline values only.
    """
    from datetime import datetime
    
    # Find all BudgetPlanGroups with this budgeting_group_id for the fiscal year
    groups = db.query(BudgetPlanGroup).join(BudgetPlan).filter(
        BudgetPlanGroup.budgeting_group_id == group_id,
        BudgetPlan.fiscal_year == fiscal_year,
        BudgetPlan.is_current == True
    ).all()
    
    if not groups:
        raise HTTPException(status_code=404, detail="No budget plan groups found for this budgeting group")
    
    locked_count = 0
    for group in groups:
        group.locked_by_cfo = True
        group.cfo_locked_at = datetime.utcnow()
        group.cfo_locked_by_user_id = current_user.id
        group.cfo_lock_reason = reason
        locked_count += 1
    
    db.commit()
    
    return {
        'status': 'success',
        'budgeting_group_id': group_id,
        'fiscal_year': fiscal_year,
        'locked_count': locked_count,
        'locked_by': current_user.username,
        'reason': reason,
    }


@router.post("/unlock-group/{group_id}")
def cfo_unlock_group(
    group_id: int,
    fiscal_year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    CFO unlocks a budgeting group to allow adjustments.
    """
    groups = db.query(BudgetPlanGroup).join(BudgetPlan).filter(
        BudgetPlanGroup.budgeting_group_id == group_id,
        BudgetPlan.fiscal_year == fiscal_year,
        BudgetPlan.is_current == True
    ).all()
    
    if not groups:
        raise HTTPException(status_code=404, detail="No budget plan groups found for this budgeting group")
    
    unlocked_count = 0
    for group in groups:
        group.locked_by_cfo = False
        group.cfo_locked_at = None
        group.cfo_locked_by_user_id = None
        group.cfo_lock_reason = None
        unlocked_count += 1
    
    db.commit()
    
    return {
        'status': 'success',
        'budgeting_group_id': group_id,
        'fiscal_year': fiscal_year,
        'unlocked_count': unlocked_count,
    }


@router.get("/locked-groups/{fiscal_year}")
def get_locked_groups(
    fiscal_year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get all CFO-locked budgeting groups for a fiscal year.
    """
    from sqlalchemy import distinct
    
    # Get distinct locked groups
    locked_groups = db.query(
        BudgetPlanGroup.budgeting_group_id,
        BudgetPlanGroup.budgeting_group_name,
        BudgetPlanGroup.cfo_lock_reason,
        BudgetPlanGroup.cfo_locked_at,
        BudgetPlanGroup.cfo_locked_by_user_id,
    ).join(BudgetPlan).filter(
        BudgetPlan.fiscal_year == fiscal_year,
        BudgetPlan.is_current == True,
        BudgetPlanGroup.locked_by_cfo == True
    ).distinct(BudgetPlanGroup.budgeting_group_id).all()
    
    # Get user info for locked_by
    user_map = {}
    user_ids = [g.cfo_locked_by_user_id for g in locked_groups if g.cfo_locked_by_user_id]
    if user_ids:
        users = db.query(User).filter(User.id.in_(user_ids)).all()
        user_map = {u.id: u.username for u in users}
    
    return {
        'fiscal_year': fiscal_year,
        'locked_groups': [
            {
                'budgeting_group_id': g.budgeting_group_id,
                'budgeting_group_name': g.budgeting_group_name,
                'lock_reason': g.cfo_lock_reason,
                'locked_at': g.cfo_locked_at.isoformat() if g.cfo_locked_at else None,
                'locked_by': user_map.get(g.cfo_locked_by_user_id),
            }
            for g in locked_groups
        ],
        'total_locked': len(locked_groups),
    }


@router.get("/all-groups/{fiscal_year}")
def get_all_budgeting_groups(
    fiscal_year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get all budgeting groups for a fiscal year with their lock status.
    Used by CFO Locking Panel UI.
    """
    from sqlalchemy import distinct, func
    
    # Get distinct groups with aggregated info
    groups = db.query(
        BudgetPlanGroup.budgeting_group_id,
        BudgetPlanGroup.budgeting_group_name,
        BudgetPlanGroup.bs_flag,
        BudgetPlanGroup.bs_class_name,
        BudgetPlanGroup.bs_group,
        BudgetPlanGroup.bs_group_name,
        func.bool_or(BudgetPlanGroup.locked_by_cfo).label('locked_by_cfo'),
        func.max(BudgetPlanGroup.cfo_lock_reason).label('cfo_lock_reason'),
        func.sum(BudgetPlanGroup.baseline_total).label('total_baseline'),
        func.sum(BudgetPlanGroup.adjusted_total).label('total_adjusted'),
    ).join(BudgetPlan).filter(
        BudgetPlan.fiscal_year == fiscal_year,
        BudgetPlan.is_current == True,
        BudgetPlanGroup.budgeting_group_id.isnot(None)
    ).group_by(
        BudgetPlanGroup.budgeting_group_id,
        BudgetPlanGroup.budgeting_group_name,
        BudgetPlanGroup.bs_flag,
        BudgetPlanGroup.bs_class_name,
        BudgetPlanGroup.bs_group,
        BudgetPlanGroup.bs_group_name,
    ).all()
    
    return {
        'fiscal_year': fiscal_year,
        'groups': [
            {
                'budgeting_group_id': g.budgeting_group_id,
                'budgeting_group_name': g.budgeting_group_name,
                'bs_flag': g.bs_flag,
                'bs_class_name': g.bs_class_name,
                'bs_group': g.bs_group,
                'bs_group_name': g.bs_group_name,
                'locked_by_cfo': g.locked_by_cfo or False,
                'cfo_lock_reason': g.cfo_lock_reason,
                'total_baseline': float(g.total_baseline or 0),
                'total_adjusted': float(g.total_adjusted or 0),
            }
            for g in groups
        ],
        'total_groups': len(groups),
    }


# ============================================================================
# Status & Reporting
# ============================================================================

@router.get("/status/{fiscal_year}")
def get_workflow_status(
    fiscal_year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get overall workflow status for a fiscal year"""
    service = BudgetPlanningService(db)
    return service.get_workflow_status(fiscal_year)


@router.get("/plans/{fiscal_year}")
def list_plans(
    fiscal_year: int,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all budget plans for a fiscal year"""
    query = db.query(BudgetPlan).filter(
        BudgetPlan.fiscal_year == fiscal_year,
        BudgetPlan.is_current == True
    )
    
    if status_filter:
        query = query.filter(BudgetPlan.status == status_filter)
    
    plans = query.all()
    
    return {
        'fiscal_year': fiscal_year,
        'plans': [
            {
                'id': p.id,
                'department_id': p.department_id,
                'department_code': p.department.code,
                'department_name': p.department.name_en,
                'status': p.status.value,
                'total_baseline': float(p.total_baseline or 0),
                'total_adjusted': float(p.total_adjusted or 0),
                'total_variance': float(p.total_variance or 0),
                'submitted_at': p.submitted_at.isoformat() if p.submitted_at else None,
                'dept_approved_at': p.dept_approved_at.isoformat() if p.dept_approved_at else None,
                'cfo_approved_at': p.cfo_approved_at.isoformat() if p.cfo_approved_at else None,
            }
            for p in plans
        ]
    }


@router.get("/plan/{plan_id}")
def get_plan_detail(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get detailed information about a specific budget plan"""
    service = BudgetPlanningService(db)
    summary = service.get_plan_summary(plan_id)
    
    if not summary:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    return summary


@router.get("/plan/{plan_id}/approvals")
def get_plan_approvals(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get approval history for a budget plan"""
    plan = db.query(BudgetPlan).filter(BudgetPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    return {
        'plan_id': plan_id,
        'approvals': [
            {
                'id': a.id,
                'level': a.level.value,
                'action': a.action.value,
                'user_id': a.user_id,
                'comment': a.comment,
                'status_before': a.status_before,
                'status_after': a.status_after,
                'created_at': a.created_at.isoformat() if a.created_at else None,
            }
            for a in plan.approvals
        ]
    }
