"""
DWH Integration Service - Bidirectional ETL Controller
Handles data flow between DWH and FPNA Platform

Features:
- Ingestion: DWH -> Platform (snapshots, actuals)
- Egress: Platform -> DWH (approved budgets, scenarios)
- Column mapping with COA transformation
- Version management for budget cycles
- Audit trail for all operations
"""

from sqlalchemy.orm import Session
from sqlalchemy import text, create_engine
from sqlalchemy.engine import Engine
from typing import List, Dict, Optional, Any, Tuple
from datetime import date, datetime
from decimal import Decimal
import uuid
import logging

from app.models.dwh_connection import DWHConnection
from app.models.snapshot import BalanceSnapshot, BaselineBudget, SnapshotImportLog
from app.models.coa import Account, AccountClass, AccountGroup, AccountCategory
from app.models.budget import Budget, BudgetLineItem, BudgetStatus
from app.models.currency import CurrencyRate

logger = logging.getLogger(__name__)


class DWHColumnMapping:
    """Standard column mappings for DWH tables"""
    
    # Mapping for balans_ato table (raw DWH format)
    BALANS_ATO = {
        "snapshot_date": "CURDATE",
        "account_code": "KODBALANS",
        "currency_code": "KODVALUTA",
        "branch_code": "OTDELENIE",
        "balance_uzs": "OSTATALL",           # Outgoing balance in UZS equivalent
        "balance_currency": "OSTATALLVAL",    # Outgoing balance in original currency
        "balance_uzs_resident": "OSTATUZSREZ",
        "balance_uzs_nonresident": "OSTATUZSNEREZ",
        "balance_val_resident": "OSTATVALREZ",
        "balance_val_nonresident": "OSTATVALNEREZ",
        "incoming_balance_uzs": "OSTATALL_IN",
        "incoming_balance_val": "OSTATALLVAL_IN",
        "debit_turnover": "OSTATALL_DT",
        "credit_turnover": "OSTATALL_CT",
    }
    
    # Currency code mapping (ISO numeric to ISO alpha)
    CURRENCY_CODES = {
        0: 'UZS',
        860: 'UZS',
        840: 'USD',
        978: 'EUR',
        643: 'RUB',
        756: 'CHF',
        826: 'GBP',
        392: 'JPY',
        156: 'CNY',
        398: 'KZT',
    }
    
    BUDGET_EXPORT = {
        "budget_code": "budget_code",
        "fiscal_year": "fiscal_year",
        "account_code": "account_code",
        "month": "month",
        "amount": "planned_amount",
        "amount_uzs": "planned_amount_uzs",
        "currency": "currency",
        "department": "department",
        "version": "budget_version",
        "scenario": "scenario_type",
    }


