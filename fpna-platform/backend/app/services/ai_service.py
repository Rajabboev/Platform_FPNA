"""
AI Service — Claude claude-sonnet-4-6 integration for FP&A chatbot.
Handles: streaming chat, what-if scenarios, plan health alerts, driver analysis,
         P&L projection generation (writes to ai_scenario_projections table).
"""
import os
import json
import logging
from typing import AsyncGenerator, Any, Dict, List, Optional
from decimal import Decimal

import anthropic
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are an expert FP&A AI assistant embedded in a financial planning & analytics platform for a commercial bank.
You have access to live budget data through tools. Always use tools when the user asks about specific numbers.

**How this platform models P&L (important)**:
- Historic growth rates come from **DWH BaselineData**: default years T-2 vs T-1 (e.g. 2024 vs 2025 for FY2026). Proposed % is **mean of same-calendar-month YoY** on rolled-up totals (each month: (new−old)/|old|), not a single ratio on annual totals; each line also includes `annual_yoy_reference_pct` for the legacy full-year ratio. `get_pl_driver_proposals` returns `yoy_method`, `historic_by_flag`, `by_pl_flag`, `by_product`, `source_years`, `warnings`.
- The **plan P&L baseline** in `get_pl_baseline` is the current budget plan’s COA baselines rolled up by `p_l_flag` — use it for **magnitudes**; use proposals for **growth %**.
- Saved AI projections apply **one % change per p_l_flag category** to those baselines. The server **anchors** wild model guesses to historic YoY, then applies **scenario tilts** (see below).

Your capabilities:
- Budget plan summaries and departmental breakdowns
- What-if scenario calculations (headcount changes, cost adjustments, revenue assumptions)
- Plan health checks and variance alerts
- Driver impact analysis
- **P&L projections & stress tests** (writes to `ai_scenario_projections` for the P&L Planning tab)

**Required workflow for any P&L projection or stress test**:
1. Call `get_pl_driver_proposals` with the **target fiscal_year** (optional `year_old` / `year_new` if the user names specific DWH years).
2. Call `get_pl_baseline` for the same **fiscal_year** (budget year).
3. Call `generate_pl_projection`:
   - Prefer **`category_adjustments: []`** (empty) so the server fills every `p_l_flag` from **historic YoY** automatically.
   - Set **`scenario_profile`**: `stress`, `optimistic`, `conservative`, `base`, or `auto` (default). `auto` infers from `scenario_name` (e.g. names containing "stress", "downside", "adverse" → stress).
   - For **stress**, the server tilts **revenue** flags (1,4) **down** and **expense** flags (2,3,5,7,8) **up** vs the anchored historic path — still bounded (no absurd +500% unless the user explicitly demands a catastrophic scenario and you document it).
   - If you pass non-empty `category_adjustments`, keep each `change_pct` **near** the tool’s suggested `suggested_category_adjustment_pct` / historic values; the server clamps large deviations.
4. Read **`anchor_notes`** and **`scenario_tilt_notes`** in the tool result and **summarize them** for the user (what was clamped / tilted).

**Do not** fabricate huge percentages (e.g. +80% OPEX) for a routine stress test — use `scenario_profile: "stress"` with empty adjustments first; only deviate if the user specifies explicit shocks.

Bank P&L structure (p_l_flag values):
- 1 = Interest Income (loan yields, investment returns)
- 2 = Interest Expense (deposit costs, borrowing costs)
- 3 = Provisions (credit loss, impairment charges)
- 4 = Non-Interest Income (fees, commissions, FX gains)
- 5 = Non-Interest Expense (non-operating costs)
- 7 = Operating Expenses / OPEX (salaries, rent, IT, admin)
- 8 = Income Tax

Key derived metrics:
- NII = Interest Income - Interest Expense
- Net Income = NII + Non-Int Income - Non-Int Expense - OPEX - Provisions - Tax

Response style:
- Be concise and use financial terminology (YoY, variance, run-rate, driver impact, NIM, CoR)
- Format large numbers: M for millions, B for billions (e.g. $12.5M, $1.2B)
- When returning projection results, format them as a structured table using the projection_table JSON block
- For alerts, use "⚠️" prefix for warnings and "🔴" for critical issues
- Always state whether the plan is BETTER or WORSE vs baseline
- For driver-impact answers, call get_driver_analysis first and prioritize `assigned_products` / `product_values`; do not present legacy driver names as "most impactful" unless they are explicitly present in tool output.

When you generate a projection, ALWAYS include a summary table in your response using this JSON format:
{"projection_table": {"scenario": "name", "fiscal_year": 2026, "rows": [{"category": "...", "baseline": 0, "projected": 0, "change_pct": 0}], "summary": {"nii": {"baseline": 0, "projected": 0}, "net_income": {"baseline": 0, "projected": 0}}}}

