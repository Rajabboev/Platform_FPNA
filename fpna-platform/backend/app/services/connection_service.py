"""DWH connection service - test connection, list tables/columns"""

import urllib.parse
from typing import List, Optional, Tuple
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


# Default ports per DB type
DEFAULT_PORTS = {
    "sql_server": 1433,
    "postgresql": 5432,
    "mysql": 3306,
    "oracle": 1521,
}


def _get_sql_server_driver() -> str:
    """Try common SQL Server ODBC drivers."""
    try:
        import pyodbc
        drivers = [d for d in pyodbc.drivers() if 'SQL Server' in d]
        return drivers[0] if drivers else "ODBC Driver 17 for SQL Server"
    except Exception:
        return "ODBC Driver 17 for SQL Server"


def _build_connection_url(
    db_type: str,
    host: str,
    port: Optional[int],
    database_name: str,
    username: str,
    password: str,
    schema_name: Optional[str] = None,
    use_ssl: bool = False,
) -> str:
    """Build SQLAlchemy connection URL for the given DB type."""
    port = port or DEFAULT_PORTS.get(db_type, 1433)

    if db_type == "sql_server":
        driver = _get_sql_server_driver()
        params = urllib.parse.quote_plus(
            f"DRIVER={{{driver}}};"
            f"SERVER={host},{port};"
            f"DATABASE={database_name};"
            f"UID={username};"
            f"PWD={password};"
            f"TrustServerCertificate=yes;"
        )
        return f"mssql+pyodbc:///?odbc_connect={params}"

    if db_type == "postgresql":
        # Try psycopg2 if available
        ssl = "?sslmode=require" if use_ssl else ""
        return f"postgresql+psycopg2://{username}:{urllib.parse.quote_plus(password)}@{host}:{port}/{database_name}{ssl}"

    if db_type == "mysql":
        ssl = "?ssl_ca=/path/to/ca" if use_ssl else ""
        return f"mysql+pymysql://{username}:{urllib.parse.quote_plus(password)}@{host}:{port}/{database_name}{ssl}"

    raise ValueError(f"Unsupported db_type: {db_type}. Use sql_server, postgresql, or mysql.")


def get_engine_for_connection(conn) -> "create_engine":
    """Build SQLAlchemy engine from a DWHConnection model instance."""
    if not conn or not conn.password_encrypted:
        raise ValueError("Connection missing or no password")
    url = _build_connection_url(
        db_type=conn.db_type,
        host=conn.host,
        port=conn.port,
        database_name=conn.database_name,
        username=conn.username,
        password=conn.password_encrypted,
        schema_name=conn.schema_name,
        use_ssl=conn.use_ssl,
    )
    return create_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=2)


def test_connection(
    db_type: str,
    host: str,
    port: Optional[int],
    database_name: str,
    username: str,
    password: str,
    schema_name: Optional[str] = None,
    use_ssl: bool = False,
) -> Tuple[bool, str]:
    """
    Test database connection. Returns (success, message).
    """
    try:
        url = _build_connection_url(
            db_type=db_type,
            host=host,
            port=port,
            database_name=database_name,
            username=username,
            password=password,
            schema_name=schema_name,
            use_ssl=use_ssl,
        )
        engine = create_engine(url, pool_pre_ping=True, connect_args={"timeout": 10} if db_type != "sql_server" else {})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "Connection successful"
    except ImportError as e:
        return False, f"Database driver not installed: {e}"
    except SQLAlchemyError as e:
        return False, str(e.orig) if hasattr(e, "orig") else str(e)
    except Exception as e:
        return False, str(e)


