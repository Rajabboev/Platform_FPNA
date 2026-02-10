"""Pydantic schemas for DWH connections"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class ConnectionBase(BaseModel):
    name: str
    db_type: str = Field(..., description="sql_server, postgresql, mysql, oracle")
    host: str
    port: Optional[int] = None
    database_name: str
    username: str
    schema_name: Optional[str] = None
    use_ssl: bool = False
    description: Optional[str] = None


class ConnectionCreate(ConnectionBase):
    password: str


class ConnectionUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    database_name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    schema_name: Optional[str] = None
    use_ssl: Optional[bool] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None


class ConnectionResponse(ConnectionBase):
    id: int
    is_active: bool
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class ConnectionResponseSafe(ConnectionBase):
    """Response without password - for list/detail"""
    id: int
    is_active: bool
    created_at: Optional[str] = None
    # password never returned

    class Config:
        from_attributes = True


class TestConnectionRequest(BaseModel):
    """Credentials for testing (can override stored)"""
    password: Optional[str] = None


class TableInfo(BaseModel):
    schema_name: Optional[str] = None
    table_name: str
    full_name: str  # schema.table or table


class ColumnInfo(BaseModel):
    column_name: str
    data_type: str
    is_nullable: bool = True


class TableMappingCreate(BaseModel):
    connection_id: Optional[int] = None  # From URL if omitted
    source_schema: Optional[str] = None
    source_table: str
    target_entity: str = Field(..., description="FPNA entity: budgets, budget_line_items, fact_sales, etc.")
    target_description: Optional[str] = None
    column_mapping: Optional[Dict[str, str]] = None
    sync_enabled: bool = True


class TableMappingUpdate(BaseModel):
    source_schema: Optional[str] = None
    source_table: Optional[str] = None
    target_entity: Optional[str] = None
    target_description: Optional[str] = None
    column_mapping: Optional[Dict[str, str]] = None
    is_active: Optional[bool] = None
    sync_enabled: Optional[bool] = None


class TableMappingResponse(BaseModel):
    id: int
    connection_id: int
    source_schema: Optional[str] = None
    source_table: str
    target_entity: str
    target_description: Optional[str] = None
    column_mapping: Optional[Dict[str, str]] = None
    is_active: bool
    sync_enabled: bool

    class Config:
        from_attributes = True
