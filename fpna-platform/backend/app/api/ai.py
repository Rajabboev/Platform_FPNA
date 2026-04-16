"""
AI API endpoints — chat (streaming SSE), what-if scenario, plan health, projections.
"""
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import ai_service
from app.models.scenario import AIScenarioProjection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["AI Assistant"])


# ── Request/Response models ────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str        # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    fiscal_year: Optional[int] = 2026


class ScenarioAdjustment(BaseModel):
    label: str
    department: Optional[str] = "ALL"
    change_type: str = "percentage"   # "percentage" | "absolute"
    value: float


class ScenarioRequest(BaseModel):
    fiscal_year: int = 2026
    adjustments: List[ScenarioAdjustment]


class HealthRequest(BaseModel):
    fiscal_year: int = 2026
    alert_threshold_pct: float = 10.0


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/chat")
async def chat_stream(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Streaming SSE chat endpoint.
    Returns Server-Sent Events: data: {"type": "text", "content": "..."}
    Supports tool use (budget queries, what-if, plan health).
    """
    try:
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        return StreamingResponse(
            ai_service.stream_chat(messages, db),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Chat error: %s", e)
        raise HTTPException(status_code=500, detail="AI service error")


@router.post("/scenario")
def run_scenario(request: ScenarioRequest, db: Session = Depends(get_db)):
    """
    Non-streaming what-if scenario calculation with AI narrative.
    Returns: calculation results + CFO-ready narrative.
    """
    try:
        adjustments = [a.model_dump() for a in request.adjustments]
        result = ai_service.run_scenario([], db, request.fiscal_year, adjustments)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Scenario error: %s", e)
        raise HTTPException(status_code=500, detail="Scenario calculation failed")


@router.post("/health-check")
def plan_health_check(request: HealthRequest, db: Session = Depends(get_db)):
    """
    Quick plan health check — returns alerts, variance, verdict.
    Used by the frontend alert banner.
    """
    try:
        from app.services.ai_service import _tool_check_plan_health
        result = _tool_check_plan_health(db, request.fiscal_year, request.alert_threshold_pct)
        return result
    except Exception as e:
        logger.exception("Health check error: %s", e)
        raise HTTPException(status_code=500, detail="Health check failed")


@router.get("/projections")
def list_projections(fiscal_year: int = 2026, db: Session = Depends(get_db)):
    """List all saved AI scenario projections for a fiscal year."""
    scenarios = (
        db.query(
            AIScenarioProjection.scenario_name,
            AIScenarioProjection.assumptions,
            AIScenarioProjection.confidence,
            AIScenarioProjection.model_used,
            AIScenarioProjection.created_at,
        )
        .filter(AIScenarioProjection.fiscal_year == fiscal_year)
        .group_by(
            AIScenarioProjection.scenario_name,
            AIScenarioProjection.assumptions,
            AIScenarioProjection.confidence,
            AIScenarioProjection.model_used,
            AIScenarioProjection.created_at,
        )
        .all()
    )
    return [
        {
            "scenario_name": s[0],
            "assumptions": s[1],
            "confidence": float(s[2] or 0),
            "model_used": s[3],
            "created_at": s[4].isoformat() if s[4] else None,
        }
        for s in scenarios
    ]


@router.get("/projections/{scenario_name}")
def get_projection_detail(scenario_name: str, fiscal_year: int = 2026, db: Session = Depends(get_db)):
    """Get detailed projection data for a specific scenario."""
    months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
              'jul', 'aug', 'sep', 'oct', 'nov', 'dec']

    rows = (
        db.query(AIScenarioProjection)
        .filter(
            AIScenarioProjection.fiscal_year == fiscal_year,
            AIScenarioProjection.scenario_name == scenario_name,
        )
        .order_by(AIScenarioProjection.p_l_flag, AIScenarioProjection.coa_code)
        .all()
    )
    if not rows:
        raise HTTPException(404, "Scenario not found")

    # Group by p_l_flag
    categories = {}
    for r in rows:
        flag = r.p_l_flag
        if flag not in categories:
            categories[flag] = {
                "p_l_flag": flag,
                "category": r.p_l_flag_name,
                "accounts": [],
                "total_projected": 0,
            }
        categories[flag]["accounts"].append({
            "coa_code": r.coa_code,
            "coa_name": r.coa_name,
            "annual_total": float(r.annual_total or 0),
            "monthly": {m: float(getattr(r, m, 0) or 0) for m in months},
        })
        categories[flag]["total_projected"] += float(r.annual_total or 0)

    return {
        "scenario_name": scenario_name,
        "fiscal_year": fiscal_year,
        "assumptions": rows[0].assumptions if rows else "",
        "confidence": float(rows[0].confidence or 0) if rows else 0,
        "model_used": rows[0].model_used if rows else "",
        "created_at": rows[0].created_at.isoformat() if rows and rows[0].created_at else None,
        "categories": sorted(categories.values(), key=lambda c: c["p_l_flag"]),
        "total_accounts": len(rows),
    }


@router.delete("/projections/{scenario_name}")
def delete_projection(scenario_name: str, fiscal_year: int = 2026, db: Session = Depends(get_db)):
    """Delete a saved projection scenario."""
    deleted = db.query(AIScenarioProjection).filter(
        AIScenarioProjection.fiscal_year == fiscal_year,
        AIScenarioProjection.scenario_name == scenario_name,
    ).delete()
    db.commit()
    return {"deleted": deleted, "scenario_name": scenario_name}
