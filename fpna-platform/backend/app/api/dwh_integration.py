"""
DWH Integration API Endpoints
Handles bidirectional ETL between DWH and FPNA Platform
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List, Dict
from datetime import date
from pydantic import BaseModel, Field

from app.database import get_db
from app.services.dwh_integration_service import DWHIntegrationService, ensure_audit_trail_table
from app.services.balans_signed_balance import sql_signed_balance_sum, sql_signed_balance_row
from app.services.alert_engine import AlertEngine
from app.models.dwh_connection import DWHConnection
from app.models.snapshot import BalanceSnapshot, BaselineBudget, SnapshotImportLog

router = APIRouter(prefix="/dwh", tags=["DWH Integration"])


# ============================================
# Pydantic Schemas
# ============================================

class ColumnMappingSchema(BaseModel):
    source_column: str
    target_column: str


class IngestSnapshotsRequest(BaseModel):
    connection_id: int
    source_table: str = "balans_ato"
    source_schema: Optional[str] = "dbo"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    branch_code: Optional[int] = None
    aggregate_branches: bool = True


class IngestActualsRequest(BaseModel):
    connection_id: int
    source_table: str
    fiscal_year: int
    month: int
    column_mapping: Optional[Dict[str, str]] = None


class GenerateBaselinesRequest(BaseModel):
    fiscal_year: int
    method: str = Field(default="average", description="average, weighted_average, or trend")
    apply_trend: bool = True
    apply_seasonality: bool = True
    account_codes: Optional[List[str]] = None


class ExportBudgetRequest(BaseModel):
    connection_id: int
    budget_id: int
    target_table: str = "fpna_approved_budgets"
    target_schema: Optional[str] = "dbo"
    version_label: Optional[str] = None


class ExportScenarioRequest(BaseModel):
    connection_id: int
    budget_id: int
    scenario_type: str = Field(description="OPTIMISTIC or PESSIMISTIC")
    adjustment_factor: float = Field(description="Multiplier for scenario (e.g., 1.1 for +10%)")
    target_table: str = "fpna_budget_scenarios"


class CreateVersionRequest(BaseModel):
    budget_id: int
    version_label: str = Field(description="Version label (e.g., V2, Final)")


class SetThresholdRequest(BaseModel):
    department: Optional[str] = None
    account_code: Optional[str] = None
    info_threshold: float = 5.0
    warning_threshold: float = 10.0
    critical_threshold: float = 20.0
    notify_department_head: bool = True
    notify_cfo: bool = False


class AlertActionRequest(BaseModel):
    alert_code: str
    notes: Optional[str] = None


# ============================================
# Ingestion Endpoints (DWH -> Platform)
# ============================================

@router.post("/ingest/snapshots", response_model=dict)
def ingest_balance_snapshots(
    request: IngestSnapshotsRequest,
    db: Session = Depends(get_db)
):
    """
    Import balance snapshots from DWH (balans_ato table)
    Aggregates data by account/date/currency across branches
    """
    ensure_audit_trail_table(db)
    service = DWHIntegrationService(db)
    
    try:
        result = service.ingest_balance_snapshots(
            connection_id=request.connection_id,
            source_table=request.source_table,
            source_schema=request.source_schema,
            start_date=request.start_date,
            end_date=request.end_date,
            branch_code=request.branch_code,
            aggregate_branches=request.aggregate_branches
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.post("/ingest/actuals", response_model=dict)
def ingest_actuals(
    request: IngestActualsRequest,
    db: Session = Depends(get_db)
):
    """
    Import actual (fact) data for Plan vs Fact analysis
    Updates variance fields in budget line items
    """
    ensure_audit_trail_table(db)
    service = DWHIntegrationService(db)
    
    try:
        result = service.ingest_actuals(
            connection_id=request.connection_id,
            source_table=request.source_table,
            fiscal_year=request.fiscal_year,
            month=request.month,
            column_mapping=request.column_mapping
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


# ============================================
# Baseline Generation
# ============================================

@router.post("/baselines/generate", response_model=dict)
def generate_baselines(
    request: GenerateBaselinesRequest,
    db: Session = Depends(get_db)
):
    """
    Generate baseline budgets from historical snapshots
    
    Methods:
    - average: Simple average of historical values
    - weighted_average: Recent values weighted more heavily
    - trend: Apply linear trend projection
    """
    ensure_audit_trail_table(db)
    service = DWHIntegrationService(db)
    
    try:
        result = service.generate_baselines(
            fiscal_year=request.fiscal_year,
            method=request.method,
            apply_trend=request.apply_trend,
            apply_seasonality=request.apply_seasonality,
            account_codes=request.account_codes
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Baseline generation failed: {str(e)}")


@router.get("/baselines", response_model=list)
def list_baselines(
    fiscal_year: Optional[int] = None,
    account_code: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List generated baseline budgets"""
    query = db.query(BaselineBudget).filter(BaselineBudget.is_active == True)
    
    if fiscal_year:
        query = query.filter(BaselineBudget.fiscal_year == fiscal_year)
    if account_code:
        query = query.filter(BaselineBudget.account_code == account_code)
    
    baselines = query.order_by(BaselineBudget.fiscal_year.desc(), BaselineBudget.account_code).offset(skip).limit(limit).all()
    
    return [
        {
            "id": b.id,
            "fiscal_year": b.fiscal_year,
            "account_code": b.account_code,
            "currency": b.currency,
            "monthly_values": {
                "jan": float(b.jan or 0),
                "feb": float(b.feb or 0),
                "mar": float(b.mar or 0),
                "apr": float(b.apr or 0),
                "may": float(b.may or 0),
                "jun": float(b.jun or 0),
                "jul": float(b.jul or 0),
                "aug": float(b.aug or 0),
                "sep": float(b.sep or 0),
                "oct": float(b.oct or 0),
                "nov": float(b.nov or 0),
                "dec": float(b.dec or 0)
            },
            "annual_total": float(b.annual_total or 0),
            "calculation_method": b.calculation_method,
            "baseline_version": b.baseline_version,
            "yoy_growth_rate": float(b.yoy_growth_rate or 0) if b.yoy_growth_rate else None
        }
        for b in baselines
    ]


