"""
Budget Planning API

Endpoints for the budget planning workflow:
1. Initialize (Ingest + Calculate Baseline)
2. Assign Departments
3. Department Entry (Templates)
4. Approval Workflow
5. Export to DWH
"""

from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, text, or_
from pydantic import BaseModel

from app.database import get_db
from app.models.department import Department
from app.models.budget_plan import (
    BudgetPlan, BudgetPlanGroup, BudgetPlanDetail, BudgetPlanApproval,
    BudgetPlanStatus, ApprovalLevel
)
from app.models.baseline import BaselineData, ApprovedBudgetFact
from app.models.coa_dimension import COADimension
from app.models.scenario import AIScenarioProjection
from app.models.user import User
from app.services.budget_planning_service import BudgetPlanningService
from app.services.coa_product_taxonomy import (
    resolve_coa_taxonomy,
    effective_pl_flag_for_planning,
    TAXONOMY_BY_KEY,
    department_list_sort_key,
)
from app.services.pl_driver_proposal_service import compute_pl_yoy_proposals
from app.utils.dependencies import get_current_active_user

router = APIRouter(prefix="/budget-planning", tags=["Budget Planning"])


# ============================================================================
# Permission helpers
# ============================================================================

def _user_dept_ids(user: User, db: Session):
    """
    Returns the set of department IDs this user is allowed to access.
    Returns None when the user has VIEW_ALL (CFO / CEO / Admin) — no restriction.
    """
    from app.utils.permissions import get_user_permissions
    from app.models.department import DepartmentAssignment
    roles = [r.name for r in user.roles]
    perms = get_user_permissions(roles)
    if "view_all" in perms:
        return None  # unrestricted
    assignments = db.query(DepartmentAssignment).filter(
        DepartmentAssignment.user_id == user.id,
        DepartmentAssignment.is_active == True,
    ).all()
    return {a.department_id for a in assignments}


def _require_cfo_admin(user: User) -> None:
    """Raise 403 unless user is CFO / Admin (has view_all or manage_users)."""
    from app.utils.permissions import get_user_permissions
    roles = [r.name for r in user.roles]
    perms = get_user_permissions(roles)
    if not any(p in perms for p in ("view_all", "manage_users")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CFO or Admin access required for this action.",
        )


def _require_dept_access(user: User, dept_id: int, db: Session) -> None:
    """Raise 403 if the user cannot access the given department."""
    allowed = _user_dept_ids(user, db)
    if allowed is None:
        return  # VIEW_ALL — no restriction
    if dept_id not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this department.",
        )


# ============================================================================
# Pydantic Schemas
# ============================================================================

class ColumnMapping(BaseModel):
    coa_col: Optional[str] = None
    date_col: Optional[str] = None
    balance_col: Optional[str] = None
    currency_col: Optional[str] = None
    segment_col: Optional[str] = None
    # DWH balans_ato: signed balance from PRIZNALL + OSTATALL (see balans_signed_balance)
    priznall_col: Optional[str] = None
    balance_orig_col: Optional[str] = None  # e.g. OSTATALLVAL when using signed sums
    signed_priznall: Optional[bool] = None  # default True in service; set False if column missing


class PreviewSourceRequest(BaseModel):
    connection_id: int
    table_name: str
    limit: int = 50


class InitializeRequest(BaseModel):
    connection_id: int
    source_table: str = "balans_ato"
    source_years: Optional[List[int]] = None
    calculation_method: str = "simple_average"
    column_mapping: Optional[ColumnMapping] = None


class DeptGroupAssignment(BaseModel):
    department_id: int
    budgeting_group_ids: List[int] = []
    can_edit: bool = True
    can_submit: bool = True


class AssignDepartmentsRequest(BaseModel):
    assignments: List[Dict[str, Any]]  # Legacy format


class AssignDepartmentsV2Request(BaseModel):
    fiscal_year: int
    assignments: List[DeptGroupAssignment]
    notify: bool = True


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


class DriverConfigItem(BaseModel):
    budgeting_group_id: Optional[int] = None
    fpna_product_key: Optional[str] = None
    driver_id: Optional[int] = None
    rate: Optional[float] = None
    monthly_rates: Optional[Dict[str, float]] = None  # {"1": 5.5, "2": 6.0, ...}


class DriverConfigRequest(BaseModel):
    configs: List[DriverConfigItem]


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

