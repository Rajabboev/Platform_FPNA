"""
ETL Service - Extract, Transform, Load between databases.
Production-ready: supports DWH ↔ FPNA app, column mapping, create table, full/append.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import pandas as pd
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import Engine

from app.database import engine as app_engine
from app.models.dwh_connection import DWHConnection
from app.models.etl_job import ETLJob, ETLRun
from app.services.connection_service import get_engine_for_connection

logger = logging.getLogger(__name__)


def _get_source_engine(job: ETLJob, db_session) -> Engine:
    """Get SQLAlchemy engine for source."""
    if job.source_type == "fpna_app":
        return app_engine
    conn = db_session.query(DWHConnection).filter(DWHConnection.id == job.source_connection_id).first()
    if not conn:
        raise ValueError("Source connection not found")
    return get_engine_for_connection(conn)


def _get_target_engine(job: ETLJob, db_session) -> Engine:
    """Get SQLAlchemy engine for target."""
    if job.target_type == "fpna_app":
        return app_engine
    conn = db_session.query(DWHConnection).filter(DWHConnection.id == job.target_connection_id).first()
    if not conn:
        raise ValueError("Target connection not found")
    return get_engine_for_connection(conn)


def _quoted_table(schema: Optional[str], table: str, dialect: str = "mssql") -> str:
    """Return quoted schema.table for SQL."""
    if dialect == "mssql":
        s = f"[{schema}]" if schema else "[dbo]"
        t = f"[{table}]"
        return f"{s}.{t}"
    if dialect in ("postgresql", "mysql"):
        s = f'"{schema}"' if schema else "public" if dialect == "postgresql" else ""
        t = f'"{table}"'
        return f"{s}.{t}" if s else t
    return f"{schema}.{table}" if schema else table


def _get_dialect(engine: Engine) -> str:
    """Get dialect name from engine."""
    name = engine.dialect.name
    if "mssql" in name or "sqlserver" in name:
        return "mssql"
    if "postgresql" in name:
        return "postgresql"
    if "mysql" in name:
        return "mysql"
    return "mssql"


def _table_exists(engine: Engine, schema: Optional[str], table: str) -> bool:
    """Check if table exists."""
    inspector = inspect(engine)
    sch = schema or ("dbo" if "mssql" in str(engine.dialect.name).lower() else "public")
    try:
        tables = inspector.get_table_names(schema=sch)
    except Exception:
        tables = inspector.get_table_names()
    return table in tables


def _create_table_from_df(engine: Engine, df: pd.DataFrame, schema: Optional[str], table: str) -> None:
    """Create table with schema from DataFrame. Uses pandas to_sql with if_exists='fail'."""
    sch = schema or ("dbo" if "mssql" in engine.dialect.name else "public")
    # For SQL Server dbo is default (schema=None); for PostgreSQL public is default
    pandas_schema = None
    if "mssql" in engine.dialect.name and sch != "dbo":
        pandas_schema = sch
    elif "postgresql" in engine.dialect.name and sch != "public":
        pandas_schema = sch
    df.head(0).to_sql(table, engine, schema=pandas_schema, if_exists="fail", index=False, chunksize=1000)


def run_etl_job(job: ETLJob, db_session) -> ETLRun:
    """
    Execute ETL job: extract from source, transform (column mapping), load to target.
    Returns ETLRun with status, rows, error.
    """
    run = ETLRun(job_id=job.id, status="running")
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    try:
        source_engine = _get_source_engine(job, db_session)
        target_engine = _get_target_engine(job, db_session)
        src_dialect = _get_dialect(source_engine)
        tgt_dialect = _get_dialect(target_engine)

        src_schema = job.source_schema or ("dbo" if "mssql" in source_engine.dialect.name else "public")
        tgt_schema = job.target_schema or ("dbo" if "mssql" in target_engine.dialect.name else "public")
        src_table = _quoted_table(src_schema, job.source_table, src_dialect)
        tgt_table = _quoted_table(tgt_schema, job.target_table, tgt_dialect)

        # Extract
        read_sql = f"SELECT * FROM {src_table}"
        df = pd.read_sql(read_sql, source_engine)
        rows_extracted = len(df)

        if df.empty:
            run.status = "success"
            run.rows_extracted = 0
            run.rows_loaded = 0
            db_session.commit()
            return run

        # Transform: column mapping (source_col -> target_col)
        mapping = job.column_mapping or {}
        if mapping:
            rename_map = {k: v for k, v in mapping.items() if k in df.columns}
            df = df.rename(columns=rename_map)
            # Keep only columns that are in the mapping (target side)
            target_cols = [v for k, v in mapping.items() if k in df.columns]
            if target_cols:
                df = df[[c for c in df.columns if c in target_cols]]

        # Check/create target table
        if not _table_exists(target_engine, tgt_schema, job.target_table):
            if job.create_target_if_missing:
                _create_table_from_df(target_engine, df, tgt_schema, job.target_table)
            else:
                raise ValueError(f"Target table {job.target_table} does not exist. Enable 'Create target if missing' or create it manually.")

        # Load
        if job.load_mode == "full_replace":
            with target_engine.begin() as conn:
                conn.execute(text(f"TRUNCATE TABLE {tgt_table}"))

        rows_loaded = len(df)
        sch_for_pandas = tgt_schema if tgt_schema not in ("dbo", "public") else None
        # pyodbc + SQL Server: multi-row INSERT hits 2100 param limit. Use chunksize=1 so each INSERT has one row only.
        df.to_sql(job.target_table, target_engine, schema=sch_for_pandas, if_exists="append", index=False, method="multi", chunksize=1)

        run.status = "success"
        run.rows_extracted = rows_extracted
        run.rows_loaded = rows_loaded

    except Exception as e:
        logger.exception("ETL job %s failed: %s", job.name, e)
        run.status = "failed"
        run.error_message = str(e)[:2000]  # Limit length

    run.finished_at = datetime.now(timezone.utc)
    db_session.commit()
    db_session.refresh(run)
    return run
