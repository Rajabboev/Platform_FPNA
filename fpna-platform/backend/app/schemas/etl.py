"""Pydantic schemas for ETL jobs"""

from pydantic import BaseModel, Field
from typing import Optional, Dict


class ETLJobBase(BaseModel):
    name: str
    description: Optional[str] = None
    source_type: str = Field(..., description="dwh_connection | fpna_app")
    source_connection_id: Optional[int] = None
    source_schema: Optional[str] = None
    source_table: str
    target_type: str = Field(..., description="dwh_connection | fpna_app")
    target_connection_id: Optional[int] = None
    target_schema: Optional[str] = None
    target_table: str
    column_mapping: Optional[Dict[str, str]] = None
    create_target_if_missing: bool = False
    load_mode: str = "full_replace"  # full_replace | append


class ETLJobCreate(ETLJobBase):
    pass


class ETLJobUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    source_schema: Optional[str] = None
    source_table: Optional[str] = None
    target_schema: Optional[str] = None
    target_table: Optional[str] = None
    column_mapping: Optional[Dict[str, str]] = None
    create_target_if_missing: Optional[bool] = None
    load_mode: Optional[str] = None
    is_active: Optional[bool] = None


class ETLJobResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    source_type: str
    source_connection_id: Optional[int] = None
    source_schema: Optional[str] = None
    source_table: str
    target_type: str
    target_connection_id: Optional[int] = None
    target_schema: Optional[str] = None
    target_table: str
    column_mapping: Optional[Dict[str, str]] = None
    create_target_if_missing: bool
    load_mode: str
    is_active: bool
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class ETLRunResponse(BaseModel):
    id: int
    job_id: int
    status: str
    rows_extracted: int
    rows_loaded: int
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None

    class Config:
        from_attributes = True
