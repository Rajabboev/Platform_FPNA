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
    """Check if table exists using raw SQL to avoid pyodbc parameter binding issues."""
    dialect = _get_dialect(engine)
    sch = schema or ("dbo" if dialect == "mssql" else "public")
    
    try:
        with engine.connect() as conn:
            if dialect == "mssql":
                # Use raw SQL without parameters to avoid pyodbc binding issues
                result = conn.execute(text(f"""
                    SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
                    WHERE TABLE_SCHEMA = '{sch}' AND TABLE_NAME = '{table}' AND TABLE_TYPE = 'BASE TABLE'
                """))
            elif dialect == "postgresql":
                result = conn.execute(text(f"""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_schema = '{sch}' AND table_name = '{table}'
                """))
            else:
                result = conn.execute(text(f"SHOW TABLES LIKE '{table}'"))
                return result.fetchone() is not None
            
            count = result.scalar()
            return count > 0
    except Exception as e:
        logger.warning(f"Error checking table existence: {e}")
        # Fallback to inspector
        try:
            inspector = inspect(engine)
            tables = inspector.get_table_names(schema=sch)
            return table in tables
        except Exception:
            return False


def _pandas_dtype_to_sql(dtype, dialect: str) -> str:
    """Convert pandas dtype to SQL data type."""
    dtype_str = str(dtype).lower()
    
    if 'int64' in dtype_str or 'int32' in dtype_str:
        return 'BIGINT' if dialect == 'mssql' else 'BIGINT'
    elif 'int' in dtype_str:
        return 'INT'
    elif 'float' in dtype_str:
        return 'FLOAT' if dialect == 'mssql' else 'DOUBLE PRECISION'
    elif 'bool' in dtype_str:
        return 'BIT' if dialect == 'mssql' else 'BOOLEAN'
    elif 'datetime' in dtype_str:
        return 'DATETIME2' if dialect == 'mssql' else 'TIMESTAMP'
    elif 'date' in dtype_str:
        return 'DATE'
    elif 'object' in dtype_str:
        return 'NVARCHAR(MAX)' if dialect == 'mssql' else 'TEXT'
    else:
        return 'NVARCHAR(MAX)' if dialect == 'mssql' else 'TEXT'


def _escape_value(val, dialect: str) -> str:
    """Escape a value for SQL insertion."""
    if pd.isna(val) or val is None:
        return "NULL"
    if isinstance(val, bool):
        return "1" if val else "0"
    if isinstance(val, (int, float)):
        if pd.isna(val):
            return "NULL"
        return str(val)
    if isinstance(val, datetime):
        return f"'{val.isoformat()}'"
    # String - escape single quotes
    val_str = str(val).replace("'", "''")
    if dialect == "mssql":
        return f"N'{val_str}'"
    return f"'{val_str}'"


def _insert_dataframe(engine: Engine, df: pd.DataFrame, schema: Optional[str], table: str, dialect: str) -> None:
    """Insert DataFrame rows using raw SQL to avoid pyodbc parameter binding issues."""
    if df.empty:
        return
    
    full_table = _quoted_table(schema, table, dialect)
    
    # Quote column names
    if dialect == "mssql":
        columns = ", ".join([f"[{col}]" for col in df.columns])
    else:
        columns = ", ".join([f'"{col}"' for col in df.columns])
    
    # Insert in batches to avoid very long SQL statements
    batch_size = 100
    total_rows = len(df)
    
    with engine.begin() as conn:
        for start in range(0, total_rows, batch_size):
            end = min(start + batch_size, total_rows)
            batch_df = df.iloc[start:end]
            
            values_list = []
            for _, row in batch_df.iterrows():
                row_values = ", ".join([_escape_value(v, dialect) for v in row])
                values_list.append(f"({row_values})")
            
            values_sql = ",\n".join(values_list)
            insert_sql = f"INSERT INTO {full_table} ({columns}) VALUES {values_sql}"
            
            try:
                conn.execute(text(insert_sql))
            except Exception as e:
                logger.error(f"Batch insert failed at rows {start}-{end}: {e}")
                # Fall back to row-by-row insert
                for _, row in batch_df.iterrows():
                    row_values = ", ".join([_escape_value(v, dialect) for v in row])
                    single_insert = f"INSERT INTO {full_table} ({columns}) VALUES ({row_values})"
                    conn.execute(text(single_insert))
    
    logger.info(f"Inserted {total_rows} rows into {full_table}")


def _create_table_from_df(engine: Engine, df: pd.DataFrame, schema: Optional[str], table: str) -> None:
    """Create table with schema from DataFrame using raw SQL to avoid pyodbc issues."""
    dialect = _get_dialect(engine)
    sch = schema or ("dbo" if dialect == "mssql" else "public")
    
    # Build CREATE TABLE statement
    columns = []
    for col_name, dtype in df.dtypes.items():
        sql_type = _pandas_dtype_to_sql(dtype, dialect)
        # Quote column names
        if dialect == "mssql":
            columns.append(f"[{col_name}] {sql_type} NULL")
        else:
            columns.append(f'"{col_name}" {sql_type}')
    
    columns_sql = ",\n    ".join(columns)
    full_table = _quoted_table(sch, table, dialect)
    
    create_sql = f"CREATE TABLE {full_table} (\n    {columns_sql}\n)"
    
    logger.info(f"Creating table with SQL: {create_sql[:500]}...")
    
    with engine.begin() as conn:
        conn.execute(text(create_sql))


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
        table_existed = _table_exists(target_engine, tgt_schema, job.target_table)
        
        if table_existed and job.load_mode == "full_replace":
            with target_engine.begin() as conn:
                conn.execute(text(f"TRUNCATE TABLE {tgt_table}"))

        rows_loaded = len(df)
        
        # Use raw SQL inserts to avoid pyodbc parameter binding issues with pandas to_sql
        _insert_dataframe(target_engine, df, tgt_schema, job.target_table, tgt_dialect)

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
