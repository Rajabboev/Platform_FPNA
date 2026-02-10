"""
DWH Connection and Table Mapping models for FPNA data warehouse integration
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class DWHTypeEnum(str, enum.Enum):
    """Supported data warehouse / database types"""
    SQL_SERVER = "sql_server"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    ORACLE = "oracle"


class DWHConnection(Base):
    """DWH database connection configuration"""
    __tablename__ = "dwh_connections"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    db_type = Column(String(50), nullable=False)  # sql_server, postgresql, mysql, oracle
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=True)  # Default per db_type if null
    database_name = Column(String(255), nullable=False)
    username = Column(String(255), nullable=False)
    password_encrypted = Column(String(500), nullable=True)  # Store encrypted; use secrets in production

    # Optional: schema (e.g. for PostgreSQL, SQL Server)
    schema_name = Column(String(100), nullable=True)

    # SSL / connection options
    use_ssl = Column(Boolean, default=False)
    extra_params = Column(Text, nullable=True)  # JSON string for driver-specific options

    is_active = Column(Boolean, default=True)
    description = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    table_mappings = relationship("DWHTableMapping", back_populates="connection", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<DWHConnection(name={self.name}, type={self.db_type})>"


class DWHTableMapping(Base):
    """Maps DWH source tables to FPNA app entities with column mappings"""
    __tablename__ = "dwh_table_mappings"

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(Integer, ForeignKey("dwh_connections.id", ondelete="CASCADE"), nullable=False, index=True)

    # Source (DWH)
    source_schema = Column(String(100), nullable=True)
    source_table = Column(String(255), nullable=False)

    # Target (FPNA app entity)
    target_entity = Column(String(100), nullable=False)  # e.g. budgets, budget_line_items, fact_sales
    target_description = Column(String(255), nullable=True)

    # Column mapping: { "source_col": "target_col", ... }
    column_mapping = Column(JSON, nullable=True)  # {"dwh_amount": "amount", "dwh_date": "fiscal_date"}

    is_active = Column(Boolean, default=True)
    sync_enabled = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    connection = relationship("DWHConnection", back_populates="table_mappings")

    def __repr__(self):
        return f"<DWHTableMapping({self.source_table} -> {self.target_entity})>"
