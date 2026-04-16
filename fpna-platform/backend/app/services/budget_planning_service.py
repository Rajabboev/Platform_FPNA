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
from typing import Dict, List, Optional, Any, Collection
from types import SimpleNamespace
import uuid

import pandas as pd
from sqlalchemy import text, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.department import Department, DepartmentAssignment, DepartmentRole, DepartmentProductAccess
from app.models.budget_plan import (
    BudgetPlan, BudgetPlanGroup, BudgetPlanDetail, BudgetPlanApproval,
    BudgetPlanStatus, ApprovalLevel, ApprovalAction
)
from app.models.coa_dimension import COADimension, BudgetingGroup, BSClass
from app.models.baseline import BaselineData
from app.models.dwh_connection import DWHConnection
from app.models.user import User
from app.models.driver import Driver, DriverValue, DriverGroupAssignment
from app.services.connection_service import get_engine_for_connection
from app.services.coa_product_taxonomy import resolve_coa_taxonomy, product_keys_for_legacy_budgeting_groups

logger = logging.getLogger(__name__)

MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']


def _dataframe_from_sql(engine, sql_str: str) -> pd.DataFrame:
    """
    Run SQL on a SQLAlchemy engine and build a DataFrame.
    Avoids pd.read_sql: pandas 3 may not treat SA 2.x Connection as SQLAlchemy
    (falls through to ADBC/DBAPI and errors on text() or .cursor()).
    """
    with engine.connect() as sa_conn:
        result = sa_conn.execute(text(sql_str))
        cols = list(result.keys())
        rows = result.fetchall()
        return pd.DataFrame(rows, columns=cols) if cols else pd.DataFrame()


def _norm_segment(val: Optional[str]) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