def list_tables(
    db_type: str,
    host: str,
    port: Optional[int],
    database_name: str,
    username: str,
    password: str,
    schema_name: Optional[str] = None,
    use_ssl: bool = False,
) -> List[dict]:
    """
    List tables in the database. Returns list of {schema_name, table_name, full_name}.
    """
    try:
        url = _build_connection_url(
            db_type=db_type,
            host=host,
            port=port,
            database_name=database_name,
            username=username,
            password=password,
            schema_name=schema_name,
            use_ssl=use_ssl,
        )
        engine = create_engine(url, pool_pre_ping=True)

        if db_type == "sql_server":
            with engine.connect() as conn:
                if schema_name:
                    result = conn.execute(text("""
                        SELECT TABLE_SCHEMA, TABLE_NAME
                        FROM INFORMATION_SCHEMA.TABLES
                        WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_CATALOG = :db
                        AND TABLE_SCHEMA = :schema
                        ORDER BY TABLE_SCHEMA, TABLE_NAME
                    """), {"db": database_name, "schema": schema_name})
                else:
                    result = conn.execute(text("""
                        SELECT TABLE_SCHEMA, TABLE_NAME
                        FROM INFORMATION_SCHEMA.TABLES
                        WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_CATALOG = :db
                        ORDER BY TABLE_SCHEMA, TABLE_NAME
                    """), {"db": database_name})
                rows = result.fetchall()
            return [
                {"schema_name": r[0], "table_name": r[1], "full_name": f"{r[0]}.{r[1]}" if r[0] else r[1]}
                for r in rows
            ]

        if db_type == "postgresql":
            with engine.connect() as conn:
                schema = schema_name or "public"
                result = conn.execute(text("""
                    SELECT table_schema, table_name
                    FROM information_schema.tables
                    WHERE table_schema = :schema AND table_type = 'BASE TABLE'
                    ORDER BY table_schema, table_name
                """), {"schema": schema})
                rows = result.fetchall()
            return [
                {"schema_name": r[0], "table_name": r[1], "full_name": f"{r[0]}.{r[1]}"}
                for r in rows
            ]

        if db_type == "mysql":
            with engine.connect() as conn:
                result = conn.execute(text("SHOW TABLES"))
                rows = result.fetchall()
            db_name = database_name or "?"
            return [
                {"schema_name": db_name, "table_name": r[0], "full_name": r[0]}
                for r in rows
            ]

        return []
    except Exception as e:
        raise ValueError(str(e))


def list_columns(
    db_type: str,
    host: str,
    port: Optional[int],
    database_name: str,
    username: str,
    password: str,
    table_schema: Optional[str],
    table_name: str,
    use_ssl: bool = False,
) -> List[dict]:
    """
    List columns for a table. Returns list of {column_name, data_type, is_nullable}.
    """
    try:
        url = _build_connection_url(
            db_type=db_type,
            host=host,
            port=port,
            database_name=database_name,
            username=username,
            password=password,
            schema_name=table_schema,
            use_ssl=use_ssl,
        )
        engine = create_engine(url, pool_pre_ping=True)

        if db_type == "sql_server":
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_CATALOG = :db
                    AND (TABLE_SCHEMA = :schema OR (:schema IS NULL AND TABLE_SCHEMA = 'dbo'))
                    AND TABLE_NAME = :tbl
                    ORDER BY ORDINAL_POSITION
                """), {"db": database_name, "schema": table_schema or "dbo", "tbl": table_name})
                rows = result.fetchall()
            return [
                {"column_name": r[0], "data_type": r[1], "is_nullable": r[2] == "YES"}
                for r in rows
            ]

        if db_type == "postgresql":
            schema = table_schema or "public"
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = :schema AND table_name = :tbl
                    ORDER BY ordinal_position
                """), {"schema": schema, "tbl": table_name})
                rows = result.fetchall()
            return [
                {"column_name": r[0], "data_type": r[1], "is_nullable": r[2] == "YES"}
                for r in rows
            ]

        if db_type == "mysql":
            with engine.connect() as conn:
                result = conn.execute(text(f"DESCRIBE `{table_name}`"))
                rows = result.fetchall()
            return [
                {"column_name": r[0], "data_type": r[1], "is_nullable": r[2] == "YES"}
                for r in rows
            ]

        return []
    except Exception as e:
        raise ValueError(str(e))
