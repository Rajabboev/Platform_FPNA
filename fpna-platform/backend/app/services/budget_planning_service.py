"""
Budget Planning Service - COA Hierarchy-Based Budget Planning

This service implements the new group-based budget planning workflow:
1. Initialize: Ingest DWH data → Calculate baseline by budgeting groups
2. Assign: Assign budgeting groups to departments
3. Plan: Departments adjust group-level budgets using drivers
4. Approve: Two-level approval (Dept Head → CFO)
5. Export: Consolidate and export to DWH
"""

import logging
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
import uuid

import pandas as pd
from sqlalchemy import text, func
from sqlalchemy.orm import Session

from app.models.department import Department, DepartmentAssignment, DepartmentRole
from app.models.budget_plan import (
    BudgetPlan, BudgetPlanGroup, BudgetPlanDetail, BudgetPlanApproval,
    BudgetPlanStatus, ApprovalLevel, ApprovalAction
)
from app.models.coa_dimension import COADimension, BudgetingGroup, BSClass
from app.models.baseline import BaselineData
from app.models.dwh_connection import DWHConnection
from app.models.user import User
from app.services.connection_service import get_engine_for_connection

logger = logging.getLogger(__name__)

MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']


class BudgetPlanningService:
    """Service for managing the budget planning workflow"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # =========================================================================
    # STEP 1: Initialize - Ingest and Calculate Baseline
    # =========================================================================
    
    def ingest_from_dwh(
        self,
        connection_id: int,
        source_table: str = "balans_ato",
        fiscal_years: List[int] = None,
    ) -> Dict[str, Any]:
        """
        Ingest balance data from DWH and store in baseline_data table.
        
        Args:
            connection_id: DWH connection ID
            source_table: Source table name (default: balans_ato)
            fiscal_years: List of fiscal years to ingest (default: last 3 years)
        
        DWH balans_ato table columns:
            KODBALANS = COA code
            CURDATE = Date (e.g., 2022-01-31)
            KODVALUTA = Currency code (0=UZS, 840=USD, 978=EUR)
            OSTATALL = Balance in UZS
            OSTATALLVAL = Balance in original currency
        """
        if fiscal_years is None:
            current_year = datetime.now().year
            fiscal_years = [current_year - 3, current_year - 2, current_year - 1]
        
        conn = self.db.query(DWHConnection).filter(DWHConnection.id == connection_id).first()
        if not conn:
            raise ValueError(f"Connection {connection_id} not found")
        
        dwh_engine = get_engine_for_connection(conn)
        batch_id = str(uuid.uuid4())[:8]
        
        # Query DWH for balance data using actual column names
        years_str = ",".join(str(y) for y in fiscal_years)
        query = f"""
            SELECT 
                KODBALANS as coa_code,
                YEAR(CURDATE) as fiscal_year,
                MONTH(CURDATE) as fiscal_month,
                CURDATE as snapshot_date,
                SUM(OSTATALL) as balance_uzs,
                SUM(OSTATALLVAL) as balance_orig,
                KODVALUTA as currency_code
            FROM [{source_table}]
            WHERE YEAR(CURDATE) IN ({years_str})
            GROUP BY KODBALANS, YEAR(CURDATE), MONTH(CURDATE), CURDATE, KODVALUTA
        """
        
        try:
            df = pd.read_sql(query, dwh_engine)
            
            if df.empty:
                return {"status": "warning", "message": "No data found in DWH for the specified years", "rows": 0}
            
            # Map currency codes to ISO alpha codes
            currency_map = {0: 'UZS', 840: 'USD', 978: 'EUR', 826: 'GBP', 392: 'JPY', 643: 'RUB'}
            
            # Clear existing baseline_data for these years
            self.db.query(BaselineData).filter(
                BaselineData.fiscal_year.in_(fiscal_years)
            ).delete(synchronize_session=False)
            
            # Insert new data
            rows_inserted = 0
            for _, row in df.iterrows():
                fiscal_year = int(row['fiscal_year'])
                fiscal_month = int(row['fiscal_month'])
                snapshot_dt = row['snapshot_date']
                if isinstance(snapshot_dt, str):
                    snapshot_dt = datetime.strptime(snapshot_dt, '%Y-%m-%d').date()
                elif hasattr(snapshot_dt, 'date'):
                    snapshot_dt = snapshot_dt.date()
                
                # Map currency code to ISO alpha
                currency_code = int(row['currency_code']) if pd.notna(row['currency_code']) else 0
                currency = currency_map.get(currency_code, 'UZS')
                
                baseline = BaselineData(
                    account_code=str(row['coa_code']),
                    fiscal_year=fiscal_year,
                    fiscal_month=fiscal_month,
                    snapshot_date=snapshot_dt,
                    balance_uzs=Decimal(str(row['balance_uzs'])) if pd.notna(row['balance_uzs']) else Decimal(0),
                    balance=Decimal(str(row['balance_orig'])) if pd.notna(row['balance_orig']) else Decimal(0),
                    currency=currency,
                    currency_code=currency_code,
                    import_batch_id=batch_id,
                )
                self.db.add(baseline)
                rows_inserted += 1
            
            self.db.commit()
            
            return {
                "status": "success",
                "batch_id": batch_id,
                "rows_inserted": rows_inserted,
                "fiscal_years": fiscal_years,
            }
            
        except Exception as e:
            self.db.rollback()
            logger.exception(f"DWH ingestion failed: {e}")
            raise
    
    def calculate_baseline_by_groups(
        self,
        target_fiscal_year: int,
        source_years: List[int] = None,
        method: str = "simple_average",
    ) -> Dict[str, Any]:
        """
        Calculate baseline budget with 4-level hierarchy:
        Level 1: BS Class (Assets, Liabilities, Capital, Off-balance)
        Level 2: BS Group (3-digit code)
        Level 3: Budgeting Group (FP&A grouping)
        Level 4: COA Account (5-digit code)
        
        Args:
            target_fiscal_year: The fiscal year to create baseline for
            source_years: Years to use for calculation (default: previous 3 years)
            method: Calculation method (simple_average, weighted_average, trend)
        
        Returns:
            Dict with 4-level hierarchical baseline data
        """
        if source_years is None:
            source_years = [target_fiscal_year - 3, target_fiscal_year - 2, target_fiscal_year - 1]
        
        # Get COA dimension with all hierarchy levels
        coa_map = {}
        coa_records = self.db.query(COADimension).filter(COADimension.is_active == True).all()
        for coa in coa_records:
            coa_map[coa.coa_code] = {
                'coa_code': coa.coa_code,
                'coa_name': coa.coa_name,
                'budgeting_group_id': coa.budgeting_groups,
                'budgeting_group_name': coa.budgeting_groups_name,
                'bs_flag': coa.bs_flag,
                'bs_name': coa.bs_name,
                'bs_group': coa.bs_group,
                'bs_group_name': coa.group_name,
            }
        
        # Get baseline data
        baseline_records = self.db.query(BaselineData).filter(
            BaselineData.fiscal_year.in_(source_years)
        ).all()
        
        if not baseline_records:
            return {"status": "warning", "message": "No baseline data found", "groups": [], "hierarchy": []}
        
        # Build 4-level hierarchy data structure
        # {bs_flag: {bs_group: {bg_id: {coa_code: {month: [values]}}}}}
        hierarchy_data = {}
        
        for record in baseline_records:
            coa_info = coa_map.get(record.account_code)
            if not coa_info:
                continue
            
            bs_flag = coa_info['bs_flag'] or 0
            bs_group = coa_info['bs_group'] or '000'
            bg_id = coa_info['budgeting_group_id']
            coa_code = record.account_code
            month = record.fiscal_month
            
            # Initialize nested structure
            if bs_flag not in hierarchy_data:
                hierarchy_data[bs_flag] = {
                    'bs_name': coa_info['bs_name'],
                    'bs_groups': {}
                }
            
            if bs_group not in hierarchy_data[bs_flag]['bs_groups']:
                hierarchy_data[bs_flag]['bs_groups'][bs_group] = {
                    'bs_group_name': coa_info['bs_group_name'],
                    'budgeting_groups': {}
                }
            
            if bg_id not in hierarchy_data[bs_flag]['bs_groups'][bs_group]['budgeting_groups']:
                hierarchy_data[bs_flag]['bs_groups'][bs_group]['budgeting_groups'][bg_id] = {
                    'budgeting_group_name': coa_info['budgeting_group_name'],
                    'accounts': {}
                }
            
            if coa_code not in hierarchy_data[bs_flag]['bs_groups'][bs_group]['budgeting_groups'][bg_id]['accounts']:
                hierarchy_data[bs_flag]['bs_groups'][bs_group]['budgeting_groups'][bg_id]['accounts'][coa_code] = {
                    'coa_name': coa_info['coa_name'],
                    'months': {m: [] for m in range(1, 13)}
                }
            
            hierarchy_data[bs_flag]['bs_groups'][bs_group]['budgeting_groups'][bg_id]['accounts'][coa_code]['months'][month].append(
                float(record.balance_uzs or 0)
            )
        
        def calc_average(values: List[float]) -> float:
            if not values:
                return 0
            if method == "simple_average":
                return sum(values) / len(values)
            elif method == "weighted_average":
                weights = [1, 2, 3][:len(values)]
                return sum(v * w for v, w in zip(values, weights)) / sum(weights)
            return sum(values) / len(values)
        
        # Build result hierarchy
        result_hierarchy = []
        flat_groups = []  # For backward compatibility
        
        for bs_flag in sorted(hierarchy_data.keys()):
            bs_data = hierarchy_data[bs_flag]
            bs_class_result = {
                'bs_flag': bs_flag,
                'bs_name': bs_data['bs_name'],
                'bs_groups': [],
                'total': 0,
            }
            
            for bs_group in sorted(bs_data['bs_groups'].keys()):
                bs_group_data = bs_data['bs_groups'][bs_group]
                bs_group_result = {
                    'bs_group': bs_group,
                    'bs_group_name': bs_group_data['bs_group_name'],
                    'budgeting_groups': [],
                    'total': 0,
                }
                
                for bg_id, bg_data in bs_group_data['budgeting_groups'].items():
                    bg_monthly = {m: 0 for m in range(1, 13)}
                    accounts_result = []
                    
                    for coa_code, acc_data in bg_data['accounts'].items():
                        acc_monthly = {}
                        for month in range(1, 13):
                            acc_monthly[month] = calc_average(acc_data['months'][month])
                            bg_monthly[month] += acc_monthly[month]
                        
                        accounts_result.append({
                            'coa_code': coa_code,
                            'coa_name': acc_data['coa_name'],
                            'monthly': acc_monthly,
                            'total': sum(acc_monthly.values()),
                        })
                    
                    bg_total = sum(bg_monthly.values())
                    bg_result = {
                        'budgeting_group_id': bg_id,
                        'budgeting_group_name': bg_data['budgeting_group_name'],
                        'monthly': bg_monthly,
                        'total': bg_total,
                        'accounts': sorted(accounts_result, key=lambda x: x['coa_code']),
                    }
                    bs_group_result['budgeting_groups'].append(bg_result)
                    bs_group_result['total'] += bg_total
                    
                    # Also add to flat groups for backward compatibility
                    flat_groups.append({
                        'budgeting_group_id': bg_id,
                        'budgeting_group_name': bg_data['budgeting_group_name'],
                        'bs_flag': bs_flag,
                        'bs_class_name': bs_data['bs_name'],
                        'bs_group': bs_group,
                        'bs_group_name': bs_group_data['bs_group_name'],
                        'monthly': bg_monthly,
                        'total': bg_total,
                        'details': [{
                            'coa_code': a['coa_code'],
                            'coa_name': a['coa_name'],
                            'bs_group': bs_group,
                            'bs_group_name': bs_group_data['bs_group_name'],
                            'monthly': a['monthly'],
                            'total': a['total'],
                        } for a in accounts_result],
                    })
                
                bs_group_result['budgeting_groups'].sort(key=lambda x: x['budgeting_group_name'] or '')
                bs_class_result['bs_groups'].append(bs_group_result)
                bs_class_result['total'] += bs_group_result['total']
            
            bs_class_result['bs_groups'].sort(key=lambda x: x['bs_group'])
            result_hierarchy.append(bs_class_result)
        
        return {
            "status": "success",
            "target_fiscal_year": target_fiscal_year,
            "source_years": source_years,
            "method": method,
            "hierarchy": result_hierarchy,  # New 4-level structure
            "groups": flat_groups,  # Backward compatible flat structure
            "group_count": len(flat_groups),
        }
    
    # =========================================================================
    # STEP 2: Create Budget Plans for Departments
    # =========================================================================
    
    def create_department_plans(
        self,
        fiscal_year: int,
        baseline_data: Dict[str, Any],
        user_id: int,
    ) -> Dict[str, Any]:
        """
        Create budget plans for all active departments based on baseline data.
        
        Args:
            fiscal_year: Target fiscal year
            baseline_data: Result from calculate_baseline_by_groups
            user_id: User creating the plans
        """
        departments = self.db.query(Department).filter(Department.is_active == True).all()
        
        if not departments:
            return {"status": "warning", "message": "No active departments found"}
        
        plans_created = []
        
        for dept in departments:
            # Check if plan already exists
            existing = self.db.query(BudgetPlan).filter(
                BudgetPlan.fiscal_year == fiscal_year,
                BudgetPlan.department_id == dept.id,
                BudgetPlan.is_current == True
            ).first()
            
            if existing:
                # Archive existing plan
                existing.is_current = False
            
            # Create new plan
            plan = BudgetPlan(
                fiscal_year=fiscal_year,
                department_id=dept.id,
                status=BudgetPlanStatus.DRAFT,
                version=1,
                is_current=True,
                created_by_user_id=user_id,
            )
            self.db.add(plan)
            self.db.flush()  # Get plan.id
            
            # Get assigned budgeting groups for this department
            assigned_groups = [bg.group_id for bg in dept.budgeting_groups]
            
            # If no groups assigned, use all groups (for baseline-only departments)
            if not assigned_groups or dept.is_baseline_only:
                assigned_groups = [g['budgeting_group_id'] for g in baseline_data.get('groups', [])]
            
            # Create plan groups
            for group_data in baseline_data.get('groups', []):
                if group_data['budgeting_group_id'] not in assigned_groups:
                    continue
                
                monthly = group_data['monthly']
                
                # Determine if this group should be locked
                # Lock if: no budgeting_group_name OR department is baseline-only
                is_locked = (
                    group_data['budgeting_group_name'] is None 
                    or dept.is_baseline_only
                )
                
                plan_group = BudgetPlanGroup(
                    plan_id=plan.id,
                    budgeting_group_id=group_data['budgeting_group_id'],
                    budgeting_group_name=group_data['budgeting_group_name'],
                    bs_flag=group_data['bs_flag'],
                    bs_class_name=group_data['bs_class_name'],
                    bs_group=group_data.get('bs_group'),
                    bs_group_name=group_data.get('bs_group_name'),
                    baseline_jan=Decimal(str(monthly.get(1, 0))),
                    baseline_feb=Decimal(str(monthly.get(2, 0))),
                    baseline_mar=Decimal(str(monthly.get(3, 0))),
                    baseline_apr=Decimal(str(monthly.get(4, 0))),
                    baseline_may=Decimal(str(monthly.get(5, 0))),
                    baseline_jun=Decimal(str(monthly.get(6, 0))),
                    baseline_jul=Decimal(str(monthly.get(7, 0))),
                    baseline_aug=Decimal(str(monthly.get(8, 0))),
                    baseline_sep=Decimal(str(monthly.get(9, 0))),
                    baseline_oct=Decimal(str(monthly.get(10, 0))),
                    baseline_nov=Decimal(str(monthly.get(11, 0))),
                    baseline_dec=Decimal(str(monthly.get(12, 0))),
                    # Initialize adjusted = baseline
                    adjusted_jan=Decimal(str(monthly.get(1, 0))),
                    adjusted_feb=Decimal(str(monthly.get(2, 0))),
                    adjusted_mar=Decimal(str(monthly.get(3, 0))),
                    adjusted_apr=Decimal(str(monthly.get(4, 0))),
                    adjusted_may=Decimal(str(monthly.get(5, 0))),
                    adjusted_jun=Decimal(str(monthly.get(6, 0))),
                    adjusted_jul=Decimal(str(monthly.get(7, 0))),
                    adjusted_aug=Decimal(str(monthly.get(8, 0))),
                    adjusted_sep=Decimal(str(monthly.get(9, 0))),
                    adjusted_oct=Decimal(str(monthly.get(10, 0))),
                    adjusted_nov=Decimal(str(monthly.get(11, 0))),
                    adjusted_dec=Decimal(str(monthly.get(12, 0))),
                    is_locked=is_locked,
                )
                plan_group.recalculate_totals()
                self.db.add(plan_group)
                self.db.flush()
                
                # Create detail records
                for detail in group_data.get('details', []):
                    detail_monthly = detail['monthly']
                    plan_detail = BudgetPlanDetail(
                        group_id=plan_group.id,
                        coa_code=detail['coa_code'],
                        coa_name=detail['coa_name'],
                        bs_group=detail['bs_group'],
                        bs_group_name=detail['bs_group_name'],
                        baseline_jan=Decimal(str(detail_monthly.get(1, 0))),
                        baseline_feb=Decimal(str(detail_monthly.get(2, 0))),
                        baseline_mar=Decimal(str(detail_monthly.get(3, 0))),
                        baseline_apr=Decimal(str(detail_monthly.get(4, 0))),
                        baseline_may=Decimal(str(detail_monthly.get(5, 0))),
                        baseline_jun=Decimal(str(detail_monthly.get(6, 0))),
                        baseline_jul=Decimal(str(detail_monthly.get(7, 0))),
                        baseline_aug=Decimal(str(detail_monthly.get(8, 0))),
                        baseline_sep=Decimal(str(detail_monthly.get(9, 0))),
                        baseline_oct=Decimal(str(detail_monthly.get(10, 0))),
                        baseline_nov=Decimal(str(detail_monthly.get(11, 0))),
                        baseline_dec=Decimal(str(detail_monthly.get(12, 0))),
                        baseline_total=Decimal(str(detail['total'])),
                    )
                    self.db.add(plan_detail)
            
            plan.recalculate_totals()
            plans_created.append({
                'department_id': dept.id,
                'department_code': dept.code,
                'plan_id': plan.id,
                'groups_count': len([g for g in baseline_data.get('groups', []) if g['budgeting_group_id'] in assigned_groups]),
            })
        
        self.db.commit()
        
        return {
            "status": "success",
            "fiscal_year": fiscal_year,
            "plans_created": len(plans_created),
            "plans": plans_created,
        }
    
    # =========================================================================
    # STEP 3: Update Group Adjustments
    # =========================================================================
    
    def update_group_adjustment(
        self,
        plan_id: int,
        group_id: int,
        driver_code: Optional[str],
        driver_name: Optional[str] = None,
        driver_rate: Optional[Decimal] = None,
        monthly_adjustments: Optional[Dict[str, Decimal]] = None,
        notes: Optional[str] = None,
        user_id: int = None,
    ) -> BudgetPlanGroup:
        """
        Update adjustments for a budget plan group.
        
        Args:
            plan_id: Budget plan ID
            group_id: Budget plan group ID
            driver_code: Driver code to apply (optional)
            driver_name: Driver name for display (optional)
            driver_rate: Driver rate as percentage (optional)
            monthly_adjustments: Dict of month -> adjusted value (optional)
            notes: Adjustment notes
            user_id: User making the adjustment
        """
        plan = self.db.query(BudgetPlan).filter(BudgetPlan.id == plan_id).first()
        if not plan:
            raise ValueError("Budget plan not found")
        
        if plan.status not in [BudgetPlanStatus.DRAFT, BudgetPlanStatus.REJECTED]:
            raise ValueError(f"Cannot edit plan in {plan.status} status")
        
        group = self.db.query(BudgetPlanGroup).filter(
            BudgetPlanGroup.id == group_id,
            BudgetPlanGroup.plan_id == plan_id
        ).first()
        
        if not group:
            raise ValueError("Budget plan group not found")
        
        if group.is_locked:
            raise ValueError("This group is locked and cannot be edited")
        
        # Apply driver rate if provided
        if driver_rate is not None:
            group.apply_driver(driver_rate)
            group.driver_code = driver_code
            group.driver_name = driver_name or driver_code
        
        # Apply manual monthly adjustments if provided
        if monthly_adjustments:
            for month, value in monthly_adjustments.items():
                month_lower = month.lower()[:3]
                if month_lower in MONTHS:
                    setattr(group, f'adjusted_{month_lower}', Decimal(str(value)))
            group.recalculate_totals()
        
        group.adjustment_notes = notes
        group.last_edited_at = datetime.now(timezone.utc)
        group.last_edited_by_user_id = user_id
        
        # Recalculate plan totals
        plan.recalculate_totals()
        
        self.db.commit()
        return group
    
    # =========================================================================
    # STEP 4: Approval Workflow
    # =========================================================================
    
    def submit_plan(self, plan_id: int, user_id: int) -> BudgetPlan:
        """Submit a budget plan for approval"""
        plan = self.db.query(BudgetPlan).filter(BudgetPlan.id == plan_id).first()
        if not plan:
            raise ValueError("Budget plan not found")
        
        if plan.status != BudgetPlanStatus.DRAFT and plan.status != BudgetPlanStatus.REJECTED:
            raise ValueError(f"Cannot submit plan in {plan.status} status")
        
        old_status = plan.status
        plan.status = BudgetPlanStatus.SUBMITTED
        plan.submitted_at = datetime.now(timezone.utc)
        plan.submitted_by_user_id = user_id
        
        # Create approval record
        approval = BudgetPlanApproval(
            plan_id=plan.id,
            level=ApprovalLevel.DEPT_HEAD,
            action=ApprovalAction.SUBMIT,
            user_id=user_id,
            status_before=old_status.value,
            status_after=plan.status.value,
        )
        self.db.add(approval)
        self.db.commit()
        
        return plan
    
    def approve_plan_dept(self, plan_id: int, user_id: int, comment: Optional[str] = None) -> BudgetPlan:
        """Department head approval"""
        plan = self.db.query(BudgetPlan).filter(BudgetPlan.id == plan_id).first()
        if not plan:
            raise ValueError("Budget plan not found")
        
        if plan.status != BudgetPlanStatus.SUBMITTED:
            raise ValueError(f"Cannot approve plan in {plan.status} status")
        
        old_status = plan.status
        plan.status = BudgetPlanStatus.DEPT_APPROVED
        plan.dept_approved_at = datetime.now(timezone.utc)
        plan.dept_approved_by_user_id = user_id
        plan.dept_approval_comment = comment
        
        approval = BudgetPlanApproval(
            plan_id=plan.id,
            level=ApprovalLevel.DEPT_HEAD,
            action=ApprovalAction.APPROVE,
            user_id=user_id,
            comment=comment,
            status_before=old_status.value,
            status_after=plan.status.value,
        )
        self.db.add(approval)
        self.db.commit()
        
        return plan
    
    def approve_plan_cfo(self, plan_id: int, user_id: int, comment: Optional[str] = None) -> BudgetPlan:
        """CFO final approval"""
        plan = self.db.query(BudgetPlan).filter(BudgetPlan.id == plan_id).first()
        if not plan:
            raise ValueError("Budget plan not found")
        
        if plan.status != BudgetPlanStatus.DEPT_APPROVED:
            raise ValueError(f"Cannot CFO-approve plan in {plan.status} status")
        
        old_status = plan.status
        plan.status = BudgetPlanStatus.CFO_APPROVED
        plan.cfo_approved_at = datetime.now(timezone.utc)
        plan.cfo_approved_by_user_id = user_id
        plan.cfo_approval_comment = comment
        
        approval = BudgetPlanApproval(
            plan_id=plan.id,
            level=ApprovalLevel.CFO,
            action=ApprovalAction.APPROVE,
            user_id=user_id,
            comment=comment,
            status_before=old_status.value,
            status_after=plan.status.value,
        )
        self.db.add(approval)
        self.db.commit()
        
        return plan
    
    def reject_plan(self, plan_id: int, user_id: int, reason: str, level: ApprovalLevel) -> BudgetPlan:
        """Reject a budget plan"""
        plan = self.db.query(BudgetPlan).filter(BudgetPlan.id == plan_id).first()
        if not plan:
            raise ValueError("Budget plan not found")
        
        old_status = plan.status
        plan.status = BudgetPlanStatus.REJECTED
        plan.rejected_at = datetime.now(timezone.utc)
        plan.rejected_by_user_id = user_id
        plan.rejection_reason = reason
        
        approval = BudgetPlanApproval(
            plan_id=plan.id,
            level=level,
            action=ApprovalAction.REJECT,
            user_id=user_id,
            comment=reason,
            status_before=old_status.value,
            status_after=plan.status.value,
        )
        self.db.add(approval)
        self.db.commit()
        
        return plan
    
    # =========================================================================
    # STEP 5: Export to DWH
    # =========================================================================
    
    def export_to_dwh(
        self,
        fiscal_year: int,
        connection_id: int,
        target_table: str = "fpna_budget_final",
    ) -> Dict[str, Any]:
        """
        Export approved budget plans to DWH.
        
        Only exports CFO_APPROVED plans.
        """
        conn = self.db.query(DWHConnection).filter(DWHConnection.id == connection_id).first()
        if not conn:
            raise ValueError(f"Connection {connection_id} not found")
        
        # Get all approved plans for the fiscal year
        plans = self.db.query(BudgetPlan).filter(
            BudgetPlan.fiscal_year == fiscal_year,
            BudgetPlan.status == BudgetPlanStatus.CFO_APPROVED,
            BudgetPlan.is_current == True
        ).all()
        
        if not plans:
            return {"status": "warning", "message": "No approved plans to export"}
        
        # Build export data
        export_rows = []
        batch_id = str(uuid.uuid4())[:8]
        
        for plan in plans:
            dept = plan.department
            for group in plan.groups:
                for month_idx, month_name in enumerate(MONTHS, 1):
                    baseline_val = getattr(group, f'baseline_{month_name}', 0) or 0
                    adjusted_val = getattr(group, f'adjusted_{month_name}', 0) or 0
                    
                    export_rows.append({
                        'fiscal_year': fiscal_year,
                        'department_code': dept.code,
                        'department_name': dept.name_en,
                        'budgeting_group_id': group.budgeting_group_id,
                        'budgeting_group_name': group.budgeting_group_name,
                        'bs_flag': group.bs_flag,
                        'month': month_idx,
                        'baseline_amount': float(baseline_val),
                        'adjusted_amount': float(adjusted_val),
                        'variance': float(adjusted_val) - float(baseline_val),
                        'driver_code': group.driver_code,
                        'driver_rate': float(group.driver_rate) if group.driver_rate else None,
                        'export_batch_id': batch_id,
                        'exported_at': datetime.now(timezone.utc).isoformat(),
                    })
        
        if not export_rows:
            return {"status": "warning", "message": "No data to export"}
        
        # Export to DWH
        df = pd.DataFrame(export_rows)
        dwh_engine = get_engine_for_connection(conn)
        
        # Create table if not exists and insert
        from app.services.etl_service import _table_exists, _create_table_from_df, _insert_dataframe, _get_dialect
        
        dialect = _get_dialect(dwh_engine)
        if not _table_exists(dwh_engine, 'dbo', target_table):
            _create_table_from_df(dwh_engine, df, 'dbo', target_table)
        
        _insert_dataframe(dwh_engine, df, 'dbo', target_table, dialect)
        
        # Update plan status
        for plan in plans:
            plan.status = BudgetPlanStatus.EXPORTED
            plan.exported_at = datetime.now(timezone.utc)
            plan.export_batch_id = batch_id
        
        self.db.commit()
        
        return {
            "status": "success",
            "batch_id": batch_id,
            "plans_exported": len(plans),
            "rows_exported": len(export_rows),
            "target_table": target_table,
        }
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def get_plan_summary(self, plan_id: int) -> Dict[str, Any]:
        """Get summary of a budget plan"""
        plan = self.db.query(BudgetPlan).filter(BudgetPlan.id == plan_id).first()
        if not plan:
            return None
        
        return {
            'id': plan.id,
            'fiscal_year': plan.fiscal_year,
            'department_id': plan.department_id,
            'department_code': plan.department.code,
            'department_name': plan.department.name_en,
            'status': plan.status.value,
            'version': plan.version,
            'total_baseline': float(plan.total_baseline or 0),
            'total_adjusted': float(plan.total_adjusted or 0),
            'total_variance': float(plan.total_variance or 0),
            'total_variance_pct': float(plan.total_variance_pct or 0),
            'groups_count': len(plan.groups),
            'submitted_at': plan.submitted_at.isoformat() if plan.submitted_at else None,
            'dept_approved_at': plan.dept_approved_at.isoformat() if plan.dept_approved_at else None,
            'cfo_approved_at': plan.cfo_approved_at.isoformat() if plan.cfo_approved_at else None,
        }
    
    def get_workflow_status(self, fiscal_year: int) -> Dict[str, Any]:
        """Get overall workflow status for a fiscal year"""
        plans = self.db.query(BudgetPlan).filter(
            BudgetPlan.fiscal_year == fiscal_year,
            BudgetPlan.is_current == True
        ).all()
        
        status_counts = {}
        for plan in plans:
            status = plan.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            'fiscal_year': fiscal_year,
            'total_plans': len(plans),
            'status_counts': status_counts,
            'all_approved': all(p.status == BudgetPlanStatus.CFO_APPROVED for p in plans),
            'ready_for_export': sum(1 for p in plans if p.status == BudgetPlanStatus.CFO_APPROVED),
        }