class BudgetPlanningService:
    """Service for managing the budget planning workflow"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # =========================================================================
    # STEP 1: Initialize - Ingest and Calculate Baseline
    # =========================================================================
    
    def preview_dwh_table(
        self,
        connection_id: int,
        table_name: str,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Preview rows from a DWH table and auto-detect column roles."""
        conn = self.db.query(DWHConnection).filter(DWHConnection.id == connection_id).first()
        if not conn:
            raise ValueError(f"Connection {connection_id} not found")

        dwh_engine = get_engine_for_connection(conn)
        df = _dataframe_from_sql(
            dwh_engine,
            f"SELECT TOP {int(limit)} * FROM [{table_name}]",
        )

        columns = list(df.columns)
        sample = df.head(10).to_dict(orient='records')

        # Auto-detect column roles by name heuristics
        mapping: Dict[str, Optional[str]] = {
            'coa_col': None, 'date_col': None,
            'balance_col': None, 'currency_col': None,
            'segment_col': None,
        }
        coa_hints = ['kodbalans', 'coa_code', 'account_code', 'account', 'gl_code', 'coa']
        date_hints = ['curdate', 'date', 'snapshot_date', 'period', 'posting_date']
        bal_hints = ['ostatall', 'balance', 'amount', 'balance_uzs', 'debit', 'saldo']
        cur_hints = ['kodvaluta', 'currency', 'currency_code', 'ccy']
        segment_hints = ['segment', 'business_line', 'bu_code', 'p_segment', 'lob', 'division', 'cbu']

        lower_cols = {c.lower(): c for c in columns}
        for hint in coa_hints:
            if hint in lower_cols:
                mapping['coa_col'] = lower_cols[hint]; break
        for hint in date_hints:
            if hint in lower_cols:
                mapping['date_col'] = lower_cols[hint]; break
        for hint in bal_hints:
            if hint in lower_cols:
                mapping['balance_col'] = lower_cols[hint]; break
        for hint in cur_hints:
            if hint in lower_cols:
                mapping['currency_col'] = lower_cols[hint]; break
        for hint in segment_hints:
            if hint in lower_cols:
                mapping['segment_col'] = lower_cols[hint]; break

        return {
            'table': table_name,
            'columns': columns,
            'row_count': len(df),
            'sample': sample,
            'auto_mapping': mapping,
        }

    def ingest_from_dwh(
        self,
        connection_id: int,
        source_table: str = "balans_ato",
        fiscal_years: List[int] = None,
        column_mapping: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Ingest balance data from DWH and store in baseline_data table.

        column_mapping keys (all optional, defaults to balans_ato layout):
            coa_col, date_col, balance_col, currency_col, segment_col (optional — Retail/Corporate slice)
            priznall_col (default PRIZNALL), signed_priznall (default True) — when True, balance is
            (PRIZNALL='1' ? +amount : 0) - (PRIZNALL='0' ? amount : 0) per row, then SUM; else plain SUM(balance_col).
        """
        if fiscal_years is None:
            current_year = datetime.now().year
            fiscal_years = [current_year - 3, current_year - 2, current_year - 1]

        from app.services.balans_signed_balance import sql_signed_balance_sum

        cm = column_mapping or {}
        coa_col = cm.get('coa_col', 'KODBALANS')
        date_col = cm.get('date_col', 'CURDATE')
        balance_col = cm.get('balance_col', 'OSTATALL')
        currency_col = cm.get('currency_col', 'KODVALUTA')
        segment_col = _norm_segment(cm.get('segment_col'))
        priznall_col = cm.get('priznall_col') or 'PRIZNALL'
        use_signed = cm.get('signed_priznall')
        if use_signed is None:
            use_signed = True
        if use_signed:
            bal_uzs_expr = sql_signed_balance_sum(balance_col, priznall_col)
            orig_col = cm.get('balance_orig_col', 'OSTATALLVAL')
            bal_orig_expr = sql_signed_balance_sum(orig_col, priznall_col)
        else:
            bal_uzs_expr = f"SUM([{balance_col}])"
            bal_orig_expr = bal_uzs_expr

        conn = self.db.query(DWHConnection).filter(DWHConnection.id == connection_id).first()
        if not conn:
            raise ValueError(f"Connection {connection_id} not found")

        dwh_engine = get_engine_for_connection(conn)
        batch_id = str(uuid.uuid4())[:8]

        years_str = ",".join(str(y) for y in fiscal_years)
        if segment_col:
            query = f"""
                SELECT
                    [{coa_col}] as coa_code,
                    YEAR([{date_col}]) as fiscal_year,
                    MONTH([{date_col}]) as fiscal_month,
                    [{date_col}] as snapshot_date,
                    {bal_uzs_expr} as balance_uzs,
                    {bal_orig_expr} as balance_orig,
                    [{currency_col}] as currency_code,
                    CAST([{segment_col}] AS NVARCHAR(100)) AS segment_key
                FROM [{source_table}]
                WHERE YEAR([{date_col}]) IN ({years_str})
                GROUP BY [{coa_col}], YEAR([{date_col}]), MONTH([{date_col}]), [{date_col}], [{currency_col}], [{segment_col}]
            """
        else:
            query = f"""
                SELECT
                    [{coa_col}] as coa_code,
                    YEAR([{date_col}]) as fiscal_year,
                    MONTH([{date_col}]) as fiscal_month,
                    [{date_col}] as snapshot_date,
                    {bal_uzs_expr} as balance_uzs,
                    {bal_orig_expr} as balance_orig,
                    [{currency_col}] as currency_code
                FROM [{source_table}]
                WHERE YEAR([{date_col}]) IN ({years_str})
                GROUP BY [{coa_col}], YEAR([{date_col}]), MONTH([{date_col}]), [{date_col}], [{currency_col}]
            """

        try:
            df = _dataframe_from_sql(dwh_engine, query)

            if df.empty:
                return {"status": "warning", "message": "No data found in DWH for the specified years", "rows": 0}

            currency_map = {0: 'UZS', 840: 'USD', 978: 'EUR', 826: 'GBP', 392: 'JPY', 643: 'RUB'}

            self.db.query(BaselineData).filter(
                BaselineData.fiscal_year.in_(fiscal_years)
            ).delete(synchronize_session=False)

            rows_inserted = 0
            for _, row in df.iterrows():
                fiscal_year = int(row['fiscal_year'])
                fiscal_month = int(row['fiscal_month'])
                snapshot_dt = row['snapshot_date']
                if isinstance(snapshot_dt, str):
                    snapshot_dt = datetime.strptime(snapshot_dt, '%Y-%m-%d').date()
                elif hasattr(snapshot_dt, 'date'):
                    snapshot_dt = snapshot_dt.date()

                currency_code = int(row['currency_code']) if pd.notna(row['currency_code']) else 0
                currency = currency_map.get(currency_code, 'UZS')

                seg_raw = row['segment_key'] if segment_col and 'segment_key' in row else None
                if seg_raw is not None and pd.notna(seg_raw):
                    sk = str(seg_raw).strip()
                    segment_key_val = sk if sk else None
                else:
                    segment_key_val = None

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
                    segment_key=segment_key_val,
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

    def _rollup_baseline_for_segment(
        self,
        fiscal_years: List[int],
        segment_filter: Optional[str],
        account_codes: Optional[Collection[str]] = None,
    ) -> List[Any]:
        """
        One row per (account_code, fiscal_year, fiscal_month) via SQL aggregation.
        segment_filter set: only rows whose segment_key matches (case-insensitive, trimmed).
        segment_filter None: consolidate all segment_key values (SUM).
        Canonical T-SQL reference: app/sql/baseline_rollup_monthly.sql
        """
        if not fiscal_years:
            return []

        trim_seg = func.rtrim(func.ltrim(func.coalesce(BaselineData.segment_key, "")))
        stmt = (
            select(
                BaselineData.account_code,
                BaselineData.fiscal_year,
                BaselineData.fiscal_month,
                func.sum(func.coalesce(BaselineData.balance_uzs, 0)).label("balance_uzs"),
                func.sum(func.coalesce(BaselineData.balance, 0)).label("balance"),
            )
            .where(BaselineData.fiscal_year.in_(fiscal_years))
            .group_by(
                BaselineData.account_code,
                BaselineData.fiscal_year,
                BaselineData.fiscal_month,
            )
            .order_by(
                BaselineData.account_code,
                BaselineData.fiscal_year,
                BaselineData.fiscal_month,
            )
        )
        if account_codes:
            stmt = stmt.where(BaselineData.account_code.in_(list(account_codes)))
        sf = _norm_segment(segment_filter)
        if sf is not None:
            stmt = stmt.where(func.upper(trim_seg) == sf.upper())

        rows = self.db.execute(stmt).all()
        merged: List[Any] = []
        for r in rows:
            m = r._mapping
            merged.append(
                SimpleNamespace(
                    account_code=m["account_code"],
                    fiscal_year=int(m["fiscal_year"]),
                    fiscal_month=int(m["fiscal_month"]),
                    balance_uzs=float(m["balance_uzs"] or 0),
                    balance=float(m["balance"] or 0),
                )
            )
        return merged
    
    def calculate_baseline_by_groups(
        self,
        target_fiscal_year: int,
        source_years: List[int] = None,
        method: str = "simple_average",
        segment_filter: Optional[str] = None,
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
            segment_filter: If set, only DWH rows with this segment_key; if None, consolidated (sum all segments)
        
        Returns:
            Dict with 4-level hierarchical baseline data
        """
        if source_years is None:
            source_years = [target_fiscal_year - 3, target_fiscal_year - 2, target_fiscal_year - 1]
        
        # COA map + FP&A product taxonomy (replaces CBU budgeting group as primary bucket)
        coa_map = {}
        coa_records = self.db.query(COADimension).filter(COADimension.is_active == True).all()
        for coa in coa_records:
            tax = resolve_coa_taxonomy(coa)
            coa_map[coa.coa_code] = {
                'coa_code': coa.coa_code,
                'coa_name': coa.coa_name,
                'product_key': tax['product_key'],
                'product_label_en': tax['product_label_en'],
                'product_pillar': tax['product_pillar'],
                'display_group': tax['display_group'],
                'bs_flag': coa.bs_flag,
                'bs_name': coa.bs_name,
                'bs_group': coa.bs_group,
                'bs_group_name': coa.group_name,
            }

        if not self.db.query(BaselineData.id).filter(BaselineData.fiscal_year.in_(source_years)).first():
            return {"status": "warning", "message": "No baseline data found", "groups": [], "hierarchy": []}

        work_records = self._rollup_baseline_for_segment(source_years, segment_filter)
        if not work_records:
            return {
                "status": "warning",
                "message": "No baseline data for this segment filter",
                "groups": [],
                "hierarchy": [],
                "segment_filter": _norm_segment(segment_filter),
            }

        # {bs_flag: {product_key: {accounts}}}
        hierarchy_data = {}

        for record in work_records:
            coa_info = coa_map.get(record.account_code)
            if not coa_info:
                continue

            bs_flag = coa_info['bs_flag'] or 0
            product_key = coa_info['product_key']
            coa_code = record.account_code
            month = record.fiscal_month

            if bs_flag not in hierarchy_data:
                hierarchy_data[bs_flag] = {
                    'bs_name': coa_info['bs_name'],
                    'products': {},
                }

            if product_key not in hierarchy_data[bs_flag]['products']:
                hierarchy_data[bs_flag]['products'][product_key] = {
                    'product_label_en': coa_info['product_label_en'],
                    'product_pillar': coa_info['product_pillar'],
                    'display_group': coa_info['display_group'],
                    'accounts': {},
                }

            pdata = hierarchy_data[bs_flag]['products'][product_key]
            if coa_code not in pdata['accounts']:
                pdata['accounts'][coa_code] = {
                    'coa_name': coa_info['coa_name'],
                    'bs_group': coa_info['bs_group'],
                    'bs_group_name': coa_info['bs_group_name'],
                    'months': {m: [] for m in range(1, 13)},
                }

            pdata['accounts'][coa_code]['months'][month].append(float(getattr(record, 'balance_uzs', 0) or 0))
        
        is_ml = method in ('ai_forecast', 'ml_trend')

        def calc_average(values: List[float]) -> float:
            if not values:
                return 0
            if method == "simple_average":
                return sum(values) / len(values)
            elif method == "weighted_average":
                weights = [1, 2, 3][:len(values)]
                return sum(v * w for v, w in zip(values, weights)) / sum(weights)
            return sum(values) / len(values)

        # FP&A display logic:
        # Balance Sheet accounts (bs_flag 1-4): total = December year-end balance
        #   (summing monthly BS balances is meaningless — each month IS the balance)
        # Income/Expense accounts (bs_flag 5+): total = annual sum of monthly flows
        BS_FLAGS = {1, 2, 3, 4, 9}  # Assets, Liabilities, Capital, legacy 4, Off-balance (9)

        def get_representative_total(monthly: dict, bs_flag_val: int) -> float:
            """
            For BS items: year-end balance (Dec).
            For P&L items: annual sum.
            avg_monthly is provided separately for reference.
            """
            if bs_flag_val in BS_FLAGS:
                # Year-end balance = December projected balance
                return monthly.get(12, 0)
            return sum(monthly.values())

        result_hierarchy = []
        flat_groups = []

        for bs_flag in sorted(hierarchy_data.keys()):
            bs_data = hierarchy_data[bs_flag]
            is_bs_item = bs_flag in BS_FLAGS
            bs_class_result = {
                'bs_flag': bs_flag,
                'bs_name': bs_data['bs_name'],
                'is_balance_sheet': is_bs_item,
                'bs_groups': [],
                'total': 0,
                'total_label': 'Year-end Balance' if is_bs_item else 'Annual Total',
            }

            synthetic_bs = {
                'bs_group': '0',
                'group_name': 'FP&A products',
                'budgeting_groups': [],
                'total': 0,
            }

            for product_key in sorted(bs_data['products'].keys()):
                bg_data = bs_data['products'][product_key]
                bg_monthly = {m: 0 for m in range(1, 13)}
                accounts_result = []

                for coa_code, acc_data in bg_data['accounts'].items():
                    if is_ml:
                        from app.services.ml_baseline_service import compute_ml_baseline
                        ml_monthly, ml_lower, ml_upper = compute_ml_baseline(
                            method, acc_data['months'], source_years, target_fiscal_year,
                        )
                        acc_monthly = ml_monthly
                    else:
                        acc_monthly = {}
                        for month in range(1, 13):
                            acc_monthly[month] = calc_average(acc_data['months'][month])

                    for month in range(1, 13):
                        bg_monthly[month] += acc_monthly.get(month, 0)

                    acc_rep_total = get_representative_total(acc_monthly, bs_flag)
                    accounts_result.append({
                        'coa_code': coa_code,
                        'coa_name': acc_data['coa_name'],
                        'bs_group': acc_data.get('bs_group'),
                        'bs_group_name': acc_data.get('bs_group_name'),
                        'monthly': acc_monthly,
                        'total': acc_rep_total,
                        'avg_monthly': sum(acc_monthly.values()) / 12 if acc_monthly else 0,
                    })

                bg_rep_total = get_representative_total(bg_monthly, bs_flag)
                bg_avg_monthly = sum(bg_monthly.values()) / 12
                label = bg_data['product_label_en']
                bg_result = {
                    'product_key': product_key,
                    'product_label_en': label,
                    'product_pillar': bg_data['product_pillar'],
                    'display_group': bg_data['display_group'],
                    'fpna_product_key': product_key,
                    'fpna_product_label_en': label,
                    'budgeting_group_id': None,
                    'budgeting_group_name': label,
                    'monthly': bg_monthly,
                    'total': bg_rep_total,
                    'avg_monthly': bg_avg_monthly,
                    'accounts': sorted(accounts_result, key=lambda x: x['coa_code']),
                }
                synthetic_bs['budgeting_groups'].append(bg_result)
                synthetic_bs['total'] += bg_rep_total

                flat_groups.append({
                    'product_key': product_key,
                    'product_label_en': label,
                    'product_pillar': bg_data['product_pillar'],
                    'display_group': bg_data['display_group'],
                    'fpna_product_key': product_key,
                    'fpna_product_label_en': label,
                    'budgeting_group_id': None,
                    'budgeting_group_name': label,
                    'bs_flag': bs_flag,
                    'bs_class_name': bs_data['bs_name'],
                    'is_balance_sheet': is_bs_item,
                    'bs_group': '0',
                    'bs_group_name': 'FP&A products',
                    'monthly': bg_monthly,
                    'total': bg_rep_total,
                    'avg_monthly': bg_avg_monthly,
                    'details': [{
                        'coa_code': a['coa_code'],
                        'coa_name': a['coa_name'],
                        'bs_group': a.get('bs_group'),
                        'bs_group_name': a.get('bs_group_name'),
                        'monthly': a['monthly'],
                        'total': a['total'],
                        'avg_monthly': a['avg_monthly'],
                    } for a in accounts_result],
                })

            synthetic_bs['budgeting_groups'].sort(key=lambda x: x['product_label_en'] or '')
            bs_class_result['bs_groups'].append(synthetic_bs)
            bs_class_result['total'] = synthetic_bs['total']
            result_hierarchy.append(bs_class_result)

        return {
            "status": "success",
            "target_fiscal_year": target_fiscal_year,
            "source_years": source_years,
            "method": method,
            "segment_filter": _norm_segment(segment_filter),
            "total_label": "Year-end Balance (BS) / Annual Total (P&L)",
            "hierarchy": result_hierarchy,
            "groups": flat_groups,
            "group_count": len(flat_groups),
        }
    
    # =========================================================================
    # STEP 2: Create Budget Plans for Departments
    # =========================================================================
    
    def create_department_plans(
        self,
        fiscal_year: int,
        user_id: int,
        baseline_data: Optional[Dict[str, Any]] = None,
        source_years: Optional[List[int]] = None,
        method: str = "simple_average",
    ) -> Dict[str, Any]:
        """
        Create budget plans for all active departments.

        If any department has ``dwh_segment_value`` set, baselines are recalculated per
        department (segment slice from ``baseline_data.segment_key`` after ingest).
        Otherwise a single ``baseline_data`` (or freshly computed consolidated baseline) is reused.
        """
        departments = self.db.query(Department).filter(Department.is_active == True).order_by(Department.id).all()
        
        if not departments:
            return {"status": "warning", "message": "No active departments found"}
        
        use_per_dept_baseline = any(
            _norm_segment(getattr(d, 'dwh_segment_value', None)) for d in departments
        )

        shared_baseline: Optional[Dict[str, Any]] = None
        if not use_per_dept_baseline:
            shared_baseline = baseline_data
            if not shared_baseline or shared_baseline.get('status') != 'success':
                shared_baseline = self.calculate_baseline_by_groups(
                    target_fiscal_year=fiscal_year,
                    source_years=source_years,
                    method=method,
                    segment_filter=None,
                )
            if shared_baseline.get('status') != 'success':
                return {
                    "status": "warning",
                    "message": shared_baseline.get('message', 'Baseline calculation failed'),
                    "plans_created": 0,
                    "plans": [],
                }

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

            baseline_warn = None
            if use_per_dept_baseline:
                seg = _norm_segment(dept.dwh_segment_value)
                baseline_for_dept = self.calculate_baseline_by_groups(
                    target_fiscal_year=fiscal_year,
                    source_years=source_years,
                    method=method,
                    segment_filter=seg,
                )
                if baseline_for_dept.get('status') != 'success':
                    baseline_warn = baseline_for_dept.get('message')
                    baseline_for_dept = {'groups': []}
            else:
                baseline_for_dept = shared_baseline or {'groups': []}
            
            explicit_products = [
                r.product_key
                for r in self.db.query(DepartmentProductAccess).filter(
                    DepartmentProductAccess.department_id == dept.id
                ).all()
            ]
            if explicit_products:
                assigned_keys = set(explicit_products)
            else:
                legacy_gids = [bg.group_id for bg in dept.budgeting_groups]
                assigned_keys = set(product_keys_for_legacy_budgeting_groups(self.db, legacy_gids))

            all_keys = {g.get('product_key') for g in baseline_for_dept.get('groups', []) if g.get('product_key')}
            if not assigned_keys or dept.is_baseline_only:
                assigned_keys = set(all_keys)

            groups_added = 0
            for group_data in baseline_for_dept.get('groups', []):
                pk = group_data.get('product_key')
                if pk not in assigned_keys:
                    continue

                monthly = group_data['monthly']
                is_locked = pk == 'UNCLASSIFIED'

                plan_group = BudgetPlanGroup(
                    plan_id=plan.id,
                    fpna_product_key=pk,
                    fpna_product_label_en=group_data.get('product_label_en') or group_data.get('budgeting_group_name'),
                    budgeting_group_id=group_data.get('budgeting_group_id'),
                    budgeting_group_name=group_data.get('budgeting_group_name'),
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
                groups_added += 1
            
            plan.recalculate_totals()
            entry = {
                'department_id': dept.id,
                'department_code': dept.code,
                'plan_id': plan.id,
                'groups_count': groups_added,
            }
            if use_per_dept_baseline:
                entry['dwh_segment_value'] = _norm_segment(dept.dwh_segment_value)
            if baseline_warn:
                entry['baseline_warning'] = baseline_warn
            plans_created.append(entry)
        
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
            driver_type = None
            monthly_rates = None

            if driver_code:
                driver_record = self.db.query(Driver).filter(
                    Driver.code == driver_code
                ).first()
                if driver_record:
                    driver_type = driver_record.driver_type.value if driver_record.driver_type else None

                    # Look up per-month DriverValue entries for this driver + group
                    dv_q = self.db.query(DriverValue).filter(
                        DriverValue.driver_id == driver_record.id,
                        DriverValue.fiscal_year == plan.fiscal_year,
                        DriverValue.month.isnot(None),
                    )
                    if group.fpna_product_key:
                        dv_q = dv_q.filter(DriverValue.fpna_product_key == group.fpna_product_key)
                    elif group.budgeting_group_id is not None:
                        dv_q = dv_q.filter(DriverValue.budgeting_group_id == group.budgeting_group_id)
                    dv_rows = dv_q.all()
                    if dv_rows:
                        monthly_rates = {dv.month: dv.value for dv in dv_rows}

            group.apply_driver(driver_rate, driver_type=driver_type,
                               monthly_rates=monthly_rates)
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
    # STEP 3b: Bulk Apply Drivers (CFO)
    # =========================================================================

    def apply_historic_yoy_to_baseline_pl_plan(self, fiscal_year: int, user_id: int) -> Dict[str, Any]:
        """
        Set group **adjusted** months on the Baseline Reference plan by summing, per COA line,
        ``baseline_m × (1 + YoY% for that row's p_l_flag)`` from BaselineData (same YoY as
        /pl-driver-proposals).

        This fixes the case where every P&L line showed the same variance because the UI used
        a **single** group ratio for all accounts in one mega-group.
        """
        from app.services.pl_driver_proposal_service import compute_pl_yoy_proposals

        props = compute_pl_yoy_proposals(self.db, fiscal_year_target=fiscal_year)
        raw_hf = props.get("historic_by_flag") or {}
        hbf = {int(k): float(v) for k, v in raw_hf.items()}

        if not hbf:
            w = props.get("warnings") or []
            msg = (
                w[0]
                if w
                else "No historic YoY by p_l_flag — ingest BaselineData for the source years."
            )
            return {
                "status": "warning",
                "message": msg,
                "groups_updated": 0,
                "source_years": props.get("source_years"),
                "warnings": w,
            }

        baseline_dept = (
            self.db.query(Department)
            .filter(Department.is_baseline_only == True, Department.is_active == True)
            .first()
        )
        if not baseline_dept:
            return {"status": "error", "message": "No Baseline Reference department found", "groups_updated": 0}

        plan = (
            self.db.query(BudgetPlan)
            .options(joinedload(BudgetPlan.groups).joinedload(BudgetPlanGroup.details))
            .filter(
                BudgetPlan.department_id == baseline_dept.id,
                BudgetPlan.fiscal_year == fiscal_year,
                BudgetPlan.is_current == True,
            )
            .first()
        )
        if not plan:
            return {"status": "error", "message": "No current baseline plan for this fiscal year", "groups_updated": 0}

        all_coa = set()
        for g in plan.groups:
            for d in g.details or []:
                all_coa.add(d.coa_code)
        coa_map = {
            c.coa_code: c
            for c in self.db.query(COADimension).filter(COADimension.coa_code.in_(all_coa)).all()
        }

        updated = 0
        for group in plan.groups:
            if group.is_locked or group.locked_by_cfo:
                continue
            details = list(group.details or [])
            if not details:
                continue
            has_pl = any(
                coa_map.get(d.coa_code) is not None and coa_map[d.coa_code].p_l_flag is not None
                for d in details
            )
            if not has_pl:
                continue
            for mname in MONTHS:
                s = Decimal(0)
                for d in details:
                    coa = coa_map.get(d.coa_code)
                    b = getattr(d, f"baseline_{mname}", None)
                    if b is None:
                        b = Decimal(0)
                    elif not isinstance(b, Decimal):
                        b = Decimal(str(b))
                    if not coa or coa.p_l_flag is None:
                        s += b
                        continue
                    y = hbf.get(int(coa.p_l_flag), 0.0)
                    mult = Decimal(1) + (Decimal(str(y)) / Decimal(100))
                    s += (b * mult).quantize(Decimal("0.01"))
                setattr(group, f"adjusted_{mname}", s)
            group.recalculate_totals()
            group.driver_code = "DWH_YOY_P_L_FLAG"
            group.driver_name = "DWH BaselineData YoY (per p_l_flag)"
            group.driver_type = "inflation_rate"
            group.driver_rate = None
            group.last_edited_by_user_id = user_id
            group.last_edited_at = datetime.now(timezone.utc)
            updated += 1

        plan.recalculate_totals()
        self.db.commit()

        return {
            "status": "success",
            "groups_updated": updated,
            "source_years": props.get("source_years"),
            "applied_p_l_flag_yoy": [{"p_l_flag": f, "yoy_pct": hbf[f]} for f in sorted(hbf.keys())],
        }

    def bulk_apply_drivers(self, fiscal_year: int, user_id: int) -> Dict[str, Any]:
        """
        Apply assigned drivers to all draft/rejected budget plan groups.

        For each group that has a DriverGroupAssignment, look up the driver
        record and any per-month DriverValue entries, then apply the
        type-specific formula.
        """
        plans = self.db.query(BudgetPlan).filter(
            BudgetPlan.fiscal_year == fiscal_year,
            BudgetPlan.is_current == True,
            BudgetPlan.status.in_([BudgetPlanStatus.DRAFT, BudgetPlanStatus.REJECTED]),
        ).all()

        if not plans:
            return {"status": "warning", "message": "No editable plans found"}

        assignments = self.db.query(DriverGroupAssignment).filter(
            DriverGroupAssignment.is_active == True,
        ).all()
        assign_by_product: Dict[str, DriverGroupAssignment] = {}
        assign_by_bg: Dict[int, DriverGroupAssignment] = {}
        for a in assignments:
            if a.fpna_product_key:
                pk = a.fpna_product_key
                if pk not in assign_by_product or a.is_default:
                    assign_by_product[pk] = a
            if a.budgeting_group_id is not None:
                bg = a.budgeting_group_id
                if bg not in assign_by_bg or a.is_default:
                    assign_by_bg[bg] = a

        applied = 0
        skipped = 0

        for plan in plans:
            for group in plan.groups:
                if group.is_locked or group.locked_by_cfo:
                    skipped += 1
                    continue

                assignment = None
                if group.fpna_product_key:
                    assignment = assign_by_product.get(group.fpna_product_key)
                if not assignment and group.budgeting_group_id is not None:
                    assignment = assign_by_bg.get(group.budgeting_group_id)
                if not assignment:
                    skipped += 1
                    continue

                driver = assignment.driver
                driver_type = driver.driver_type.value if driver.driver_type else None
                rate = driver.default_value or Decimal(0)

                dv_q = self.db.query(DriverValue).filter(
                    DriverValue.driver_id == driver.id,
                    DriverValue.fiscal_year == fiscal_year,
                    DriverValue.month.isnot(None),
                )
                if group.fpna_product_key:
                    dv_rows = dv_q.filter(
                        DriverValue.fpna_product_key == group.fpna_product_key
                    ).all()
                elif group.budgeting_group_id is not None:
                    dv_rows = dv_q.filter(
                        DriverValue.budgeting_group_id == group.budgeting_group_id
                    ).all()
                else:
                    dv_rows = []
                monthly_rates = {dv.month: dv.value for dv in dv_rows} if dv_rows else None

                group.apply_driver(rate, driver_type=driver_type,
                                   monthly_rates=monthly_rates)
                group.driver_code = driver.code
                group.driver_name = driver.name_en
                group.last_edited_by_user_id = user_id
                group.last_edited_at = datetime.now(timezone.utc)
                applied += 1

            plan.recalculate_totals()

        self.db.commit()

        return {
            "status": "success",
            "fiscal_year": fiscal_year,
            "groups_applied": applied,
            "groups_skipped": skipped,
        }

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
    # STEP 4b: CEO Consolidated Approval
    # =========================================================================

    def get_consolidated_plan(self, fiscal_year: int) -> Dict[str, Any]:
        """Aggregate all CFO_APPROVED plans into a CEO-facing consolidated view."""
        plans = self.db.query(BudgetPlan).filter(
            BudgetPlan.fiscal_year == fiscal_year,
            BudgetPlan.is_current == True,
        ).all()

        cfo_approved = [p for p in plans if p.status == BudgetPlanStatus.CFO_APPROVED]
        ceo_approved = [p for p in plans if p.status == BudgetPlanStatus.CEO_APPROVED]
        all_ready = len(cfo_approved) + len(ceo_approved)

        # Summary by BS class
        bs_class_totals: Dict[str, Dict] = {}
        dept_summaries = []

        for plan in cfo_approved + ceo_approved:
            dept = plan.department
            dept_summaries.append({
                'department_id': dept.id,
                'department_code': dept.code,
                'department_name': dept.name_en,
                'status': plan.status.value,
                'total_baseline': float(plan.total_baseline or 0),
                'total_adjusted': float(plan.total_adjusted or 0),
                'total_variance': float(plan.total_variance or 0),
                'total_variance_pct': float(plan.total_variance_pct or 0),
                'cfo_approved_at': plan.cfo_approved_at.isoformat() if plan.cfo_approved_at else None,
            })

            for g in plan.groups:
                cls_name = g.bs_class_name or f"Class {g.bs_flag}"
                if cls_name not in bs_class_totals:
                    bs_class_totals[cls_name] = {'baseline': 0, 'adjusted': 0}
                bs_class_totals[cls_name]['baseline'] += float(g.baseline_total or 0)
                bs_class_totals[cls_name]['adjusted'] += float(g.adjusted_total or 0)

        grand_baseline = sum(v['baseline'] for v in bs_class_totals.values())
        grand_adjusted = sum(v['adjusted'] for v in bs_class_totals.values())

        return {
            'fiscal_year': fiscal_year,
            'total_plans': len(plans),
            'cfo_approved_count': len(cfo_approved),
            'ceo_approved_count': len(ceo_approved),
            'ready_for_ceo': len(cfo_approved),
            'grand_baseline': round(grand_baseline, 2),
            'grand_adjusted': round(grand_adjusted, 2),
            'grand_variance': round(grand_adjusted - grand_baseline, 2),
            'bs_class_totals': [
                {'bs_class': k, 'baseline': round(v['baseline'], 2), 'adjusted': round(v['adjusted'], 2),
                 'variance': round(v['adjusted'] - v['baseline'], 2)}
                for k, v in sorted(bs_class_totals.items())
            ],
            'departments': dept_summaries,
        }

    def ceo_approve_consolidated(self, fiscal_year: int, user_id: int, comment: Optional[str] = None) -> Dict[str, Any]:
        """CEO approves the entire fiscal year plan as a consolidated package."""
        plans = self.db.query(BudgetPlan).filter(
            BudgetPlan.fiscal_year == fiscal_year,
            BudgetPlan.status == BudgetPlanStatus.CFO_APPROVED,
            BudgetPlan.is_current == True,
        ).all()

        if not plans:
            raise ValueError("No CFO-approved plans found for CEO sign-off")

        for plan in plans:
            old_status = plan.status
            plan.status = BudgetPlanStatus.CEO_APPROVED
            plan.ceo_approved_at = datetime.now(timezone.utc)
            plan.ceo_approved_by_user_id = user_id
            plan.ceo_approval_comment = comment

            approval = BudgetPlanApproval(
                plan_id=plan.id,
                level=ApprovalLevel.CEO,
                action=ApprovalAction.APPROVE,
                user_id=user_id,
                comment=comment,
                status_before=old_status.value,
                status_after=plan.status.value,
            )
            self.db.add(approval)

        self.db.commit()

        return {
            'status': 'success',
            'fiscal_year': fiscal_year,
            'plans_approved': len(plans),
        }

    def ceo_reject_consolidated(self, fiscal_year: int, user_id: int, reason: str) -> Dict[str, Any]:
        """CEO rejects - reverts all CFO_APPROVED plans back so CFO can revise."""
        plans = self.db.query(BudgetPlan).filter(
            BudgetPlan.fiscal_year == fiscal_year,
            BudgetPlan.status == BudgetPlanStatus.CFO_APPROVED,
            BudgetPlan.is_current == True,
        ).all()

        if not plans:
            raise ValueError("No CFO-approved plans to reject")

        for plan in plans:
            old_status = plan.status
            plan.status = BudgetPlanStatus.REJECTED
            plan.rejected_at = datetime.now(timezone.utc)
            plan.rejected_by_user_id = user_id
            plan.rejection_reason = reason

            approval = BudgetPlanApproval(
                plan_id=plan.id,
                level=ApprovalLevel.CEO,
                action=ApprovalAction.REJECT,
                user_id=user_id,
                comment=reason,
                status_before=old_status.value,
                status_after=plan.status.value,
            )
            self.db.add(approval)

        self.db.commit()

        return {
            'status': 'success',
            'fiscal_year': fiscal_year,
            'plans_rejected': len(plans),
        }

    # =========================================================================
    # STEP 5: Export to DWH
    # =========================================================================
    
    def export_to_dwh(
        self,
        fiscal_year: int,
        connection_id: int,
        target_table: str = "year_budget_approved",
    ) -> Dict[str, Any]:
        """
        Export approved budget plans to DWH.

        Exports CEO_APPROVED plans (falls back to CFO_APPROVED for backwards compat).
        Also saves to local approved_budgets_local table for analytics.
        """
        conn = self.db.query(DWHConnection).filter(DWHConnection.id == connection_id).first()
        if not conn:
            raise ValueError(f"Connection {connection_id} not found")

        # Prefer CEO_APPROVED, fall back to CFO_APPROVED
        plans = self.db.query(BudgetPlan).filter(
            BudgetPlan.fiscal_year == fiscal_year,
            BudgetPlan.status == BudgetPlanStatus.CEO_APPROVED,
            BudgetPlan.is_current == True
        ).all()

        if not plans:
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
                        'submitted_at': plan.submitted_at.isoformat() if plan.submitted_at else None,
                        'dept_approved_at': plan.dept_approved_at.isoformat() if plan.dept_approved_at else None,
                        'cfo_approved_at': plan.cfo_approved_at.isoformat() if plan.cfo_approved_at else None,
                        'ceo_approved_at': plan.ceo_approved_at.isoformat() if plan.ceo_approved_at else None,
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

        # Build and export account-level fact table (DWH source grain)
        detail_table = target_table + '_detail'
        fact_rows_exported = 0
        try:
            fact_df = self.build_fact_table(fiscal_year, batch_id, plans)
            if not fact_df.empty:
                if not _table_exists(dwh_engine, 'dbo', detail_table):
                    _create_table_from_df(dwh_engine, fact_df, 'dbo', detail_table)
                _insert_dataframe(dwh_engine, fact_df, 'dbo', detail_table, dialect)
                fact_rows_exported = len(fact_df)
                logger.info(f"Exported {fact_rows_exported} fact rows to {detail_table}")
        except Exception as e:
            logger.warning(f"Fact table export failed (non-fatal): {e}")

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
            "fact_rows_exported": fact_rows_exported,
            "target_table": target_table,
            "detail_table": detail_table,
        }
    
    def build_fact_table(
        self,
        fiscal_year: int,
        batch_id: str,
        plans: List[BudgetPlan],
    ) -> pd.DataFrame:
        """
        Build account-level fact rows mirroring DWH source grain.

        One row per (coa_code, month) with baseline, adjusted, driver info, and version.
        Suitable for direct join with actuals for fact-vs-plan and ML pipelines.
        """
        from app.models.baseline import ApprovedBudgetFact

        # Clear previous export for this FY
        self.db.query(ApprovedBudgetFact).filter(
            ApprovedBudgetFact.fiscal_year == fiscal_year,
        ).delete(synchronize_session=False)

        fact_rows = []
        version = 1  # Increment on re-export if needed

        for plan in plans:
            dept = plan.department
            for group in plan.groups:
                for detail in group.details:
                    for month_idx, month_name in enumerate(MONTHS, 1):
                        baseline_val = float(getattr(detail, f'baseline_{month_name}', 0) or 0)

                        # Apply the same driver ratio as the group level
                        group_baseline_m = float(getattr(group, f'baseline_{month_name}', 0) or 0)
                        group_adjusted_m = float(getattr(group, f'adjusted_{month_name}', 0) or 0)

                        if group_baseline_m != 0:
                            ratio = group_adjusted_m / group_baseline_m
                        else:
                            ratio = 1.0

                        adjusted_val = round(baseline_val * ratio, 2)

                        row = {
                            'coa_code': detail.coa_code,
                            'fiscal_year': fiscal_year,
                            'fiscal_month': month_idx,
                            'currency': 'UZS',
                            'baseline_amount': baseline_val,
                            'adjusted_amount': adjusted_val,
                            'variance': round(adjusted_val - baseline_val, 2),
                            'coa_name': detail.coa_name,
                            'bs_flag': group.bs_flag,
                            'bs_class_name': group.bs_class_name,
                            'bs_group': group.bs_group,
                            'bs_group_name': group.bs_group_name,
                            'budgeting_group_id': group.budgeting_group_id,
                            'budgeting_group_name': group.budgeting_group_name,
                            'department_code': dept.code,
                            'department_name': dept.name_en,
                            'driver_code': group.driver_code,
                            'driver_rate': float(group.driver_rate) if group.driver_rate else None,
                            'driver_type': group.driver_type,
                            'version': version,
                            'plan_status': plan.status.value,
                            'export_batch_id': batch_id,
                            'submitted_at': plan.submitted_at,
                            'dept_approved_at': plan.dept_approved_at,
                            'cfo_approved_at': plan.cfo_approved_at,
                            'ceo_approved_at': plan.ceo_approved_at,
                            'exported_at': datetime.now(timezone.utc),
                        }

                        fact_rows.append(row)

                        fact = ApprovedBudgetFact(**row)
                        self.db.add(fact)

        self.db.commit()

        if fact_rows:
            return pd.DataFrame(fact_rows)
        return pd.DataFrame()

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
            'all_cfo_approved': all(p.status in (BudgetPlanStatus.CFO_APPROVED, BudgetPlanStatus.CEO_APPROVED, BudgetPlanStatus.EXPORTED) for p in plans) and len(plans) > 0,
            'all_ceo_approved': all(p.status in (BudgetPlanStatus.CEO_APPROVED, BudgetPlanStatus.EXPORTED) for p in plans) and len(plans) > 0,
            'ready_for_ceo': sum(1 for p in plans if p.status == BudgetPlanStatus.CFO_APPROVED),
            'ready_for_export': sum(1 for p in plans if p.status in (BudgetPlanStatus.CEO_APPROVED, BudgetPlanStatus.CFO_APPROVED)),
        }