class AuditTrail:
    """Audit trail entry for ETL operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def log(
        self,
        operation: str,
        source_table: str,
        target_table: str,
        record_count: int,
        user_id: Optional[int] = None,
        batch_id: Optional[str] = None,
        details: Optional[Dict] = None,
        status: str = "SUCCESS"
    ):
        """Log an ETL operation to audit trail"""
        try:
            self.db.execute(text("""
                INSERT INTO etl_audit_trail 
                (batch_id, operation, source_table, target_table, record_count, 
                 user_id, details, status, created_at)
                VALUES (:batch_id, :operation, :source_table, :target_table, :record_count,
                        :user_id, :details, :status, GETUTCDATE())
            """), {
                "batch_id": batch_id or str(uuid.uuid4()),
                "operation": operation,
                "source_table": source_table,
                "target_table": target_table,
                "record_count": record_count,
                "user_id": user_id,
                "details": str(details) if details else None,
                "status": status
            })
            self.db.commit()
        except Exception as e:
            logger.warning(f"Failed to log audit trail: {e}")


class DWHIntegrationService:
    """
    Main DWH Integration Service
    Handles bidirectional data flow between DWH and FPNA Platform
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditTrail(db)
    
    def get_dwh_engine(self, connection_id: int) -> Optional[Engine]:
        """Create SQLAlchemy engine for DWH connection"""
        from urllib.parse import quote_plus
        
        conn = self.db.query(DWHConnection).filter(
            DWHConnection.id == connection_id,
            DWHConnection.is_active == True
        ).first()
        
        if not conn:
            return None
        
        # URL-encode password to handle special characters
        password = quote_plus(conn.password_encrypted or '')
        
        if conn.db_type == "sql_server":
            conn_str = (
                f"mssql+pyodbc://{conn.username}:{password}@"
                f"{conn.host}:{conn.port or 1433}/{conn.database_name}"
                f"?driver=ODBC+Driver+17+for+SQL+Server&timeout=30"
            )
        elif conn.db_type == "postgresql":
            conn_str = (
                f"postgresql://{conn.username}:{password}@"
                f"{conn.host}:{conn.port or 5432}/{conn.database_name}"
            )
        else:
            raise ValueError(f"Unsupported database type: {conn.db_type}")
        
        return create_engine(conn_str, connect_args={"timeout": 30})
    
    # ==========================================
    # INGESTION: DWH -> Platform
    # ==========================================
    
    def ingest_balance_snapshots(
        self,
        connection_id: int,
        source_table: str = "balans_ato",
        source_schema: Optional[str] = "dbo",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        branch_code: Optional[int] = None,
        aggregate_branches: bool = True,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Import balance snapshots from DWH balans_ato table
        
        Args:
            connection_id: DWH connection ID
            source_table: Source table name in DWH (default: balans_ato)
            source_schema: Schema name (default: dbo)
            start_date: Filter start date
            end_date: Filter end date
            branch_code: Filter by specific branch (None = all branches)
            aggregate_branches: If True, aggregate all branches per account/date/currency
            user_id: User performing the import
        
        Returns:
            Import result summary
        """
        batch_id = str(uuid.uuid4())
        currency_map = DWHColumnMapping.CURRENCY_CODES
        
        import_log = SnapshotImportLog(
            import_batch_id=batch_id,
            source_type="dwh_connection",
            source_connection_id=connection_id,
            start_date=start_date,
            end_date=end_date,
            status="RUNNING",
            created_by_user_id=user_id
        )
        self.db.add(import_log)
        self.db.commit()
        
        try:
            dwh_engine = self.get_dwh_engine(connection_id)
            if not dwh_engine:
                raise ValueError(f"Connection {connection_id} not found or inactive")
            
            full_table = f"{source_schema}.{source_table}" if source_schema else source_table
            
            # Build WHERE clause
            where_parts = ["1=1"]
            params = {}
            if start_date:
                where_parts.append("CURDATE >= :start_date")
                params["start_date"] = start_date
            if end_date:
                where_parts.append("CURDATE <= :end_date")
                params["end_date"] = end_date
            if branch_code:
                where_parts.append("OTDELENIE = :branch_code")
                params["branch_code"] = branch_code
            
            where_clause = " AND ".join(where_parts)
            
            # Build query - aggregate by account/date/currency across branches
            if aggregate_branches:
                query = f"""
                    SELECT 
                        CURDATE as snapshot_date,
                        KODBALANS as account_code,
                        KODVALUTA as currency_code,
                        SUM(ISNULL(OSTATALL, 0)) as balance_uzs,
                        SUM(ISNULL(OSTATALLVAL, 0)) as balance_currency,
                        SUM(ISNULL(OSTATALL_IN, 0)) as incoming_balance_uzs,
                        SUM(ISNULL(OSTATALL_DT, 0)) as debit_turnover,
                        SUM(ISNULL(OSTATALL_CT, 0)) as credit_turnover,
                        COUNT(DISTINCT OTDELENIE) as branch_count
                    FROM {full_table}
                    WHERE {where_clause}
                    GROUP BY CURDATE, KODBALANS, KODVALUTA
                    ORDER BY CURDATE, KODBALANS, KODVALUTA
                """
            else:
                query = f"""
                    SELECT 
                        CURDATE as snapshot_date,
                        KODBALANS as account_code,
                        KODVALUTA as currency_code,
                        OTDELENIE as branch_code,
                        ISNULL(OSTATALL, 0) as balance_uzs,
                        ISNULL(OSTATALLVAL, 0) as balance_currency,
                        ISNULL(OSTATALL_IN, 0) as incoming_balance_uzs,
                        ISNULL(OSTATALL_DT, 0) as debit_turnover,
                        ISNULL(OSTATALL_CT, 0) as credit_turnover
                    FROM {full_table}
                    WHERE {where_clause}
                    ORDER BY CURDATE, KODBALANS, KODVALUTA
                """
            
            with dwh_engine.connect() as dwh_conn:
                result = dwh_conn.execute(text(query), params)
                rows = result.fetchall()
                columns = result.keys()
            
            import_log.total_records = len(rows)
            imported = 0
            failed = 0
            
            for row in rows:
                try:
                    row_dict = dict(zip(columns, row))
                    
                    # Convert currency code to ISO alpha
                    currency_code = int(row_dict.get("currency_code", 0) or 0)
                    currency = currency_map.get(currency_code, 'UZS')
                    
                    # Get balance values
                    balance_uzs = float(row_dict.get("balance_uzs", 0) or 0)
                    balance_currency = float(row_dict.get("balance_currency", 0) or 0)
                    
                    # Calculate FX rate
                    if currency == 'UZS':
                        balance = balance_uzs
                        fx_rate = 1.0
                    else:
                        balance = balance_currency
                        fx_rate = balance_uzs / balance_currency if balance_currency != 0 else 1.0
                    
                    account_code = str(row_dict["account_code"]).strip()
                    snapshot_date = row_dict["snapshot_date"]
                    
                    # Check for existing record
                    existing = self.db.query(BalanceSnapshot).filter(
                        BalanceSnapshot.snapshot_date == snapshot_date,
                        BalanceSnapshot.account_code == account_code,
                        BalanceSnapshot.currency == currency
                    ).first()
                    
                    if existing:
                        existing.balance = balance
                        existing.balance_uzs = balance_uzs
                        existing.fx_rate = fx_rate
                        existing.import_batch_id = batch_id
                        existing.data_source = f"DWH:{source_table}"
                    else:
                        snapshot = BalanceSnapshot(
                            snapshot_date=snapshot_date,
                            account_code=account_code,
                            currency=currency,
                            balance=balance,
                            balance_uzs=balance_uzs,
                            fx_rate=fx_rate,
                            data_source=f"DWH:{source_table}",
                            import_batch_id=batch_id
                        )
                        self.db.add(snapshot)
                    
                    imported += 1
                    
                    # Commit in batches
                    if imported % 1000 == 0:
                        self.db.commit()
                        
                except Exception as e:
                    logger.error(f"Failed to import row: {e}")
                    failed += 1
            
            self.db.commit()
            
            import_log.imported_records = imported
            import_log.failed_records = failed
            import_log.status = "COMPLETED" if failed == 0 else "PARTIAL"
            import_log.completed_at = datetime.utcnow()
            self.db.commit()
            
            self.audit.log(
                operation="INGEST_SNAPSHOTS",
                source_table=full_table,
                target_table="balance_snapshots",
                record_count=imported,
                user_id=user_id,
                batch_id=batch_id,
                details={
                    "start_date": str(start_date), 
                    "end_date": str(end_date),
                    "aggregate_branches": aggregate_branches
                }
            )
            
            return {
                "batch_id": batch_id,
                "status": import_log.status,
                "total_records": import_log.total_records,
                "imported_records": imported,
                "failed_records": failed
            }
            
        except Exception as e:
            import_log.status = "FAILED"
            import_log.error_message = str(e)
            import_log.completed_at = datetime.utcnow()
            self.db.commit()
            
            self.audit.log(
                operation="INGEST_SNAPSHOTS",
                source_table=source_table,
                target_table="balance_snapshots",
                record_count=0,
                user_id=user_id,
                batch_id=batch_id,
                status="FAILED",
                details={"error": str(e)}
            )
            
            raise
    
    def ingest_actuals(
        self,
        connection_id: int,
        source_table: str,
        fiscal_year: int,
        month: int,
        column_mapping: Optional[Dict[str, str]] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Import actual (fact) data for Plan vs Fact analysis
        Called monthly after period close
        """
        batch_id = str(uuid.uuid4())
        
        try:
            dwh_engine = self.get_dwh_engine(connection_id)
            if not dwh_engine:
                raise ValueError(f"Connection {connection_id} not found")
            
            mapping = column_mapping or {
                "account_code": "account_code",
                "amount": "actual_amount",
                "amount_uzs": "actual_amount_uzs",
                "currency": "currency"
            }
            
            source_cols = ", ".join([f"{src} AS {tgt}" for src, tgt in mapping.items()])
            query = f"""
                SELECT {source_cols} 
                FROM {source_table} 
                WHERE fiscal_year = :year AND month = :month
            """
            
            with dwh_engine.connect() as dwh_conn:
                result = dwh_conn.execute(text(query), {"year": fiscal_year, "month": month})
                rows = result.fetchall()
                columns = result.keys()
            
            imported = 0
            for row in rows:
                row_dict = dict(zip(columns, row))
                
                line_items = self.db.query(BudgetLineItem).join(Budget).filter(
                    Budget.fiscal_year == fiscal_year,
                    Budget.status == BudgetStatus.APPROVED,
                    BudgetLineItem.account_code == row_dict["account_code"],
                    BudgetLineItem.month == month
                ).all()
                
                for item in line_items:
                    actual = row_dict.get("actual_amount", 0) or 0
                    planned = item.amount or 0
                    
                    item.variance = Decimal(str(actual)) - Decimal(str(planned))
                    if planned != 0:
                        item.variance_percent = (item.variance / Decimal(str(planned))) * 100
                    
                    imported += 1
            
            self.db.commit()
            
            self.audit.log(
                operation="INGEST_ACTUALS",
                source_table=source_table,
                target_table="budget_line_items",
                record_count=imported,
                user_id=user_id,
                batch_id=batch_id,
                details={"fiscal_year": fiscal_year, "month": month}
            )
            
            return {
                "batch_id": batch_id,
                "status": "COMPLETED",
                "records_updated": imported,
                "fiscal_year": fiscal_year,
                "month": month
            }
            
        except Exception as e:
            logger.error(f"Failed to ingest actuals: {e}")
            raise
    
    # ==========================================
    # BASELINE GENERATION
    # ==========================================
    
    def generate_baselines(
        self,
        fiscal_year: int,
        method: str = "average",
        apply_trend: bool = True,
        apply_seasonality: bool = True,
        account_codes: Optional[List[str]] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate baseline budgets from historical snapshots
        
        Args:
            fiscal_year: Target fiscal year for baseline
            method: Calculation method (average, weighted_average, trend)
            apply_trend: Apply YoY trend adjustment
            apply_seasonality: Apply seasonal patterns
            account_codes: Specific accounts to process (None = all)
            user_id: User performing the operation
        
        Returns:
            Generation result summary
        """
        batch_id = str(uuid.uuid4())
        
        query = self.db.query(BalanceSnapshot.account_code).distinct()
        if account_codes:
            query = query.filter(BalanceSnapshot.account_code.in_(account_codes))
        
        unique_accounts = [r[0] for r in query.all()]
        
        created = 0
        updated = 0
        
        for account_code in unique_accounts:
            snapshots = self.db.query(BalanceSnapshot).filter(
                BalanceSnapshot.account_code == account_code
            ).order_by(BalanceSnapshot.snapshot_date).all()
            
            if not snapshots:
                continue
            
            monthly_data = {}
            for snap in snapshots:
                month = snap.snapshot_date.month
                year = snap.snapshot_date.year
                
                if month not in monthly_data:
                    monthly_data[month] = []
                monthly_data[month].append({
                    "year": year,
                    "balance": float(snap.balance_uzs or snap.balance or 0)
                })
            
            baseline_values = {}
            for month in range(1, 13):
                if month in monthly_data:
                    values = [d["balance"] for d in monthly_data[month]]
                    
                    if method == "average":
                        baseline_values[month] = sum(values) / len(values)
                    elif method == "weighted_average":
                        weights = list(range(1, len(values) + 1))
                        weighted_sum = sum(v * w for v, w in zip(values, weights))
                        baseline_values[month] = weighted_sum / sum(weights)
                    elif method == "trend":
                        if len(values) >= 2:
                            trend = (values[-1] - values[0]) / len(values)
                            baseline_values[month] = values[-1] + trend
                        else:
                            baseline_values[month] = values[-1] if values else 0
                else:
                    baseline_values[month] = 0
            
            if apply_trend and len(snapshots) >= 24:
                recent_year = sum(
                    float(s.balance_uzs or s.balance or 0) 
                    for s in snapshots[-12:]
                )
                prior_year = sum(
                    float(s.balance_uzs or s.balance or 0) 
                    for s in snapshots[-24:-12]
                )
                if prior_year != 0:
                    yoy_growth = (recent_year - prior_year) / prior_year
                    for month in baseline_values:
                        baseline_values[month] *= (1 + yoy_growth)
            
            existing = self.db.query(BaselineBudget).filter(
                BaselineBudget.fiscal_year == fiscal_year,
                BaselineBudget.account_code == account_code,
                BaselineBudget.is_active == True
            ).first()
            
            if existing:
                existing.jan = baseline_values.get(1, 0)
                existing.feb = baseline_values.get(2, 0)
                existing.mar = baseline_values.get(3, 0)
                existing.apr = baseline_values.get(4, 0)
                existing.may = baseline_values.get(5, 0)
                existing.jun = baseline_values.get(6, 0)
                existing.jul = baseline_values.get(7, 0)
                existing.aug = baseline_values.get(8, 0)
                existing.sep = baseline_values.get(9, 0)
                existing.oct = baseline_values.get(10, 0)
                existing.nov = baseline_values.get(11, 0)
                existing.dec = baseline_values.get(12, 0)
                existing.annual_total = sum(baseline_values.values())
                existing.calculation_method = method
                existing.baseline_version += 1
                updated += 1
            else:
                baseline = BaselineBudget(
                    fiscal_year=fiscal_year,
                    account_code=account_code,
                    currency="UZS",
                    jan=baseline_values.get(1, 0),
                    feb=baseline_values.get(2, 0),
                    mar=baseline_values.get(3, 0),
                    apr=baseline_values.get(4, 0),
                    may=baseline_values.get(5, 0),
                    jun=baseline_values.get(6, 0),
                    jul=baseline_values.get(7, 0),
                    aug=baseline_values.get(8, 0),
                    sep=baseline_values.get(9, 0),
                    oct=baseline_values.get(10, 0),
                    nov=baseline_values.get(11, 0),
                    dec=baseline_values.get(12, 0),
                    annual_total=sum(baseline_values.values()),
                    calculation_method=method,
                    baseline_version=1,
                    is_active=True,
                    created_by_user_id=user_id
                )
                self.db.add(baseline)
                created += 1
        
        self.db.commit()
        
        self.audit.log(
            operation="GENERATE_BASELINES",
            source_table="balance_snapshots",
            target_table="baseline_budgets",
            record_count=created + updated,
            user_id=user_id,
            batch_id=batch_id,
            details={
                "fiscal_year": fiscal_year,
                "method": method,
                "created": created,
                "updated": updated
            }
        )
        
        return {
            "batch_id": batch_id,
            "status": "COMPLETED",
            "fiscal_year": fiscal_year,
            "baselines_created": created,
            "baselines_updated": updated,
            "total_accounts": len(unique_accounts)
        }
    
    # ==========================================
    # EGRESS: Platform -> DWH
    # ==========================================
    
    def export_approved_budget(
        self,
        connection_id: int,
        budget_id: int,
        target_table: str = "fpna_approved_budgets",
        target_schema: Optional[str] = "dbo",
        version_label: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Export approved budget to DWH
        Creates versioned budget data in DWH for KPI tracking
        """
        batch_id = str(uuid.uuid4())
        
        budget = self.db.query(Budget).filter(
            Budget.id == budget_id,
            Budget.status == BudgetStatus.APPROVED
        ).first()
        
        if not budget:
            raise ValueError(f"Approved budget {budget_id} not found")
        
        version = version_label or f"{budget.fiscal_year}_V{budget.version}"
        
        try:
            dwh_engine = self.get_dwh_engine(connection_id)
            if not dwh_engine:
                raise ValueError(f"Connection {connection_id} not found")
            
            full_table = f"{target_schema}.{target_table}" if target_schema else target_table
            
            with dwh_engine.connect() as dwh_conn:
                dwh_conn.execute(text(f"""
                    IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = '{target_table}')
                    CREATE TABLE {full_table} (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        budget_code NVARCHAR(50),
                        fiscal_year INT,
                        account_code NVARCHAR(50),
                        account_name NVARCHAR(200),
                        month INT,
                        planned_amount DECIMAL(20,2),
                        planned_amount_uzs DECIMAL(20,2),
                        currency NVARCHAR(3),
                        department NVARCHAR(100),
                        budget_version NVARCHAR(50),
                        scenario_type NVARCHAR(50) DEFAULT 'BASE',
                        exported_at DATETIME2 DEFAULT GETUTCDATE(),
                        export_batch_id NVARCHAR(50)
                    )
                """))
                dwh_conn.commit()
            
            line_items = self.db.query(BudgetLineItem).filter(
                BudgetLineItem.budget_id == budget_id
            ).all()
            
            exported = 0
            with dwh_engine.connect() as dwh_conn:
                for item in line_items:
                    dwh_conn.execute(text(f"""
                        INSERT INTO {full_table} 
                        (budget_code, fiscal_year, account_code, account_name, month,
                         planned_amount, planned_amount_uzs, currency, department,
                         budget_version, scenario_type, export_batch_id)
                        VALUES 
                        (:budget_code, :fiscal_year, :account_code, :account_name, :month,
                         :amount, :amount_uzs, :currency, :department,
                         :version, :scenario, :batch_id)
                    """), {
                        "budget_code": budget.budget_code,
                        "fiscal_year": budget.fiscal_year,
                        "account_code": item.account_code,
                        "account_name": item.account_name,
                        "month": item.month,
                        "amount": float(item.amount or 0),
                        "amount_uzs": float(item.amount_uzs or item.amount or 0),
                        "currency": item.currency or "UZS",
                        "department": budget.department,
                        "version": version,
                        "scenario": "BASE",
                        "batch_id": batch_id
                    })
                    exported += 1
                dwh_conn.commit()
            
            self.audit.log(
                operation="EXPORT_BUDGET",
                source_table="budgets",
                target_table=full_table,
                record_count=exported,
                user_id=user_id,
                batch_id=batch_id,
                details={
                    "budget_id": budget_id,
                    "budget_code": budget.budget_code,
                    "version": version
                }
            )
            
            return {
                "batch_id": batch_id,
                "status": "COMPLETED",
                "budget_code": budget.budget_code,
                "version": version,
                "records_exported": exported
            }
            
        except Exception as e:
            logger.error(f"Failed to export budget: {e}")
            self.audit.log(
                operation="EXPORT_BUDGET",
                source_table="budgets",
                target_table=target_table,
                record_count=0,
                user_id=user_id,
                batch_id=batch_id,
                status="FAILED",
                details={"error": str(e)}
            )
            raise
    
    def export_scenario(
        self,
        connection_id: int,
        budget_id: int,
        scenario_type: str,
        adjustment_factor: float,
        target_table: str = "fpna_budget_scenarios",
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Export budget scenario (Optimistic/Pessimistic) to DWH
        Used for risk management and liquidity forecasting
        """
        batch_id = str(uuid.uuid4())
        
        budget = self.db.query(Budget).filter(Budget.id == budget_id).first()
        if not budget:
            raise ValueError(f"Budget {budget_id} not found")
        
        try:
            dwh_engine = self.get_dwh_engine(connection_id)
            if not dwh_engine:
                raise ValueError(f"Connection {connection_id} not found")
            
            with dwh_engine.connect() as dwh_conn:
                dwh_conn.execute(text(f"""
                    IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = '{target_table}')
                    CREATE TABLE {target_table} (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        budget_code NVARCHAR(50),
                        fiscal_year INT,
                        account_code NVARCHAR(50),
                        month INT,
                        base_amount DECIMAL(20,2),
                        scenario_amount DECIMAL(20,2),
                        scenario_type NVARCHAR(50),
                        adjustment_factor DECIMAL(8,4),
                        exported_at DATETIME2 DEFAULT GETUTCDATE(),
                        export_batch_id NVARCHAR(50)
                    )
                """))
                dwh_conn.commit()
            
            line_items = self.db.query(BudgetLineItem).filter(
                BudgetLineItem.budget_id == budget_id
            ).all()
            
            exported = 0
            with dwh_engine.connect() as dwh_conn:
                for item in line_items:
                    base_amount = float(item.amount or 0)
                    scenario_amount = base_amount * adjustment_factor
                    
                    dwh_conn.execute(text(f"""
                        INSERT INTO {target_table}
                        (budget_code, fiscal_year, account_code, month,
                         base_amount, scenario_amount, scenario_type,
                         adjustment_factor, export_batch_id)
                        VALUES
                        (:budget_code, :fiscal_year, :account_code, :month,
                         :base_amount, :scenario_amount, :scenario_type,
                         :adjustment_factor, :batch_id)
                    """), {
                        "budget_code": budget.budget_code,
                        "fiscal_year": budget.fiscal_year,
                        "account_code": item.account_code,
                        "month": item.month,
                        "base_amount": base_amount,
                        "scenario_amount": scenario_amount,
                        "scenario_type": scenario_type,
                        "adjustment_factor": adjustment_factor,
                        "batch_id": batch_id
                    })
                    exported += 1
                dwh_conn.commit()
            
            self.audit.log(
                operation="EXPORT_SCENARIO",
                source_table="budgets",
                target_table=target_table,
                record_count=exported,
                user_id=user_id,
                batch_id=batch_id,
                details={
                    "scenario_type": scenario_type,
                    "adjustment_factor": adjustment_factor
                }
            )
            
            return {
                "batch_id": batch_id,
                "status": "COMPLETED",
                "scenario_type": scenario_type,
                "records_exported": exported
            }
            
        except Exception as e:
            logger.error(f"Failed to export scenario: {e}")
            raise
    
    # ==========================================
    # VERSION MANAGEMENT
    # ==========================================
    
    def create_budget_version(
        self,
        budget_id: int,
        version_label: str,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a new version of a budget (e.g., 2024_V1 -> 2024_V2)
        Preserves history for audit and comparison
        """
        budget = self.db.query(Budget).filter(Budget.id == budget_id).first()
        if not budget:
            raise ValueError(f"Budget {budget_id} not found")
        
        budget.is_current_version = False
        
        new_budget = Budget(
            budget_code=f"{budget.budget_code}_{version_label}",
            fiscal_year=budget.fiscal_year,
            department=budget.department,
            branch=budget.branch,
            business_unit_id=budget.business_unit_id,
            total_amount=budget.total_amount,
            total_amount_uzs=budget.total_amount_uzs,
            currency=budget.currency,
            description=f"Version {version_label} of {budget.budget_code}",
            status=BudgetStatus.DRAFT,
            template_id=budget.template_id,
            parent_budget_id=budget.id,
            version=budget.version + 1,
            is_current_version=True,
            uploaded_by=budget.uploaded_by
        )
        self.db.add(new_budget)
        self.db.flush()
        
        line_items = self.db.query(BudgetLineItem).filter(
            BudgetLineItem.budget_id == budget_id
        ).all()
        
        for item in line_items:
            new_item = BudgetLineItem(
                budget_id=new_budget.id,
                account_code=item.account_code,
                account_name=item.account_name,
                category=item.category,
                month=item.month,
                quarter=item.quarter,
                year=item.year,
                amount=item.amount,
                currency=item.currency,
                amount_uzs=item.amount_uzs,
                fx_rate_used=item.fx_rate_used,
                baseline_amount=item.baseline_amount,
                baseline_amount_uzs=item.baseline_amount_uzs,
                quantity=item.quantity,
                unit_price=item.unit_price,
                notes=item.notes
            )
            self.db.add(new_item)
        
        self.db.commit()
        
        self.audit.log(
            operation="CREATE_VERSION",
            source_table="budgets",
            target_table="budgets",
            record_count=len(line_items),
            user_id=user_id,
            details={
                "original_budget_id": budget_id,
                "new_budget_id": new_budget.id,
                "version_label": version_label
            }
        )
        
        return {
            "status": "COMPLETED",
            "original_budget_id": budget_id,
            "new_budget_id": new_budget.id,
            "new_budget_code": new_budget.budget_code,
            "version": new_budget.version
        }
    
    # ==========================================
    # COA TRANSFORMATION
    # ==========================================
    
    def transform_to_coa(
        self,
        raw_account_code: str,
        mapping_rules: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Transform raw DWH account code to FPNA COA hierarchy
        """
        account = self.db.query(Account).filter(
            Account.code == raw_account_code,
            Account.is_active == True
        ).first()
        
        if account:
            return account.code
        
        if mapping_rules and raw_account_code in mapping_rules:
            return mapping_rules[raw_account_code]
        
        if len(raw_account_code) >= 3:
            category_code = raw_account_code[:3]
            category = self.db.query(AccountCategory).filter(
                AccountCategory.code == category_code
            ).first()
            if category:
                return raw_account_code
        
        return None
    
    def get_coa_hierarchy_for_account(self, account_code: str) -> Optional[Dict]:
        """Get full COA hierarchy for an account code"""
        account = self.db.query(Account).filter(Account.code == account_code).first()
        if not account:
            return None
        
        category = self.db.query(AccountCategory).filter(
            AccountCategory.id == account.category_id
        ).first()
        
        if not category:
            return {"account": account_code}
        
        group = self.db.query(AccountGroup).filter(
            AccountGroup.id == category.group_id
        ).first()
        
        if not group:
            return {"account": account_code, "category": category.code}
        
        acc_class = self.db.query(AccountClass).filter(
            AccountClass.id == group.class_id
        ).first()
        
        return {
            "account": account_code,
            "account_name": account.name_en,
            "category": category.code,
            "category_name": category.name_en,
            "group": group.code,
            "group_name": group.name_en,
            "class": acc_class.code if acc_class else None,
            "class_name": acc_class.name_en if acc_class else None
        }
    
    # ==========================================
    # UTILITY METHODS
    # ==========================================
    
    def get_dwh_tables(self, connection_id: int) -> List[Dict]:
        """List available tables in DWH"""
        try:
            dwh_engine = self.get_dwh_engine(connection_id)
            if not dwh_engine:
                return []
            
            with dwh_engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
                    FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_TYPE = 'BASE TABLE'
                    ORDER BY TABLE_SCHEMA, TABLE_NAME
                """))
                return [
                    {"schema": r[0], "table": r[1], "type": r[2]}
                    for r in result.fetchall()
                ]
        except Exception as e:
            logger.error(f"Failed to list DWH tables: {e}")
            return []
    
    def get_table_columns(
        self,
        connection_id: int,
        table_name: str,
        schema_name: str = "dbo"
    ) -> List[Dict]:
        """Get column metadata for a DWH table"""
        try:
            dwh_engine = self.get_dwh_engine(connection_id)
            if not dwh_engine:
                return []
            
            with dwh_engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, 
                           CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = :table_name AND TABLE_SCHEMA = :schema_name
                    ORDER BY ORDINAL_POSITION
                """), {"table_name": table_name, "schema_name": schema_name})
                
                return [
                    {
                        "name": r[0],
                        "type": r[1],
                        "nullable": r[2] == "YES",
                        "max_length": r[3],
                        "precision": r[4]
                    }
                    for r in result.fetchall()
                ]
        except Exception as e:
            logger.error(f"Failed to get table columns: {e}")
            return []
    
    def preview_table_data(
        self,
        connection_id: int,
        table_name: str,
        schema_name: str = "dbo",
        limit: int = 100
    ) -> Tuple[List[str], List[Dict]]:
        """Preview data from a DWH table"""
        try:
            dwh_engine = self.get_dwh_engine(connection_id)
            if not dwh_engine:
                return [], []
            
            full_table = f"{schema_name}.{table_name}" if schema_name else table_name
            
            with dwh_engine.connect() as conn:
                result = conn.execute(text(f"SELECT TOP {limit} * FROM {full_table}"))
                columns = list(result.keys())
                rows = [dict(zip(columns, row)) for row in result.fetchall()]
                return columns, rows
        except Exception as e:
            logger.error(f"Failed to preview table: {e}")
            return [], []


def ensure_audit_trail_table(db: Session):
    """Create audit trail table if not exists"""
    try:
        db.execute(text("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'etl_audit_trail')
            CREATE TABLE etl_audit_trail (
                id INT IDENTITY(1,1) PRIMARY KEY,
                batch_id NVARCHAR(50) NOT NULL,
                operation NVARCHAR(50) NOT NULL,
                source_table NVARCHAR(255),
                target_table NVARCHAR(255),
                record_count INT DEFAULT 0,
                user_id INT NULL,
                details NVARCHAR(MAX),
                status NVARCHAR(20) DEFAULT 'SUCCESS',
                created_at DATETIME2 DEFAULT GETUTCDATE()
            )
        """))
        db.commit()
    except Exception as e:
        logger.warning(f"Failed to create audit trail table: {e}")
