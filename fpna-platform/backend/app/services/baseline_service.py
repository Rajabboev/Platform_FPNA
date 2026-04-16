"""
Baseline Service
Handles: Ingestion → Baseline Calculation → Budget Planning → Export
"""

from sqlalchemy.orm import Session
from sqlalchemy import text, func
from typing import Dict, List, Optional, Any
from datetime import date, datetime
from decimal import Decimal
import uuid
import logging

from app.models.baseline import BaselineData, BudgetBaseline, BudgetPlanned
from app.models.dwh_connection import DWHConnection
from app.services.dwh_integration_service import DWHIntegrationService, DWHColumnMapping

logger = logging.getLogger(__name__)

# Currency code mapping
CURRENCY_MAP = {
    0: 'UZS', 860: 'UZS', 840: 'USD', 978: 'EUR', 643: 'RUB',
    756: 'CHF', 826: 'GBP', 392: 'JPY', 156: 'CNY', 398: 'KZT'
}

MONTH_COLUMNS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 
                 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']


class BaselineService:
    """Service for baseline data management and budget calculation"""
    
    def __init__(self, db: Session):
        self.db = db
        self.dwh_service = DWHIntegrationService(db)
    
    # ==========================================
    # STEP 1: INGEST - DWH balans_ato → baseline_data
    # ==========================================
    
    def ingest_baseline_data(
        self,
        connection_id: int,
        start_year: int = 2023,
        end_year: int = 2025,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Import snapshot data from DWH balans_ato into baseline_data table
        Aggregates by account/month across all branches and currencies
        """
        batch_id = str(uuid.uuid4())
        
        try:
            dwh_engine = self.dwh_service.get_dwh_engine(connection_id)
            if not dwh_engine:
                raise ValueError(f"Connection {connection_id} not found or inactive")
            
            # Signed balance: PRIZNALL=1 -> +OSTATALL, PRIZNALL=0 -> -OSTATALL (else +OSTATALL)
            from app.services.balans_signed_balance import sql_signed_balance_sum

            _uzs = sql_signed_balance_sum("OSTATALL", "PRIZNALL")
            _val = sql_signed_balance_sum("OSTATALLVAL", "PRIZNALL")
            query = text(f"""
                SELECT 
                    KODBALANS as account_code,
                    CURDATE as snapshot_date,
                    YEAR(CURDATE) as fiscal_year,
                    MONTH(CURDATE) as fiscal_month,
                    KODVALUTA as currency_code,
                    {_uzs} as balance_uzs,
                    {_val} as balance,
                    SUM(ISNULL(OSTATALL_DT, 0)) as debit_turnover,
                    SUM(ISNULL(OSTATALL_CT, 0)) as credit_turnover
                FROM dbo.balans_ato
                WHERE YEAR(CURDATE) >= :start_year 
                  AND YEAR(CURDATE) <= :end_year
                  AND KODBALANS IS NOT NULL
                GROUP BY KODBALANS, CURDATE, YEAR(CURDATE), MONTH(CURDATE), KODVALUTA
                ORDER BY CURDATE, KODBALANS
            """)
            
            with dwh_engine.connect() as conn:
                result = conn.execute(query, {
                    "start_year": start_year,
                    "end_year": end_year
                })
                rows = result.fetchall()
            
            # Clear existing baseline data for the period
            self.db.execute(text("""
                DELETE FROM baseline_data 
                WHERE fiscal_year >= :start_year AND fiscal_year <= :end_year
            """), {"start_year": start_year, "end_year": end_year})
            self.db.commit()
            
            imported = 0
            for row in rows:
                currency_code = int(row[4] or 0)
                currency = CURRENCY_MAP.get(currency_code, 'UZS')
                
                baseline_data = BaselineData(
                    import_batch_id=batch_id,
                    source_connection_id=connection_id,
                    account_code=str(row[0]).strip(),
                    snapshot_date=row[1],
                    fiscal_year=row[2],
                    fiscal_month=row[3],
                    currency_code=currency_code,
                    currency=currency,
                    balance_uzs=float(row[5] or 0),
                    balance=float(row[6] or 0),
                    debit_turnover=float(row[7] or 0),
                    credit_turnover=float(row[8] or 0),
                    net_change=float((row[8] or 0) - (row[7] or 0)),
                    branch_code='ALL'
                )
                self.db.add(baseline_data)
                imported += 1
                
                if imported % 1000 == 0:
                    self.db.commit()
            
            self.db.commit()
            
            # Get summary
            summary = self.db.execute(text("""
                SELECT 
                    COUNT(DISTINCT account_code) as accounts,
                    COUNT(DISTINCT fiscal_year) as years,
                    MIN(snapshot_date) as min_date,
                    MAX(snapshot_date) as max_date
                FROM baseline_data
                WHERE import_batch_id = :batch_id
            """), {"batch_id": batch_id}).fetchone()
            
            return {
                "batch_id": batch_id,
                "status": "COMPLETED",
                "records_imported": imported,
                "unique_accounts": summary[0],
                "years_covered": summary[1],
                "date_range": f"{summary[2]} to {summary[3]}"
            }
            
        except Exception as e:
            logger.error(f"Ingestion failed: {e}")
            raise
    
    # ==========================================
    # STEP 2: CALCULATE - baseline_data → budget_baseline
    # ==========================================
    
    def calculate_baseline(
        self,
        fiscal_year: int,
        method: str = "simple_average",
        source_years: List[int] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Calculate baseline budget for a fiscal year using historical data
        
        Methods:
        - simple_average: Average of same month across source years
        - weighted_average: Recent years weighted more heavily
        - trend: Apply YoY growth trend
        """
        if source_years is None:
            source_years = [fiscal_year - 3, fiscal_year - 2, fiscal_year - 1]
        
        source_years_str = ",".join(map(str, source_years))
        
        # Get unique accounts from baseline_data (SQL Server compatible)
        years_list = ",".join(str(y) for y in source_years)
        accounts = self.db.execute(text(f"""
            SELECT DISTINCT account_code
            FROM baseline_data
            WHERE fiscal_year IN ({years_list})
        """)).fetchall()
        
        # First delete planned budgets that reference baselines for this year
        # (due to FK constraint: budget_planned.baseline_id -> budget_baseline.id)
        self.db.execute(text("""
            DELETE FROM budget_planned 
            WHERE baseline_id IN (SELECT id FROM budget_baseline WHERE fiscal_year = :year)
        """), {"year": fiscal_year})
        self.db.commit()
        
        # Now delete existing baselines for this year
        self.db.execute(text("""
            DELETE FROM budget_baseline WHERE fiscal_year = :year
        """), {"year": fiscal_year})
        self.db.commit()
        
        created = 0
        for (account_code,) in accounts:
            # Get monthly averages
            monthly_data = {}
            for month in range(1, 13):
                result = self.db.execute(text(f"""
                    SELECT AVG(balance_uzs) as avg_balance
                    FROM baseline_data
                    WHERE account_code = :account
                      AND fiscal_month = :month
                      AND fiscal_year IN ({years_list})
                """), {
                    "account": account_code,
                    "month": month
                }).fetchone()
                
                monthly_data[month] = float(result[0] or 0) if result[0] else 0
            
            # Calculate YoY growth rate
            yoy_growth = self._calculate_yoy_growth(account_code, source_years)
            
            # Apply trend adjustment if method is 'trend'
            if method == "trend" and yoy_growth:
                for month in range(1, 13):
                    monthly_data[month] *= (1 + yoy_growth)
            
            # Create baseline record
            annual_total = sum(monthly_data.values())
            
            baseline = BudgetBaseline(
                fiscal_year=fiscal_year,
                account_code=account_code,
                currency='UZS',
                jan=monthly_data[1],
                feb=monthly_data[2],
                mar=monthly_data[3],
                apr=monthly_data[4],
                may=monthly_data[5],
                jun=monthly_data[6],
                jul=monthly_data[7],
                aug=monthly_data[8],
                sep=monthly_data[9],
                oct=monthly_data[10],
                nov=monthly_data[11],
                dec=monthly_data[12],
                annual_total=annual_total,
                annual_total_uzs=annual_total,
                calculation_method=method,
                source_years=source_years_str,
                yoy_growth_rate=yoy_growth,
                is_active=True,
                created_by_user_id=user_id
            )
            self.db.add(baseline)
            created += 1
            
            if created % 100 == 0:
                self.db.commit()
        
        self.db.commit()
        
        return {
            "fiscal_year": fiscal_year,
            "method": method,
            "source_years": source_years,
            "baselines_created": created,
            "status": "COMPLETED"
        }
    
    def _calculate_yoy_growth(self, account_code: str, years: List[int]) -> Optional[float]:
        """Calculate year-over-year growth rate for an account"""
        if len(years) < 2:
            return None
        
        yearly_totals = []
        for year in sorted(years):
            result = self.db.execute(text("""
                SELECT SUM(balance_uzs) as total
                FROM baseline_data
                WHERE account_code = :account AND fiscal_year = :year
            """), {"account": account_code, "year": year}).fetchone()
            
            if result[0]:
                yearly_totals.append((year, float(result[0])))
        
        if len(yearly_totals) < 2:
            return None
        
        # Calculate average growth rate
        growth_rates = []
        for i in range(1, len(yearly_totals)):
            prev_total = yearly_totals[i-1][1]
            curr_total = yearly_totals[i][1]
            if prev_total != 0:
                growth_rates.append((curr_total - prev_total) / abs(prev_total))
        
        return sum(growth_rates) / len(growth_rates) if growth_rates else None
    
    # ==========================================
    # STEP 3: PLAN - budget_baseline → budget_planned
    # ==========================================
    
    def create_planned_budget(
        self,
        fiscal_year: int,
        account_code: str,
        driver_adjustment_pct: float = 0,
        driver_code: Optional[str] = None,
        department: Optional[str] = None,
        scenario: str = "BASE",
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a planned budget from baseline with driver adjustments
        """
        # Get baseline
        baseline = self.db.query(BudgetBaseline).filter(
            BudgetBaseline.fiscal_year == fiscal_year,
            BudgetBaseline.account_code == account_code,
            BudgetBaseline.is_active == True
        ).first()
        
        if not baseline:
            raise ValueError(f"No baseline found for {account_code} in {fiscal_year}")
        
        # Generate budget code
        budget_code = f"BUD-{fiscal_year}-{account_code}-{scenario}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Apply driver adjustment
        adjustment_factor = 1 + driver_adjustment_pct
        
        planned = BudgetPlanned(
            budget_code=budget_code,
            fiscal_year=fiscal_year,
            account_code=account_code,
            currency=baseline.currency,
            department=department,
            jan=float(baseline.jan or 0) * adjustment_factor,
            feb=float(baseline.feb or 0) * adjustment_factor,
            mar=float(baseline.mar or 0) * adjustment_factor,
            apr=float(baseline.apr or 0) * adjustment_factor,
            may=float(baseline.may or 0) * adjustment_factor,
            jun=float(baseline.jun or 0) * adjustment_factor,
            jul=float(baseline.jul or 0) * adjustment_factor,
            aug=float(baseline.aug or 0) * adjustment_factor,
            sep=float(baseline.sep or 0) * adjustment_factor,
            oct=float(baseline.oct or 0) * adjustment_factor,
            nov=float(baseline.nov or 0) * adjustment_factor,
            dec=float(baseline.dec or 0) * adjustment_factor,
            driver_code=driver_code,
            driver_adjustment_pct=driver_adjustment_pct,
            baseline_id=baseline.id,
            baseline_amount=float(baseline.annual_total or 0),
            scenario=scenario,
            status='DRAFT',
            created_by_user_id=user_id
        )
        
        # Calculate totals and variance
        planned.annual_total = sum([
            planned.jan, planned.feb, planned.mar, planned.apr,
            planned.may, planned.jun, planned.jul, planned.aug,
            planned.sep, planned.oct, planned.nov, planned.dec
        ])
        planned.annual_total_uzs = planned.annual_total
        planned.variance_from_baseline = planned.annual_total - planned.baseline_amount
        planned.variance_pct = (planned.variance_from_baseline / planned.baseline_amount * 100) if planned.baseline_amount else 0
        
        self.db.add(planned)
        self.db.commit()
        self.db.refresh(planned)
        
        return {
            "budget_code": planned.budget_code,
            "fiscal_year": fiscal_year,
            "account_code": account_code,
            "baseline_amount": float(planned.baseline_amount),
            "planned_amount": float(planned.annual_total),
            "driver_adjustment_pct": driver_adjustment_pct,
            "variance": float(planned.variance_from_baseline),
            "variance_pct": float(planned.variance_pct),
            "status": planned.status
        }
    
    def bulk_create_planned_budgets(
        self,
        fiscal_year: int,
        driver_adjustment_pct: float = 0,
        driver_code: Optional[str] = None,
        account_codes: Optional[List[str]] = None,
        scenario: str = "BASE",
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create planned budgets for all baselines or specific accounts
        """
        query = self.db.query(BudgetBaseline).filter(
            BudgetBaseline.fiscal_year == fiscal_year,
            BudgetBaseline.is_active == True
        )
        
        if account_codes:
            query = query.filter(BudgetBaseline.account_code.in_(account_codes))
        
        baselines = query.all()
        
        created = 0
        errors = []
        
        for baseline in baselines:
            try:
                self.create_planned_budget(
                    fiscal_year=fiscal_year,
                    account_code=baseline.account_code,
                    driver_adjustment_pct=driver_adjustment_pct,
                    driver_code=driver_code,
                    scenario=scenario,
                    user_id=user_id
                )
                created += 1
            except Exception as e:
                errors.append({"account": baseline.account_code, "error": str(e)})
        
        return {
            "fiscal_year": fiscal_year,
            "budgets_created": created,
            "errors": errors,
            "status": "COMPLETED" if not errors else "PARTIAL"
        }
    
    def submit_planned_budget(self, budget_code: str, user_id: int) -> Dict[str, Any]:
        """Submit a planned budget for approval"""
        budget = self.db.query(BudgetPlanned).filter(
            BudgetPlanned.budget_code == budget_code
        ).first()
        
        if not budget:
            raise ValueError(f"Budget {budget_code} not found")
        
        budget.status = 'SUBMITTED'
        budget.submitted_at = datetime.utcnow()
        budget.submitted_by_user_id = user_id
        self.db.commit()
        
        return {"budget_code": budget_code, "status": "SUBMITTED"}
    
    def approve_planned_budget(self, budget_code: str, user_id: int) -> Dict[str, Any]:
        """Approve a submitted budget"""
        budget = self.db.query(BudgetPlanned).filter(
            BudgetPlanned.budget_code == budget_code
        ).first()
        
        if not budget:
            raise ValueError(f"Budget {budget_code} not found")
        
        budget.status = 'APPROVED'
        budget.approved_at = datetime.utcnow()
        budget.approved_by_user_id = user_id
        self.db.commit()
        
        return {"budget_code": budget_code, "status": "APPROVED"}
    
    # ==========================================
    # STEP 4: EXPORT - budget_planned → DWH
    # ==========================================
    
    def export_to_dwh(
        self,
        connection_id: int,
        fiscal_year: int,
        target_table: str = "fpna_budget_planned",
        status_filter: str = "APPROVED",
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Export approved planned budgets to DWH
        """
        batch_id = str(uuid.uuid4())
        
        try:
            dwh_engine = self.dwh_service.get_dwh_engine(connection_id)
            if not dwh_engine:
                raise ValueError(f"Connection {connection_id} not found")
            
            # Get budgets to export
            budgets = self.db.query(BudgetPlanned).filter(
                BudgetPlanned.fiscal_year == fiscal_year,
                BudgetPlanned.status == status_filter,
                BudgetPlanned.is_current == True
            ).all()
            
            if not budgets:
                return {"status": "NO_DATA", "message": f"No {status_filter} budgets found for {fiscal_year}"}
            
            # Create target table if not exists
            create_table_sql = f"""
                IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = '{target_table}')
                CREATE TABLE dbo.{target_table} (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    export_batch_id NVARCHAR(50),
                    budget_code NVARCHAR(50),
                    fiscal_year INT,
                    account_code NVARCHAR(10),
                    currency NVARCHAR(3),
                    department NVARCHAR(100),
                    jan NUMERIC(22,2),
                    feb NUMERIC(22,2),
                    mar NUMERIC(22,2),
                    apr NUMERIC(22,2),
                    may NUMERIC(22,2),
                    jun NUMERIC(22,2),
                    jul NUMERIC(22,2),
                    aug NUMERIC(22,2),
                    sep NUMERIC(22,2),
                    oct NUMERIC(22,2),
                    nov NUMERIC(22,2),
                    [dec] NUMERIC(22,2),
                    annual_total NUMERIC(22,2),
                    baseline_amount NUMERIC(22,2),
                    variance_pct NUMERIC(10,4),
                    scenario NVARCHAR(20),
                    status NVARCHAR(20),
                    exported_at DATETIME DEFAULT GETDATE()
                )
            """
            
            with dwh_engine.connect() as conn:
                conn.execute(text(create_table_sql))
                conn.commit()
                
                # Insert budgets
                exported = 0
                for budget in budgets:
                    insert_sql = text(f"""
                        INSERT INTO dbo.{target_table} 
                        (export_batch_id, budget_code, fiscal_year, account_code, currency, department,
                         jan, feb, mar, apr, may, jun, jul, aug, sep, oct, nov, [dec],
                         annual_total, baseline_amount, variance_pct, scenario, status)
                        VALUES 
                        (:batch_id, :budget_code, :fiscal_year, :account_code, :currency, :department,
                         :jan, :feb, :mar, :apr, :may, :jun, :jul, :aug, :sep, :oct, :nov, :dec,
                         :annual_total, :baseline_amount, :variance_pct, :scenario, :status)
                    """)
                    
                    conn.execute(insert_sql, {
                        "batch_id": batch_id,
                        "budget_code": budget.budget_code,
                        "fiscal_year": budget.fiscal_year,
                        "account_code": budget.account_code,
                        "currency": budget.currency,
                        "department": budget.department,
                        "jan": float(budget.jan or 0),
                        "feb": float(budget.feb or 0),
                        "mar": float(budget.mar or 0),
                        "apr": float(budget.apr or 0),
                        "may": float(budget.may or 0),
                        "jun": float(budget.jun or 0),
                        "jul": float(budget.jul or 0),
                        "aug": float(budget.aug or 0),
                        "sep": float(budget.sep or 0),
                        "oct": float(budget.oct or 0),
                        "nov": float(budget.nov or 0),
                        "dec": float(budget.dec or 0),
                        "annual_total": float(budget.annual_total or 0),
                        "baseline_amount": float(budget.baseline_amount or 0),
                        "variance_pct": float(budget.variance_pct or 0),
                        "scenario": budget.scenario,
                        "status": budget.status
                    })
                    
                    # Update budget with export info
                    budget.exported_at = datetime.utcnow()
                    budget.export_batch_id = batch_id
                    budget.status = 'EXPORTED'
                    exported += 1
                
                conn.commit()
            
            self.db.commit()
            
            return {
                "batch_id": batch_id,
                "fiscal_year": fiscal_year,
                "target_table": target_table,
                "budgets_exported": exported,
                "status": "COMPLETED"
            }
            
        except Exception as e:
            logger.error(f"Export failed: {e}")
            raise
    
    # ==========================================
    # QUERY METHODS
    # ==========================================
    
    def get_baseline_summary(self, fiscal_year: int) -> Dict[str, Any]:
        """Get summary of baselines for a fiscal year"""
        result = self.db.execute(text("""
            SELECT 
                COUNT(*) as total_accounts,
                SUM(annual_total) as total_amount,
                AVG(yoy_growth_rate) as avg_growth_rate
            FROM budget_baseline
            WHERE fiscal_year = :year AND is_active = 1
        """), {"year": fiscal_year}).fetchone()
        
        return {
            "fiscal_year": fiscal_year,
            "total_accounts": result[0] or 0,
            "total_amount": float(result[1] or 0),
            "avg_growth_rate": float(result[2] or 0) if result[2] else None
        }
    
    def get_planned_summary(self, fiscal_year: int) -> Dict[str, Any]:
        """Get summary of planned budgets for a fiscal year"""
        result = self.db.execute(text("""
            SELECT 
                status,
                COUNT(*) as count,
                SUM(annual_total) as total_amount
            FROM budget_planned
            WHERE fiscal_year = :year AND is_current = 1
            GROUP BY status
        """), {"year": fiscal_year}).fetchall()
        
        summary = {row[0]: {"count": row[1], "amount": float(row[2] or 0)} for row in result}
        
        return {
            "fiscal_year": fiscal_year,
            "by_status": summary
        }
