"""DWH Connections API - manage and test data warehouse connections"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.dwh_connection import DWHConnection, DWHTableMapping
from app.models.user import User
from app.schemas.connection import (
    ConnectionCreate,
    ConnectionUpdate,
    ConnectionResponseSafe,
    TestConnectionRequest,
    TableInfo,
    ColumnInfo,
    TableMappingCreate,
    TableMappingUpdate,
    TableMappingResponse,
)
from app.utils.dependencies import get_current_active_user
from app.services.connection_service import (
    test_connection as svc_test_connection,
    list_tables as svc_list_tables,
    list_columns as svc_list_columns,
)

# Paths without trailing slash so /api/v1/connections works (avoids 404 from proxy/clients)
router = APIRouter(prefix="/connections", tags=["connections"])


def _conn_to_response(c: DWHConnection) -> ConnectionResponseSafe:
    return ConnectionResponseSafe(
        id=c.id,
        name=c.name,
        db_type=c.db_type,
        host=c.host,
        port=c.port,
        database_name=c.database_name,
        username=c.username,
        schema_name=c.schema_name,
        use_ssl=c.use_ssl,
        description=c.description,
        is_active=c.is_active,
        created_at=c.created_at.isoformat() if c.created_at else None,
    )


@router.get("", response_model=List[ConnectionResponseSafe])
def list_connections(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List all DWH connections."""
    conns = db.query(DWHConnection).order_by(DWHConnection.name).all()
    return [_conn_to_response(c) for c in conns]


