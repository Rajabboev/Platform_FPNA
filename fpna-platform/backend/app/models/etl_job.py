"""
ETL Job and Run models for data sync between databases
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class LoadModeEnum(str, enum.Enum):
    """How to load data into destination"""
    FULL_REPLACE = "full_replace"      # Truncate target, insert all
    APPEND = "append"                  # Append only (no truncate)
    UPSERT = "upsert"                  # Insert or update on key (future)


class ETLJob(Base):
    """ETL job definition - source → destination table sync"""
    __tablename__ = "etl_jobs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(String(500), nullable=True)

    # Source: DWH connection or FPNA_APP (NO ACTION to avoid SQL Server multiple cascade paths)
    source_type = Column(String(20), nullable=False)  # "dwh_connection" | "fpna_app"
    source_connection_id = Column(Integer, ForeignKey("dwh_connections.id", ondelete="NO ACTION"), nullable=True)
    source_schema = Column(String(100), nullable=True)
    source_table = Column(String(255), nullable=False)

    # Destination: DWH connection or FPNA_APP (NO ACTION to avoid SQL Server multiple cascade paths)
    target_type = Column(String(20), nullable=False)  # "dwh_connection" | "fpna_app"
    target_connection_id = Column(Integer, ForeignKey("dwh_connections.id", ondelete="NO ACTION"), nullable=True)
    target_schema = Column(String(100), nullable=True)
    target_table = Column(String(255), nullable=False)

    # Column mapping: { "source_col": "target_col" } - if empty, use same names
    column_mapping = Column(JSON, nullable=True)

    # If true, create target table from source schema when missing
    create_target_if_missing = Column(Boolean, default=False)

    load_mode = Column(String(30), nullable=False, default="full_replace")  # full_replace, append, upsert

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    source_connection = relationship("DWHConnection", foreign_keys=[source_connection_id])
    target_connection = relationship("DWHConnection", foreign_keys=[target_connection_id])
    runs = relationship("ETLRun", back_populates="job", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ETLJob({self.name}: {self.source_table} -> {self.target_table})>"


class ETLRun(Base):
    """ETL job run history"""
    __tablename__ = "etl_runs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("etl_jobs.id", ondelete="CASCADE"), nullable=False, index=True)

    status = Column(String(20), nullable=False)  # running, success, failed
    rows_extracted = Column(Integer, default=0)
    rows_loaded = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)

    job = relationship("ETLJob", back_populates="runs")

    def __repr__(self):
        return f"<ETLRun(job={self.job_id}, status={self.status})>"
