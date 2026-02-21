"""Pydantic schemas for universal data source upload"""
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, HttpUrl


class SourceType(str, Enum):
    """Supported data source types"""
    EXCEL = "excel"
    CSV = "csv"
    SQL_SERVER = "sql_server"
    POSTGRESQL = "postgresql"
    API = "api"


class AuthType(str, Enum):
    """API authentication types"""
    NONE = "none"
    BASIC = "basic"
    BEARER = "bearer"
    API_KEY = "api_key"


class ColumnMapping(BaseModel):
    """Single column mapping from source to target"""
    source_column: str = Field(..., description="Source column name")
    target_field: str = Field(..., description="Target budget field name")


class ColumnMappingSuggestion(BaseModel):
    """Suggested column mapping with confidence"""
    source_column: str
    suggested_target: Optional[str] = None
    confidence: float = 0
    required: bool = False


class DatabaseSourceConfig(BaseModel):
    """Configuration for database source (SQL Server or PostgreSQL)"""
    connection_id: int = Field(..., description="ID of saved DWH connection")
    schema_name: Optional[str] = Field(None, description="Database schema name")
    table_name: str = Field(..., description="Table to extract from")
    where_clause: Optional[str] = Field(None, description="Optional WHERE clause filter")


class APISourceConfig(BaseModel):
    """Configuration for REST API source"""
    url: str = Field(..., description="API endpoint URL")
    method: str = Field("GET", description="HTTP method (GET or POST)")
    headers: Optional[Dict[str, str]] = Field(None, description="Custom HTTP headers")
    auth_type: AuthType = Field(AuthType.NONE, description="Authentication type")
    auth_credentials: Optional[Dict[str, str]] = Field(
        None, 
        description="Auth credentials: basic={username, password}, bearer={token}, api_key={key, header_name or param_name}"
    )
    data_path: Optional[str] = Field(
        None, 
        description="JSON path to data array (e.g., 'data', 'results', 'data.items')"
    )
    params: Optional[Dict[str, Any]] = Field(None, description="URL query parameters")
    body: Optional[Dict[str, Any]] = Field(None, description="Request body for POST")


class FileSourceConfig(BaseModel):
    """Configuration for file source (Excel or CSV)"""
    sheet_name: Optional[str] = Field(None, description="Excel sheet name (default: first sheet)")
    delimiter: str = Field(",", description="CSV delimiter character")
    encoding: str = Field("utf-8", description="File encoding")


class HeaderValues(BaseModel):
    """Budget header values for import"""
    fiscal_year: int = Field(..., description="Budget fiscal year")
    department: Optional[str] = Field("", description="Department name")
    branch: Optional[str] = Field("", description="Branch/location")
    currency: str = Field("USD", description="Currency code")
    description: Optional[str] = Field("", description="Budget description")


class PreviewRequest(BaseModel):
    """Request to preview data from a source"""
    source_type: SourceType
    database_config: Optional[DatabaseSourceConfig] = None
    api_config: Optional[APISourceConfig] = None
    file_config: Optional[FileSourceConfig] = None
    rows: int = Field(10, ge=1, le=100, description="Number of rows to preview")


class PreviewResponse(BaseModel):
    """Response from data preview"""
    success: bool
    columns: List[Dict[str, Any]] = Field(default_factory=list)
    data: List[Dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    total_rows: Optional[int] = None
    message: Optional[str] = None
    suggested_mappings: Optional[List[ColumnMappingSuggestion]] = None


class ValidateMappingRequest(BaseModel):
    """Request to validate column mapping"""
    source_columns: List[str] = Field(..., description="List of source column names")
    mapping: List[ColumnMapping] = Field(..., description="Proposed column mappings")
    schema_type: str = Field("line_items", description="Target schema type")


class ValidateMappingResponse(BaseModel):
    """Response from mapping validation"""
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    mapped_fields: List[str] = Field(default_factory=list)
    missing_required: List[str] = Field(default_factory=list)
    coverage: Dict[str, int] = Field(default_factory=dict)


class ImportFromDatabaseRequest(BaseModel):
    """Request to import budget from database"""
    source_type: SourceType = Field(..., description="sql_server or postgresql")
    database_config: DatabaseSourceConfig
    mapping: List[ColumnMapping]
    header_values: HeaderValues
    uploaded_by: Optional[str] = None


class ImportFromAPIRequest(BaseModel):
    """Request to import budget from API"""
    api_config: APISourceConfig
    mapping: List[ColumnMapping]
    header_values: HeaderValues
    uploaded_by: Optional[str] = None


class ImportFromFileRequest(BaseModel):
    """Request metadata for file import (file sent as multipart)"""
    source_type: SourceType = Field(..., description="excel or csv")
    file_config: Optional[FileSourceConfig] = None
    mapping: List[ColumnMapping]
    header_values: HeaderValues
    uploaded_by: Optional[str] = None


class TargetSchemaField(BaseModel):
    """Definition of a target schema field"""
    name: str
    type: str
    required: bool
    description: str
    default: Optional[Any] = None


class TargetSchemaResponse(BaseModel):
    """Response with target schema definition"""
    header_fields: List[TargetSchemaField]
    line_item_fields: List[TargetSchemaField]


class ImportResponse(BaseModel):
    """Response from budget import"""
    success: bool
    budget_id: Optional[int] = None
    budget_code: Optional[str] = None
    message: str
    summary: Optional[Dict[str, Any]] = None


class TestConnectionRequest(BaseModel):
    """Request to test a data source connection"""
    source_type: SourceType
    database_config: Optional[DatabaseSourceConfig] = None
    api_config: Optional[APISourceConfig] = None


class TestConnectionResponse(BaseModel):
    """Response from connection test"""
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None