@router.post("", response_model=ConnectionResponseSafe, status_code=status.HTTP_201_CREATED)
def create_connection(
    payload: ConnectionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Create a new DWH connection."""
    if db.query(DWHConnection).filter(DWHConnection.name == payload.name).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Connection name already exists")
    conn = DWHConnection(
        name=payload.name,
        db_type=payload.db_type,
        host=payload.host,
        port=payload.port,
        database_name=payload.database_name,
        username=payload.username,
        password_encrypted=payload.password,  # TODO: encrypt in production
        schema_name=payload.schema_name,
        use_ssl=payload.use_ssl,
        description=payload.description,
        created_by_user_id=current_user.id,
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return _conn_to_response(conn)


@router.post("/test-new")
def test_new_connection(
    payload: ConnectionCreate,
    current_user: User = Depends(get_current_active_user),
):
    """Test a connection before saving (validate credentials)."""
    ok, msg = svc_test_connection(
        db_type=payload.db_type,
        host=payload.host,
        port=payload.port,
        database_name=payload.database_name,
        username=payload.username,
        password=payload.password,
        schema_name=payload.schema_name,
        use_ssl=payload.use_ssl,
    )
    return {"success": ok, "message": msg}


@router.get("/{connection_id}", response_model=ConnectionResponseSafe)
def get_connection(
    connection_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get a connection by ID."""
    conn = db.query(DWHConnection).filter(DWHConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    return _conn_to_response(conn)


@router.patch("/{connection_id}", response_model=ConnectionResponseSafe)
def update_connection(
    connection_id: int,
    payload: ConnectionUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Update a connection."""
    conn = db.query(DWHConnection).filter(DWHConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    data = payload.model_dump(exclude_unset=True)
    if "password" in data:
        conn.password_encrypted = data.pop("password")
    for k, v in data.items():
        setattr(conn, k, v)
    db.commit()
    db.refresh(conn)
    return _conn_to_response(conn)


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection(
    connection_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Delete (soft-deactivate) a connection."""
    conn = db.query(DWHConnection).filter(DWHConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    conn.is_active = False
    db.commit()
    return None


@router.post("/{connection_id}/test")
def test_connection(
    connection_id: int,
    body: TestConnectionRequest = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Test a connection. Optionally pass password to override stored."""
    conn = db.query(DWHConnection).filter(DWHConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    password = body.password if body and body.password else (conn.password_encrypted or "")
    if not password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password required to test connection")
    ok, msg = svc_test_connection(
        db_type=conn.db_type,
        host=conn.host,
        port=conn.port,
        database_name=conn.database_name,
        username=conn.username,
        password=password,
        schema_name=conn.schema_name,
        use_ssl=conn.use_ssl,
    )
    return {"success": ok, "message": msg}


@router.get("/{connection_id}/tables", response_model=List[TableInfo])
def get_tables(
    connection_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List tables in the DWH database."""
    conn = db.query(DWHConnection).filter(DWHConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    if not conn.password_encrypted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Connection has no stored password")
    try:
        tables = svc_list_tables(
            db_type=conn.db_type,
            host=conn.host,
            port=conn.port,
            database_name=conn.database_name,
            username=conn.username,
            password=conn.password_encrypted,
            schema_name=conn.schema_name,
            use_ssl=conn.use_ssl,
        )
        return [TableInfo(**t) for t in tables]
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{connection_id}/tables/{table_name}/columns", response_model=List[ColumnInfo])
def get_table_columns(
    connection_id: int,
    table_name: str,
    schema_name: str = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List columns for a table."""
    conn = db.query(DWHConnection).filter(DWHConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    if not conn.password_encrypted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Connection has no stored password")
    try:
        cols = svc_list_columns(
            db_type=conn.db_type,
            host=conn.host,
            port=conn.port,
            database_name=conn.database_name,
            username=conn.username,
            password=conn.password_encrypted,
            table_schema=schema_name or conn.schema_name,
            table_name=table_name,
            use_ssl=conn.use_ssl,
        )
        return [ColumnInfo(**c) for c in cols]
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# Table mappings
@router.get("/{connection_id}/mappings", response_model=List[TableMappingResponse])
def list_mappings(
    connection_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List table mappings for a connection."""
    conn = db.query(DWHConnection).filter(DWHConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    mappings = db.query(DWHTableMapping).filter(
        DWHTableMapping.connection_id == connection_id,
        DWHTableMapping.is_active == True,
    ).all()
    return [
        TableMappingResponse(
            id=m.id,
            connection_id=m.connection_id,
            source_schema=m.source_schema,
            source_table=m.source_table,
            target_entity=m.target_entity,
            target_description=m.target_description,
            column_mapping=m.column_mapping,
            is_active=m.is_active,
            sync_enabled=m.sync_enabled,
        )
        for m in mappings
    ]


@router.post("/{connection_id}/mappings", response_model=TableMappingResponse, status_code=status.HTTP_201_CREATED)
def create_mapping(
    connection_id: int,
    payload: TableMappingCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Create a table mapping."""
    conn = db.query(DWHConnection).filter(DWHConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    # Use path connection_id (ignore payload.connection_id if present)
    m = DWHTableMapping(
        connection_id=connection_id,
        source_schema=payload.source_schema,
        source_table=payload.source_table,
        target_entity=payload.target_entity,
        target_description=payload.target_description,
        column_mapping=payload.column_mapping,
        sync_enabled=payload.sync_enabled,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return TableMappingResponse(
        id=m.id,
        connection_id=m.connection_id,
        source_schema=m.source_schema,
        source_table=m.source_table,
        target_entity=m.target_entity,
        target_description=m.target_description,
        column_mapping=m.column_mapping,
        is_active=m.is_active,
        sync_enabled=m.sync_enabled,
    )


@router.patch("/{connection_id}/mappings/{mapping_id}", response_model=TableMappingResponse)
def update_mapping(
    connection_id: int,
    mapping_id: int,
    payload: TableMappingUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Update a table mapping."""
    m = db.query(DWHTableMapping).filter(
        DWHTableMapping.id == mapping_id,
        DWHTableMapping.connection_id == connection_id,
    ).first()
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping not found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(m, k, v)
    db.commit()
    db.refresh(m)
    return TableMappingResponse(
        id=m.id,
        connection_id=m.connection_id,
        source_schema=m.source_schema,
        source_table=m.source_table,
        target_entity=m.target_entity,
        target_description=m.target_description,
        column_mapping=m.column_mapping,
        is_active=m.is_active,
        sync_enabled=m.sync_enabled,
    )


@router.delete("/{connection_id}/mappings/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mapping(
    connection_id: int,
    mapping_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Delete a table mapping."""
    m = db.query(DWHTableMapping).filter(
        DWHTableMapping.id == mapping_id,
        DWHTableMapping.connection_id == connection_id,
    ).first()
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping not found")
    m.is_active = False
    db.commit()
    return None
