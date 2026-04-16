"""
Metadata rule and driver execution service.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.metadata_logic import (
    MetadataLogicDriver,
    MetadataLogicRule,
    MetadataLogicRevision,
    MetadataExecutionLog,
)
from app.models.driver import Driver, DriverType
from app.services.metadata_formula_engine import MetadataFormulaEngine


class MetadataRuleEngine:
    def __init__(self, db: Session):
        self.db = db
        self.formula_engine = MetadataFormulaEngine()

    def get_active_driver_logic(self, driver_id: int) -> Optional[MetadataLogicDriver]:
        return (
            self.db.query(MetadataLogicDriver)
            .filter(
                MetadataLogicDriver.driver_id == driver_id,
                MetadataLogicDriver.is_active.is_(True),
                MetadataLogicDriver.is_published.is_(True),
            )
            .order_by(MetadataLogicDriver.version.desc())
            .first()
        )

    def evaluate_driver(self, driver_logic: MetadataLogicDriver, context: Dict[str, Any]) -> Decimal:
        run_id = uuid.uuid4().hex[:16]
        try:
            result = self.formula_engine.evaluate(
                driver_logic.formula_expr,
                context,
                min_value=driver_logic.min_value,
                max_value=driver_logic.max_value,
            )
            self.db.add(
                MetadataExecutionLog(
                    run_id=run_id,
                    logic_code=driver_logic.code,
                    formula_used=driver_logic.formula_expr,
                    context_json=json.dumps(context, default=str),
                    result_value=result,
                    status="SUCCESS",
                )
            )
            self.db.flush()
            return result
        except Exception as exc:
            self.db.add(
                MetadataExecutionLog(
                    run_id=run_id,
                    logic_code=driver_logic.code,
                    formula_used=driver_logic.formula_expr,
                    context_json=json.dumps(context, default=str),
                    status="FAILED",
                    error=str(exc),
                )
            )
            self.db.flush()
            raise

    def apply_rules(self, context: Dict[str, Any]) -> Dict[str, Any]:
        outcome: Dict[str, Any] = {}
        rules = (
            self.db.query(MetadataLogicRule)
            .filter(
                MetadataLogicRule.is_active.is_(True),
                MetadataLogicRule.is_published.is_(True),
            )
            .order_by(MetadataLogicRule.priority.asc(), MetadataLogicRule.id.asc())
            .all()
        )
        for rule in rules:
            matched = bool(self.formula_engine.evaluate(rule.condition_expr, context, rounding_places=6))
            if not matched:
                continue
            payload = {}
            if rule.action_payload:
                try:
                    payload = json.loads(rule.action_payload)
                except json.JSONDecodeError:
                    payload = {"raw": rule.action_payload}
            outcome[rule.code] = {"action_type": rule.action_type, "payload": payload}
            if rule.stop_on_match:
                break
        return outcome

    def create_revision(
        self,
        *,
        entity_type: str,
        entity_id: int,
        version: int,
        change_type: str,
        before_payload: Optional[Dict[str, Any]],
        after_payload: Optional[Dict[str, Any]],
        changed_by_user_id: Optional[int],
    ) -> MetadataLogicRevision:
        revision = MetadataLogicRevision(
            entity_type=entity_type,
            entity_id=entity_id,
            version=version,
            change_type=change_type,
            before_payload=json.dumps(before_payload, default=str) if before_payload is not None else None,
            after_payload=json.dumps(after_payload, default=str) if after_payload is not None else None,
            changed_by_user_id=changed_by_user_id,
        )
        self.db.add(revision)
        self.db.flush()
        return revision

    def seed_default_driver_logic(self, user_id: Optional[int] = None) -> Dict[str, int]:
        formula_by_type = {
            DriverType.GROWTH_RATE: "baseline * (1 + rate / 100)",
            DriverType.INFLATION_RATE: "baseline * (1 + rate / 100)",
            DriverType.YIELD_RATE: "baseline * rate / 100 / 12",
            DriverType.COST_RATE: "baseline * rate / 100 / 12",
            DriverType.PROVISION_RATE: "baseline * rate / 100",
            DriverType.FX_RATE: "baseline * (1 + rate / 100)",
            DriverType.HEADCOUNT: "baseline * (1 + rate / 100)",
            DriverType.CUSTOM: "baseline * (1 + rate / 100)",
        }
        drivers = self.db.query(Driver).filter(Driver.is_active.is_(True)).all()
        created = 0
        skipped = 0
        for driver in drivers:
            existing = (
                self.db.query(MetadataLogicDriver)
                .filter(
                    MetadataLogicDriver.driver_id == driver.id,
                    MetadataLogicDriver.code == driver.code,
                )
                .first()
            )
            if existing:
                skipped += 1
                continue
            formula = formula_by_type.get(driver.driver_type, "baseline * (1 + rate / 100)")
            row = MetadataLogicDriver(
                driver_id=driver.id,
                code=driver.code,
                name=driver.name_en,
                description=f"Seeded from driver type {driver.driver_type.value if driver.driver_type else 'custom'}",
                formula_expr=formula,
                output_mode="monthly_adjusted",
                is_active=True,
                is_published=True,
                version=1,
                created_by_user_id=user_id,
                approved_by_user_id=user_id,
            )
            self.db.add(row)
            self.db.flush()
            self.create_revision(
                entity_type="driver",
                entity_id=row.id,
                version=row.version,
                change_type="create",
                before_payload=None,
                after_payload={"driver_id": driver.id, "code": driver.code, "formula_expr": formula},
                changed_by_user_id=user_id,
            )
            created += 1
        self.db.commit()
        return {"created": created, "skipped": skipped}
