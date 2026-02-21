"""Data source extractors for universal budget upload.

Supports multiple data sources:
- Excel files (.xlsx, .xls)
- CSV files
- SQL Server databases
- PostgreSQL databases
- REST APIs
"""
from enum import Enum
from typing import Optional, Any

from .base import DataSourceExtractor, ExtractionError, ConnectionError


class SourceType(str, Enum):
    """Supported data source types"""
    EXCEL = "excel"
    CSV = "csv"
    SQL_SERVER = "sql_server"
    POSTGRESQL = "postgresql"
    API = "api"


def get_extractor(
    source_type: SourceType,
    **kwargs
) -> DataSourceExtractor:
    """Factory function to create the appropriate extractor.
    
    Args:
        source_type: Type of data source
        **kwargs: Source-specific configuration
        
    Returns:
        Configured DataSourceExtractor instance
        
    Raises:
        ValueError: If source_type is not supported
    """
    if source_type == SourceType.EXCEL:
        from .file_extractor import ExcelExtractor
        return ExcelExtractor(
            file_path=kwargs.get("file_path"),
            file_content=kwargs.get("file_content"),
            sheet_name=kwargs.get("sheet_name")
        )
    
    elif source_type == SourceType.CSV:
        from .file_extractor import CSVExtractor
        return CSVExtractor(
            file_path=kwargs.get("file_path"),
            file_content=kwargs.get("file_content"),
            delimiter=kwargs.get("delimiter", ","),
            encoding=kwargs.get("encoding", "utf-8")
        )
    
    elif source_type == SourceType.SQL_SERVER:
        from .sql_extractor import SQLServerExtractor
        return SQLServerExtractor(
            connection_id=kwargs.get("connection_id"),
            connection_config=kwargs.get("connection_config"),
            table_name=kwargs.get("table_name"),
            schema_name=kwargs.get("schema_name"),
            where_clause=kwargs.get("where_clause"),
            db_session=kwargs.get("db_session")
        )
    
    elif source_type == SourceType.POSTGRESQL:
        from .postgres_extractor import PostgreSQLExtractor
        return PostgreSQLExtractor(
            connection_id=kwargs.get("connection_id"),
            connection_config=kwargs.get("connection_config"),
            table_name=kwargs.get("table_name"),
            schema_name=kwargs.get("schema_name"),
            where_clause=kwargs.get("where_clause"),
            db_session=kwargs.get("db_session")
        )
    
    elif source_type == SourceType.API:
        from .api_extractor import APIExtractor
        return APIExtractor(
            url=kwargs.get("url"),
            method=kwargs.get("method", "GET"),
            headers=kwargs.get("headers"),
            auth_type=kwargs.get("auth_type"),
            auth_credentials=kwargs.get("auth_credentials"),
            data_path=kwargs.get("data_path"),
            params=kwargs.get("params")
        )
    
    else:
        raise ValueError(f"Unsupported source type: {source_type}")


__all__ = [
    "DataSourceExtractor",
    "ExtractionError", 
    "ConnectionError",
    "SourceType",
    "get_extractor"
]
