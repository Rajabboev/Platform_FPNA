"""PostgreSQL data source extractor"""
import pandas as pd
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from .base import DataSourceExtractor, ExtractionError, ConnectionError
from ..connection_service import (
    _build_connection_url,
    get_engine_for_connection,
    list_columns as service_list_columns
)


class PostgreSQLExtractor(DataSourceExtractor):
    """Extract data from PostgreSQL databases"""
    
    def __init__(
        self,
        connection_id: Optional[int] = None,
        connection_config: Optional[Dict[str, Any]] = None,
        table_name: Optional[str] = None,
        schema_name: Optional[str] = None,
        where_clause: Optional[str] = None,
        db_session: Optional[Session] = None,
        custom_query: Optional[str] = None
    ):
        """Initialize PostgreSQL extractor.
        
        Args:
            connection_id: ID of saved DWH connection (requires db_session)
            connection_config: Direct connection config dict with host, port, etc.
            table_name: Table to extract from
            schema_name: Schema name (default: public)
            where_clause: Optional WHERE clause for filtering
            db_session: SQLAlchemy session for loading connection by ID
            custom_query: Custom SQL query (overrides table_name)
        """
        self.connection_id = connection_id
        self.connection_config = connection_config
        self.table_name = table_name
        self.schema_name = schema_name or "public"
        self.where_clause = where_clause
        self.db_session = db_session
        self.custom_query = custom_query
        self._engine = None
        self._connection_model = None
    
    def _get_engine(self):
        """Get or create SQLAlchemy engine"""
        if self._engine is not None:
            return self._engine
        
        if self.connection_id and self.db_session:
            from ...models.dwh_connection import DWHConnection
            self._connection_model = self.db_session.query(DWHConnection).filter(
                DWHConnection.id == self.connection_id
            ).first()
            
            if not self._connection_model:
                raise ConnectionError(f"Connection ID {self.connection_id} not found")
            
            self._engine = get_engine_for_connection(self._connection_model)
            
        elif self.connection_config:
            url = _build_connection_url(
                db_type="postgresql",
                host=self.connection_config.get("host"),
                port=self.connection_config.get("port"),
                database_name=self.connection_config.get("database_name"),
                username=self.connection_config.get("username"),
                password=self.connection_config.get("password"),
                schema_name=self.connection_config.get("schema_name"),
                use_ssl=self.connection_config.get("use_ssl", False)
            )
            self._engine = create_engine(url, pool_pre_ping=True)
        else:
            raise ValueError("Either connection_id with db_session or connection_config must be provided")
        
        return self._engine
    
    def _build_query(self, limit: Optional[int] = None) -> str:
        """Build SQL query for extraction"""
        if self.custom_query:
            query = self.custom_query
            if limit and "LIMIT" not in query.upper():
                query = f"{query} LIMIT {limit}"
            return query
        
        if not self.table_name:
            raise ValueError("table_name is required when not using custom_query")
        
        full_table = f'"{self.schema_name}"."{self.table_name}"'
        query = f"SELECT * FROM {full_table}"
        
        if self.where_clause:
            clean_where = self.where_clause.strip()
            if not clean_where.upper().startswith("WHERE"):
                clean_where = f"WHERE {clean_where}"
            query = f"{query} {clean_where}"
        
        if limit:
            query = f"{query} LIMIT {limit}"
        
        return query
    
    def extract(self, limit: Optional[int] = None) -> pd.DataFrame:
        """Extract data from PostgreSQL.
        
        Args:
            limit: Optional limit on rows to extract
            
        Returns:
            DataFrame with extracted data
        """
        try:
            engine = self._get_engine()
            query = self._build_query(limit)
            
            with engine.connect() as conn:
                df = pd.read_sql(text(query), conn)
            
            return df
            
        except Exception as e:
            raise ExtractionError(f"Failed to extract data from PostgreSQL: {str(e)}")
    
    def get_columns(self) -> List[Dict[str, Any]]:
        """Get column information from the table"""
        if not self.table_name:
            if self.custom_query:
                df = self.extract(limit=1)
                return [{"name": col, "type": str(df[col].dtype)} for col in df.columns]
            raise ValueError("table_name is required to get columns")
        
        try:
            config = self._get_connection_config()
            columns = service_list_columns(
                db_type="postgresql",
                host=config["host"],
                port=config["port"],
                database_name=config["database_name"],
                username=config["username"],
                password=config["password"],
                table_schema=self.schema_name,
                table_name=self.table_name,
                use_ssl=config.get("use_ssl", False)
            )
            return [
                {"name": c["column_name"], "type": c["data_type"], "nullable": c["is_nullable"]}
                for c in columns
            ]
        except Exception as e:
            raise ExtractionError(f"Failed to get columns: {str(e)}")
    
    def _get_connection_config(self) -> Dict[str, Any]:
        """Get connection config from model or direct config"""
        if self._connection_model:
            return {
                "host": self._connection_model.host,
                "port": self._connection_model.port,
                "database_name": self._connection_model.database_name,
                "username": self._connection_model.username,
                "password": self._connection_model.password_encrypted,
                "use_ssl": self._connection_model.use_ssl
            }
        elif self.connection_config:
            return self.connection_config
        else:
            self._get_engine()
            return self._get_connection_config()
    
    def test_connection(self) -> Dict[str, Any]:
        """Test PostgreSQL connection"""
        try:
            engine = self._get_engine()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return {
                "success": True,
                "message": "PostgreSQL connection successful"
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e)
            }
    
    def get_tables(self) -> List[Dict[str, Any]]:
        """List available tables in the database"""
        from ..connection_service import list_tables
        
        config = self._get_connection_config()
        return list_tables(
            db_type="postgresql",
            host=config["host"],
            port=config["port"],
            database_name=config["database_name"],
            username=config["username"],
            password=config["password"],
            schema_name=self.schema_name,
            use_ssl=config.get("use_ssl", False)
        )
    
    def get_row_count(self) -> int:
        """Get total row count for the table"""
        if not self.table_name:
            raise ValueError("table_name is required to get row count")
        
        try:
            engine = self._get_engine()
            full_table = f'"{self.schema_name}"."{self.table_name}"'
            query = f"SELECT COUNT(*) FROM {full_table}"
            
            if self.where_clause:
                clean_where = self.where_clause.strip()
                if not clean_where.upper().startswith("WHERE"):
                    clean_where = f"WHERE {clean_where}"
                query = f"{query} {clean_where}"
            
            with engine.connect() as conn:
                result = conn.execute(text(query))
                return result.scalar()
                
        except Exception as e:
            raise ExtractionError(f"Failed to get row count: {str(e)}")