# ============================================
# DWH Data Preview Endpoints
# ============================================

@router.get("/connections/{connection_id}/balans-summary", response_model=dict)
def get_balans_summary(
    connection_id: int,
    db: Session = Depends(get_db)
):
    """
    Get summary of balans_ato data from DWH
    Returns date range, account counts, and sample data
    """
    service = DWHIntegrationService(db)
    
    try:
        dwh_engine = service.get_dwh_engine(connection_id)
        if not dwh_engine:
            raise HTTPException(status_code=404, detail="Connection not found")
        
        _tot_uzs = sql_signed_balance_sum("OSTATALL", "PRIZNALL")
        _cur_uzs = sql_signed_balance_sum("OSTATALL", "PRIZNALL")
        with dwh_engine.connect() as conn:
            # Get summary statistics (signed OSTATALL via PRIZNALL)
            result = conn.execute(text(f"""
                SELECT 
                    COUNT(*) as total_rows,
                    COUNT(DISTINCT KODBALANS) as unique_accounts,
                    COUNT(DISTINCT CURDATE) as unique_dates,
                    COUNT(DISTINCT KODVALUTA) as unique_currencies,
                    COUNT(DISTINCT OTDELENIE) as unique_branches,
                    MIN(CURDATE) as min_date,
                    MAX(CURDATE) as max_date,
                    {_tot_uzs} as total_balance_uzs
                FROM dbo.balans_ato
            """))
            summary = result.fetchone()
            
            # Get available dates
            result = conn.execute(text("""
                SELECT DISTINCT CURDATE 
                FROM dbo.balans_ato 
                ORDER BY CURDATE DESC
            """))
            dates = [str(row[0]) for row in result.fetchall()]
            
            # Get currency distribution
            result = conn.execute(text(f"""
                SELECT 
                    KODVALUTA,
                    COUNT(DISTINCT KODBALANS) as account_count,
                    {_cur_uzs} as total_balance
                FROM dbo.balans_ato
                GROUP BY KODVALUTA
                ORDER BY total_balance DESC
            """))
            currencies = [
                {"code": row[0], "accounts": row[1], "balance": float(row[2] or 0)}
                for row in result.fetchall()
            ]
            
            # Get account class distribution
            result = conn.execute(text("""
                SELECT 
                    LEFT(KODBALANS, 1) as account_class,
                    COUNT(DISTINCT KODBALANS) as account_count
                FROM dbo.balans_ato
                GROUP BY LEFT(KODBALANS, 1)
                ORDER BY account_class
            """))
            account_classes = [
                {"class": row[0], "count": row[1]}
                for row in result.fetchall()
            ]
        
        return {
            "total_rows": summary[0],
            "unique_accounts": summary[1],
            "unique_dates": summary[2],
            "unique_currencies": summary[3],
            "unique_branches": summary[4],
            "date_range": {
                "min": str(summary[5]) if summary[5] else None,
                "max": str(summary[6]) if summary[6] else None
            },
            "total_balance_uzs": float(summary[7] or 0),
            "available_dates": dates[:12],  # Last 12 dates
            "currencies": currencies,
            "account_classes": account_classes
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get summary: {str(e)}")


@router.get("/connections/{connection_id}/balans-preview", response_model=dict)
def preview_balans_data(
    connection_id: int,
    snapshot_date: Optional[str] = None,
    account_code: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    db: Session = Depends(get_db)
):
    """
    Preview balans_ato data from DWH with optional filters
    """
    service = DWHIntegrationService(db)
    
    try:
        dwh_engine = service.get_dwh_engine(connection_id)
        if not dwh_engine:
            raise HTTPException(status_code=404, detail="Connection not found")
        
        where_parts = ["1=1"]
        params = {"limit": limit}
        
        if snapshot_date:
            where_parts.append("CURDATE = :snapshot_date")
            params["snapshot_date"] = snapshot_date
        if account_code:
            where_parts.append("KODBALANS LIKE :account_code")
            params["account_code"] = f"{account_code}%"
        
        where_clause = " AND ".join(where_parts)
        _row_uzs = sql_signed_balance_row("OSTATALL", "PRIZNALL")
        _row_val = sql_signed_balance_row("OSTATALLVAL", "PRIZNALL")

        with dwh_engine.connect() as conn:
            result = conn.execute(text(f"""
                SELECT TOP (:limit)
                    KODBALANS as account_code,
                    CURDATE as snapshot_date,
                    KODVALUTA as currency_code,
                    OTDELENIE as branch_code,
                    {_row_uzs} as balance_uzs,
                    {_row_val} as balance_currency,
                    OSTATALL_IN as incoming_balance,
                    OSTATALL_DT as debit_turnover,
                    OSTATALL_CT as credit_turnover
                FROM dbo.balans_ato
                WHERE {where_clause}
                ORDER BY CURDATE DESC, {_row_uzs} DESC
            """), params)
            
            rows = []
            for row in result.fetchall():
                rows.append({
                    "account_code": str(row[0]).strip(),
                    "snapshot_date": str(row[1]),
                    "currency_code": row[2],
                    "branch_code": row[3],
                    "balance_uzs": float(row[4] or 0),
                    "balance_currency": float(row[5] or 0),
                    "incoming_balance": float(row[6] or 0),
                    "debit_turnover": float(row[7] or 0),
                    "credit_turnover": float(row[8] or 0)
                })
        
        return {
            "count": len(rows),
            "data": rows
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to preview data: {str(e)}")


# ============================================
# Egress Endpoints (Platform -> DWH)
# ============================================

@router.post("/export/budget", response_model=dict)
def export_approved_budget(
    request: ExportBudgetRequest,
    db: Session = Depends(get_db)
):
    """
    Export approved budget to DWH
    Creates versioned budget data for KPI tracking
    """
    ensure_audit_trail_table(db)
    service = DWHIntegrationService(db)
    
    try:
        result = service.export_approved_budget(
            connection_id=request.connection_id,
            budget_id=request.budget_id,
            target_table=request.target_table,
            target_schema=request.target_schema,
            version_label=request.version_label
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.post("/export/scenario", response_model=dict)
def export_scenario(
    request: ExportScenarioRequest,
    db: Session = Depends(get_db)
):
    """
    Export budget scenario (Optimistic/Pessimistic) to DWH
    Used for risk management and liquidity forecasting
    """
    ensure_audit_trail_table(db)
    service = DWHIntegrationService(db)
    
    try:
        result = service.export_scenario(
            connection_id=request.connection_id,
            budget_id=request.budget_id,
            scenario_type=request.scenario_type,
            adjustment_factor=request.adjustment_factor,
            target_table=request.target_table
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


# ============================================
# Version Management
# ============================================

@router.post("/versions/create", response_model=dict)
def create_budget_version(
    request: CreateVersionRequest,
    db: Session = Depends(get_db)
):
    """
    Create a new version of a budget (e.g., 2024_V1 -> 2024_V2)
    Preserves history for audit and comparison
    """
    ensure_audit_trail_table(db)
    service = DWHIntegrationService(db)
    
    try:
        result = service.create_budget_version(
            budget_id=request.budget_id,
            version_label=request.version_label
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Version creation failed: {str(e)}")


# ============================================
# DWH Exploration
# ============================================

@router.get("/connections/{connection_id}/tables", response_model=list)
def list_dwh_tables(
    connection_id: int,
    db: Session = Depends(get_db)
):
    """List available tables in DWH connection"""
    service = DWHIntegrationService(db)
    tables = service.get_dwh_tables(connection_id)
    return tables


@router.get("/connections/{connection_id}/tables/{table_name}/columns", response_model=list)
def get_table_columns(
    connection_id: int,
    table_name: str,
    schema_name: str = Query(default="dbo"),
    db: Session = Depends(get_db)
):
    """Get column metadata for a DWH table"""
    service = DWHIntegrationService(db)
    columns = service.get_table_columns(connection_id, table_name, schema_name)
    return columns


@router.get("/connections/{connection_id}/tables/{table_name}/preview", response_model=dict)
def preview_table_data(
    connection_id: int,
    table_name: str,
    schema_name: str = Query(default="dbo"),
    limit: int = Query(default=100, le=1000),
    db: Session = Depends(get_db)
):
    """Preview data from a DWH table"""
    service = DWHIntegrationService(db)
    columns, rows = service.preview_table_data(connection_id, table_name, schema_name, limit)
    
    serialized_rows = []
    for row in rows:
        serialized_row = {}
        for k, v in row.items():
            if hasattr(v, 'isoformat'):
                serialized_row[k] = v.isoformat()
            elif isinstance(v, (int, float, str, bool, type(None))):
                serialized_row[k] = v
            else:
                serialized_row[k] = str(v)
        serialized_rows.append(serialized_row)
    
    return {
        "columns": columns,
        "rows": serialized_rows,
        "row_count": len(serialized_rows)
    }


# ============================================
# COA Transformation
# ============================================

@router.get("/coa/hierarchy/{account_code}", response_model=dict)
def get_coa_hierarchy(
    account_code: str,
    db: Session = Depends(get_db)
):
    """Get full COA hierarchy for an account code"""
    service = DWHIntegrationService(db)
    hierarchy = service.get_coa_hierarchy_for_account(account_code)
    
    if not hierarchy:
        raise HTTPException(status_code=404, detail=f"Account {account_code} not found")
    
    return hierarchy


# ============================================
# Alert Engine Endpoints
# ============================================

@router.post("/alerts/check", response_model=list)
def check_variances(
    fiscal_year: int,
    month: Optional[int] = None,
    department: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Check budget variances and generate alerts
    Compares Plan vs Fact and creates alerts for threshold breaches
    """
    engine = AlertEngine(db)
    alerts = engine.check_variances(fiscal_year, month, department)
    return alerts


@router.get("/alerts", response_model=list)
def get_pending_alerts(
    department: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db)
):
    """Get pending variance alerts"""
    engine = AlertEngine(db)
    return engine.get_pending_alerts(department, severity, limit)


@router.get("/alerts/summary", response_model=dict)
def get_alert_summary(
    fiscal_year: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get summary of alerts by severity and status"""
    engine = AlertEngine(db)
    return engine.get_alert_summary(fiscal_year)


@router.post("/alerts/acknowledge", response_model=dict)
def acknowledge_alert(
    request: AlertActionRequest,
    db: Session = Depends(get_db)
):
    """Acknowledge a variance alert"""
    engine = AlertEngine(db)
    return engine.acknowledge_alert(request.alert_code, user_id=1, notes=request.notes)


@router.post("/alerts/resolve", response_model=dict)
def resolve_alert(
    request: AlertActionRequest,
    db: Session = Depends(get_db)
):
    """Resolve a variance alert"""
    engine = AlertEngine(db)
    if not request.notes:
        raise HTTPException(status_code=400, detail="Resolution notes required")
    return engine.resolve_alert(request.alert_code, user_id=1, resolution_notes=request.notes)


@router.post("/alerts/thresholds", response_model=dict)
def set_alert_threshold(
    request: SetThresholdRequest,
    db: Session = Depends(get_db)
):
    """Set or update variance alert thresholds"""
    engine = AlertEngine(db)
    return engine.set_threshold(
        department=request.department,
        account_code=request.account_code,
        info_threshold=request.info_threshold,
        warning_threshold=request.warning_threshold,
        critical_threshold=request.critical_threshold,
        notify_department_head=request.notify_department_head,
        notify_cfo=request.notify_cfo
    )


@router.get("/alerts/thresholds", response_model=list)
def list_alert_thresholds(
    db: Session = Depends(get_db)
):
    """List all configured alert thresholds"""
    from sqlalchemy import text
    result = db.execute(text("""
        SELECT department, account_code, info_threshold, warning_threshold,
               critical_threshold, notify_department_head, notify_cfo, is_active
        FROM alert_thresholds
        ORDER BY department, account_code
    """))
    
    return [
        {
            "department": r[0],
            "account_code": r[1],
            "info_threshold": float(r[2] or 5),
            "warning_threshold": float(r[3] or 10),
            "critical_threshold": float(r[4] or 20),
            "notify_department_head": bool(r[5]),
            "notify_cfo": bool(r[6]),
            "is_active": bool(r[7])
        }
        for r in result.fetchall()
    ]


# ============================================
# Variance Reports
# ============================================

@router.get("/reports/variance", response_model=dict)
def get_variance_report(
    fiscal_year: int,
    month: Optional[int] = None,
    department: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Generate variance report for Plan vs Fact analysis
    Shows planned vs actual with variance calculations
    """
    engine = AlertEngine(db)
    return engine.get_variance_report(fiscal_year, month, department)


# ============================================
# Import History
# ============================================

@router.get("/imports/history", response_model=list)
def get_import_history(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get history of snapshot imports"""
    query = db.query(SnapshotImportLog).order_by(SnapshotImportLog.started_at.desc())
    
    if status:
        query = query.filter(SnapshotImportLog.status == status)
    
    logs = query.offset(skip).limit(limit).all()
    
    return [
        {
            "id": log.id,
            "import_batch_id": log.import_batch_id,
            "source_type": log.source_type,
            "source_connection_id": log.source_connection_id,
            "start_date": log.start_date.isoformat() if log.start_date else None,
            "end_date": log.end_date.isoformat() if log.end_date else None,
            "status": log.status,
            "total_records": log.total_records,
            "imported_records": log.imported_records,
            "failed_records": log.failed_records,
            "error_message": log.error_message,
            "started_at": log.started_at.isoformat() if log.started_at else None,
            "completed_at": log.completed_at.isoformat() if log.completed_at else None
        }
        for log in logs
    ]


@router.get("/snapshots", response_model=list)
def list_snapshots(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    account_code: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List imported balance snapshots"""
    query = db.query(BalanceSnapshot)
    
    if start_date:
        query = query.filter(BalanceSnapshot.snapshot_date >= start_date)
    if end_date:
        query = query.filter(BalanceSnapshot.snapshot_date <= end_date)
    if account_code:
        query = query.filter(BalanceSnapshot.account_code == account_code)
    
    snapshots = query.order_by(
        BalanceSnapshot.snapshot_date.desc(),
        BalanceSnapshot.account_code
    ).offset(skip).limit(limit).all()
    
    return [
        {
            "id": s.id,
            "snapshot_date": s.snapshot_date.isoformat(),
            "account_code": s.account_code,
            "currency": s.currency,
            "balance": float(s.balance or 0),
            "balance_uzs": float(s.balance_uzs or 0),
            "fx_rate": float(s.fx_rate or 1),
            "data_source": s.data_source,
            "import_batch_id": s.import_batch_id,
            "is_validated": s.is_validated
        }
        for s in snapshots
    ]


# ============================================
# Audit Trail
# ============================================

@router.get("/audit", response_model=list)
def get_audit_trail(
    operation: Optional[str] = None,
    batch_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get ETL audit trail"""
    from sqlalchemy import text
    
    query = "SELECT batch_id, operation, source_table, target_table, record_count, user_id, details, status, created_at FROM etl_audit_trail WHERE 1=1"
    params = {}
    
    if operation:
        query += " AND operation = :op"
        params["op"] = operation
    if batch_id:
        query += " AND batch_id = :batch"
        params["batch"] = batch_id
    
    query += " ORDER BY created_at DESC OFFSET :skip ROWS FETCH NEXT :limit ROWS ONLY"
    params["skip"] = skip
    params["limit"] = limit
    
    try:
        result = db.execute(text(query), params)
        return [
            {
                "batch_id": r[0],
                "operation": r[1],
                "source_table": r[2],
                "target_table": r[3],
                "record_count": r[4],
                "user_id": r[5],
                "details": r[6],
                "status": r[7],
                "created_at": r[8].isoformat() if r[8] else None
            }
            for r in result.fetchall()
        ]
    except Exception:
        return []