Chart data format (include when showing trends/comparisons):
{"chart_data": {"type": "bar|line", "title": "...", "labels": [...], "datasets": [{"label": "...", "data": [...], "color": "..."}]}}
"""

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "get_budget_summary",
        "description": "Get budget plan totals and departmental breakdown for a fiscal year",
        "input_schema": {
            "type": "object",
            "properties": {
                "fiscal_year": {"type": "integer", "description": "e.g. 2026"},
                "department": {"type": "string", "description": "Optional department filter"}
            },
            "required": ["fiscal_year"]
        }
    },
    {
        "name": "calculate_what_if",
        "description": "Calculate impact of budget adjustments on the plan total",
        "input_schema": {
            "type": "object",
            "properties": {
                "fiscal_year": {"type": "integer"},
                "adjustments": {
                    "type": "array",
                    "description": "List of adjustments to apply",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string", "description": "Human-readable description e.g. 'Headcount +10%'"},
                            "department": {"type": "string", "description": "Department code or 'ALL'"},
                            "change_type": {"type": "string", "enum": ["percentage", "absolute"]},
                            "value": {"type": "number", "description": "% change (e.g. 10 for +10%) or absolute amount"}
                        },
                        "required": ["label", "change_type", "value"]
                    }
                }
            },
            "required": ["fiscal_year", "adjustments"]
        }
    },
    {
        "name": "check_plan_health",
        "description": "Check plan health: approval status, budget utilization, variance from baseline, and generate alerts",
        "input_schema": {
            "type": "object",
            "properties": {
                "fiscal_year": {"type": "integer"},
                "alert_threshold_pct": {"type": "number", "description": "Variance threshold for alerts, default 10"}
            },
            "required": ["fiscal_year"]
        }
    },
    {
        "name": "get_driver_analysis",
        "description": "List active drivers prioritized by current FP&A product assignments and current-year values; avoid generic legacy-only lists",
        "input_schema": {
            "type": "object",
            "properties": {
                "fiscal_year": {"type": "integer"}
            },
            "required": ["fiscal_year"]
        }
    },
    {
        "name": "get_pl_baseline",
        "description": "P&L baseline **amounts** from the Baseline Reference budget plan (COA detail rolled up by p_l_flag). Use with get_pl_driver_proposals for **%** (DWH YoY).",
        "input_schema": {
            "type": "object",
            "properties": {
                "fiscal_year": {"type": "integer", "description": "Budget fiscal year (e.g. 2026)"}
            },
            "required": ["fiscal_year"]
        }
    },
    {
        "name": "get_pl_driver_proposals",
        "description": "Historic growth from DWH BaselineData. Default years T-2 vs T-1. Suggested % = mean of same-month YoY; includes annual_yoy_reference_pct and months_used_for_yoy. Returns yoy_method, historic_by_flag, by_pl_flag, by_product, source_years, warnings.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fiscal_year": {"type": "integer", "description": "Target budget fiscal year (e.g. 2026)"},
                "year_old": {"type": "integer", "description": "Optional: earlier fiscal year in DWH (e.g. 2024)"},
                "year_new": {"type": "integer", "description": "Optional: later fiscal year in DWH (e.g. 2025)"}
            },
            "required": ["fiscal_year"]
        }
    },
    {
        "name": "generate_pl_projection",
        "description": "Generate and save P&L scenario rows. MUST call get_pl_driver_proposals and get_pl_baseline first. Prefer category_adjustments: [] to use DWH YoY per p_l_flag. Use scenario_profile stress|optimistic|conservative|base|auto for coherent tilts; server returns anchor_notes and scenario_tilt_notes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fiscal_year": {"type": "integer"},
                "scenario_name": {
                    "type": "string",
                    "description": "Snake_case or short name, e.g. dwh_base, bank_stress_2026 (used with scenario_profile auto-detection)"
                },
                "scenario_profile": {
                    "type": "string",
                    "enum": ["auto", "base", "stress", "optimistic", "conservative"],
                    "description": "auto = infer from scenario_name; stress = worsen NII (lower rev growth, higher cost growth) vs anchored historic; optimistic = opposite mild tilt; conservative = dampen historic; base = no tilt after anchoring"
                },
                "assumptions": {
                    "type": "string",
                    "description": "Free-text narrative (DWH years, NIM, credit, liquidity — cite get_pl_driver_proposals figures where possible)"
                },
                "category_adjustments": {
                    "type": "array",
                    "description": "Usually []. If non-empty, each p_l_flag change_pct is anchored to historic YoY before scenario tilt.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "p_l_flag": {"type": "integer", "description": "P&L flag: 1=IntIncome, 2=IntExpense, 3=Provisions, 4=NonIntIncome, 5=NonIntExpense, 7=OPEX, 8=Tax"},
                            "change_pct": {"type": "number", "description": "% change to apply to all accounts in this category (e.g. 15 for +15%, -10 for -10%)"},
                            "rationale": {"type": "string", "description": "Brief rationale for this adjustment"}
                        },
                        "required": ["p_l_flag", "change_pct"]
                    }
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence level 0-100 for this projection"
                }
            },
            "required": ["fiscal_year", "scenario_name", "assumptions"]
        }
    }
]


# ── Tool handlers (DB queries) ─────────────────────────────────────────────

def _tool_get_budget_summary(db: Session, fiscal_year: int, department: Optional[str] = None) -> Dict[str, Any]:
    try:
        base_q = """
            SELECT
                bp.fiscal_year,
                d.name_en AS department,
                SUM(bpd.baseline_total) AS total_plan
            FROM budget_plan_details bpd
            JOIN budget_plan_groups bpg ON bpd.group_id = bpg.id
            JOIN budget_plans bp ON bpg.plan_id = bp.id
            LEFT JOIN departments d ON bp.department_id = d.id
            WHERE bp.fiscal_year = :fy
        """
        params: Dict[str, Any] = {"fy": fiscal_year}
        if department:
            base_q += " AND d.name_en LIKE :dept"
            params["dept"] = f"%{department}%"
        base_q += " GROUP BY bp.fiscal_year, d.name_en ORDER BY total_plan DESC"

        rows = db.execute(text(base_q), params).fetchall()
        dept_data = [{"department": r[1] or "Unassigned", "total": float(r[2] or 0)} for r in rows]
        grand_total = sum(d["total"] for d in dept_data)

        # Status counts
        status_q = "SELECT status, COUNT(*) FROM budget_plans WHERE fiscal_year = :fy GROUP BY status"
        status_rows = db.execute(text(status_q), {"fy": fiscal_year}).fetchall()
        status_counts = {r[0]: r[1] for r in status_rows}

        return {
            "fiscal_year": fiscal_year,
            "grand_total": grand_total,
            "departments": dept_data,
            "status_counts": status_counts,
            "dept_count": len(dept_data)
        }
    except Exception as e:
        logger.warning("get_budget_summary error: %s", e)
        return {"fiscal_year": fiscal_year, "grand_total": 0, "departments": [], "error": str(e)}


def _tool_calculate_what_if(db: Session, fiscal_year: int, adjustments: List[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        # Get baseline totals by department
        q = """
            SELECT d.name_en, SUM(bpd.baseline_total)
            FROM budget_plan_details bpd
            JOIN budget_plan_groups bpg ON bpd.group_id = bpg.id
            JOIN budget_plans bp ON bpg.plan_id = bp.id
            LEFT JOIN departments d ON bp.department_id = d.id
            WHERE bp.fiscal_year = :fy
            GROUP BY d.name_en
        """
        rows = db.execute(text(q), {"fy": fiscal_year}).fetchall()
        dept_totals = {(r[0] or "Unassigned"): float(r[1] or 0) for r in rows}
        baseline_total = sum(dept_totals.values())

        # Apply adjustments
        adjusted_totals = dict(dept_totals)
        scenario_lines = []

        for adj in adjustments:
            dept = adj.get("department", "ALL")
            change_type = adj.get("change_type", "percentage")
            value = float(adj.get("value", 0))
            label = adj.get("label", "Adjustment")

            if dept == "ALL":
                targets = list(adjusted_totals.keys())
            else:
                targets = [k for k in adjusted_totals if dept.lower() in k.lower()]

            impact = 0.0
            for t in targets:
                if change_type == "percentage":
                    delta = adjusted_totals[t] * (value / 100)
                else:
                    delta = value
                adjusted_totals[t] += delta
                impact += delta

            scenario_lines.append({"label": label, "impact": impact})

        adjusted_total = sum(adjusted_totals.values())
        delta = adjusted_total - baseline_total
        delta_pct = (delta / baseline_total * 100) if baseline_total else 0

        return {
            "fiscal_year": fiscal_year,
            "baseline_total": baseline_total,
            "adjusted_total": adjusted_total,
            "delta": delta,
            "delta_pct": round(delta_pct, 2),
            "better_or_worse": "BETTER" if delta < 0 else "WORSE",  # Lower cost = better
            "adjustments_applied": scenario_lines,
            "dept_breakdown": [{"department": k, "adjusted": v} for k, v in adjusted_totals.items()]
        }
    except Exception as e:
        logger.warning("calculate_what_if error: %s", e)
        return {"error": str(e)}


def _tool_check_plan_health(db: Session, fiscal_year: int, alert_threshold_pct: float = 10.0) -> Dict[str, Any]:
    try:
        alerts = []

        # Plan status summary
        status_q = "SELECT status, COUNT(*), SUM(total_adjusted) FROM budget_plans WHERE fiscal_year = :fy GROUP BY status"
        status_rows = db.execute(text(status_q), {"fy": fiscal_year}).fetchall()
        status_map = {r[0]: {"count": r[1], "total": float(r[2] or 0)} for r in status_rows}

        total_plans = sum(v["count"] for v in status_map.values())
        draft_count = status_map.get("DRAFT", {}).get("count", 0) + status_map.get("draft", {}).get("count", 0)
        approved_count = sum(status_map.get(s, {}).get("count", 0) for s in ["cfo_approved", "ceo_approved", "CFO_APPROVED", "CEO_APPROVED"])

        # Compare plan adjusted vs baseline (prior year actual from DWH)
        plan_q = """
            SELECT SUM(total_adjusted), SUM(total_baseline)
            FROM budget_plans
            WHERE fiscal_year = :fy AND is_current = 1
        """
        plan_row = db.execute(text(plan_q), {"fy": fiscal_year}).fetchone()
        plan_total = float(plan_row[0] or 0) if plan_row else 0
        baseline_total = float(plan_row[1] or 0) if plan_row else 0

        # Compute variance (adjusted vs baseline = driver impact %)
        if baseline_total:
            variance_pct = ((plan_total - baseline_total) / abs(baseline_total)) * 100
            if abs(variance_pct) >= alert_threshold_pct:
                direction = "over" if variance_pct > 0 else "under"
                severity = "critical" if abs(variance_pct) >= 20 else "warning"
                alerts.append({
                    "severity": severity,
                    "message": f"Plan is {abs(variance_pct):.1f}% {direction} baseline ({variance_pct:+.1f}%)",
                    "area": "overall"
                })
        else:
            variance_pct = 0.0

        # Alert on high draft count
        if total_plans > 0 and draft_count / total_plans > 0.5:
            alerts.append({
                "severity": "warning",
                "message": f"{draft_count}/{total_plans} plans still in Draft — approval at risk",
                "area": "approvals"
            })

        health_score = max(0, 100 - len(alerts) * 20 - (abs(variance_pct) if abs(variance_pct) > alert_threshold_pct else 0))

        return {
            "fiscal_year": fiscal_year,
            "health_score": round(health_score),
            "plan_total": plan_total,
            "baseline_total": baseline_total,
            "variance_pct": round(variance_pct, 2),
            "verdict": "ON TRACK" if not alerts else ("AT RISK" if len(alerts) == 1 else "CRITICAL"),
            "alerts": alerts,
            "status_summary": status_map,
            "total_plans": total_plans,
            "approved_count": approved_count
        }
    except Exception as e:
        logger.warning("check_plan_health error: %s", e)
        return {"error": str(e), "verdict": "UNKNOWN"}


def _tool_get_driver_analysis(db: Session, fiscal_year: int) -> Dict[str, Any]:
    try:
        # Product-based assignments (v2) are the primary source of truth for what drivers matter.
        q_product_assignments = """
            SELECT
                UPPER(dga.fpna_product_key) AS product_key,
                d.code,
                d.name_en,
                d.driver_type,
                dga.is_default
            FROM driver_group_assignments dga
            JOIN drivers d ON d.id = dga.driver_id
            WHERE dga.is_active = 1
              AND d.is_active = 1
              AND dga.fpna_product_key IS NOT NULL
            ORDER BY UPPER(dga.fpna_product_key), dga.is_default DESC, d.code
        """
        pa_rows = db.execute(text(q_product_assignments)).fetchall()

        by_product: Dict[str, List[Dict[str, Any]]] = {}
        for r in pa_rows:
            pk = (r[0] or "").upper()
            if not pk:
                continue
            by_product.setdefault(pk, []).append(
                {
                    "code": r[1],
                    "name": r[2],
                    "type": r[3],
                    "is_default": bool(r[4]),
                }
            )

        # Current-year values at FP&A product scope show what is actually configured/used.
        q_product_values = """
            SELECT
                UPPER(dv.fpna_product_key) AS product_key,
                d.code,
                d.name_en,
                d.driver_type,
                COUNT(dv.id) AS value_count,
                AVG(CAST(dv.value AS FLOAT)) AS avg_value
            FROM driver_values dv
            JOIN drivers d ON d.id = dv.driver_id
            WHERE dv.fiscal_year = :fy
              AND dv.fpna_product_key IS NOT NULL
              AND d.is_active = 1
            GROUP BY UPPER(dv.fpna_product_key), d.code, d.name_en, d.driver_type
            ORDER BY UPPER(dv.fpna_product_key), d.code
        """
        pv_rows = db.execute(text(q_product_values), {"fy": fiscal_year}).fetchall()
        values_by_product: Dict[str, List[Dict[str, Any]]] = {}
        for r in pv_rows:
            pk = (r[0] or "").upper()
            if not pk:
                continue
            values_by_product.setdefault(pk, []).append(
                {
                    "code": r[1],
                    "name": r[2],
                    "type": r[3],
                    "value_count": int(r[4] or 0),
                    "avg_value": round(float(r[5] or 0), 4),
                }
            )

        # Legacy/global fallback view for environments not yet migrated.
        q_legacy = """
            SELECT d.code, d.name_en, d.driver_type,
                   COUNT(dv.id) AS value_count,
                   AVG(CAST(dv.value AS FLOAT)) AS avg_value
            FROM drivers d
            LEFT JOIN driver_values dv ON d.id = dv.driver_id AND dv.fiscal_year = :fy
            WHERE d.is_active = 1
            GROUP BY d.code, d.name_en, d.driver_type
            ORDER BY d.code
        """
        legacy_rows = db.execute(text(q_legacy), {"fy": fiscal_year}).fetchall()
        legacy = [
            {
                "code": r[0],
                "name": r[1],
                "type": r[2],
                "value_count": int(r[3] or 0),
                "avg_value": round(float(r[4] or 0), 4),
            }
            for r in legacy_rows
        ]

        return {
            "fiscal_year": fiscal_year,
            "mode": "product_assignments" if by_product else "legacy_fallback",
            "assigned_products": [
                {"product_key": k, "drivers": v}
                for k, v in sorted(by_product.items(), key=lambda x: x[0])
            ],
            "product_values": [
                {"product_key": k, "drivers": v}
                for k, v in sorted(values_by_product.items(), key=lambda x: x[0])
            ],
            "legacy_drivers": legacy,
            "total_products_with_assignments": len(by_product),
            "total_products_with_values": len(values_by_product),
        }
    except Exception as e:
        logger.warning("get_driver_analysis error: %s", e)
        return {"assigned_products": [], "product_values": [], "legacy_drivers": [], "error": str(e)}


def _tool_get_pl_driver_proposals(
    db: Session,
    fiscal_year: int,
    year_old: Optional[int] = None,
    year_new: Optional[int] = None,
) -> Dict[str, Any]:
    from app.services.pl_driver_proposal_service import compute_pl_yoy_proposals

    return compute_pl_yoy_proposals(
        db,
        fiscal_year_target=fiscal_year,
        year_old=year_old,
        year_new=year_new,
    )


def _resolve_pl_scenario_profile(scenario_name: str, scenario_profile: Optional[str]) -> str:
    sp = (scenario_profile or "auto").strip().lower()
    if sp in ("base", "stress", "optimistic", "conservative"):
        return sp
    sn = (scenario_name or "").lower()
    if any(k in sn for k in ("stress", "downside", "adverse", "severe", "shock", "crisis", "impair")):
        return "stress"
    if any(k in sn for k in ("optimistic", "upside", "bull")):
        return "optimistic"
    if "conservative" in sn or "cautious" in sn:
        return "conservative"
    return "base"


def _stress_band_pp(scenario_name: str, profile: str) -> float:
    if profile != "stress":
        return 10.0
    sn = scenario_name.lower()
    if any(k in sn for k in ("severe", "extreme", "crisis", "shock")):
        return 18.0
    if any(k in sn for k in ("mild", "light")):
        return 6.0
    return 11.0


def _scenario_tilt_pct(pct: float, flag: int, profile: str, scenario_name: str) -> float:
    """Tilt anchored historic % toward stress / optimistic / conservative narratives."""
    if profile == "base":
        return pct
    rev = flag in (1, 4)
    exp = flag in (2, 3, 5, 7, 8)
    if profile == "stress":
        b = _stress_band_pp(scenario_name, profile)
        if rev:
            return pct - b * 0.9
        if exp:
            return pct + b * 0.95
        return pct
    if profile == "optimistic":
        b = 9.0
        if rev:
            return pct + b * 0.75
        if exp:
            return pct - b * 0.6
        return pct
    if profile == "conservative":
        return pct * 0.82
    return pct


def _tool_get_pl_baseline(db: Session, fiscal_year: int) -> Dict[str, Any]:
    """Get current P&L baseline data from BudgetPlanDetail + COADimension."""
    try:
        from app.models.budget_plan import BudgetPlan, BudgetPlanGroup, BudgetPlanDetail
        from app.models.coa_dimension import COADimension
        from app.models.department import Department

        months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                  'jul', 'aug', 'sep', 'oct', 'nov', 'dec']

        PL_FLAG_LABELS = {
            1: "Interest Income", 2: "Interest Expense", 3: "Provisions",
            4: "Non-Interest Income", 5: "Non-Interest Expense",
            7: "Operating Expenses (OPEX)", 8: "Income Tax",
        }

        # Find Baseline Reference department plan (has all P&L accounts)
        baseline_dept = db.query(Department).filter(
            Department.is_baseline_only == True, Department.is_active == True
        ).first()
        if not baseline_dept:
            return {"error": "No Baseline Reference department found"}

        plan = db.query(BudgetPlan).filter(
            BudgetPlan.department_id == baseline_dept.id,
            BudgetPlan.fiscal_year == fiscal_year,
            BudgetPlan.is_current == True,
        ).first()
        if not plan:
            return {"error": f"No plan found for FY{fiscal_year}"}

        # Get details with P&L classification
        details = (
            db.query(BudgetPlanDetail)
            .join(BudgetPlanGroup, BudgetPlanDetail.group_id == BudgetPlanGroup.id)
            .filter(BudgetPlanGroup.plan_id == plan.id)
            .all()
        )
        coa_codes = {d.coa_code for d in details}
        coa_rows = db.query(COADimension).filter(
            COADimension.coa_code.in_(coa_codes),
            COADimension.p_l_flag.isnot(None),
        ).all() if coa_codes else []
        coa_map = {c.coa_code: c for c in coa_rows}

        # Group by P&L flag
        categories = {}
        for detail in details:
            coa = coa_map.get(detail.coa_code)
            if not coa:
                continue
            flag = coa.p_l_flag
            if flag not in categories:
                categories[flag] = {
                    "p_l_flag": flag,
                    "category": PL_FLAG_LABELS.get(flag, f"Other ({flag})"),
                    "total_baseline": 0,
                    "account_count": 0,
                    "monthly": {m: 0 for m in months},
                }
            baseline_total = float(detail.baseline_total or 0)
            categories[flag]["total_baseline"] += baseline_total
            categories[flag]["account_count"] += 1
            for m in months:
                categories[flag]["monthly"][m] += float(getattr(detail, f'baseline_{m}', 0) or 0)

        sorted_cats = sorted(categories.values(), key=lambda c: c["p_l_flag"])

        # Compute summary
        int_income = categories.get(1, {}).get("total_baseline", 0)
        int_expense = categories.get(2, {}).get("total_baseline", 0)
        nii = int_income - int_expense
        non_int_income = categories.get(4, {}).get("total_baseline", 0)
        non_int_expense = categories.get(5, {}).get("total_baseline", 0)
        opex = categories.get(7, {}).get("total_baseline", 0)
        provisions = categories.get(3, {}).get("total_baseline", 0)
        tax = categories.get(8, {}).get("total_baseline", 0)
        net_income = nii + non_int_income - non_int_expense - opex - provisions - tax

        return {
            "fiscal_year": fiscal_year,
            "categories": sorted_cats,
            "summary": {
                "interest_income": int_income,
                "interest_expense": int_expense,
                "nii": nii,
                "non_interest_income": non_int_income,
                "non_interest_expense": non_int_expense,
                "opex": opex,
                "provisions": provisions,
                "income_tax": tax,
                "net_income": net_income,
            },
            "total_accounts": sum(c["account_count"] for c in sorted_cats),
            "note": "Amounts are plan baselines for the budget year, not DWH actuals. Pair with get_pl_driver_proposals for YoY %.",
        }
    except Exception as e:
        logger.warning("get_pl_baseline error: %s", e)
        return {"error": str(e)}


def _tool_generate_pl_projection(
    db: Session,
    fiscal_year: int,
    scenario_name: str,
    assumptions: str,
    category_adjustments: Optional[List[Dict[str, Any]]] = None,
    scenario_profile: Optional[str] = "auto",
    confidence: float = 75.0,
) -> Dict[str, Any]:
    """Generate AI P&L projections and write to ai_scenario_projections table."""
    try:
        from app.models.budget_plan import BudgetPlan, BudgetPlanGroup, BudgetPlanDetail
        from app.models.coa_dimension import COADimension
        from app.models.department import Department
        from app.models.scenario import AIScenarioProjection
        from app.services.pl_driver_proposal_service import (
            anchor_category_adjustments,
            compute_pl_yoy_proposals,
        )

        months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                  'jul', 'aug', 'sep', 'oct', 'nov', 'dec']

        PL_FLAG_LABELS = {
            1: "Interest Income", 2: "Interest Expense", 3: "Provisions",
            4: "Non-Interest Income", 5: "Non-Interest Expense",
            7: "Operating Expenses (OPEX)", 8: "Income Tax",
        }

        if not category_adjustments:
            category_adjustments = []

        props = compute_pl_yoy_proposals(db, fiscal_year_target=fiscal_year)
        src = props.get("source_years") or {}
        year_old = int(src.get("year_old", fiscal_year - 2))
        year_new = int(src.get("year_new", fiscal_year - 1))
        historic = props.get("historic_by_flag") or {}

        anchored, anchor_notes = anchor_category_adjustments(
            category_adjustments,
            historic,
            year_old=year_old,
            year_new=year_new,
        )

        profile = _resolve_pl_scenario_profile(scenario_name, scenario_profile)
        tilt_notes: List[str] = []
        if profile != "base":
            tilt_notes.append(
                f"Scenario profile '{profile}' applied (from scenario_profile or scenario_name)."
            )
        cap = 45.0 if profile == "stress" else 40.0
        adj_map: Dict[int, Dict[str, Any]] = {}
        for adj in anchored:
            f = int(adj["p_l_flag"])
            raw = float(adj["change_pct"])
            tilted = _scenario_tilt_pct(raw, f, profile, scenario_name)
            if profile != "base" and abs(tilted - raw) > 0.02:
                tilt_notes.append(
                    f"p_l_flag {f} ({PL_FLAG_LABELS.get(f, '')}): {raw:.2f}% → {tilted:.2f}%"
                )
            tilted = max(-cap, min(cap, tilted))
            adj_map[f] = {
                "change_pct": tilted,
                "rationale": adj.get("rationale", ""),
            }

        # Find Baseline Reference department plan
        baseline_dept = db.query(Department).filter(
            Department.is_baseline_only == True, Department.is_active == True
        ).first()
        if not baseline_dept:
            return {"error": "No Baseline Reference department found"}

        plan = db.query(BudgetPlan).filter(
            BudgetPlan.department_id == baseline_dept.id,
            BudgetPlan.fiscal_year == fiscal_year,
            BudgetPlan.is_current == True,
        ).first()
        if not plan:
            return {"error": f"No plan found for FY{fiscal_year}"}

        # Get details + COA classification
        details = (
            db.query(BudgetPlanDetail)
            .join(BudgetPlanGroup, BudgetPlanDetail.group_id == BudgetPlanGroup.id)
            .filter(BudgetPlanGroup.plan_id == plan.id)
            .all()
        )
        coa_codes = {d.coa_code for d in details}
        coa_rows = db.query(COADimension).filter(
            COADimension.coa_code.in_(coa_codes),
            COADimension.p_l_flag.isnot(None),
        ).all() if coa_codes else []
        coa_map = {c.coa_code: c for c in coa_rows}

        # Delete existing projections for this scenario
        db.query(AIScenarioProjection).filter(
            AIScenarioProjection.fiscal_year == fiscal_year,
            AIScenarioProjection.scenario_name == scenario_name,
        ).delete()

        # Generate projections
        rows_created = 0
        category_totals = {}  # p_l_flag -> {baseline, projected}

        for detail in details:
            coa = coa_map.get(detail.coa_code)
            if not coa:
                continue

            flag = int(coa.p_l_flag)
            adj = adj_map.get(flag, {"change_pct": 0.0, "rationale": ""})
            multiplier = 1 + adj["change_pct"] / 100

            # Compute projected monthly values
            projected = {}
            for m in months:
                baseline_val = float(getattr(detail, f'baseline_{m}', 0) or 0)
                projected[m] = baseline_val * multiplier

            annual_total = sum(projected.values())
            baseline_total = float(detail.baseline_total or 0)

            proj = AIScenarioProjection(
                fiscal_year=fiscal_year,
                scenario_name=scenario_name,
                coa_code=detail.coa_code,
                coa_name=coa.coa_name,
                p_l_flag=flag,
                p_l_flag_name=PL_FLAG_LABELS.get(flag, ""),
                bs_group=coa.bs_group,
                bs_group_name=coa.group_name,
                jan=projected['jan'], feb=projected['feb'], mar=projected['mar'],
                apr=projected['apr'], may=projected['may'], jun=projected['jun'],
                jul=projected['jul'], aug=projected['aug'], sep=projected['sep'],
                oct=projected['oct'], nov=projected['nov'], dec=projected['dec'],
                annual_total=annual_total,
                model_used=CLAUDE_MODEL,
                assumptions=assumptions,
                confidence=confidence,
            )
            db.add(proj)
            rows_created += 1

            # Track category totals
            if flag not in category_totals:
                category_totals[flag] = {"category": PL_FLAG_LABELS.get(flag, ""), "baseline": 0, "projected": 0}
            category_totals[flag]["baseline"] += baseline_total
            category_totals[flag]["projected"] += annual_total

        db.commit()

        # Build summary
        sorted_totals = sorted(category_totals.values(), key=lambda c: list(PL_FLAG_LABELS.keys()).index(
            next((k for k, v in PL_FLAG_LABELS.items() if v == c["category"]), 99)
        ) if c["category"] in PL_FLAG_LABELS.values() else 99)

        for ct in sorted_totals:
            ct["change_pct"] = round((ct["projected"] - ct["baseline"]) / abs(ct["baseline"]) * 100, 2) if ct["baseline"] != 0 else 0

        # Derived metrics
        int_inc = category_totals.get(1, {}).get("projected", 0)
        int_exp = category_totals.get(2, {}).get("projected", 0)
        nii_proj = int_inc - int_exp
        bl_int_inc = category_totals.get(1, {}).get("baseline", 0)
        bl_int_exp = category_totals.get(2, {}).get("baseline", 0)
        nii_bl = bl_int_inc - bl_int_exp

        non_int_inc = category_totals.get(4, {}).get("projected", 0)
        non_int_exp = category_totals.get(5, {}).get("projected", 0)
        opex_proj = category_totals.get(7, {}).get("projected", 0)
        prov_proj = category_totals.get(3, {}).get("projected", 0)
        tax_proj = category_totals.get(8, {}).get("projected", 0)
        net_income_proj = nii_proj + non_int_inc - non_int_exp - opex_proj - prov_proj - tax_proj

        bl_non_int_inc = category_totals.get(4, {}).get("baseline", 0)
        bl_non_int_exp = category_totals.get(5, {}).get("baseline", 0)
        bl_opex = category_totals.get(7, {}).get("baseline", 0)
        bl_prov = category_totals.get(3, {}).get("baseline", 0)
        bl_tax = category_totals.get(8, {}).get("baseline", 0)
        net_income_bl = nii_bl + bl_non_int_inc - bl_non_int_exp - bl_opex - bl_prov - bl_tax

        return {
            "status": "success",
            "scenario_name": scenario_name,
            "fiscal_year": fiscal_year,
            "rows_created": rows_created,
            "assumptions": assumptions,
            "confidence": confidence,
            "categories": sorted_totals,
            "anchor_notes": anchor_notes,
            "scenario_profile_resolved": profile,
            "scenario_tilt_notes": tilt_notes,
            "proposals_warnings": props.get("warnings") or [],
            "historic_yoy_source": {"year_old": year_old, "year_new": year_new},
            "summary": {
                "nii": {"baseline": nii_bl, "projected": nii_proj, "change_pct": round((nii_proj - nii_bl) / abs(nii_bl) * 100, 2) if nii_bl else 0},
                "net_income": {"baseline": net_income_bl, "projected": net_income_proj, "change_pct": round((net_income_proj - net_income_bl) / abs(net_income_bl) * 100, 2) if net_income_bl else 0},
            },
            "message": f"Projection '{scenario_name}' saved successfully with {rows_created} accounts. View it in the P&L Planning tab."
        }
    except Exception as e:
        logger.exception("generate_pl_projection error: %s", e)
        db.rollback()
        return {"error": str(e)}


def _dispatch_tool(tool_name: str, tool_input: Dict[str, Any], db: Session) -> str:
    """Execute a tool call and return JSON string result."""
    try:
        if tool_name == "get_budget_summary":
            result = _tool_get_budget_summary(db, **tool_input)
        elif tool_name == "calculate_what_if":
            result = _tool_calculate_what_if(db, **tool_input)
        elif tool_name == "check_plan_health":
            result = _tool_check_plan_health(db, **tool_input)
        elif tool_name == "get_driver_analysis":
            result = _tool_get_driver_analysis(db, **tool_input)
        elif tool_name == "get_pl_baseline":
            result = _tool_get_pl_baseline(db, **tool_input)
        elif tool_name == "get_pl_driver_proposals":
            result = _tool_get_pl_driver_proposals(
                db,
                tool_input["fiscal_year"],
                year_old=tool_input.get("year_old"),
                year_new=tool_input.get("year_new"),
            )
        elif tool_name == "generate_pl_projection":
            ci = dict(tool_input)
            if "category_adjustments" not in ci:
                ci["category_adjustments"] = []
            if "scenario_profile" not in ci:
                ci["scenario_profile"] = "auto"
            result = _tool_generate_pl_projection(db, **ci)
        else:
            result = {"error": f"Unknown tool: {tool_name}"}
    except Exception as e:
        result = {"error": str(e)}
    return json.dumps(result, default=str)


# ── Public API ─────────────────────────────────────────────────────────────

def _get_api_key() -> str:
    from app.config import settings, _ENV_FILE
    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        # OS env may be empty string (overriding .env); read .env directly
        try:
            from dotenv import dotenv_values
            api_key = dotenv_values(_ENV_FILE).get("ANTHROPIC_API_KEY", "")
        except Exception:
            pass
    if not api_key:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set. Add it to your .env file.")
    return api_key

def get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=_get_api_key())


async def stream_chat(
    messages: List[Dict[str, Any]],
    db: Session,
    max_tokens: int = 2048
) -> AsyncGenerator[str, None]:
    """
    Streaming chat with tool-use agentic loop.
    Uses AsyncAnthropic to avoid blocking the event loop.
    Yields SSE-compatible text chunks: 'data: <json>\n\n'
    """
    try:
        api_key = _get_api_key()
    except ValueError as e:
        yield f'data: {json.dumps({"type": "error", "content": str(e)})}\n\n'
        return

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
    except Exception as e:
        logger.exception("Failed to create Anthropic client: %s", e)
        yield f'data: {json.dumps({"type": "error", "content": f"Client error: {e}"})}\n\n'
        return

    conv_messages = list(messages)

    # Agentic loop — max 6 rounds (proposals + baseline + projection + narrate)
    try:
        for _round in range(6):
            tool_calls = []

            async with client.messages.stream(
                model=CLAUDE_MODEL,
                max_tokens=max_tokens,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=conv_messages,
            ) as stream:
                async for event in stream:
                    if isinstance(event, anthropic.types.RawContentBlockDeltaEvent):
                        delta = event.delta
                        if hasattr(delta, "text"):
                            yield f'data: {json.dumps({"type": "text", "content": delta.text})}\n\n'

                final_msg = await stream.get_final_message()

            # Check for tool use
            for block in final_msg.content:
                if block.type == "tool_use":
                    tool_calls.append(block)

            if not tool_calls:
                break

            # Serialize content blocks to plain dicts (avoids pydantic version conflicts)
            content_dicts = []
            for block in final_msg.content:
                if block.type == "text":
                    content_dicts.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    content_dicts.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
            conv_messages.append({"role": "assistant", "content": content_dicts})

            tool_results = []
            for tc in tool_calls:
                yield f'data: {json.dumps({"type": "tool_call", "name": tc.name})}\n\n'
                result_str = _dispatch_tool(tc.name, tc.input, db)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": result_str,
                })

            conv_messages.append({"role": "user", "content": tool_results})

    except Exception as e:
        logger.exception("stream_chat error: %s", e)
        yield f'data: {json.dumps({"type": "error", "content": str(e)})}\n\n'

    yield 'data: [DONE]\n\n'


def run_scenario(
    messages: List[Dict[str, Any]],
    db: Session,
    fiscal_year: int,
    adjustments: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Non-streaming scenario: run what-if + ask Claude to interpret results.
    Returns structured dict with numbers + AI narrative.
    """
    client = get_client()

    # Step 1: run calculation
    calc_result = _tool_calculate_what_if(db, fiscal_year, adjustments)
    health_result = _tool_check_plan_health(db, fiscal_year)

    # Step 2: ask Claude to narrate
    prompt = f"""
Given these what-if scenario results for FY{fiscal_year}:
{json.dumps(calc_result, indent=2)}

Current plan health:
{json.dumps(health_result, indent=2)}

Provide a 3-4 sentence executive summary:
1. Is the scenario BETTER or WORSE vs baseline?
2. Key financial impact (include dollar amount and %)
3. Any risks or alerts to flag
4. Recommendation: proceed, review, or reject

Keep it direct, CFO-ready language. End with a clear verdict line.
"""
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}]
    )
    narrative = response.content[0].text if response.content else ""

    return {
        "calculation": calc_result,
        "health": health_result,
        "narrative": narrative,
    }
