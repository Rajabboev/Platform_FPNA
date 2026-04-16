"""
Suggested P&L growth deltas from DWH BaselineData: YoY between two fiscal years.

For a budget target year T (e.g. 2026), defaults use actuals Y_new = T-1 vs Y_old = T-2
(e.g. 2025 vs 2024). Maps INCOME taxonomy products to PL_GROWTH_* driver codes and
p_l_flag buckets for AI / CFO overrides.

YoY % for proposals uses **same-calendar-month growth, then arithmetic mean**:
for each month m in 1..12, pct_m = (new_m - old_m) / max(|old_m|, eps) * 100 on rolled-up
totals for that month; the suggested rate is mean(pct_m) over months where |old_m| >= eps.
This avoids a single distorted annual total (e.g. compositing errors) driving unrealistic YoY.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.baseline import BaselineData
from app.models.coa_dimension import COADimension
from app.services.budget_planning_service import BudgetPlanningService
from app.services.coa_product_taxonomy import resolve_coa_taxonomy, effective_pl_flag_for_planning

# Balance-sheet classes: use Dec-only in _annual_flow (not sum of 12 months).
# Include 9 = off-balance per coa_dimension; 4 kept for legacy data.
BS_FLAGS = {1, 2, 3, 4, 9}

PRODUCT_TO_DRIVER: Dict[str, str] = {
    "REV_INTEREST": "PL_GROWTH_REV_INTEREST",
    "REV_NONINTEREST": "PL_GROWTH_REV_NONINT",
    "EXP_INTEREST": "PL_GROWTH_EXP_INTEREST",
    "EXP_NONINTEREST": "PL_GROWTH_EXP_NONINT",
    "OPEX": "PL_GROWTH_OPEX",
    "TAX": "PL_GROWTH_TAX",
    "CAPEX_PNL": "PL_GROWTH_CAPEX_PNL",
}

PL_FLAG_LABELS: Dict[int, str] = {
    1: "Interest Income",
    2: "Interest Expense",
    3: "Provisions",
    4: "Non-Interest Income",
    5: "Non-Interest Expense",
    7: "Operating Expenses (OPEX)",
    8: "Income Tax",
}

PL_FLAGS_ORDER = [1, 2, 4, 5, 7, 3, 8]

# When COA rows have p_l_flag but resolve_coa_taxonomy() is not INCOME (legacy / mixed BS+P&L
# rows), prod_totals stays empty. Roll up BaselineData by p_l_flag into FP&A product buckets.
PRODUCT_FLAG_BUCKETS: Dict[str, Tuple[int, ...]] = {
    "REV_INTEREST": (1,),
    "EXP_INTEREST": (2,),
    "REV_NONINTEREST": (4,),
    "EXP_NONINTEREST": (3, 5),  # provisions + non-interest expense → one PL growth bucket
    "OPEX": (7,),
    "TAX": (8,),
    "CAPEX_PNL": (),  # no standard CBU p_l_flag; leave to taxonomy path only
}


def _annual_flow(month_vals: Dict[int, float], bs_flag_val: int) -> float:
    if bs_flag_val in BS_FLAGS:
        return float(month_vals.get(12, 0.0))
    return float(sum(month_vals.get(m, 0.0) for m in range(1, 13)))


def _mean_same_month_yoy(
    old_by_month: Dict[int, float],
    new_by_month: Dict[int, float],
    *,
    eps: float = 1e-6,
) -> Tuple[float, int]:
    """
    Mean of monthly YoY %: for each m, (new_m - old_m) / max(|old_m|, eps) * 100.
    Skips months where |old_m| < eps and |new_m| < eps (both negligible).
    Skips months where |old_m| < eps but |new_m| >= eps (unstable ratio).
    Returns (mean_pct, months_used).
    """
    pcts: List[float] = []
    for m in range(1, 13):
        o = float(old_by_month.get(m, 0.0))
        n = float(new_by_month.get(m, 0.0))
        if abs(o) < eps and abs(n) < eps:
            continue
        if abs(o) < eps:
            continue
        pcts.append((n - o) / max(abs(o), eps) * 100.0)
    if not pcts:
        return 0.0, 0
    return sum(pcts) / len(pcts), len(pcts)


def compute_pl_yoy_proposals(
    db: Session,
    fiscal_year_target: int,
    year_old: Optional[int] = None,
    year_new: Optional[int] = None,
    segment_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Suggested YoY % uses mean of same-month YoY on rolled-up monthly totals (see module doc).
    basis_year_old / basis_year_new remain **annual** totals (Dec for BS-class COA, sum of
    months for flows) for magnitude context. annual_yoy_reference_pct is the legacy
    single-ratio YoY on those annual totals for comparison.
    """
    if year_old is None:
        year_old = fiscal_year_target - 2
    if year_new is None:
        year_new = fiscal_year_target - 1

    svc = BudgetPlanningService(db)
    if not db.query(BaselineData.id).filter(BaselineData.fiscal_year.in_([year_old, year_new])).first():
        return {
            "fiscal_year_target": fiscal_year_target,
            "source_years": {"year_old": year_old, "year_new": year_new},
            "by_product": [],
            "by_pl_flag": [],
            "historic_by_flag": {},
            "warnings": ["No BaselineData for the selected fiscal years."],
        }

    work = svc._rollup_baseline_for_segment([year_old, year_new], segment_filter)

    coa_rows = db.query(COADimension).filter(COADimension.is_active == True).all()
    coa_map = {c.coa_code: c for c in coa_rows}

    acc_monthly: Dict[Tuple[str, int], Dict[int, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    for r in work:
        if coa_map.get(r.account_code) is None:
            continue
        acc_monthly[(r.account_code, r.fiscal_year)][r.fiscal_month] += float(
            r.balance_uzs or 0
        )

    prod_totals: Dict[Tuple[str, int], float] = defaultdict(float)
    flag_totals: Dict[Tuple[int, int], float] = defaultdict(float)
    prod_monthly: Dict[Tuple[str, int], Dict[int, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    flag_monthly: Dict[Tuple[int, int], Dict[int, float]] = defaultdict(
        lambda: defaultdict(float)
    )

    for (acc, fy), mon in acc_monthly.items():
        coa = coa_map.get(acc)
        if not coa:
            continue
        bs_flag = int(coa.bs_flag or 0)
        tax = resolve_coa_taxonomy(coa)
        mon_d = dict(mon)
        annual = _annual_flow(mon_d, bs_flag)

        if tax["product_pillar"] == "INCOME":
            pk = tax["product_key"]
            if pk in PRODUCT_TO_DRIVER:
                prod_totals[(pk, fy)] += annual
                for m in range(1, 13):
                    prod_monthly[(pk, fy)][m] += float(mon_d.get(m, 0.0))

        eff_pf = effective_pl_flag_for_planning(coa, tax)
        if eff_pf is not None:
            flag_totals[(eff_pf, fy)] += annual
            for m in range(1, 13):
                flag_monthly[(eff_pf, fy)][m] += float(mon_d.get(m, 0.0))

    eps = 1e-6

    def yoy_pct(t_old: float, t_new: float) -> float:
        base = max(abs(t_old), eps)
        return (t_new - t_old) / base * 100.0

    by_product: List[Dict[str, Any]] = []
    for pk in sorted(PRODUCT_TO_DRIVER.keys()):
        t_old = prod_totals.get((pk, year_old), 0.0)
        t_new = prod_totals.get((pk, year_new), 0.0)
        if abs(t_old) < eps and abs(t_new) < eps:
            continue
        ann_pct = yoy_pct(t_old, t_new)
        mo_old = dict(prod_monthly.get((pk, year_old), {}))
        mo_new = dict(prod_monthly.get((pk, year_new), {}))
        pct, n_mo = _mean_same_month_yoy(mo_old, mo_new, eps=eps)
        if n_mo == 0:
            pct = ann_pct
        by_product.append(
            {
                "product_key": pk,
                "driver_code": PRODUCT_TO_DRIVER[pk],
                "basis_year_old": round(t_old, 2),
                "basis_year_new": round(t_new, 2),
                "annual_yoy_reference_pct": round(ann_pct, 4),
                "months_used_for_yoy": n_mo,
                "yoy_pct": round(pct, 4),
                "suggested_driver_delta_pct": round(pct, 4),
            }
        )

    fallback_note: Optional[str] = None
    if not by_product:
        # Taxonomy often leaves P&L lines off pillar INCOME; p_l_flag rollups still work.
        for pk, flags in sorted(PRODUCT_FLAG_BUCKETS.items()):
            if not flags or pk not in PRODUCT_TO_DRIVER:
                continue
            t_old = sum(flag_totals.get((f, year_old), 0.0) for f in flags)
            t_new = sum(flag_totals.get((f, year_new), 0.0) for f in flags)
            if abs(t_old) < eps and abs(t_new) < eps:
                continue
            ann_pct = yoy_pct(t_old, t_new)
            mo_old_d: Dict[int, float] = defaultdict(float)
            mo_new_d: Dict[int, float] = defaultdict(float)
            for f in flags:
                for m, v in flag_monthly.get((f, year_old), {}).items():
                    mo_old_d[int(m)] += float(v)
                for m, v in flag_monthly.get((f, year_new), {}).items():
                    mo_new_d[int(m)] += float(v)
            pct, n_mo = _mean_same_month_yoy(dict(mo_old_d), dict(mo_new_d), eps=eps)
            if n_mo == 0:
                pct = ann_pct
            by_product.append(
                {
                    "product_key": pk,
                    "driver_code": PRODUCT_TO_DRIVER[pk],
                    "basis_year_old": round(t_old, 2),
                    "basis_year_new": round(t_new, 2),
                    "annual_yoy_reference_pct": round(ann_pct, 4),
                    "months_used_for_yoy": n_mo,
                    "yoy_pct": round(pct, 4),
                    "suggested_driver_delta_pct": round(pct, 4),
                    "source": "p_l_flag_rollup",
                }
            )
        if by_product:
            fallback_note = (
                "Product YoY derived from BaselineData rollups by effective P&L bucket "
                "(p_l_flag, p_l_group when it matches a standard code, or FP&A INCOME taxonomy) "
                "because no lines were attributed to pillar INCOME on the product path."
            )

    by_pl_flag: List[Dict[str, Any]] = []
    historic_by_flag: Dict[int, float] = {}
    for flag in PL_FLAGS_ORDER:
        if flag not in PL_FLAG_LABELS:
            continue
        t_old = flag_totals.get((flag, year_old), 0.0)
        t_new = flag_totals.get((flag, year_new), 0.0)
        if abs(t_old) < eps and abs(t_new) < eps:
            continue
        ann_pct = yoy_pct(t_old, t_new)
        mo_old = dict(flag_monthly.get((flag, year_old), {}))
        mo_new = dict(flag_monthly.get((flag, year_new), {}))
        pct, n_mo = _mean_same_month_yoy(mo_old, mo_new, eps=eps)
        if n_mo == 0:
            pct = ann_pct
        historic_by_flag[flag] = round(pct, 4)
        by_pl_flag.append(
            {
                "p_l_flag": flag,
                "category": PL_FLAG_LABELS[flag],
                "basis_year_old": round(t_old, 2),
                "basis_year_new": round(t_new, 2),
                "annual_yoy_reference_pct": round(ann_pct, 4),
                "months_used_for_yoy": n_mo,
                "yoy_pct": round(pct, 4),
                "suggested_category_adjustment_pct": round(pct, 4),
            }
        )

    warnings: List[str] = []
    if fallback_note:
        warnings.append(fallback_note)
    warnings.append(
        f"Suggested YoY = mean of same-month YoY ({year_old} vs {year_new}); "
        f"see annual_yoy_reference_pct for legacy single-year ratio on annual bases."
    )
    if any(int(x.get("months_used_for_yoy") or 0) < 6 for x in by_pl_flag):
        warnings.append(
            "Some categories averaged fewer than 6 monthly pairs (sparse BaselineData months)."
        )

    return {
        "fiscal_year_target": fiscal_year_target,
        "source_years": {"year_old": year_old, "year_new": year_new},
        "segment_filter": segment_filter,
        "yoy_method": "mean_same_month_yoy",
        "by_product": by_product,
        "by_pl_flag": by_pl_flag,
        "historic_by_flag": historic_by_flag,
        "warnings": warnings,
    }


def anchor_category_adjustments(
    category_adjustments: List[Dict[str, Any]],
    historic_by_flag: Dict[int, float],
    *,
    year_old: int,
    year_new: int,
    max_deviation_pp: float = 25.0,
    global_cap: float = 40.0,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    - Categories omitted by the model are filled with historic YoY.
    - Each change_pct is capped to [-global_cap, global_cap].
    - If the model deviates more than max_deviation_pp from historic YoY, pull toward historic
      (keeps stress/optimistic scenarios interpretable vs actual trends).
    """
    incoming: Dict[int, Dict[str, Any]] = {}
    for adj in category_adjustments:
        f = int(adj["p_l_flag"])
        incoming[f] = adj

    notes: List[str] = []
    out: List[Dict[str, Any]] = []
    default_note = f"Historic YoY {year_old}→{year_new} (BaselineData)"

    for flag in PL_FLAGS_ORDER:
        h = float(historic_by_flag.get(flag, 0.0))
        if flag in incoming:
            adj = incoming[flag]
            pct = float(adj["change_pct"])
            orig = pct
            pct = max(-global_cap, min(global_cap, pct))
            if abs(pct - h) > max_deviation_pp:
                sgn = 1.0 if pct > h else -1.0
                pct = h + sgn * max_deviation_pp
                notes.append(
                    f"p_l_flag {flag}: clamped adjustment from {orig:.2f}% toward "
                    f"historic {h:.2f}% (max deviation {max_deviation_pp}pp)."
                )
            rationale = (adj.get("rationale") or "").strip()
            out.append(
                {
                    "p_l_flag": flag,
                    "change_pct": round(pct, 4),
                    "rationale": rationale,
                }
            )
        else:
            notes.append(
                f"p_l_flag {flag}: filled with historic YoY {h:.2f}% ({default_note})."
            )
            out.append(
                {
                    "p_l_flag": flag,
                    "change_pct": round(h, 4),
                    "rationale": default_note,
                }
            )

    return out, notes