@router.post("/preview-source")
def preview_source_table(
    data: PreviewSourceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Preview a DWH source table and auto-detect column mappings."""
    service = BudgetPlanningService(db)
    try:
        return service.preview_dwh_table(
            connection_id=data.connection_id,
            table_name=data.table_name,
            limit=data.limit,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    _require_cfo_admin(current_user)
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        service = BudgetPlanningService(db)
        
        col_map = data.column_mapping.model_dump() if data.column_mapping else None

        # Step 1: Ingest from DWH
        logger.info(f"Starting DWH ingestion for FY {fiscal_year}, connection {data.connection_id}")
        ingest_result = service.ingest_from_dwh(
            connection_id=data.connection_id,
            source_table=data.source_table,
            fiscal_years=data.source_years,
            column_mapping=col_map,
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
            user_id=current_user.id,
            baseline_data=baseline_result,
            source_years=data.source_years,
            method=data.calculation_method,
        )
        logger.info(f"Plans result: {plans_result}")
        
        # Notify all department heads/managers that budget cycle is starting
        try:
            from app.services.notification_service import notify_budget_cycle_initialized
            notify_budget_cycle_initialized(
                fiscal_year=fiscal_year,
                initialized_by=current_user.username,
                db=db,
            )
        except Exception:
            pass

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
    segment_filter: Optional[str] = Query(
        None,
        description="Match baseline_data.segment_key (e.g. RETAIL). Omit for consolidated totals.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Calculate baseline without creating plans (for preview)"""
    service = BudgetPlanningService(db)

    result = service.calculate_baseline_by_groups(
        target_fiscal_year=fiscal_year,
        source_years=source_years,
        method=method,
        segment_filter=segment_filter,
    )

    return result


@router.post("/compare-baselines/{fiscal_year}")
def compare_baselines(
    fiscal_year: int,
    source_years: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Calculate baselines using all 5 methods and return side-by-side comparison.
    Useful for CFO to pick the best method.
    """
    service = BudgetPlanningService(db)
    methods_list = ['simple_average', 'weighted_average', 'trend', 'ai_forecast', 'ml_trend']
    results = {}

    for m in methods_list:
        try:
            res = service.calculate_baseline_by_groups(
                target_fiscal_year=fiscal_year,
                source_years=source_years,
                method=m,
            )
            total = sum(g.get('total', 0) for g in res.get('groups', []))
            results[m] = {
                'status': res.get('status'),
                'group_count': res.get('group_count', 0),
                'total': round(total, 2),
                'groups': [
                    {
                        'budgeting_group_id': g['budgeting_group_id'],
                        'budgeting_group_name': g['budgeting_group_name'],
                        'total': round(g.get('total', 0), 2),
                    }
                    for g in res.get('groups', [])
                ],
            }
        except Exception as e:
            results[m] = {'status': 'error', 'message': str(e), 'total': 0, 'groups': []}

    return {
        'fiscal_year': fiscal_year,
        'source_years': source_years,
        'methods': results,
    }


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


@router.post("/assign-departments-v2")
def assign_departments_v2(
    data: AssignDepartmentsV2Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    CFO assigns budgeting groups to departments with edit permissions.
    Optionally creates plans and sends notifications.
    """
    _require_cfo_admin(current_user)
    from app.models.coa_dimension import BudgetingGroup
    from app.models.department import department_budgeting_groups
    from datetime import datetime, timezone as tz

    results = []
    for item in data.assignments:
        dept = db.query(Department).filter(Department.id == item.department_id).first()
        if not dept:
            results.append({'department_id': item.department_id, 'status': 'error', 'message': 'Not found'})
            continue

        groups = db.query(BudgetingGroup).filter(
            BudgetingGroup.group_id.in_(item.budgeting_group_ids)
        ).all()

        # Clear existing assignments for this dept
        db.execute(
            department_budgeting_groups.delete().where(
                department_budgeting_groups.c.department_id == dept.id
            )
        )

        # Insert new assignments with permissions
        for g in groups:
            db.execute(
                department_budgeting_groups.insert().values(
                    department_id=dept.id,
                    budgeting_group_id=g.id,
                    can_edit=item.can_edit,
                    can_submit=item.can_submit,
                    assigned_by_user_id=current_user.id,
                    assigned_at=datetime.now(tz.utc),
                )
            )

        results.append({
            'department_id': dept.id,
            'department_name': dept.name_en,
            'status': 'success',
            'groups_assigned': len(groups),
            'can_edit': item.can_edit,
        })

        # Send notification
        if data.notify and dept.head_user_id:
            from app.services.notification_service import notify_department_assigned
            try:
                notify_department_assigned(
                    department_id=dept.id,
                    fiscal_year=data.fiscal_year,
                    group_count=len(groups),
                    assigned_by=current_user.username,
                    can_edit=item.can_edit,
                    db=db,
                )
            except Exception:
                pass  # Don't fail the whole request for notification errors

    db.commit()

    return {"status": "success", "fiscal_year": data.fiscal_year, "results": results}


@router.get("/department-assignments/{fiscal_year}")
def get_department_assignments(
    fiscal_year: int,
    product_owners_only: bool = Query(
        False,
        description="If true, only departments with primary_product_key (FP&A taxonomy owners).",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get current department-group assignments for a fiscal year (includes FP&A product owner fields)."""
    from app.models.coa_dimension import BudgetingGroup
    from app.models.department import department_budgeting_groups, DepartmentProductAccess

    dq = db.query(Department).filter(Department.is_active == True)  # noqa: E712
    if product_owners_only:
        dq = dq.filter(Department.primary_product_key.isnot(None))
    departments_list = dq.all()
    departments_list.sort(
        key=lambda d: department_list_sort_key(
            d.primary_product_key, d.display_order or 0, d.name_en
        )
    )

    all_groups = db.query(BudgetingGroup).order_by(BudgetingGroup.group_id).all()
    groups_list = [{'id': g.id, 'group_id': g.group_id, 'name': g.name_en or g.name_ru} for g in all_groups]

    # Get assignments
    assigns = db.execute(department_budgeting_groups.select()).fetchall()
    assign_map = {}
    for a in assigns:
        dept_id = a.department_id
        if dept_id not in assign_map:
            assign_map[dept_id] = []
        assign_map[dept_id].append({
            'budgeting_group_id': a.budgeting_group_id,
            'can_edit': getattr(a, 'can_edit', True),
            'can_submit': getattr(a, 'can_submit', True),
        })

    # Check which depts have plans for this FY
    plans = db.query(BudgetPlan).filter(
        BudgetPlan.fiscal_year == fiscal_year,
        BudgetPlan.is_current == True,
    ).all()
    plan_map = {p.department_id: p.status.value for p in plans}

    product_rows = db.query(DepartmentProductAccess).all()
    dept_product_keys: Dict[int, List[str]] = {}
    for pr in product_rows:
        dept_product_keys.setdefault(pr.department_id, []).append(pr.product_key)

    dept_list = []
    for dept in departments_list:
        pk = getattr(dept, "primary_product_key", None)
        tax = TAXONOMY_BY_KEY.get(pk) if pk else None
        pks = dept_product_keys.get(dept.id, [])
        dept_list.append({
            'id': dept.id,
            'code': dept.code,
            'name_en': dept.name_en,
            'is_active': dept.is_active,
            'is_baseline_only': dept.is_baseline_only,
            'head_user_id': dept.head_user_id,
            'primary_product_key': pk,
            'product_label_en': tax.label_en if tax else None,
            'product_pillar': tax.pillar if tax else None,
            'product_keys': pks,
            'assigned_groups': assign_map.get(dept.id, []),
            'plan_status': plan_map.get(dept.id),
        })

    return {
        'fiscal_year': fiscal_year,
        'product_owners_only': product_owners_only,
        'departments': dept_list,
        'available_groups': groups_list,
    }


# ============================================================================
# Step 2b: CFO Driver Configuration
# ============================================================================

@router.get("/driver-config/{fiscal_year}")
def get_driver_config(
    fiscal_year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get all budgeting groups with their currently assigned drivers and rates.
    Used by CFO to configure the driver matrix before departments start planning.
    """
    from app.models.driver import Driver, DriverGroupAssignment, DriverValue

    # All active drivers for the dropdown
    drivers = db.query(Driver).filter(Driver.is_active == True).order_by(Driver.display_order, Driver.code).all()
    drivers_list = [
        {
            'id': d.id,
            'code': d.code,
            'name_en': d.name_en,
            'driver_type': d.driver_type.value if d.driver_type else None,
            'default_value': float(d.default_value) if d.default_value else None,
            'min_value': float(d.min_value) if d.min_value else None,
            'max_value': float(d.max_value) if d.max_value else None,
            'unit': d.unit,
            'formula_description': d.formula_description,
        }
        for d in drivers
    ]

    plan_groups = db.query(
        BudgetPlanGroup.fpna_product_key,
        BudgetPlanGroup.fpna_product_label_en,
        BudgetPlanGroup.budgeting_group_id,
        BudgetPlanGroup.budgeting_group_name,
        BudgetPlanGroup.bs_flag,
        BudgetPlanGroup.bs_class_name,
        BudgetPlanGroup.bs_group,
        BudgetPlanGroup.bs_group_name,
        func.sum(BudgetPlanGroup.baseline_total).label('total_baseline'),
        func.sum(BudgetPlanGroup.adjusted_total).label('total_adjusted'),
    ).join(BudgetPlan).filter(
        BudgetPlan.fiscal_year == fiscal_year,
        BudgetPlan.is_current == True,
        or_(
            BudgetPlanGroup.budgeting_group_id.isnot(None),
            BudgetPlanGroup.fpna_product_key.isnot(None),
        ),
    ).group_by(
        BudgetPlanGroup.fpna_product_key,
        BudgetPlanGroup.fpna_product_label_en,
        BudgetPlanGroup.budgeting_group_id,
        BudgetPlanGroup.budgeting_group_name,
        BudgetPlanGroup.bs_flag,
        BudgetPlanGroup.bs_class_name,
        BudgetPlanGroup.bs_group,
        BudgetPlanGroup.bs_group_name,
    ).all()

    assignments = db.query(DriverGroupAssignment).filter(
        DriverGroupAssignment.is_active == True,
    ).all()

    def _assign_key(a):
        if a.fpna_product_key:
            return ('p', a.fpna_product_key)
        if a.budgeting_group_id is not None:
            return ('b', a.budgeting_group_id)
        return None

    assign_map = {}
    for a in assignments:
        k = _assign_key(a)
        if not k:
            continue
        if k not in assign_map or a.is_default:
            assign_map[k] = a

    dv_rows = db.query(DriverValue).filter(
        DriverValue.fiscal_year == fiscal_year,
        DriverValue.month.isnot(None),
        or_(
            DriverValue.budgeting_group_id.isnot(None),
            DriverValue.fpna_product_key.isnot(None),
        ),
    ).all()

    def _dv_key(dv):
        if dv.fpna_product_key:
            return ('p', dv.fpna_product_key)
        if dv.budgeting_group_id is not None:
            return ('b', dv.budgeting_group_id)
        return None

    dv_map: Dict[Tuple[str, Any], Dict[int, float]] = {}
    for dv in dv_rows:
        k = _dv_key(dv)
        if not k:
            continue
        if k not in dv_map:
            dv_map[k] = {}
        dv_map[k][dv.month] = float(dv.value)

    def _plan_key(g):
        if g.fpna_product_key:
            return ('p', g.fpna_product_key)
        return ('b', g.budgeting_group_id)

    groups_result = []
    for g in plan_groups:
        pk = _plan_key(g)
        assignment = assign_map.get(pk)
        driver_info = None
        rate = None
        monthly = dv_map.get(pk)

        if assignment:
            d = assignment.driver
            rate = float(d.default_value) if d.default_value else None
            driver_info = {
                'driver_id': d.id,
                'driver_code': d.code,
                'driver_name': d.name_en,
                'driver_type': d.driver_type.value if d.driver_type else None,
                'default_value': float(d.default_value) if d.default_value else None,
                'unit': d.unit,
            }

        label = g.fpna_product_label_en or g.budgeting_group_name
        groups_result.append({
            'fpna_product_key': g.fpna_product_key,
            'product_key': g.fpna_product_key,
            'product_label_en': label,
            'budgeting_group_id': g.budgeting_group_id,
            'budgeting_group_name': label or g.budgeting_group_name,
            'bs_flag': g.bs_flag,
            'bs_class_name': g.bs_class_name,
            'bs_group': g.bs_group,
            'bs_group_name': g.bs_group_name,
            'total_baseline': float(g.total_baseline or 0),
            'total_adjusted': float(g.total_adjusted or 0),
            'assigned_driver': driver_info,
            'rate': rate,
            'monthly_rates': monthly,
        })

    return {
        'fiscal_year': fiscal_year,
        'drivers': drivers_list,
        'groups': sorted(groups_result, key=lambda x: (x['bs_flag'] or 0, x['budgeting_group_name'] or '')),
    }


@router.post("/driver-config/{fiscal_year}")
def save_driver_config(
    fiscal_year: int,
    data: DriverConfigRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    CFO bulk-saves driver assignments and rates for budgeting groups.
    Creates/updates DriverGroupAssignment and DriverValue records.
    """
    _require_cfo_admin(current_user)
    from app.models.driver import Driver, DriverGroupAssignment, DriverValue

    saved = 0
    for item in data.configs:
        pk = (item.fpna_product_key or "").strip().upper() or None
        bg = item.budgeting_group_id

        if item.driver_id is None:
            dq = db.query(DriverGroupAssignment)
            if pk:
                dq = dq.filter(DriverGroupAssignment.fpna_product_key == pk)
            elif bg is not None:
                dq = dq.filter(DriverGroupAssignment.budgeting_group_id == bg)
            else:
                continue
            dq.update({'is_active': False})
            saved += 1
            continue

        if not pk and bg is None:
            continue

        driver = db.query(Driver).filter(Driver.id == item.driver_id).first()
        if not driver:
            continue

        oq = db.query(DriverGroupAssignment)
        if pk:
            oq = oq.filter(DriverGroupAssignment.fpna_product_key == pk)
        else:
            oq = oq.filter(DriverGroupAssignment.budgeting_group_id == bg)
        oq.update({'is_default': False, 'is_active': False})

        existing = db.query(DriverGroupAssignment).filter(
            DriverGroupAssignment.driver_id == item.driver_id,
        )
        if pk:
            existing = existing.filter(DriverGroupAssignment.fpna_product_key == pk)
        else:
            existing = existing.filter(DriverGroupAssignment.budgeting_group_id == bg)
        existing = existing.first()

        if existing:
            existing.is_active = True
            existing.is_default = True
            if pk:
                existing.fpna_product_key = pk
                existing.budgeting_group_id = None
            else:
                existing.budgeting_group_id = bg
                existing.fpna_product_key = None
        else:
            new_assign = DriverGroupAssignment(
                driver_id=item.driver_id,
                fpna_product_key=pk,
                budgeting_group_id=None if pk else bg,
                is_default=True,
                is_active=True,
                created_by_user_id=current_user.id,
            )
            db.add(new_assign)

        if item.rate is not None:
            driver.default_value = Decimal(str(item.rate))

        if item.monthly_rates:
            vq = db.query(DriverValue).filter(
                DriverValue.driver_id == driver.id,
                DriverValue.fiscal_year == fiscal_year,
                DriverValue.month.isnot(None),
            )
            if pk:
                vq = vq.filter(DriverValue.fpna_product_key == pk)
            else:
                vq = vq.filter(DriverValue.budgeting_group_id == bg)
            vq.delete(synchronize_session=False)

            for month_str, value in item.monthly_rates.items():
                dv = DriverValue(
                    driver_id=driver.id,
                    fiscal_year=fiscal_year,
                    month=int(month_str),
                    fpna_product_key=pk,
                    budgeting_group_id=None if pk else bg,
                    value=Decimal(str(value)),
                    value_type='planned',
                )
                db.add(dv)

        saved += 1

    db.commit()

    return {
        'status': 'success',
        'saved': saved,
    }


@router.post("/apply-drivers-bulk/{fiscal_year}")
def apply_drivers_bulk(
    fiscal_year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    CFO applies all configured drivers to all editable budget plan groups.
    Uses type-specific formulas from the driver engine.
    """
    _require_cfo_admin(current_user)
    service = BudgetPlanningService(db)

    try:
        result = service.bulk_apply_drivers(fiscal_year, current_user.id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk apply failed: {str(e)}")


@router.post("/apply-pl-historic-yoy/{fiscal_year}")
def apply_pl_historic_yoy(
    fiscal_year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    CFO: rewrite P&L **adjusted** amounts on the Baseline Reference plan using **per-product**
    historic YoY from BaselineData (not a single % for every line). Use when variance % is
    identical across categories because the same driver was applied everywhere.
    """
    _require_cfo_admin(current_user)
    service = BudgetPlanningService(db)
    try:
        return service.apply_historic_yoy_to_baseline_pl_plan(fiscal_year, current_user.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Apply historic YoY failed: {str(e)}")


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
    _require_dept_access(current_user, dept_id, db)
    plan = db.query(BudgetPlan).options(
        joinedload(BudgetPlan.groups).joinedload(BudgetPlanGroup.last_edited_by_user)
    ).filter(
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
        
        # Build formula description for the frontend tooltip
        formula_desc = None
        if group.driver_type == 'yield_rate':
            formula_desc = f"Balance + Balance x {float(group.driver_rate or 0)}% / 12 per month"
        elif group.driver_type == 'cost_rate':
            formula_desc = f"Balance + Balance x {float(group.driver_rate or 0)}% / 12 per month"
        elif group.driver_type == 'growth_rate':
            formula_desc = f"Balance x (1 + {float(group.driver_rate or 0)}%)^(month/12)"
        elif group.driver_type == 'provision_rate':
            formula_desc = f"Balance x (1 + {float(group.driver_rate or 0)}%)"
        elif group.driver_rate:
            formula_desc = f"Balance x (1 + {float(group.driver_rate or 0)}%)"

        group_data = {
            'id': group.id,
            'fpna_product_key': group.fpna_product_key,
            'fpna_product_label_en': group.fpna_product_label_en,
            'product_key': group.fpna_product_key,
            'product_label_en': group.fpna_product_label_en or group.budgeting_group_name,
            'budgeting_group_id': group.budgeting_group_id,
            'budgeting_group_name': group.budgeting_group_name or group.fpna_product_label_en,
            'baseline_total': float(group.baseline_total or 0),
            'adjusted_total': float(group.adjusted_total or 0),
            'variance': float(group.variance or 0),
            'variance_pct': float(group.variance_pct or 0),
            'driver_code': group.driver_code,
            'driver_name': group.driver_name,
            'driver_type': group.driver_type,
            'driver_rate': float(group.driver_rate) if group.driver_rate else None,
            'formula_description': formula_desc,
            'is_locked': effective_locked,
            'locked_by_cfo': group.locked_by_cfo or False,
            'cfo_lock_reason': group.cfo_lock_reason,
            'monthly_baseline': monthly_baseline,
            'monthly_adjusted': monthly_adjusted,
            'adjustment_notes': group.adjustment_notes,
            'last_edited_at': group.last_edited_at.isoformat() if group.last_edited_at else None,
            'last_edited_by': getattr(group.last_edited_by_user, 'username', None) if group.last_edited_by_user else None,
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
                'groups': sorted(
                    bs_group_data['groups'],
                    key=lambda x: (x.get('product_label_en') or x.get('budgeting_group_name') or ''),
                ),
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
    _require_dept_access(current_user, dept_id, db)
    group = db.query(BudgetPlanGroup).filter(BudgetPlanGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

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
        'fpna_product_key': group.fpna_product_key,
        'product_key': group.fpna_product_key,
        'budgeting_group_id': group.budgeting_group_id,
        'budgeting_group_name': group.budgeting_group_name or group.fpna_product_label_en,
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
    _require_dept_access(current_user, dept_id, db)
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
            'fpna_product_key': updated_group.fpna_product_key,
            'product_key': updated_group.fpna_product_key,
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
    _require_dept_access(current_user, dept_id, db)
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
    _require_cfo_admin(current_user)
    plans = db.query(BudgetPlan).filter(
        BudgetPlan.fiscal_year == fiscal_year,
        BudgetPlan.status == BudgetPlanStatus.DEPT_APPROVED,
        BudgetPlan.is_current == True
    ).all()
    
    if not plans:
        raise HTTPException(status_code=404, detail="No plans pending CFO approval")
    
    service = BudgetPlanningService(db)
    results = []
    
    from app.services.notification_service import notify_budget_plan_approved, notify_ceo_ready

    for plan in plans:
        try:
            updated_plan = service.approve_plan_cfo(plan.id, current_user.id, data.comment)
            results.append({
                'plan_id': updated_plan.id,
                'department_id': updated_plan.department_id,
                'status': 'approved',
            })
            # Notify department that their plan is CFO-approved
            try:
                notify_budget_plan_approved(
                    department_id=updated_plan.department_id,
                    fiscal_year=fiscal_year,
                    approved_by=current_user.username,
                    approval_level="CFO Approval",
                    db=db,
                    plan_id=updated_plan.id,
                )
            except Exception:
                pass
        except ValueError as e:
            results.append({
                'plan_id': plan.id,
                'department_id': plan.department_id,
                'status': 'error',
                'message': str(e),
            })

    approved_count = len([r for r in results if r['status'] == 'approved'])

    # If all plans now CFO-approved, notify CEO for sign-off
    if approved_count > 0:
        remaining = db.query(BudgetPlan).filter(
            BudgetPlan.fiscal_year == fiscal_year,
            BudgetPlan.is_current == True,
            BudgetPlan.status.notin_([
                BudgetPlanStatus.CFO_APPROVED,
                BudgetPlanStatus.CEO_APPROVED,
                BudgetPlanStatus.EXPORTED,
            ]),
        ).count()
        if remaining == 0:
            try:
                notify_ceo_ready(fiscal_year, current_user.username, db)
            except Exception:
                pass

    return {
        'status': 'success',
        'fiscal_year': fiscal_year,
        'plans_approved': approved_count,
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

        # Notify department head/manager of rejection with reason
        from app.services.notification_service import notify_budget_plan_rejected
        try:
            notify_budget_plan_rejected(
                department_id=dept_id,
                fiscal_year=fiscal_year,
                rejected_by=current_user.username,
                reason=data.reason,
                db=db,
                plan_id=updated_plan.id,
            )
        except Exception:
            pass

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
    _require_cfo_admin(current_user)
    service = BudgetPlanningService(db)
    
    try:
        result = service.export_to_dwh(
            fiscal_year=fiscal_year,
            connection_id=data.connection_id,
            target_table=data.target_table,
        )

        # Notify all stakeholders that export is complete
        try:
            from app.services.notification_service import notify_budget_exported
            notify_budget_exported(fiscal_year, current_user.username, db)
        except Exception:
            pass

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
    _require_cfo_admin(current_user)
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
    _require_cfo_admin(current_user)
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


# ============================================================================
# CEO Consolidated Approval
# ============================================================================

@router.get("/consolidated/{fiscal_year}")
def get_consolidated_plan(
    fiscal_year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get consolidated plan view for CEO sign-off."""
    service = BudgetPlanningService(db)
    return service.get_consolidated_plan(fiscal_year)


@router.post("/ceo-approve/{fiscal_year}")
def ceo_approve(
    fiscal_year: int,
    data: ApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """CEO approves the entire fiscal year plan."""
    service = BudgetPlanningService(db)
    try:
        result = service.ceo_approve_consolidated(fiscal_year, current_user.id, data.comment)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ceo-reject/{fiscal_year}")
def ceo_reject(
    fiscal_year: int,
    data: RejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """CEO rejects the entire fiscal year plan."""
    service = BudgetPlanningService(db)
    try:
        result = service.ceo_reject_consolidated(fiscal_year, current_user.id, data.reason)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# What-If Scenarios
# ============================================================================

@router.get("/scenarios/{fiscal_year}")
def list_scenarios(
    fiscal_year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all scenarios for a fiscal year."""
    from app.models.scenario import BudgetScenario
    scenarios = db.query(BudgetScenario).filter(
        BudgetScenario.plan_fiscal_year == fiscal_year,
    ).order_by(BudgetScenario.created_at.desc()).all()

    return {
        'fiscal_year': fiscal_year,
        'scenarios': [
            {
                'id': s.id,
                'name': s.name,
                'description': s.description,
                'scenario_type': s.scenario_type,
                'status': s.status,
                'created_at': s.created_at.isoformat() if s.created_at else None,
                'approved_at': s.approved_at.isoformat() if s.approved_at else None,
            }
            for s in scenarios
        ],
    }


class ScenarioCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    scenario_type: str = "what_if"


@router.post("/scenarios/{fiscal_year}")
def create_scenario(
    fiscal_year: int,
    data: ScenarioCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a new what-if scenario by cloning the current approved budget."""
    from app.models.scenario import BudgetScenario, ScenarioAdjustment

    scenario = BudgetScenario(
        plan_fiscal_year=fiscal_year,
        name=data.name,
        description=data.description,
        scenario_type=data.scenario_type,
        status='draft',
        created_by_user_id=current_user.id,
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)

    return {
        'status': 'success',
        'id': scenario.id,
        'name': scenario.name,
    }


class ScenarioAdjustmentItem(BaseModel):
    budgeting_group_id: int
    department_id: Optional[int] = None
    month: Optional[int] = None
    adjustment_type: str = "percentage"  # override, delta, percentage
    value: float
    driver_code: Optional[str] = None
    notes: Optional[str] = None


class ScenarioAdjustmentRequest(BaseModel):
    adjustments: List[ScenarioAdjustmentItem]


@router.put("/scenarios/{scenario_id}/adjustments")
def update_scenario_adjustments(
    scenario_id: int,
    data: ScenarioAdjustmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Add/replace adjustments for a scenario."""
    from app.models.scenario import BudgetScenario, ScenarioAdjustment

    scenario = db.query(BudgetScenario).filter(BudgetScenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    if scenario.status not in ('draft', 'pending'):
        raise HTTPException(status_code=400, detail="Cannot edit non-draft scenario")

    # Clear existing adjustments
    db.query(ScenarioAdjustment).filter(ScenarioAdjustment.scenario_id == scenario_id).delete()

    for item in data.adjustments:
        adj = ScenarioAdjustment(
            scenario_id=scenario_id,
            budgeting_group_id=item.budgeting_group_id,
            department_id=item.department_id,
            month=item.month,
            adjustment_type=item.adjustment_type,
            value=item.value,
            driver_code=item.driver_code,
            notes=item.notes,
        )
        db.add(adj)

    db.commit()

    return {'status': 'success', 'adjustments_saved': len(data.adjustments)}


@router.post("/scenarios/{scenario_id}/approve")
def approve_scenario(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Approve a scenario and push updated figures to DWH.
    Updates year_budget_approved table with scenario adjustments.
    """
    from app.models.scenario import BudgetScenario
    from datetime import datetime, timezone as tz

    scenario = db.query(BudgetScenario).filter(BudgetScenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    scenario.status = 'approved'
    scenario.approved_by_user_id = current_user.id
    scenario.approved_at = datetime.now(tz.utc)
    db.commit()

    return {
        'status': 'success',
        'scenario_id': scenario.id,
        'message': 'Scenario approved. DWH table will be updated on next export.',
    }


@router.get("/scenarios/{scenario_id}/compare")
def compare_scenario(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Compare scenario adjustments against the original approved budget."""
    from app.models.scenario import BudgetScenario, ScenarioAdjustment

    scenario = db.query(BudgetScenario).filter(BudgetScenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    adjustments = db.query(ScenarioAdjustment).filter(
        ScenarioAdjustment.scenario_id == scenario_id,
    ).all()

    # Get the original approved plan groups
    plans = db.query(BudgetPlan).filter(
        BudgetPlan.fiscal_year == scenario.plan_fiscal_year,
        BudgetPlan.is_current == True,
        BudgetPlan.status.in_([
            BudgetPlanStatus.CEO_APPROVED,
            BudgetPlanStatus.CFO_APPROVED,
            BudgetPlanStatus.EXPORTED,
        ]),
    ).all()

    original_by_group: Dict[int, float] = {}
    for plan in plans:
        for g in plan.groups:
            gid = g.budgeting_group_id
            original_by_group[gid] = original_by_group.get(gid, 0) + float(g.adjusted_total or 0)

    comparison = []
    for adj in adjustments:
        orig = original_by_group.get(adj.budgeting_group_id, 0)
        if adj.adjustment_type == 'override':
            scenario_val = adj.value
        elif adj.adjustment_type == 'delta':
            scenario_val = orig + adj.value
        else:  # percentage
            scenario_val = orig * (1 + adj.value / 100)

        comparison.append({
            'budgeting_group_id': adj.budgeting_group_id,
            'original': round(orig, 2),
            'scenario': round(scenario_val, 2),
            'difference': round(scenario_val - orig, 2),
            'pct_change': round((scenario_val - orig) / abs(orig) * 100, 2) if orig != 0 else 0,
            'adjustment_type': adj.adjustment_type,
            'value': adj.value,
            'notes': adj.notes,
        })

    return {
        'scenario_id': scenario.id,
        'scenario_name': scenario.name,
        'fiscal_year': scenario.plan_fiscal_year,
        'comparison': comparison,
        'total_original': round(sum(c['original'] for c in comparison), 2),
        'total_scenario': round(sum(c['scenario'] for c in comparison), 2),
    }


# =========================================================================
# FACT TABLE (Account-Level Approved Budget)
# =========================================================================

@router.get("/fact-table/{fiscal_year}")
def get_fact_table(
    fiscal_year: int,
    department_code: Optional[str] = None,
    budgeting_group_id: Optional[int] = None,
    month: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=10, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Query the account-level approved budget fact table.

    Same grain as DWH source – one row per (coa_code, month) – enriched
    with driver_code, driver_rate, version for fact-vs-plan analysis.
    """
    from app.models.baseline import ApprovedBudgetFact

    q = db.query(ApprovedBudgetFact).filter(
        ApprovedBudgetFact.fiscal_year == fiscal_year,
    )
    if department_code:
        q = q.filter(ApprovedBudgetFact.department_code == department_code)
    if budgeting_group_id:
        q = q.filter(ApprovedBudgetFact.budgeting_group_id == budgeting_group_id)
    if month:
        q = q.filter(ApprovedBudgetFact.fiscal_month == month)

    total = q.count()
    rows = q.order_by(
        ApprovedBudgetFact.coa_code,
        ApprovedBudgetFact.fiscal_month,
    ).offset((page - 1) * page_size).limit(page_size).all()

    return {
        'fiscal_year': fiscal_year,
        'page': page,
        'page_size': page_size,
        'total_rows': total,
        'rows': [
            {
                'coa_code': r.coa_code,
                'coa_name': r.coa_name,
                'fiscal_month': r.fiscal_month,
                'currency': r.currency,
                'baseline_amount': float(r.baseline_amount or 0),
                'adjusted_amount': float(r.adjusted_amount or 0),
                'variance': float(r.variance or 0),
                'bs_flag': r.bs_flag,
                'bs_class_name': r.bs_class_name,
                'bs_group': r.bs_group,
                'bs_group_name': r.bs_group_name,
                'budgeting_group_id': r.budgeting_group_id,
                'budgeting_group_name': r.budgeting_group_name,
                'department_code': r.department_code,
                'department_name': r.department_name,
                'driver_code': r.driver_code,
                'driver_rate': float(r.driver_rate) if r.driver_rate else None,
                'driver_type': r.driver_type,
                'version': r.version,
                'plan_status': r.plan_status,
                'export_batch_id': r.export_batch_id,
            }
            for r in rows
        ],
    }


@router.delete("/reset/{fiscal_year}")
def reset_budget_fiscal_year(
    fiscal_year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Admin/CFO: Delete ALL budget planning data for a fiscal year.
    Removes: plan_details → plan_groups → approvals → plans → baseline_data → notifications.
    """
    _require_cfo_admin(current_user)
    from app.models.budget_plan import BudgetPlanDetail, BudgetPlanApproval
    from app.models.baseline import BaselineData
    from app.models.notification import Notification

    deleted: dict = {}

    plan_ids = [r[0] for r in db.query(BudgetPlan.id).filter(BudgetPlan.fiscal_year == fiscal_year).all()]

    if plan_ids:
        group_ids = [r[0] for r in db.query(BudgetPlanGroup.id).filter(BudgetPlanGroup.plan_id.in_(plan_ids)).all()]
        if group_ids:
            deleted['plan_details'] = db.query(BudgetPlanDetail).filter(
                BudgetPlanDetail.group_id.in_(group_ids)
            ).delete(synchronize_session='fetch')
        deleted['approvals'] = db.query(BudgetPlanApproval).filter(
            BudgetPlanApproval.plan_id.in_(plan_ids)
        ).delete(synchronize_session='fetch')
        deleted['plan_groups'] = db.query(BudgetPlanGroup).filter(
            BudgetPlanGroup.plan_id.in_(plan_ids)
        ).delete(synchronize_session='fetch')
        deleted['notifications'] = db.query(Notification).filter(
            Notification.plan_id.in_(plan_ids)
        ).delete(synchronize_session='fetch')
        deleted['plans'] = db.query(BudgetPlan).filter(
            BudgetPlan.fiscal_year == fiscal_year
        ).delete(synchronize_session='fetch')

    deleted['baseline_data'] = db.query(BaselineData).filter(
        BaselineData.fiscal_year == fiscal_year
    ).delete(synchronize_session='fetch')

    db.commit()

    return {
        'success': True,
        'message': f'FY {fiscal_year} budget data cleared.',
        'deleted': deleted,
    }


@router.get("/fact-table/{fiscal_year}/summary")
def get_fact_table_summary(
    fiscal_year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Summary statistics for the fact table."""
    from app.models.baseline import ApprovedBudgetFact
    from sqlalchemy import func

    q = db.query(ApprovedBudgetFact).filter(
        ApprovedBudgetFact.fiscal_year == fiscal_year,
    )

    total_rows = q.count()
    if total_rows == 0:
        return {
            'fiscal_year': fiscal_year,
            'total_rows': 0,
            'message': 'No fact data exported yet for this fiscal year.',
        }

    agg = db.query(
        func.sum(ApprovedBudgetFact.baseline_amount).label('total_baseline'),
        func.sum(ApprovedBudgetFact.adjusted_amount).label('total_adjusted'),
        func.sum(ApprovedBudgetFact.variance).label('total_variance'),
        func.count(func.distinct(ApprovedBudgetFact.coa_code)).label('unique_accounts'),
        func.count(func.distinct(ApprovedBudgetFact.department_code)).label('unique_departments'),
        func.count(func.distinct(ApprovedBudgetFact.budgeting_group_id)).label('unique_groups'),
        func.max(ApprovedBudgetFact.export_batch_id).label('latest_batch'),
    ).filter(
        ApprovedBudgetFact.fiscal_year == fiscal_year,
    ).first()

    return {
        'fiscal_year': fiscal_year,
        'total_rows': total_rows,
        'total_baseline': float(agg.total_baseline or 0),
        'total_adjusted': float(agg.total_adjusted or 0),
        'total_variance': float(agg.total_variance or 0),
        'unique_accounts': agg.unique_accounts,
        'unique_departments': agg.unique_departments,
        'unique_groups': agg.unique_groups,
        'latest_batch': agg.latest_batch,
    }


# ============================================================================
# P&L Planning — COA-level income statement data
# ============================================================================

# Human-readable P&L category labels
PL_FLAG_LABELS = {
    1: "Interest Income",
    2: "Interest Expense",
    3: "Provisions",
    4: "Non-Interest Income",
    5: "Non-Interest Expense",
    7: "Operating Expenses (OPEX)",
    8: "Income Tax",
}

# Display ordering (matches standard bank income statement)
PL_FLAG_ORDER = {1: 1, 2: 2, 4: 3, 5: 4, 7: 5, 3: 6, 8: 7}


def _kpi_signed_rollup(raw: float) -> float:
    """
    Category totals from signed DWH/plan amounts: expenses often negative (credit convention).
    Use magnitude when the rolled-up total is negative so NII = income - expense stays correct
    and headline growth % are not inflated by subtracting a negative expense total.
    """
    x = float(raw or 0)
    return abs(x) if x < 0 else x


def _kpi_signed_scalar(x: float) -> float:
    x = float(x or 0)
    return abs(x) if x < 0 else x


def _uniform_monthly(total: float, months: List[str], eps: float = 1e-9) -> Dict[str, float]:
    if abs(total) <= eps:
        return {m: 0.0 for m in months}
    v = total / 12.0
    return {m: v for m in months}


def _distribute_total_to_months(
    annual: float,
    months: List[str],
    hist12: Optional[Dict[int, float]],
    eps: float = 1e-9,
) -> Dict[str, float]:
    """
    Scale plan annual amounts to months using **same-month shares** from BaselineData
    for ``reference_year`` (typically plan year − 1). Falls back to uniform only when
    no history exists for that account/flag.
    """
    if abs(annual) <= eps:
        return {m: 0.0 for m in months}
    if not hist12:
        return _uniform_monthly(annual, months, eps)
    vals = [float(hist12.get(mm, 0) or 0) for mm in range(1, 13)]
    hsum = sum(vals)
    if abs(hsum) > eps:
        return {months[i]: annual * (vals[i] / hsum) for i in range(12)}
    asum = sum(abs(v) for v in vals)
    if asum > eps:
        return {months[i]: annual * (abs(vals[i]) / asum) for i in range(12)}
    return _uniform_monthly(annual, months, eps)


def _detail_monthly_from_annual(
    annual: float,
    current: Dict[str, float],
    months: List[str],
    hist12: Optional[Dict[int, float]],
    eps: float = 1e-6,
) -> Dict[str, float]:
    """When stored monthlies are flat/zero but annual is set, apply historic seasonality or uniform."""
    s = sum(float(current.get(m, 0) or 0) for m in months)
    if abs(annual) > eps and abs(s) <= eps:
        return _distribute_total_to_months(annual, months, hist12)
    return dict(current)


def _adjusted_monthly_align(
    monthly_baseline: Dict[str, float],
    baseline_total: float,
    monthly_adjusted: Dict[str, float],
    adjusted_total: float,
    months: List[str],
    hist12: Optional[Dict[int, float]],
    eps: float = 1e-6,
) -> Dict[str, float]:
    """Keep adjusted monthlies consistent with adjusted_total; preserve baseline shape when possible."""
    sa = sum(float(monthly_adjusted.get(m, 0) or 0) for m in months)
    if abs(adjusted_total) <= eps:
        return {m: 0.0 for m in months}
    if abs(sa) > eps:
        return dict(monthly_adjusted)
    sb = sum(float(monthly_baseline.get(m, 0) or 0) for m in months)
    if abs(baseline_total) > eps and abs(sb) > eps:
        return {m: float(monthly_baseline[m]) * (adjusted_total / baseline_total) for m in months}
    return _distribute_total_to_months(adjusted_total, months, hist12)


def _load_historic_monthly_by_accounts(
    db: Session,
    account_codes: set,
    ref_year: int,
    department_id: int,
) -> Dict[str, Dict[int, float]]:
    """BaselineData month 1..12 per account (``balance_uzs``), optional department DWH segment filter."""
    if not account_codes:
        return {}
    dept = db.query(Department).filter(Department.id == department_id).first()
    seg = getattr(dept, 'dwh_segment_value', None) if dept else None
    bsvc = BudgetPlanningService(db)
    merged = bsvc._rollup_baseline_for_segment([ref_year], seg, account_codes)
    out: Dict[str, Dict[int, float]] = {}
    for row in merged:
        ac = row.account_code
        if ac not in out:
            out[ac] = {mm: 0.0 for mm in range(1, 13)}
        out[ac][int(row.fiscal_month)] = float(row.balance_uzs or 0)
    return out


def _historic_monthly_by_pl_flag(
    historic_by_account: Dict[str, Dict[int, float]],
    coa_map_src: Dict[str, COADimension],
) -> Dict[int, Dict[int, float]]:
    """Aggregate account-level historic monthlies to effective p_l_flag buckets."""
    hb: Dict[int, Dict[int, float]] = {}
    for ac, mo in historic_by_account.items():
        coa = coa_map_src.get(ac)
        if not coa:
            continue
        tax = resolve_coa_taxonomy(coa)
        fl = effective_pl_flag_for_planning(coa, tax)
        if fl is None:
            continue
        if fl not in hb:
            hb[fl] = {mm: 0.0 for mm in range(1, 13)}
        for mm in range(1, 13):
            hb[fl][mm] += float(mo.get(mm, 0) or 0)
    return hb


@router.get("/pl-driver-proposals")
def get_pl_driver_proposals(
    fiscal_year: int,
    year_old: Optional[int] = None,
    year_new: Optional[int] = None,
    segment: Optional[str] = Query(None, description="DWH segment_key filter; omit for consolidated"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Default suggested growth rates from actual YoY (BaselineData), e.g. for FY2026 use 2025 vs 2024.
    Returns FP&A product → PL_GROWTH_* deltas and p_l_flag → category adjustment % for P&L / AI.
    """
    return compute_pl_yoy_proposals(
        db,
        fiscal_year_target=fiscal_year,
        year_old=year_old,
        year_new=year_new,
        segment_filter=segment,
    )


@router.get("/department/{dept_id}/pl-data")
def get_department_pl_data(
    dept_id: int,
    fiscal_year: int,
    scenario: Optional[str] = None,
    use_plan_group_ratio: bool = Query(
        False,
        description="If true, adjusted = baseline × (group adjusted / group baseline) for every account in that group. "
        "If false (default), adjusted uses DWH BaselineData YoY % per p_l_flag when available — fixes one shared ratio for all lines.",
    ),
    seasonality_reference_year: Optional[int] = Query(
        None,
        description="Fiscal year of ingested BaselineData used to shape months (default: plan year − 1, e.g. 2025 actuals for a 2026 plan).",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get P&L planning data for the bank-wide baseline reference plan.

    Returns **monthly** amounts rolled up to **budget plan groups** (no COA drill-down):
    ``pl_monthly_groups`` has one row per (plan group × p_l_flag) with jan…dec baseline,
    adjusted, and optional AI scenario. Category-level totals for KPI cards remain in
    ``summary`` / light ``categories`` (without per-account arrays).
    """
    _require_dept_access(current_user, dept_id, db)

    months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
              'jul', 'aug', 'sep', 'oct', 'nov', 'dec']

    # 1) Get the requesting department's plan (for metadata)
    plan = db.query(BudgetPlan).filter(
        BudgetPlan.department_id == dept_id,
        BudgetPlan.fiscal_year == fiscal_year,
        BudgetPlan.is_current == True,
    ).first()

    if not plan:
        raise HTTPException(404, "No budget plan found for this department/year")

    # 2) P&L accounts live in Baseline Reference — find that plan
    #    Try the requesting dept first; if it has no P&L details, fall back
    #    to Baseline Reference (is_baseline_only=True).
    pl_plan = plan
    details = (
        db.query(BudgetPlanDetail)
        .join(BudgetPlanGroup, BudgetPlanDetail.group_id == BudgetPlanGroup.id)
        .filter(BudgetPlanGroup.plan_id == plan.id)
        .all()
    )
    plan_coa_codes = {d.coa_code for d in details}

    # P&L-eligible if dimension has p_l_flag / p_l_group as a known bucket, or FP&A INCOME taxonomy
    def _count_pl_eligible_coas(codes: set) -> int:
        if not codes:
            return 0
        rows = db.query(COADimension).filter(
            COADimension.coa_code.in_(codes),
            COADimension.is_active == True,
        ).all()
        return sum(1 for c in rows if effective_pl_flag_for_planning(c) is not None)

    pl_coa_count = _count_pl_eligible_coas(plan_coa_codes)

    if pl_coa_count == 0:
        # Fall back to Baseline Reference department
        from app.models.department import Department
        baseline_dept = db.query(Department).filter(
            Department.is_baseline_only == True,
            Department.is_active == True,
        ).first()
        if baseline_dept:
            baseline_plan = db.query(BudgetPlan).filter(
                BudgetPlan.department_id == baseline_dept.id,
                BudgetPlan.fiscal_year == fiscal_year,
                BudgetPlan.is_current == True,
            ).first()
            if baseline_plan:
                pl_plan = baseline_plan
                details = (
                    db.query(BudgetPlanDetail)
                    .join(BudgetPlanGroup, BudgetPlanDetail.group_id == BudgetPlanGroup.id)
                    .filter(BudgetPlanGroup.plan_id == baseline_plan.id)
                    .all()
                )
                plan_coa_codes = {d.coa_code for d in details}

    # 3) All active dimension rows for plan COAs (P&L bucket may come from p_l_flag, p_l_group, or taxonomy)
    coa_rows = (
        db.query(COADimension)
        .filter(
            COADimension.coa_code.in_(plan_coa_codes),
            COADimension.is_active == True,
        )
        .all()
        if plan_coa_codes
        else []
    )

    coa_map = {c.coa_code: c for c in coa_rows}

    # Historic YoY from BaselineData (e.g. FY2026 → 2025 vs 2024) — used for P&L adjusted unless legacy group ratio mode
    yoy_prop = compute_pl_yoy_proposals(db, fiscal_year_target=fiscal_year)
    historic_by_flag: Dict[int, float] = {int(k): float(v) for k, v in (yoy_prop.get("historic_by_flag") or {}).items()}

    # 4) Build a map from group_id → BudgetPlanGroup for driver/adjusted info
    group_map: Dict[int, BudgetPlanGroup] = {}
    for g in pl_plan.groups:
        group_map[g.id] = g

    season_ref = seasonality_reference_year if seasonality_reference_year is not None else (fiscal_year - 1)

    def _build_pl_account_rows(
        details_src: List[BudgetPlanDetail],
        coa_map_src: Dict[str, COADimension],
        group_map_src: Dict[int, BudgetPlanGroup],
        historic_by_account: Dict[str, Dict[int, float]],
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for detail in details_src:
            coa = coa_map_src.get(detail.coa_code)
            if not coa:
                continue

            tax = resolve_coa_taxonomy(coa)
            eff_pl_flag = effective_pl_flag_for_planning(coa, tax)
            if eff_pl_flag is None:
                continue

            parent_group = group_map_src.get(detail.group_id)

            monthly_baseline = {m: float(getattr(detail, f'baseline_{m}', 0) or 0) for m in months}
            baseline_total = float(detail.baseline_total or 0)
            hist_ac = historic_by_account.get(detail.coa_code) if historic_by_account else None
            monthly_baseline = _detail_monthly_from_annual(
                baseline_total, monthly_baseline, months, hist_ac,
            )

            monthly_adjusted = dict(monthly_baseline)
            adjusted_total = baseline_total
            driver_info = None

            pl_flag_int = eff_pl_flag
            dwh_yoy = None
            if not use_plan_group_ratio and pl_flag_int is not None and pl_flag_int in historic_by_flag:
                dwh_yoy = historic_by_flag[pl_flag_int]

            if dwh_yoy is not None:
                mult = 1.0 + dwh_yoy / 100.0
                monthly_adjusted = {m: float(monthly_baseline[m]) * mult for m in months}
                adjusted_total = float(baseline_total) * mult
                saved_grp_pct = None
                if parent_group:
                    gb = float(parent_group.baseline_total or 0)
                    ga = float(parent_group.adjusted_total or 0)
                    if gb != 0:
                        saved_grp_pct = round((ga / gb - 1.0) * 100.0, 4)
                driver_info = {
                    'code': parent_group.driver_code if parent_group else None,
                    'name': parent_group.driver_name if parent_group else None,
                    'type': 'dwh_yoy',
                    'rate': round(dwh_yoy, 4),
                    'effective_plan_pct': round(dwh_yoy, 4),
                    'dwh_yoy_pct': round(dwh_yoy, 4),
                    'saved_plan_group_pct': saved_grp_pct,
                    'rate_is_effective': False,
                }
            elif parent_group:
                grp_baseline = float(parent_group.baseline_total or 0)
                grp_adjusted = float(parent_group.adjusted_total or 0)
                ratio = 1.0
                if grp_baseline != 0:
                    ratio = grp_adjusted / grp_baseline
                    monthly_adjusted = {m: v * ratio for m, v in monthly_baseline.items()}
                    adjusted_total = baseline_total * ratio
                effective_plan_pct = (ratio - 1.0) * 100.0 if grp_baseline != 0 else 0.0
                has_driver_meta = bool(
                    parent_group.driver_code
                    or parent_group.driver_name
                    or parent_group.driver_rate is not None
                )
                if has_driver_meta or (grp_baseline != 0 and abs(ratio - 1.0) > 1e-9):
                    dr = parent_group.driver_rate
                    driver_info = {
                        'code': parent_group.driver_code,
                        'name': parent_group.driver_name,
                        'type': parent_group.driver_type or 'plan_adjustment',
                        'rate': float(dr) if dr is not None else round(effective_plan_pct, 4),
                        'effective_plan_pct': round(effective_plan_pct, 4),
                        'rate_is_effective': dr is None,
                    }

            monthly_adjusted = _adjusted_monthly_align(
                monthly_baseline,
                baseline_total,
                monthly_adjusted,
                adjusted_total,
                months,
                hist_ac,
            )

            rows.append({
                'group_id': detail.group_id,
                'budgeting_group_name': (parent_group.budgeting_group_name if parent_group else '') or '',
                'coa_code': detail.coa_code,
                'coa_name': coa.coa_name,
                'bs_group': coa.bs_group,
                'bs_group_name': coa.group_name,
                'p_l_flag': eff_pl_flag,
                'p_l_category': PL_FLAG_LABELS.get(eff_pl_flag, f"Other ({eff_pl_flag})"),
                'p_l_sub_group': coa.p_l_sub_group,
                'p_l_sub_group_name': coa.p_l_sub_group_name,
                'fpna_product_key': tax['product_key'],
                'fpna_product_label_en': tax['product_label_en'],
                'product_pillar': tax['product_pillar'],
                'baseline_total': baseline_total,
                'adjusted_total': adjusted_total,
                'variance': adjusted_total - baseline_total,
                'variance_pct': round((adjusted_total - baseline_total) / abs(baseline_total) * 100, 2)
                                if baseline_total != 0 else 0,
                'monthly_baseline': monthly_baseline,
                'monthly_adjusted': monthly_adjusted,
                'driver': driver_info,
            })
        return rows

    # 5) P&L lines: load DWH month shapes from BaselineData (reference year) then build rows
    historic_by_account = _load_historic_monthly_by_accounts(
        db, plan_coa_codes, season_ref, pl_plan.department_id,
    )
    pl_accounts = _build_pl_account_rows(details, coa_map, group_map, historic_by_account)

    if not pl_accounts:
        baseline_dept = db.query(Department).filter(
            Department.is_baseline_only == True,
            Department.is_active == True,
        ).first()
        if baseline_dept:
            baseline_plan = db.query(BudgetPlan).filter(
                BudgetPlan.department_id == baseline_dept.id,
                BudgetPlan.fiscal_year == fiscal_year,
                BudgetPlan.is_current == True,
            ).first()
            if baseline_plan and baseline_plan.id != pl_plan.id:
                pl_plan = baseline_plan
                details = (
                    db.query(BudgetPlanDetail)
                    .join(BudgetPlanGroup, BudgetPlanDetail.group_id == BudgetPlanGroup.id)
                    .filter(BudgetPlanGroup.plan_id == baseline_plan.id)
                    .all()
                )
                plan_coa_codes = {d.coa_code for d in details}
                coa_rows = (
                    db.query(COADimension)
                    .filter(
                        COADimension.coa_code.in_(plan_coa_codes),
                        COADimension.is_active == True,
                    )
                    .all()
                    if plan_coa_codes
                    else []
                )
                coa_map = {c.coa_code: c for c in coa_rows}
                group_map = {g.id: g for g in pl_plan.groups}
                historic_by_account = _load_historic_monthly_by_accounts(
                    db, plan_coa_codes, season_ref, pl_plan.department_id,
                )
                pl_accounts = _build_pl_account_rows(details, coa_map, group_map, historic_by_account)

    historic_monthly_by_pl_flag = _historic_monthly_by_pl_flag(historic_by_account, coa_map)

    # 6) Optionally fetch AI scenario projections
    ai_projections = {}
    if scenario:
        ai_rows = db.query(AIScenarioProjection).filter(
            AIScenarioProjection.fiscal_year == fiscal_year,
            AIScenarioProjection.scenario_name == scenario,
        ).all()
        for row in ai_rows:
            ai_projections[row.coa_code] = {
                'monthly': {m: float(getattr(row, m, 0) or 0) for m in months},
                'annual_total': float(row.annual_total or 0),
                'confidence': float(row.confidence or 0),
                'assumptions': row.assumptions,
            }

    # 7) Group by P&L category for structured response
    categories: Dict[int, dict] = {}
    for acct in pl_accounts:
        flag = acct['p_l_flag']
        if flag not in categories:
            categories[flag] = {
                'p_l_flag': flag,
                'category': acct['p_l_category'],
                'order': PL_FLAG_ORDER.get(flag, 99),
                'accounts': [],
                'total_baseline': 0,
                'total_adjusted': 0,
            }
        categories[flag]['accounts'].append(acct)
        categories[flag]['total_baseline'] += acct['baseline_total']
        categories[flag]['total_adjusted'] += acct['adjusted_total']

        # Attach AI data if available
        if acct['coa_code'] in ai_projections:
            acct['ai_projection'] = ai_projections[acct['coa_code']]

    # 7b) Monthly roll-up at plan-group level + by p_l_flag only (fallback grid / KPI month lines)
    pl_monthly_groups_map: Dict[Tuple[int, int], Dict[str, Any]] = {}
    pl_by_flag_map: Dict[int, Dict[str, Any]] = {}
    for acct in pl_accounts:
        gid = int(acct['group_id'])
        fl = int(acct['p_l_flag'])
        key = (gid, fl)
        if key not in pl_monthly_groups_map:
            pl_monthly_groups_map[key] = {
                'group_id': gid,
                'budgeting_group_name': acct.get('budgeting_group_name') or '',
                'p_l_flag': fl,
                'p_l_category': acct.get('p_l_category') or PL_FLAG_LABELS.get(fl, str(fl)),
                'fpna_product_key': acct.get('fpna_product_key'),
                'fpna_product_label_en': acct.get('fpna_product_label_en'),
                'monthly_baseline': {m: 0.0 for m in months},
                'monthly_adjusted': {m: 0.0 for m in months},
                'monthly_ai': {m: 0.0 for m in months},
                'driver': acct.get('driver'),
            }
        bucket = pl_monthly_groups_map[key]
        if fl not in pl_by_flag_map:
            pl_by_flag_map[fl] = {
                'group_id': None,
                'budgeting_group_name': '',
                'p_l_flag': fl,
                'p_l_category': acct.get('p_l_category') or PL_FLAG_LABELS.get(fl, str(fl)),
                'fpna_product_key': acct.get('fpna_product_key'),
                'fpna_product_label_en': acct.get('fpna_product_label_en'),
                'monthly_baseline': {m: 0.0 for m in months},
                'monthly_adjusted': {m: 0.0 for m in months},
                'monthly_ai': {m: 0.0 for m in months},
                'driver': None,
            }
        fb = pl_by_flag_map[fl]
        for m in months:
            v_b = float(acct['monthly_baseline'].get(m, 0) or 0)
            v_a = float(acct['monthly_adjusted'].get(m, 0) or 0)
            bucket['monthly_baseline'][m] += v_b
            bucket['monthly_adjusted'][m] += v_a
            fb['monthly_baseline'][m] += v_b
            fb['monthly_adjusted'][m] += v_a
            ap = acct.get('ai_projection')
            if ap and ap.get('monthly'):
                v_ai = float(ap['monthly'].get(m, 0) or 0)
                bucket['monthly_ai'][m] += v_ai
                fb['monthly_ai'][m] += v_ai
        # Prefer DWH YoY driver metadata when any line in the bucket has it
        d = acct.get('driver')
        if d and d.get('type') == 'dwh_yoy':
            bucket['driver'] = d
        elif bucket.get('driver') is None and d:
            bucket['driver'] = d
        if d and d.get('type') == 'dwh_yoy':
            fb['driver'] = d
        elif fb.get('driver') is None and d:
            fb['driver'] = d

    pl_monthly_groups_list: List[Dict[str, Any]] = []
    for key in sorted(
        pl_monthly_groups_map.keys(),
        key=lambda k: (PL_FLAG_ORDER.get(k[1], 99), (pl_monthly_groups_map[k]['budgeting_group_name'] or '').lower()),
    ):
        row = pl_monthly_groups_map[key]
        mb = row['monthly_baseline']
        ma = row['monthly_adjusted']
        mai = row['monthly_ai']
        annual_b = round(sum(mb.values()), 2)
        annual_a = round(sum(ma.values()), 2)
        annual_ai = round(sum(mai.values()), 2) if scenario else None
        row['annual_baseline'] = annual_b
        row['annual_adjusted'] = annual_a
        if scenario:
            row['annual_ai'] = annual_ai
        else:
            row.pop('monthly_ai', None)
        row['variance_pct'] = round((annual_a - annual_b) / abs(annual_b) * 100, 2) if annual_b != 0 else 0.0
        # Round monthlies for payload size
        row['monthly_baseline'] = {m: round(float(mb[m]), 2) for m in months}
        row['monthly_adjusted'] = {m: round(float(ma[m]), 2) for m in months}
        if scenario:
            row['monthly_ai'] = {m: round(float(mai[m]), 2) for m in months}
        pl_monthly_groups_list.append(row)

    pl_monthly_by_flag_list: List[Dict[str, Any]] = []
    for fl in sorted(pl_by_flag_map.keys(), key=lambda f: PL_FLAG_ORDER.get(f, 99)):
        row = pl_by_flag_map[fl]
        mb = row['monthly_baseline']
        ma = row['monthly_adjusted']
        mai = row['monthly_ai']
        annual_b = round(sum(mb.values()), 2)
        annual_a = round(sum(ma.values()), 2)
        annual_ai = round(sum(mai.values()), 2) if scenario else None
        row['annual_baseline'] = annual_b
        row['annual_adjusted'] = annual_a
        if scenario:
            row['annual_ai'] = annual_ai
        else:
            row.pop('monthly_ai', None)
        row['variance_pct'] = round((annual_a - annual_b) / abs(annual_b) * 100, 2) if annual_b != 0 else 0.0
        row['monthly_baseline'] = {m: round(float(mb[m]), 2) for m in months}
        row['monthly_adjusted'] = {m: round(float(ma[m]), 2) for m in months}
        if scenario:
            row['monthly_ai'] = {m: round(float(mai[m]), 2) for m in months}
        pl_monthly_by_flag_list.append(row)

    # If rollups produced no by-flag rows but categories have totals (edge cases / older payloads),
    # synthesize one row per p_l_flag using the same historic month-shape as real rows when available.
    if not pl_monthly_by_flag_list and categories:
        for flag, cat in sorted(categories.items(), key=lambda x: PL_FLAG_ORDER.get(x[0], 99)):
            tb = float(cat['total_baseline'] or 0)
            ta = float(cat['total_adjusted'] or 0)
            hist_f = historic_monthly_by_pl_flag.get(int(flag))
            mb = _distribute_total_to_months(tb, months, hist_f)
            ma = _distribute_total_to_months(ta, months, hist_f)
            pl_monthly_by_flag_list.append({
                'group_id': None,
                'budgeting_group_name': '',
                'p_l_flag': int(flag),
                'p_l_category': cat['category'],
                'fpna_product_key': None,
                'fpna_product_label_en': None,
                'monthly_baseline': {mm: round(float(mb[mm]), 2) for mm in months},
                'monthly_adjusted': {mm: round(float(ma[mm]), 2) for mm in months},
                'annual_baseline': round(tb, 2),
                'annual_adjusted': round(ta, 2),
                'variance_pct': round((ta - tb) / abs(tb) * 100, 2) if abs(tb) > 1e-9 else 0.0,
                'driver': None,
            })

    # KPI month lines: derive from finalized by-flag rows (includes synthesis above)
    flag_map_for_kpi_months: Dict[int, Dict[str, Any]] = {
        int(r['p_l_flag']): r for r in pl_monthly_by_flag_list
    }

    def _bucket_month_fm(flag_map: Dict[int, Dict[str, Any]], fl: int, field: str, month_key: str) -> float:
        r = flag_map.get(fl)
        if not r:
            return 0.0
        return float(r[field].get(month_key, 0) or 0)

    sm_base: Dict[str, Dict[str, float]] = {}
    sm_adj: Dict[str, Dict[str, float]] = {}
    for m in months:
        i1b = _kpi_signed_scalar(_bucket_month_fm(flag_map_for_kpi_months, 1, 'monthly_baseline', m))
        e2b = _kpi_signed_scalar(_bucket_month_fm(flag_map_for_kpi_months, 2, 'monthly_baseline', m))
        i1a = _kpi_signed_scalar(_bucket_month_fm(flag_map_for_kpi_months, 1, 'monthly_adjusted', m))
        e2a = _kpi_signed_scalar(_bucket_month_fm(flag_map_for_kpi_months, 2, 'monthly_adjusted', m))
        nii_b = i1b - e2b
        nii_a = i1a - e2a
        ni_b = (
            nii_b
            + _kpi_signed_scalar(_bucket_month_fm(flag_map_for_kpi_months, 4, 'monthly_baseline', m))
            - _kpi_signed_scalar(_bucket_month_fm(flag_map_for_kpi_months, 5, 'monthly_baseline', m))
            - _kpi_signed_scalar(_bucket_month_fm(flag_map_for_kpi_months, 7, 'monthly_baseline', m))
            - _kpi_signed_scalar(_bucket_month_fm(flag_map_for_kpi_months, 3, 'monthly_baseline', m))
            - _kpi_signed_scalar(_bucket_month_fm(flag_map_for_kpi_months, 8, 'monthly_baseline', m))
        )
        ni_a = (
            nii_a
            + _kpi_signed_scalar(_bucket_month_fm(flag_map_for_kpi_months, 4, 'monthly_adjusted', m))
            - _kpi_signed_scalar(_bucket_month_fm(flag_map_for_kpi_months, 5, 'monthly_adjusted', m))
            - _kpi_signed_scalar(_bucket_month_fm(flag_map_for_kpi_months, 7, 'monthly_adjusted', m))
            - _kpi_signed_scalar(_bucket_month_fm(flag_map_for_kpi_months, 3, 'monthly_adjusted', m))
            - _kpi_signed_scalar(_bucket_month_fm(flag_map_for_kpi_months, 8, 'monthly_adjusted', m))
        )
        sm_base.setdefault('net_interest_income', {})[m] = nii_b
        sm_adj.setdefault('net_interest_income', {})[m] = nii_a
        sm_base.setdefault('non_interest_income', {})[m] = _kpi_signed_scalar(
            _bucket_month_fm(flag_map_for_kpi_months, 4, 'monthly_baseline', m)
        )
        sm_adj.setdefault('non_interest_income', {})[m] = _kpi_signed_scalar(
            _bucket_month_fm(flag_map_for_kpi_months, 4, 'monthly_adjusted', m)
        )
        sm_base.setdefault('non_interest_expense', {})[m] = _kpi_signed_scalar(
            _bucket_month_fm(flag_map_for_kpi_months, 5, 'monthly_baseline', m)
        )
        sm_adj.setdefault('non_interest_expense', {})[m] = _kpi_signed_scalar(
            _bucket_month_fm(flag_map_for_kpi_months, 5, 'monthly_adjusted', m)
        )
        sm_base.setdefault('opex', {})[m] = _kpi_signed_scalar(_bucket_month_fm(flag_map_for_kpi_months, 7, 'monthly_baseline', m))
        sm_adj.setdefault('opex', {})[m] = _kpi_signed_scalar(_bucket_month_fm(flag_map_for_kpi_months, 7, 'monthly_adjusted', m))
        sm_base.setdefault('provisions', {})[m] = _kpi_signed_scalar(_bucket_month_fm(flag_map_for_kpi_months, 3, 'monthly_baseline', m))
        sm_adj.setdefault('provisions', {})[m] = _kpi_signed_scalar(_bucket_month_fm(flag_map_for_kpi_months, 3, 'monthly_adjusted', m))
        sm_base.setdefault('income_tax', {})[m] = _kpi_signed_scalar(_bucket_month_fm(flag_map_for_kpi_months, 8, 'monthly_baseline', m))
        sm_adj.setdefault('income_tax', {})[m] = _kpi_signed_scalar(_bucket_month_fm(flag_map_for_kpi_months, 8, 'monthly_adjusted', m))
        sm_base.setdefault('net_income', {})[m] = ni_b
        sm_adj.setdefault('net_income', {})[m] = ni_a

    summary_monthly: Dict[str, Any] = {
        'baseline': {k: {mm: round(v, 2) for mm, v in mo.items()} for k, mo in sm_base.items()},
        'adjusted': {k: {mm: round(v, 2) for mm, v in mo.items()} for k, mo in sm_adj.items()},
    }

    fpna_by_product: Dict[str, Dict[str, Any]] = {}
    for acct in pl_accounts:
        pk = acct.get('fpna_product_key') or 'UNCLASSIFIED'
        if pk not in fpna_by_product:
            fpna_by_product[pk] = {
                'product_key': pk,
                'label_en': acct.get('fpna_product_label_en') or pk,
                'pillar': acct.get('product_pillar'),
                'total_baseline': 0.0,
                'total_adjusted': 0.0,
            }
        fpna_by_product[pk]['total_baseline'] += float(acct['baseline_total'] or 0)
        fpna_by_product[pk]['total_adjusted'] += float(acct['adjusted_total'] or 0)

    fpna_product_rollups = sorted(fpna_by_product.values(), key=lambda x: x['product_key'])

    sorted_categories = sorted(categories.values(), key=lambda c: c['order'])

    # 8) Compute summary line items (signed-rollup safe for bank conventions)
    interest_income = _kpi_signed_rollup(sum(c['total_adjusted'] for c in categories.values() if c['p_l_flag'] == 1))
    interest_expense = _kpi_signed_rollup(sum(c['total_adjusted'] for c in categories.values() if c['p_l_flag'] == 2))
    nii = interest_income - interest_expense
    non_int_income = _kpi_signed_rollup(sum(c['total_adjusted'] for c in categories.values() if c['p_l_flag'] == 4))
    non_int_expense = _kpi_signed_rollup(sum(c['total_adjusted'] for c in categories.values() if c['p_l_flag'] == 5))
    opex = _kpi_signed_rollup(sum(c['total_adjusted'] for c in categories.values() if c['p_l_flag'] == 7))
    provisions = _kpi_signed_rollup(sum(c['total_adjusted'] for c in categories.values() if c['p_l_flag'] == 3))
    tax = _kpi_signed_rollup(sum(c['total_adjusted'] for c in categories.values() if c['p_l_flag'] == 8))
    net_income = nii + non_int_income - non_int_expense - opex - provisions - tax

    # Same for baseline
    bl_int_income = _kpi_signed_rollup(sum(c['total_baseline'] for c in categories.values() if c['p_l_flag'] == 1))
    bl_int_expense = _kpi_signed_rollup(sum(c['total_baseline'] for c in categories.values() if c['p_l_flag'] == 2))
    bl_nii = bl_int_income - bl_int_expense
    bl_non_int_income = _kpi_signed_rollup(sum(c['total_baseline'] for c in categories.values() if c['p_l_flag'] == 4))
    bl_non_int_expense = _kpi_signed_rollup(sum(c['total_baseline'] for c in categories.values() if c['p_l_flag'] == 5))
    bl_opex = _kpi_signed_rollup(sum(c['total_baseline'] for c in categories.values() if c['p_l_flag'] == 7))
    bl_provisions = _kpi_signed_rollup(sum(c['total_baseline'] for c in categories.values() if c['p_l_flag'] == 3))
    bl_tax = _kpi_signed_rollup(sum(c['total_baseline'] for c in categories.values() if c['p_l_flag'] == 8))
    bl_net_income = bl_nii + bl_non_int_income - bl_non_int_expense - bl_opex - bl_provisions - bl_tax

    # If month vectors are still ~zero while annual KPIs are material, spread FY/12 (matches Σ columns)
    def _patch_summary_monthly_from_annual(
        sm: Dict[str, Any],
        months_local: List[str],
        pairs: List[Tuple[str, float, float]],
        eps_sum: float = 1e-3,
        eps_ann: float = 1e-3,
    ) -> None:
        b_out = sm.setdefault('baseline', {})
        a_out = sm.setdefault('adjusted', {})
        for key, bl_y, adj_y in pairs:
            bd = dict(b_out.get(key) or {})
            ad = dict(a_out.get(key) or {})
            if sum(abs(float(ad.get(mm, 0) or 0)) for mm in months_local) < eps_sum and abs(adj_y) > eps_ann:
                va = adj_y / 12.0
                for mm in months_local:
                    ad[mm] = round(va, 2)
            if sum(abs(float(bd.get(mm, 0) or 0)) for mm in months_local) < eps_sum and abs(bl_y) > eps_ann:
                vb = bl_y / 12.0
                for mm in months_local:
                    bd[mm] = round(vb, 2)
            b_out[key] = bd
            a_out[key] = ad

    _patch_summary_monthly_from_annual(
        summary_monthly,
        months,
        [
            ('net_interest_income', bl_nii, nii),
            ('non_interest_income', bl_non_int_income, non_int_income),
            ('non_interest_expense', bl_non_int_expense, non_int_expense),
            ('opex', bl_opex, opex),
            ('provisions', bl_provisions, provisions),
            ('income_tax', bl_tax, tax),
            ('net_income', bl_net_income, net_income),
        ],
    )

    is_bank_wide = (pl_plan.id != plan.id)

    # 9) Compute AI projection summary if scenario selected
    ai_summary = {}
    if ai_projections:
        def _ai_cat_total(flag):
            cat = categories.get(flag)
            if not cat:
                return 0
            raw = sum(a.get('ai_projection', {}).get('annual_total', 0) for a in cat['accounts'])
            return _kpi_signed_rollup(raw)
        ai_int_income = _ai_cat_total(1)
        ai_int_expense = _ai_cat_total(2)
        ai_nii = ai_int_income - ai_int_expense
        ai_non_int_income = _ai_cat_total(4)
        ai_non_int_expense = _ai_cat_total(5)
        ai_opex_val = _ai_cat_total(7)
        ai_provisions_val = _ai_cat_total(3)
        ai_tax_val = _ai_cat_total(8)
        ai_net = ai_nii + ai_non_int_income - ai_non_int_expense - ai_opex_val - ai_provisions_val - ai_tax_val
        ai_summary = {
            'interest_income': ai_int_income,
            'interest_expense': ai_int_expense,
            'net_interest_income': ai_nii,
            'non_interest_income': ai_non_int_income,
            'non_interest_expense': ai_non_int_expense,
            'opex': ai_opex_val,
            'provisions': ai_provisions_val,
            'income_tax': ai_tax_val,
            'net_income': ai_net,
        }

    yoy_src = yoy_prop.get("source_years") or {}
    yoy_suggestions = {
        "source_years": yoy_src,
        "by_pl_flag": {str(k): v for k, v in historic_by_flag.items()},
        "by_product": yoy_prop.get("by_product") or [],
        "warnings": yoy_prop.get("warnings") or [],
        "adjusted_mode": "plan_group_ratio" if use_plan_group_ratio else "dwh_yoy_per_p_l_flag",
    }

    # Flag AI rows that are wildly off adjusted plan (legacy projections before anchoring)
    ai_stale_warning = False
    if ai_projections:
        for c in sorted_categories:
            adj = float(c.get("total_adjusted") or 0)
            if adj <= 0:
                continue
            ai_tot = sum(
                float(a.get("ai_projection", {}).get("annual_total") or 0)
                for a in c.get("accounts") or []
            )
            if ai_tot > 3 * adj or (adj > 0 and ai_tot < adj / 3):
                ai_stale_warning = True
                break

    categories_for_client = [
        {
            'p_l_flag': c['p_l_flag'],
            'category': c['category'],
            'order': c['order'],
            'total_baseline': c['total_baseline'],
            'total_adjusted': c['total_adjusted'],
            'group_row_count': sum(1 for g in pl_monthly_groups_list if g['p_l_flag'] == c['p_l_flag']),
        }
        for c in sorted_categories
    ]

    return {
        'plan_id': plan.id,
        'fiscal_year': fiscal_year,
        'department': {
            'id': plan.department.id,
            'code': plan.department.code,
            'name': plan.department.name_en,
        },
        'status': plan.status.value,
        'is_bank_wide': is_bank_wide,
        'pl_view': 'monthly_groups',
        'month_keys': months,
        'pl_monthly_groups': pl_monthly_groups_list,
        'pl_monthly_by_flag': pl_monthly_by_flag_list,
        'summary_monthly': summary_monthly,
        'pl_seasonality': {
            'reference_fiscal_year': season_ref,
            'accounts_with_history': sum(
                1
                for _ac, mo in historic_by_account.items()
                if any(abs(float(mo.get(mm, 0) or 0)) > 1e-9 for mm in range(1, 13))
            ),
        },
        'categories': categories_for_client,
        'summary': {
            'interest_income':    {'baseline': bl_int_income,    'adjusted': interest_income},
            'interest_expense':   {'baseline': bl_int_expense,   'adjusted': interest_expense},
            'net_interest_income': {'baseline': bl_nii,          'adjusted': nii},
            'non_interest_income': {'baseline': bl_non_int_income, 'adjusted': non_int_income},
            'non_interest_expense': {'baseline': bl_non_int_expense, 'adjusted': non_int_expense},
            'opex':               {'baseline': bl_opex,          'adjusted': opex},
            'provisions':         {'baseline': bl_provisions,    'adjusted': provisions},
            'income_tax':         {'baseline': bl_tax,           'adjusted': tax},
            'net_income':         {'baseline': bl_net_income,    'adjusted': net_income},
        },
        'ai_summary': ai_summary if ai_summary else None,
        'has_ai_scenario': len(ai_projections) > 0,
        'scenario_name': scenario,
        'fpna_products': fpna_product_rollups,
        'yoy_suggestions': yoy_suggestions,
        'pl_adjusted_mode': yoy_suggestions.get("adjusted_mode"),
        'ai_stale_warning': ai_stale_warning,
    }
