"""
Universal Budget Upload API - supports multiple data sources
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from typing import Optional
import os
import json
from datetime import datetime

from app.database import get_db
from app.models.budget import Budget, BudgetLineItem, BudgetStatus
from app.config import settings
from app.schemas.data_source import (
    SourceType,
    PreviewRequest,
    PreviewResponse,
    ValidateMappingRequest,
    ValidateMappingResponse,
    ImportFromDatabaseRequest,
    ImportFromAPIRequest,
    ImportResponse,
    TargetSchemaResponse,
    TargetSchemaField,
    TestConnectionRequest,
    TestConnectionResponse,
    ColumnMappingSuggestion,
    ColumnMapping,
    HeaderValues,
    FileSourceConfig,
)
from app.services.data_sources import get_extractor, SourceType as ExtractorSourceType
from app.services.column_mapping_service import (
    get_target_schema,
    suggest_mapping,
    validate_mapping,
    transform_to_budget_format,
)

router = APIRouter(prefix="/budgets/upload", tags=["budget-upload"])

os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)


@router.get("/target-schema", response_model=TargetSchemaResponse)
def get_budget_target_schema():
    """Get the target budget schema definition for mapping UI"""
    schema = get_target_schema()
    
    header_fields = [
        TargetSchemaField(
            name=name,
            type=config["type"],
            required=config.get("required", False),
            description=config.get("description", ""),
            default=config.get("default")
        )
        for name, config in schema["header"].items()
    ]
    
    line_item_fields = [
        TargetSchemaField(
            name=name,
            type=config["type"],
            required=config.get("required", False),
            description=config.get("description", ""),
            default=config.get("default")
        )
        for name, config in schema["line_items"].items()
    ]
    
    return TargetSchemaResponse(
        header_fields=header_fields,
        line_item_fields=line_item_fields
    )


@router.post("/test-connection", response_model=TestConnectionResponse)
def test_data_source_connection(
    request: TestConnectionRequest,
    db: Session = Depends(get_db)
):
    """Test connection to a data source"""
    try:
        if request.source_type in [SourceType.SQL_SERVER, SourceType.POSTGRESQL]:
            if not request.database_config:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="database_config is required for database sources"
                )
            
            extractor = get_extractor(
                source_type=ExtractorSourceType(request.source_type.value),
                connection_id=request.database_config.connection_id,
                table_name=request.database_config.table_name,
                schema_name=request.database_config.schema_name,
                db_session=db
            )
        
        elif request.source_type == SourceType.API:
            if not request.api_config:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="api_config is required for API sources"
                )
            
            extractor = get_extractor(
                source_type=ExtractorSourceType.API,
                url=request.api_config.url,
                method=request.api_config.method,
                headers=request.api_config.headers,
                auth_type=request.api_config.auth_type.value if request.api_config.auth_type else None,
                auth_credentials=request.api_config.auth_credentials,
                data_path=request.api_config.data_path,
                params=request.api_config.params
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Connection test not supported for {request.source_type}"
            )
        
        result = extractor.test_connection()
        return TestConnectionResponse(
            success=result["success"],
            message=result["message"],
            details=result.get("details")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        return TestConnectionResponse(
            success=False,
            message=str(e)
        )


@router.post("/preview/file", response_model=PreviewResponse)
async def preview_file_data(
    file: UploadFile = File(...),
    source_type: SourceType = Form(...),
    sheet_name: Optional[str] = Form(None),
    delimiter: str = Form(","),
    encoding: str = Form("utf-8"),
    rows: int = Form(10)
):
    """Preview data from uploaded file (Excel or CSV)"""
    if source_type not in [SourceType.EXCEL, SourceType.CSV]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_type must be 'excel' or 'csv' for file preview"
        )
    
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided"
        )
    
    contents = await file.read()
    
    if len(contents) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max size: {settings.MAX_UPLOAD_SIZE / 1024 / 1024}MB"
        )
    
    try:
        extractor = get_extractor(
            source_type=ExtractorSourceType(source_type.value),
            file_content=contents,
            sheet_name=sheet_name,
            delimiter=delimiter,
            encoding=encoding
        )
        
        preview_result = extractor.preview(rows=rows)
        
        suggestions = suggest_mapping(
            [col["name"] for col in preview_result["columns"]],
            schema_type="line_items"
        )
        
        return PreviewResponse(
            success=True,
            columns=preview_result["columns"],
            data=preview_result["data"],
            row_count=preview_result["row_count"],
            suggested_mappings=[
                ColumnMappingSuggestion(**s) for s in suggestions
            ]
        )
        
    except Exception as e:
        return PreviewResponse(
            success=False,
            message=str(e)
        )


@router.post("/preview/database", response_model=PreviewResponse)
def preview_database_data(
    request: PreviewRequest,
    db: Session = Depends(get_db)
):
    """Preview data from database connection"""
    if request.source_type not in [SourceType.SQL_SERVER, SourceType.POSTGRESQL]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_type must be 'sql_server' or 'postgresql' for database preview"
        )
    
    if not request.database_config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="database_config is required"
        )
    
    try:
        extractor = get_extractor(
            source_type=ExtractorSourceType(request.source_type.value),
            connection_id=request.database_config.connection_id,
            table_name=request.database_config.table_name,
            schema_name=request.database_config.schema_name,
            where_clause=request.database_config.where_clause,
            db_session=db
        )
        
        preview_result = extractor.preview(rows=request.rows)
        
        suggestions = suggest_mapping(
            [col["name"] for col in preview_result["columns"]],
            schema_type="line_items"
        )
        
        total_rows = None
        try:
            total_rows = extractor.get_row_count()
        except:
            pass
        
        return PreviewResponse(
            success=True,
            columns=preview_result["columns"],
            data=preview_result["data"],
            row_count=preview_result["row_count"],
            total_rows=total_rows,
            suggested_mappings=[
                ColumnMappingSuggestion(**s) for s in suggestions
            ]
        )
        
    except Exception as e:
        return PreviewResponse(
            success=False,
            message=str(e)
        )


@router.post("/preview/api", response_model=PreviewResponse)
def preview_api_data(request: PreviewRequest):
    """Preview data from REST API"""
    if request.source_type != SourceType.API:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_type must be 'api' for API preview"
        )
    
    if not request.api_config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="api_config is required"
        )
    
    try:
        extractor = get_extractor(
            source_type=ExtractorSourceType.API,
            url=request.api_config.url,
            method=request.api_config.method,
            headers=request.api_config.headers,
            auth_type=request.api_config.auth_type.value if request.api_config.auth_type else None,
            auth_credentials=request.api_config.auth_credentials,
            data_path=request.api_config.data_path,
            params=request.api_config.params,
            body=request.api_config.body
        )
        
        preview_result = extractor.preview(rows=request.rows)
        
        suggestions = suggest_mapping(
            [col["name"] for col in preview_result["columns"]],
            schema_type="line_items"
        )
        
        return PreviewResponse(
            success=True,
            columns=preview_result["columns"],
            data=preview_result["data"],
            row_count=preview_result["row_count"],
            suggested_mappings=[
                ColumnMappingSuggestion(**s) for s in suggestions
            ]
        )
        
    except Exception as e:
        return PreviewResponse(
            success=False,
            message=str(e)
        )


@router.post("/validate-mapping", response_model=ValidateMappingResponse)
def validate_column_mapping(request: ValidateMappingRequest):
    """Validate column mapping before import"""
    mapping_dicts = [m.model_dump() for m in request.mapping]
    
    result = validate_mapping(
        mapping=mapping_dicts,
        source_columns=request.source_columns,
        schema_type=request.schema_type
    )
    
    return ValidateMappingResponse(**result)


@router.post("/import/file", response_model=ImportResponse)
async def import_from_file(
    file: UploadFile = File(...),
    source_type: str = Form(...),
    mapping: str = Form(...),
    header_values: str = Form(...),
    uploaded_by: str = Form("system"),
    sheet_name: Optional[str] = Form(None),
    delimiter: str = Form(","),
    encoding: str = Form("utf-8"),
    db: Session = Depends(get_db)
):
    """Import budget from uploaded file (Excel or CSV)"""
    src_type = SourceType(source_type)
    if src_type not in [SourceType.EXCEL, SourceType.CSV]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_type must be 'excel' or 'csv'"
        )
    
    try:
        mapping_list = json.loads(mapping)
        header_dict = json.loads(header_values)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON in mapping or header_values: {str(e)}"
        )
    
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided"
        )
    
    contents = await file.read()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    temp_filename = f"{timestamp}_{file.filename}"
    temp_filepath = os.path.join(settings.UPLOAD_FOLDER, temp_filename)
    
    with open(temp_filepath, 'wb') as f:
        f.write(contents)
    
    try:
        extractor = get_extractor(
            source_type=ExtractorSourceType(src_type.value),
            file_content=contents,
            sheet_name=sheet_name,
            delimiter=delimiter,
            encoding=encoding
        )
        
        df = extractor.extract()
        
        budget_data = transform_to_budget_format(
            df=df,
            mapping=mapping_list,
            header_values=header_dict
        )
        
        budget = _create_budget_from_data(
            db=db,
            budget_data=budget_data,
            source_file=temp_filename,
            uploaded_by=uploaded_by,
            source_type=src_type.value
        )
        
        return ImportResponse(
            success=True,
            budget_id=budget.id,
            budget_code=budget.budget_code,
            message=f"Successfully imported {len(budget_data['line_items'])} line items",
            summary=budget_data["summary"]
        )
        
    except Exception as e:
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}"
        )


@router.post("/import/database", response_model=ImportResponse)
def import_from_database(
    request: ImportFromDatabaseRequest,
    db: Session = Depends(get_db)
):
    """Import budget from database connection"""
    if request.source_type not in [SourceType.SQL_SERVER, SourceType.POSTGRESQL]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_type must be 'sql_server' or 'postgresql'"
        )
    
    try:
        extractor = get_extractor(
            source_type=ExtractorSourceType(request.source_type.value),
            connection_id=request.database_config.connection_id,
            table_name=request.database_config.table_name,
            schema_name=request.database_config.schema_name,
            where_clause=request.database_config.where_clause,
            db_session=db
        )
        
        df = extractor.extract()
        
        mapping_dicts = [m.model_dump() for m in request.mapping]
        header_dict = request.header_values.model_dump()
        
        budget_data = transform_to_budget_format(
            df=df,
            mapping=mapping_dicts,
            header_values=header_dict
        )
        
        source_desc = f"{request.source_type.value}:{request.database_config.connection_id}/{request.database_config.table_name}"
        
        budget = _create_budget_from_data(
            db=db,
            budget_data=budget_data,
            source_file=source_desc,
            uploaded_by=request.uploaded_by or "system",
            source_type=request.source_type.value
        )
        
        return ImportResponse(
            success=True,
            budget_id=budget.id,
            budget_code=budget.budget_code,
            message=f"Successfully imported {len(budget_data['line_items'])} line items from database",
            summary=budget_data["summary"]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}"
        )


@router.post("/import/api", response_model=ImportResponse)
def import_from_api(
    request: ImportFromAPIRequest,
    db: Session = Depends(get_db)
):
    """Import budget from REST API"""
    try:
        extractor = get_extractor(
            source_type=ExtractorSourceType.API,
            url=request.api_config.url,
            method=request.api_config.method,
            headers=request.api_config.headers,
            auth_type=request.api_config.auth_type.value if request.api_config.auth_type else None,
            auth_credentials=request.api_config.auth_credentials,
            data_path=request.api_config.data_path,
            params=request.api_config.params,
            body=request.api_config.body
        )
        
        df = extractor.extract()
        
        mapping_dicts = [m.model_dump() for m in request.mapping]
        header_dict = request.header_values.model_dump()
        
        budget_data = transform_to_budget_format(
            df=df,
            mapping=mapping_dicts,
            header_values=header_dict
        )
        
        source_desc = f"api:{request.api_config.url}"
        
        budget = _create_budget_from_data(
            db=db,
            budget_data=budget_data,
            source_file=source_desc,
            uploaded_by=request.uploaded_by or "system",
            source_type="api"
        )
        
        return ImportResponse(
            success=True,
            budget_id=budget.id,
            budget_code=budget.budget_code,
            message=f"Successfully imported {len(budget_data['line_items'])} line items from API",
            summary=budget_data["summary"]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}"
        )


def _create_budget_from_data(
    db: Session,
    budget_data: dict,
    source_file: str,
    uploaded_by: str,
    source_type: str
) -> Budget:
    """Create budget and line items from transformed data"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    budget_code = f"BDG-{budget_data['header']['fiscal_year']}-{timestamp}"
    
    new_budget = Budget(
        budget_code=budget_code,
        fiscal_year=budget_data['header']['fiscal_year'],
        department=budget_data['header'].get('department', ''),
        branch=budget_data['header'].get('branch', ''),
        total_amount=budget_data['total_amount'],
        currency=budget_data['header'].get('currency', 'USD'),
        description=budget_data['header'].get('description', ''),
        notes=f"Imported from {source_type}",
        status=BudgetStatus.DRAFT,
        source_file=source_file,
        uploaded_by=uploaded_by
    )
    
    db.add(new_budget)
    db.flush()
    
    for item_data in budget_data['line_items']:
        line_item = BudgetLineItem(
            budget_id=new_budget.id,
            account_code=item_data.get('account_code', ''),
            account_name=item_data.get('account_name', ''),
            category=item_data.get('category'),
            month=item_data.get('month'),
            quarter=item_data.get('quarter'),
            year=item_data.get('year'),
            amount=item_data.get('amount', 0),
            quantity=item_data.get('quantity'),
            unit_price=item_data.get('unit_price'),
            notes=item_data.get('notes')
        )
        db.add(line_item)
    
    db.commit()
    db.refresh(new_budget)
    
    try:
        from app.services.notification_service import notify_managers_uploaded
        notify_managers_uploaded(new_budget, uploaded_by, db)
    except Exception:
        pass
    
    return new_budget
