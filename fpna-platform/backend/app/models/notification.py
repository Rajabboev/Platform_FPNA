"""
Notification model for manager-worker workflow
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from app.database import Base


class Notification(Base):
    """User notification for budget workflow events"""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    recipient_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(50), nullable=False, index=True)
    budget_id = Column(Integer, ForeignKey("budgets.id", ondelete="CASCADE"), nullable=True)
    budget_code = Column(String(50))
    plan_id = Column(Integer, nullable=True, index=True)  # BudgetPlan reference
    plan_code = Column(String(100))  # Display label for budget plan
    link_step = Column(Integer, nullable=True)  # Which workflow step to navigate to (1-7)
    actor_username = Column(String(100))
    message = Column(Text, nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
