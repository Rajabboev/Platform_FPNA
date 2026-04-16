"""
Metadata-driven budgeting logic models.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    DateTime,
    ForeignKey,
    Text,
    Boolean,
)
from sqlalchemy.sql import func
from app.database import Base


class MetadataLogicDriver(Base):
    __tablename__ = "metadata_logic_drivers"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False, index=True)
    code = Column(String(100), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    version = Column(Integer, default=1, nullable=False)
    is_active = Column(Boolean, default=True)
    is_published = Column(Boolean, default=False)
    scope_fields = Column(Text)  # JSON array encoded as text
    formula_expr = Column(Text, nullable=False)
    output_mode = Column(String(50), default="monthly_adjusted")
    rounding_mode = Column(String(50), default="HALF_UP")
    min_value = Column(Numeric(20, 6))
    max_value = Column(Numeric(20, 6))
    effective_from = Column(DateTime(timezone=True))
    effective_to = Column(DateTime(timezone=True))
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    published_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class MetadataLogicRule(Base):
    __tablename__ = "metadata_logic_rules"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(100), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    version = Column(Integer, default=1, nullable=False)
    priority = Column(Integer, default=100, nullable=False)
    condition_expr = Column(Text, nullable=False)
    target_selector = Column(Text)  # JSON selector payload as text
    action_type = Column(String(50), nullable=False, default="set")
    action_payload = Column(Text)  # JSON action payload as text
    stop_on_match = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    is_published = Column(Boolean, default=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    published_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class MetadataLogicRevision(Base):
    __tablename__ = "metadata_logic_revisions"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(30), nullable=False, index=True)  # driver|rule
    entity_id = Column(Integer, nullable=False, index=True)
    version = Column(Integer, nullable=False)
    change_type = Column(String(30), nullable=False)  # create|update|publish
    before_payload = Column(Text)
    after_payload = Column(Text)
    changed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    changed_at = Column(DateTime(timezone=True), server_default=func.now())


class MetadataExecutionLog(Base):
    __tablename__ = "metadata_execution_logs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(64), nullable=False, index=True)
    logic_code = Column(String(100), nullable=False, index=True)
    formula_used = Column(Text)
    context_json = Column(Text)
    result_value = Column(Numeric(20, 6))
    status = Column(String(20), default="SUCCESS")
    error = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
