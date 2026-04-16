"""
Analysis API - Year-over-Year Delta, Plan vs Historical, Variance Decomposition

Provides analytical views over DWH snapshot data and approved plans:
  1. YoY Delta: year-by-year change at budget group and driver level
  2. Plan Delta: historical baseline vs plan with variance distribution
  3. Driver Contribution: which drivers explain the variance
  4. Dashboard KPIs: aggregated metrics for the executive dashboard
"""

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from decimal import Decimal

from app.database import get_db
from app.models.user import User
from app.models.baseline import BaselineData, ApprovedBudgetFact
from app.models.budget_plan import BudgetPlan, BudgetPlanGroup, BudgetPlanStatus
from app.models.coa_dimension import BudgetingGroup
from app.utils.dependencies import get_current_active_user

router = APIRouter(prefix="/analysis", tags=["Analysis"])

MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']


def _fmt(v) -> float:
    if v is None:
        return 0.0
    return round(float(v), 2)


# =========================================================================
# 1. YEAR-OVER-YEAR DELTA (budget group level)
# =========================================================================

@router.get("/yoy-delta/{fiscal_year}")
def get_yoy_delta(
    fiscal_year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Compute year-over-year delta at budget-group level.

    Uses baseline_data for the 3 prior years plus the plan year.
    Returns per-group: amounts for each year, absolute & pct deltas,
    and compound annual growth rate (CAGR).
    """
    years = [fiscal_year - 3, fiscal_year - 2, fiscal_year - 1]

    # Historical totals by budgeting group from baseline_data joined to COA hierarchy
    year_data: Dict[int, Dict[int, float]] = {y: {} for y in years}

    for yr in years:
        rows = db.execute(text("""
            SELECT bg.id AS group_id, bg.name AS group_name,
                   SUM(bd.balance_uzs) AS total
            FROM baseline_data bd
            JOIN coa_dimension cd ON cd.coa_code = bd.account_code
            JOIN budgeting_groups bg ON bg.id = cd.budgeting_groups
            WHERE bd.fiscal_year = :yr
            GROUP BY bg.id, bg.name
        """), {"yr": yr}).fetchall()
        for r in rows:
            year_data[yr][r.group_id] = _fmt(r.total)

    # Plan data from budget_plan_groups (current approved/exported plans)
    plan_groups = db.query(
        BudgetPlanGroup.budgeting_group_id,
        BudgetPlanGroup.budgeting_group_name,
        BudgetPlanGroup.driver_code,
        BudgetPlanGroup.driver_type,
        BudgetPlanGroup.driver_rate,
        func.sum(BudgetPlanGroup.baseline_total).label('baseline_total'),
        func.sum(BudgetPlanGroup.adjusted_total).label('adjusted_total'),
    ).join(BudgetPlan).filter(
        BudgetPlan.fiscal_year == fiscal_year,
        BudgetPlan.is_current == True,
    ).group_by(
        BudgetPlanGroup.budgeting_group_id,
        BudgetPlanGroup.budgeting_group_name,
        BudgetPlanGroup.driver_code,
        BudgetPlanGroup.driver_type,
        BudgetPlanGroup.driver_rate,
    ).all()

    plan_by_group: Dict[int, Dict[str, Any]] = {}
    for pg in plan_groups:
        plan_by_group[pg.budgeting_group_id] = {
            'name': pg.budgeting_group_name,
            'driver_code': pg.driver_code,
            'driver_type': pg.driver_type,
            'driver_rate': _fmt(pg.driver_rate),
            'baseline': _fmt(pg.baseline_total),
            'adjusted': _fmt(pg.adjusted_total),
        }

    all_group_ids = set()
    for yd in year_data.values():
        all_group_ids.update(yd.keys())
    all_group_ids.update(plan_by_group.keys())

    group_names = {}
    for bg in db.query(BudgetingGroup).filter(BudgetingGroup.id.in_(all_group_ids)).all():
        group_names[bg.id] = bg.name

    result_groups = []
    for gid in sorted(all_group_ids):
        amounts = {yr: year_data[yr].get(gid, 0) for yr in years}
        plan_info = plan_by_group.get(gid, {})
        amounts[fiscal_year] = plan_info.get('adjusted', plan_info.get('baseline', 0))

        deltas = {}
        all_years = years + [fiscal_year]
        for i in range(1, len(all_years)):
            prev = amounts[all_years[i - 1]]
            curr = amounts[all_years[i]]
            d = curr - prev
            pct = round(d / abs(prev) * 100, 2) if prev != 0 else 0
            deltas[f"{all_years[i-1]}_to_{all_years[i]}"] = {
                'absolute': round(d, 2),
                'percent': pct,
            }

        first_val = amounts[years[0]]
        last_val = amounts[fiscal_year]
        n = len(all_years) - 1
        if first_val > 0 and last_val > 0 and n > 0:
            cagr = round((pow(last_val / first_val, 1 / n) - 1) * 100, 2)
        else:
            cagr = None

        result_groups.append({
            'budgeting_group_id': gid,
            'budgeting_group_name': group_names.get(gid, plan_info.get('name', f'Group {gid}')),
            'amounts': {str(k): round(v, 2) for k, v in amounts.items()},
            'deltas': deltas,
            'cagr': cagr,
            'driver_code': plan_info.get('driver_code'),
            'driver_type': plan_info.get('driver_type'),
            'driver_rate': plan_info.get('driver_rate'),
        })

    grand_totals = {}
    for yr in years + [fiscal_year]:
        grand_totals[str(yr)] = round(sum(g['amounts'].get(str(yr), 0) for g in result_groups), 2)

    return {
        'fiscal_year': fiscal_year,
        'years_analyzed': [str(y) for y in years + [fiscal_year]],
        'groups': result_groups,
        'grand_totals': grand_totals,
    }


# =========================================================================
# 2. PLAN VS HISTORICAL DELTA with VARIANCE DECOMPOSITION
# =========================================================================

@router.get("/plan-delta/{fiscal_year}")
def get_plan_delta(
    fiscal_year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Compare plan vs last historical year with variance decomposition.

    Shows:
    - Per-group: prior year actual, plan baseline, plan adjusted
    - Variance components: organic growth (baseline change) vs driver impact
    - Proportion of total variance contributed by each group
    - Driver-level aggregation of variance contribution
    """
    prior_year = fiscal_year - 1

    # Prior year actuals by group
    prior_rows = db.execute(text("""
        SELECT bg.id AS group_id, bg.name AS group_name,
               SUM(bd.balance_uzs) AS total
        FROM baseline_data bd
        JOIN coa_dimension cd ON cd.coa_code = bd.account_code
        JOIN budgeting_groups bg ON bg.id = cd.budgeting_groups
        WHERE bd.fiscal_year = :yr
        GROUP BY bg.id, bg.name
    """), {"yr": prior_year}).fetchall()

    prior_by_group = {r.group_id: _fmt(r.total) for r in prior_rows}

    # Plan data
    plan_groups = db.query(
        BudgetPlanGroup.budgeting_group_id,
        BudgetPlanGroup.budgeting_group_name,
        BudgetPlanGroup.driver_code,
        BudgetPlanGroup.driver_type,
        BudgetPlanGroup.driver_rate,
        func.sum(BudgetPlanGroup.baseline_total).label('baseline_total'),
        func.sum(BudgetPlanGroup.adjusted_total).label('adjusted_total'),
    ).join(BudgetPlan).filter(
        BudgetPlan.fiscal_year == fiscal_year,
        BudgetPlan.is_current == True,
    ).group_by(
        BudgetPlanGroup.budgeting_group_id,
        BudgetPlanGroup.budgeting_group_name,
        BudgetPlanGroup.driver_code,
        BudgetPlanGroup.driver_type,
        BudgetPlanGroup.driver_rate,
    ).all()

    all_group_ids = set(prior_by_group.keys())
    for pg in plan_groups:
        all_group_ids.add(pg.budgeting_group_id)

    group_names = {}
    for bg in db.query(BudgetingGroup).filter(BudgetingGroup.id.in_(all_group_ids)).all():
        group_names[bg.id] = bg.name

    plan_map = {}
    for pg in plan_groups:
        plan_map[pg.budgeting_group_id] = pg

    total_variance = 0
    groups_result = []

    for gid in sorted(all_group_ids):
        prior_actual = prior_by_group.get(gid, 0)
        pg = plan_map.get(gid)

        baseline = _fmt(pg.baseline_total) if pg else 0
        adjusted = _fmt(pg.adjusted_total) if pg else 0
        driver_code = pg.driver_code if pg else None
        driver_type = pg.driver_type if pg else None
        driver_rate = _fmt(pg.driver_rate) if pg else 0

        # Total change: plan adjusted - prior year actual
        total_change = adjusted - prior_actual

        # Decompose: organic = baseline - prior, driver_impact = adjusted - baseline
        organic_change = baseline - prior_actual
        driver_impact = adjusted - baseline

        total_variance += total_change

        groups_result.append({
            'budgeting_group_id': gid,
            'budgeting_group_name': group_names.get(gid, pg.budgeting_group_name if pg else f'Group {gid}'),
            'prior_year_actual': prior_actual,
            'plan_baseline': baseline,
            'plan_adjusted': adjusted,
            'total_change': round(total_change, 2),
            'total_change_pct': round(total_change / abs(prior_actual) * 100, 2) if prior_actual != 0 else 0,
            'organic_change': round(organic_change, 2),
            'driver_impact': round(driver_impact, 2),
            'driver_code': driver_code,
            'driver_type': driver_type,
            'driver_rate': driver_rate,
        })

    # Compute proportion of total variance
    for g in groups_result:
        if total_variance != 0:
            g['proportion_pct'] = round(g['total_change'] / abs(total_variance) * 100, 2)
        else:
            g['proportion_pct'] = 0

    # Driver-level aggregation
    driver_summary: Dict[str, Dict[str, Any]] = {}
    for g in groups_result:
        dc = g['driver_code'] or 'No Driver'
        if dc not in driver_summary:
            driver_summary[dc] = {
                'driver_code': dc,
                'driver_type': g['driver_type'],
                'groups_count': 0,
                'total_prior': 0,
                'total_plan': 0,
                'total_change': 0,
                'organic_total': 0,
                'driver_impact_total': 0,
            }
        ds = driver_summary[dc]
        ds['groups_count'] += 1
        ds['total_prior'] += g['prior_year_actual']
        ds['total_plan'] += g['plan_adjusted']
        ds['total_change'] += g['total_change']
        ds['organic_total'] += g['organic_change']
        ds['driver_impact_total'] += g['driver_impact']

    driver_agg = []
    for dc, ds in sorted(driver_summary.items()):
        ds['total_change_pct'] = round(ds['total_change'] / abs(ds['total_prior']) * 100, 2) if ds['total_prior'] != 0 else 0
        ds['proportion_pct'] = round(ds['total_change'] / abs(total_variance) * 100, 2) if total_variance != 0 else 0
        driver_agg.append(ds)

    # Grand totals
    grand_prior = sum(g['prior_year_actual'] for g in groups_result)
    grand_baseline = sum(g['plan_baseline'] for g in groups_result)
    grand_adjusted = sum(g['plan_adjusted'] for g in groups_result)

    return {
        'fiscal_year': fiscal_year,
        'prior_year': prior_year,
        'groups': groups_result,
        'driver_breakdown': driver_agg,
        'grand_totals': {
            'prior_year_actual': round(grand_prior, 2),
            'plan_baseline': round(grand_baseline, 2),
            'plan_adjusted': round(grand_adjusted, 2),
            'total_variance': round(total_variance, 2),
            'total_variance_pct': round(total_variance / abs(grand_prior) * 100, 2) if grand_prior != 0 else 0,
            'organic_change': round(grand_baseline - grand_prior, 2),
            'driver_impact': round(grand_adjusted - grand_baseline, 2),
        },
    }


# =========================================================================
# 3. MONTHLY TREND (for sparklines / charts on dashboard)
# =========================================================================

@router.get("/monthly-trend/{fiscal_year}")
def get_monthly_trend(
    fiscal_year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Monthly breakdown across years for trend visualization."""
    years = [fiscal_year - 2, fiscal_year - 1, fiscal_year]

    result: Dict[str, Any] = {'fiscal_year': fiscal_year, 'years': {}}

    for yr in years[:-1]:
        rows = db.execute(text("""
            SELECT fiscal_month, SUM(balance_uzs) AS total
            FROM baseline_data
            WHERE fiscal_year = :yr
            GROUP BY fiscal_month
            ORDER BY fiscal_month
        """), {"yr": yr}).fetchall()
        monthly = [0.0] * 12
        for r in rows:
            if 1 <= r.fiscal_month <= 12:
                monthly[r.fiscal_month - 1] = _fmt(r.total)
        result['years'][str(yr)] = monthly

    # Plan year from budget_plan_groups
    plan_monthly = [0.0] * 12
    groups = db.query(BudgetPlanGroup).join(BudgetPlan).filter(
        BudgetPlan.fiscal_year == fiscal_year,
        BudgetPlan.is_current == True,
    ).all()

    for g in groups:
        for mi, mn in enumerate(MONTHS):
            plan_monthly[mi] += _fmt(getattr(g, f'adjusted_{mn}', 0))

    result['years'][str(fiscal_year)] = [round(v, 2) for v in plan_monthly]

    return result


# =========================================================================
# 4. DASHBOARD KPIs
# =========================================================================

@router.get("/dashboard-kpis/{fiscal_year}")
def get_dashboard_kpis(
    fiscal_year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Aggregate KPIs for the executive dashboard."""
    prior_year = fiscal_year - 1

    # Plan totals
    plan_agg = db.query(
        func.count(BudgetPlan.id).label('plan_count'),
        func.sum(BudgetPlan.total_baseline).label('total_baseline'),
        func.sum(BudgetPlan.total_adjusted).label('total_adjusted'),
    ).filter(
        BudgetPlan.fiscal_year == fiscal_year,
        BudgetPlan.is_current == True,
    ).first()

    # Status breakdown
    status_rows = db.query(
        BudgetPlan.status,
        func.count(BudgetPlan.id).label('cnt'),
    ).filter(
        BudgetPlan.fiscal_year == fiscal_year,
        BudgetPlan.is_current == True,
    ).group_by(BudgetPlan.status).all()

    status_counts = {}
    for sr in status_rows:
        status_counts[sr.status.value if hasattr(sr.status, 'value') else str(sr.status)] = sr.cnt

    plan_total = _fmt(plan_agg.total_adjusted) if plan_agg else 0
    baseline_total = _fmt(plan_agg.total_baseline) if plan_agg else 0

    # YoY comparison: plan adjusted vs plan baseline (= prior year actual from DWH)
    # total_baseline IS the prior year's actual imported from DWH, so this is the
    # correct apples-to-apples comparison within the same scope of budget groups.
    prior_total = baseline_total
    yoy_change = plan_total - baseline_total
    yoy_pct = round(yoy_change / abs(baseline_total) * 100, 2) if baseline_total != 0 else 0

    # Departments with plans
    dept_count = db.query(func.count(func.distinct(BudgetPlan.department_id))).filter(
        BudgetPlan.fiscal_year == fiscal_year,
        BudgetPlan.is_current == True,
    ).scalar() or 0

    # Groups count
    group_count = db.query(func.count(func.distinct(BudgetPlanGroup.budgeting_group_id))).join(BudgetPlan).filter(
        BudgetPlan.fiscal_year == fiscal_year,
        BudgetPlan.is_current == True,
    ).scalar() or 0

    # Driver coverage: groups with a driver assigned
    driver_coverage = db.query(func.count(func.distinct(BudgetPlanGroup.budgeting_group_id))).join(BudgetPlan).filter(
        BudgetPlan.fiscal_year == fiscal_year,
        BudgetPlan.is_current == True,
        BudgetPlanGroup.driver_code.isnot(None),
    ).scalar() or 0

    return {
        'fiscal_year': fiscal_year,
        'plan_count': plan_agg.plan_count if plan_agg else 0,
        'total_baseline': baseline_total,
        'total_adjusted': plan_total,
        'driver_impact': round(plan_total - baseline_total, 2),
        'prior_year_total': prior_total,
        'yoy_change': round(yoy_change, 2),
        'yoy_change_pct': yoy_pct,
        'status_counts': status_counts,
        'departments': dept_count,
        'budget_groups': group_count,
        'driver_coverage': driver_coverage,
        'driver_coverage_pct': round(driver_coverage / group_count * 100, 1) if group_count > 0 else 0,
    }
