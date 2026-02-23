"""
Budget Plan Models - COA Hierarchy-Based Budget Planning

This module implements the new group-based budget planning system where:
- BudgetPlan: Department's budget for a fiscal year
- BudgetPlanGroup: Aggregated budget by budgeting group (editable)
- BudgetPlanDetail: Individual account breakdown (read-only, for drill-down)

Workflow:
1. Initialize: Ingest DWH data → Calculate baseline by budgeting groups
2. Assign: Assign budgeting groups to departments
3. Plan: Departments adjust group-level budgets using drivers
4. Approve: Two-level approval (Dept Head → CFO)
5. Export: Consolidate and export to DWH
"""

from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, ForeignKey, Enum, Text, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from decimal import Decimal
import enum

from app.database import Base


class BudgetPlanStatus(str, enum.Enum):
    """Budget plan status workflow"""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    DEPT_APPROVED = "dept_approved"
    CFO_APPROVED = "cfo_approved"
    REJECTED = "rejected"
    EXPORTED = "exported"


class ApprovalLevel(str, enum.Enum):
    """Approval levels"""
    DEPT_HEAD = "dept_head"
    CFO = "cfo"


class ApprovalAction(str, enum.Enum):
    """Approval actions"""
    SUBMIT = "submit"
    APPROVE = "approve"
    REJECT = "reject"
    RETURN = "return"


