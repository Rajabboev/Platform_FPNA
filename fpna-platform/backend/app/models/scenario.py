"""
Budget Scenario Models - What-If / Reforecast / Stress Test scenarios

Scenarios allow mid-year adjustments to the approved budget.
Once approved, they update the year_budget_approved table in the DWH.
"""

from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class BudgetScenario(Base):
    """
    A what-if / reforecast / stress-test scenario for a fiscal year.

    Lifecycle: draft -> pending -> approved -> active
    """
    __tablename__ = "budget_scenarios"

    id = Column(Integer, primary_key=True, index=True)

    plan_fiscal_year = Column(Integer, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)

    scenario_type = Column(String(50), default="what_if")  # what_if, reforecast, stress_test
    status = Column(String(30), default="draft", index=True)  # draft, pending, approved, active

    parent_scenario_id = Column(Integer, ForeignKey("budget_scenarios.id", ondelete="NO ACTION"), nullable=True)

    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="NO ACTION"), nullable=True)
    approved_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="NO ACTION"), nullable=True)
    approved_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    adjustments = relationship("ScenarioAdjustment", back_populates="scenario", cascade="all, delete-orphan")
    parent = relationship("BudgetScenario", remote_side=[id])

    __table_args__ = (
        Index("ix_scenario_fy_status", "plan_fiscal_year", "status"),
    )

    def __repr__(self):
        return f"<BudgetScenario(id={self.id}, name={self.name}, fy={self.plan_fiscal_year})>"


class ScenarioAdjustment(Base):
    """
    Individual adjustment within a scenario.

    adjustment_type:
      - override:   replace the group total with this value
      - delta:      add this value to the group total
      - percentage: multiply the group total by (1 + value/100)
    """
    __tablename__ = "scenario_adjustments"

    id = Column(Integer, primary_key=True, index=True)

    scenario_id = Column(Integer, ForeignKey("budget_scenarios.id", ondelete="CASCADE"), nullable=False, index=True)
    budgeting_group_id = Column(Integer, nullable=False, index=True)
    department_id = Column(Integer, nullable=True)
    month = Column(Integer, nullable=True)  # NULL = all months

    adjustment_type = Column(String(30), default="percentage")  # override, delta, percentage
    value = Column(Numeric(20, 4), nullable=False)

    driver_code = Column(String(50), nullable=True)
    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    scenario = relationship("BudgetScenario", back_populates="adjustments")

    __table_args__ = (
        Index("ix_scenario_adj_group", "scenario_id", "budgeting_group_id"),
    )

    def __repr__(self):
        return f"<ScenarioAdjustment(scenario={self.scenario_id}, group={self.budgeting_group_id}, type={self.adjustment_type})>"


class AIScenarioProjection(Base):
    """
    AI-generated P&L projections at COA account level.

    The AI assistant writes projections here; the UI reads them alongside
    baseline / adjusted data for side-by-side comparison.

    One row per (fiscal_year, scenario_name, coa_code).
    """
    __tablename__ = "ai_scenario_projections"

    id = Column(Integer, primary_key=True, index=True)

    fiscal_year = Column(Integer, nullable=False, index=True)
    scenario_name = Column(String(100), nullable=False, index=True)  # e.g. "base", "optimistic", "stress"

    # COA account
    coa_code = Column(String(10), nullable=False, index=True)
    coa_name = Column(String(1000))

    # P&L classification (from coa_dimension)
    p_l_flag = Column(Integer)          # 1-8
    p_l_flag_name = Column(String(255))
    bs_group = Column(Integer)
    bs_group_name = Column(String(500))

    # Monthly projections
    jan = Column(Numeric(22, 2), default=0)
    feb = Column(Numeric(22, 2), default=0)
    mar = Column(Numeric(22, 2), default=0)
    apr = Column(Numeric(22, 2), default=0)
    may = Column(Numeric(22, 2), default=0)
    jun = Column(Numeric(22, 2), default=0)
    jul = Column(Numeric(22, 2), default=0)
    aug = Column(Numeric(22, 2), default=0)
    sep = Column(Numeric(22, 2), default=0)
    oct = Column(Numeric(22, 2), default=0)
    nov = Column(Numeric(22, 2), default=0)
    dec = Column(Numeric(22, 2), default=0)
    annual_total = Column(Numeric(22, 2), default=0)

    # AI metadata
    model_used = Column(String(100))
    assumptions = Column(Text)       # JSON or free-text description of assumptions
    confidence = Column(Numeric(5, 2))  # 0-100

    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="NO ACTION"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_ai_proj_fy_scenario", "fiscal_year", "scenario_name"),
        Index("ix_ai_proj_coa", "fiscal_year", "coa_code"),
    )