class BudgetPlan(Base):
    """
    Department's budget plan for a fiscal year
    
    Each department has one budget plan per fiscal year.
    The plan contains multiple BudgetPlanGroups (one per assigned budgeting group).
    """
    __tablename__ = "budget_plans"

    id = Column(Integer, primary_key=True, index=True)
    
    # Core identifiers
    fiscal_year = Column(Integer, nullable=False, index=True)
    department_id = Column(Integer, ForeignKey('departments.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Status workflow
    status = Column(Enum(BudgetPlanStatus), default=BudgetPlanStatus.DRAFT, nullable=False, index=True)
    version = Column(Integer, default=1)
    is_current = Column(Boolean, default=True)
    
    # Totals (calculated from groups)
    total_baseline = Column(Numeric(20, 2), default=0)
    total_adjusted = Column(Numeric(20, 2), default=0)
    total_variance = Column(Numeric(20, 2), default=0)
    total_variance_pct = Column(Numeric(10, 4), default=0)
    
    # Submission tracking
    submitted_at = Column(DateTime(timezone=True))
    submitted_by_user_id = Column(Integer, ForeignKey('users.id', ondelete='NO ACTION'))
    
    # Department approval
    dept_approved_at = Column(DateTime(timezone=True))
    dept_approved_by_user_id = Column(Integer, ForeignKey('users.id', ondelete='NO ACTION'))
    dept_approval_comment = Column(Text)
    
    # CFO approval
    cfo_approved_at = Column(DateTime(timezone=True))
    cfo_approved_by_user_id = Column(Integer, ForeignKey('users.id', ondelete='NO ACTION'))
    cfo_approval_comment = Column(Text)
    
    # Rejection tracking
    rejected_at = Column(DateTime(timezone=True))
    rejected_by_user_id = Column(Integer, ForeignKey('users.id', ondelete='NO ACTION'))
    rejection_reason = Column(Text)
    
    # Export tracking
    exported_at = Column(DateTime(timezone=True))
    export_batch_id = Column(String(100))
    
    # Notes
    notes = Column(Text)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by_user_id = Column(Integer, ForeignKey('users.id', ondelete='NO ACTION'))
    
    # Relationships
    department = relationship("Department", back_populates="budget_plans")
    groups = relationship("BudgetPlanGroup", back_populates="plan", cascade="all, delete-orphan")
    approvals = relationship("BudgetPlanApproval", back_populates="plan", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('ix_budget_plan_year_dept', 'fiscal_year', 'department_id'),
        Index('ix_budget_plan_status', 'status', 'fiscal_year'),
    )

    def __repr__(self):
        return f"<BudgetPlan(year={self.fiscal_year}, dept={self.department_id}, status={self.status})>"
    
    def recalculate_totals(self):
        """Recalculate totals from groups"""
        self.total_baseline = sum(g.baseline_total or 0 for g in self.groups)
        self.total_adjusted = sum(g.adjusted_total or 0 for g in self.groups)
        self.total_variance = self.total_adjusted - self.total_baseline
        if self.total_baseline and self.total_baseline != 0:
            self.total_variance_pct = (self.total_variance / self.total_baseline) * 100


class BudgetPlanGroup(Base):
    """
    Budget data aggregated by budgeting group
    
    This is the main editable unit for department users.
    Each group has baseline (read-only) and adjusted (editable) monthly values.
    Drivers are applied at this level.
    """
    __tablename__ = "budget_plan_groups"

    id = Column(Integer, primary_key=True, index=True)
    
    # Parent plan
    plan_id = Column(Integer, ForeignKey('budget_plans.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Group identification - 4 level hierarchy
    budgeting_group_id = Column(Integer, index=True)  # From budgeting_groups table
    budgeting_group_name = Column(String(500))
    bs_flag = Column(Integer, index=True)  # Level 1: 1=Assets, 2=Liabilities, 3=Capital
    bs_class_name = Column(String(255))
    bs_group = Column(String(10), index=True)  # Level 2: 3-digit BS group code
    bs_group_name = Column(String(255))  # Level 2 name
    
    # Totals
    baseline_total = Column(Numeric(20, 2), default=0)
    adjusted_total = Column(Numeric(20, 2), default=0)
    variance = Column(Numeric(20, 2), default=0)
    variance_pct = Column(Numeric(10, 4), default=0)
    
    # Monthly baseline values (read-only, from DWH)
    baseline_jan = Column(Numeric(20, 2), default=0)
    baseline_feb = Column(Numeric(20, 2), default=0)
    baseline_mar = Column(Numeric(20, 2), default=0)
    baseline_apr = Column(Numeric(20, 2), default=0)
    baseline_may = Column(Numeric(20, 2), default=0)
    baseline_jun = Column(Numeric(20, 2), default=0)
    baseline_jul = Column(Numeric(20, 2), default=0)
    baseline_aug = Column(Numeric(20, 2), default=0)
    baseline_sep = Column(Numeric(20, 2), default=0)
    baseline_oct = Column(Numeric(20, 2), default=0)
    baseline_nov = Column(Numeric(20, 2), default=0)
    baseline_dec = Column(Numeric(20, 2), default=0)
    
    # Monthly adjusted values (editable)
    adjusted_jan = Column(Numeric(20, 2), default=0)
    adjusted_feb = Column(Numeric(20, 2), default=0)
    adjusted_mar = Column(Numeric(20, 2), default=0)
    adjusted_apr = Column(Numeric(20, 2), default=0)
    adjusted_may = Column(Numeric(20, 2), default=0)
    adjusted_jun = Column(Numeric(20, 2), default=0)
    adjusted_jul = Column(Numeric(20, 2), default=0)
    adjusted_aug = Column(Numeric(20, 2), default=0)
    adjusted_sep = Column(Numeric(20, 2), default=0)
    adjusted_oct = Column(Numeric(20, 2), default=0)
    adjusted_nov = Column(Numeric(20, 2), default=0)
    adjusted_dec = Column(Numeric(20, 2), default=0)
    
    # Driver applied
    driver_code = Column(String(50), index=True)
    driver_name = Column(String(255))
    driver_rate = Column(Numeric(10, 4))  # e.g., 5.5 for 5.5%
    
    # Editing
    is_locked = Column(Boolean, default=False)
    adjustment_notes = Column(Text)
    last_edited_at = Column(DateTime(timezone=True))
    last_edited_by_user_id = Column(Integer, ForeignKey('users.id', ondelete='NO ACTION'))
    
    # CFO Locking - separate from is_locked (which is for baseline-only)
    locked_by_cfo = Column(Boolean, default=False)
    cfo_locked_at = Column(DateTime(timezone=True))
    cfo_locked_by_user_id = Column(Integer, ForeignKey('users.id', ondelete='NO ACTION'))
    cfo_lock_reason = Column(String(500))
    
    # Relationships
    plan = relationship("BudgetPlan", back_populates="groups")
    details = relationship("BudgetPlanDetail", back_populates="group", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('ix_plan_group_bg', 'plan_id', 'budgeting_group_id'),
    )

    def __repr__(self):
        return f"<BudgetPlanGroup(plan={self.plan_id}, group={self.budgeting_group_id})>"
    
    def recalculate_totals(self):
        """Recalculate totals from monthly values"""
        self.baseline_total = sum([
            self.baseline_jan or 0, self.baseline_feb or 0, self.baseline_mar or 0,
            self.baseline_apr or 0, self.baseline_may or 0, self.baseline_jun or 0,
            self.baseline_jul or 0, self.baseline_aug or 0, self.baseline_sep or 0,
            self.baseline_oct or 0, self.baseline_nov or 0, self.baseline_dec or 0,
        ])
        self.adjusted_total = sum([
            self.adjusted_jan or 0, self.adjusted_feb or 0, self.adjusted_mar or 0,
            self.adjusted_apr or 0, self.adjusted_may or 0, self.adjusted_jun or 0,
            self.adjusted_jul or 0, self.adjusted_aug or 0, self.adjusted_sep or 0,
            self.adjusted_oct or 0, self.adjusted_nov or 0, self.adjusted_dec or 0,
        ])
        self.variance = self.adjusted_total - self.baseline_total
        if self.baseline_total and self.baseline_total != 0:
            self.variance_pct = (self.variance / self.baseline_total) * 100
    
    def apply_driver(self, rate: Decimal):
        """Apply a driver rate to all monthly values"""
        multiplier = Decimal(1) + (rate / Decimal(100))
        self.adjusted_jan = (self.baseline_jan or 0) * multiplier
        self.adjusted_feb = (self.baseline_feb or 0) * multiplier
        self.adjusted_mar = (self.baseline_mar or 0) * multiplier
        self.adjusted_apr = (self.baseline_apr or 0) * multiplier
        self.adjusted_may = (self.baseline_may or 0) * multiplier
        self.adjusted_jun = (self.baseline_jun or 0) * multiplier
        self.adjusted_jul = (self.baseline_jul or 0) * multiplier
        self.adjusted_aug = (self.baseline_aug or 0) * multiplier
        self.adjusted_sep = (self.baseline_sep or 0) * multiplier
        self.adjusted_oct = (self.baseline_oct or 0) * multiplier
        self.adjusted_nov = (self.baseline_nov or 0) * multiplier
        self.adjusted_dec = (self.baseline_dec or 0) * multiplier
        self.driver_rate = rate
        self.recalculate_totals()


class BudgetPlanDetail(Base):
    """
    Individual account breakdown within a budgeting group
    
    This is read-only data for drill-down purposes.
    Shows how the group total breaks down by individual COA accounts.
    """
    __tablename__ = "budget_plan_details"

    id = Column(Integer, primary_key=True, index=True)
    
    # Parent group
    group_id = Column(Integer, ForeignKey('budget_plan_groups.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Account identification
    coa_code = Column(String(10), nullable=False, index=True)
    coa_name = Column(String(1000))
    bs_group = Column(Integer)  # 3-digit group code
    bs_group_name = Column(String(500))
    
    # Monthly baseline values
    baseline_jan = Column(Numeric(20, 2), default=0)
    baseline_feb = Column(Numeric(20, 2), default=0)
    baseline_mar = Column(Numeric(20, 2), default=0)
    baseline_apr = Column(Numeric(20, 2), default=0)
    baseline_may = Column(Numeric(20, 2), default=0)
    baseline_jun = Column(Numeric(20, 2), default=0)
    baseline_jul = Column(Numeric(20, 2), default=0)
    baseline_aug = Column(Numeric(20, 2), default=0)
    baseline_sep = Column(Numeric(20, 2), default=0)
    baseline_oct = Column(Numeric(20, 2), default=0)
    baseline_nov = Column(Numeric(20, 2), default=0)
    baseline_dec = Column(Numeric(20, 2), default=0)
    baseline_total = Column(Numeric(20, 2), default=0)
    
    # Relationships
    group = relationship("BudgetPlanGroup", back_populates="details")
    
    __table_args__ = (
        Index('ix_plan_detail_coa', 'group_id', 'coa_code'),
    )

    def __repr__(self):
        return f"<BudgetPlanDetail(group={self.group_id}, coa={self.coa_code})>"


class BudgetPlanApproval(Base):
    """
    Approval audit trail for budget plans
    
    Records all approval actions (submit, approve, reject, return).
    """
    __tablename__ = "budget_plan_approvals"

    id = Column(Integer, primary_key=True, index=True)
    
    # Parent plan
    plan_id = Column(Integer, ForeignKey('budget_plans.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Approval details
    level = Column(Enum(ApprovalLevel), nullable=False)
    action = Column(Enum(ApprovalAction), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='NO ACTION'), nullable=False)
    comment = Column(Text)
    
    # Status before/after
    status_before = Column(String(50))
    status_after = Column(String(50))
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    plan = relationship("BudgetPlan", back_populates="approvals")
    user = relationship("User")
    
    __table_args__ = (
        Index('ix_approval_plan_level', 'plan_id', 'level'),
    )

    def __repr__(self):
        return f"<BudgetPlanApproval(plan={self.plan_id}, level={self.level}, action={self.action})>"
