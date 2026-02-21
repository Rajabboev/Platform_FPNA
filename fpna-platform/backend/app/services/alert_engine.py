"""
Alert Engine - Plan vs Fact Variance Notifications
Monitors budget variances and sends alerts when thresholds are exceeded

Features:
- Configurable variance thresholds per department/account
- Multi-channel notifications (email, in-app, webhook)
- Alert history and acknowledgment tracking
- Escalation rules for critical variances
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
import logging
import uuid

from app.models.budget import Budget, BudgetLineItem, BudgetStatus

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class AlertChannel(str, Enum):
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"
    WEBHOOK = "WEBHOOK"


class VarianceThreshold:
    """Default variance thresholds"""
    INFO = 5.0
    WARNING = 10.0
    CRITICAL = 20.0


class AlertEngine:
    """
    Alert Engine for monitoring budget variances
    Sends notifications when Plan vs Fact exceeds thresholds
    """
    
    def __init__(self, db: Session):
        self.db = db
        self._ensure_alert_tables()
    
    def _ensure_alert_tables(self):
        """Create alert tables if not exist"""
        try:
            self.db.execute(text("""
                IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'variance_alerts')
                CREATE TABLE variance_alerts (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    alert_code NVARCHAR(50) UNIQUE NOT NULL,
                    budget_id INT NOT NULL,
                    line_item_id INT NULL,
                    account_code NVARCHAR(50),
                    department NVARCHAR(100),
                    fiscal_year INT,
                    month INT,
                    
                    planned_amount DECIMAL(20,2),
                    actual_amount DECIMAL(20,2),
                    variance_amount DECIMAL(20,2),
                    variance_percent DECIMAL(8,4),
                    
                    severity NVARCHAR(20) DEFAULT 'WARNING',
                    status NVARCHAR(20) DEFAULT 'PENDING',
                    
                    message NVARCHAR(500),
                    details NVARCHAR(MAX),
                    
                    assigned_to_user_id INT NULL,
                    acknowledged_by_user_id INT NULL,
                    acknowledged_at DATETIME2 NULL,
                    resolved_at DATETIME2 NULL,
                    resolution_notes NVARCHAR(500),
                    
                    created_at DATETIME2 DEFAULT GETUTCDATE(),
                    updated_at DATETIME2 NULL
                )
            """))
            
            self.db.execute(text("""
                IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'alert_notifications')
                CREATE TABLE alert_notifications (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    alert_id INT NOT NULL,
                    channel NVARCHAR(20) NOT NULL,
                    recipient_user_id INT NULL,
                    recipient_email NVARCHAR(255) NULL,
                    webhook_url NVARCHAR(500) NULL,
                    
                    status NVARCHAR(20) DEFAULT 'PENDING',
                    sent_at DATETIME2 NULL,
                    error_message NVARCHAR(500) NULL,
                    
                    created_at DATETIME2 DEFAULT GETUTCDATE()
                )
            """))
            
            self.db.execute(text("""
                IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'alert_thresholds')
                CREATE TABLE alert_thresholds (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    department NVARCHAR(100) NULL,
                    account_code NVARCHAR(50) NULL,
                    
                    info_threshold DECIMAL(8,4) DEFAULT 5.0,
                    warning_threshold DECIMAL(8,4) DEFAULT 10.0,
                    critical_threshold DECIMAL(8,4) DEFAULT 20.0,
                    
                    notify_department_head BIT DEFAULT 1,
                    notify_cfo BIT DEFAULT 0,
                    escalate_after_hours INT DEFAULT 24,
                    
                    is_active BIT DEFAULT 1,
                    created_at DATETIME2 DEFAULT GETUTCDATE(),
                    updated_at DATETIME2 NULL
                )
            """))
            
            self.db.commit()
        except Exception as e:
            logger.warning(f"Failed to create alert tables: {e}")
    
    def check_variances(
        self,
        fiscal_year: int,
        month: Optional[int] = None,
        department: Optional[str] = None
    ) -> List[Dict]:
        """
        Check all budget line items for variance alerts
        
        Args:
            fiscal_year: Fiscal year to check
            month: Specific month (None = all months)
            department: Specific department (None = all)
        
        Returns:
            List of generated alerts
        """
        query = self.db.query(BudgetLineItem).join(Budget).filter(
            Budget.fiscal_year == fiscal_year,
            Budget.status == BudgetStatus.APPROVED,
            BudgetLineItem.variance.isnot(None)
        )
        
        if month:
            query = query.filter(BudgetLineItem.month == month)
        if department:
            query = query.filter(Budget.department == department)
        
        line_items = query.all()
        alerts = []
        
        for item in line_items:
            if item.variance_percent is None:
                continue
            
            variance_pct = abs(float(item.variance_percent))
            
            thresholds = self._get_thresholds(
                item.budget.department,
                item.account_code
            )
            
            severity = None
            if variance_pct >= thresholds["critical"]:
                severity = AlertSeverity.CRITICAL
            elif variance_pct >= thresholds["warning"]:
                severity = AlertSeverity.WARNING
            elif variance_pct >= thresholds["info"]:
                severity = AlertSeverity.INFO
            
            if severity:
                alert = self._create_alert(item, severity, thresholds)
                if alert:
                    alerts.append(alert)
        
        return alerts
    
    def _get_thresholds(
        self,
        department: Optional[str],
        account_code: Optional[str]
    ) -> Dict[str, float]:
        """Get variance thresholds for department/account"""
        result = self.db.execute(text("""
            SELECT TOP 1 info_threshold, warning_threshold, critical_threshold,
                   notify_department_head, notify_cfo
            FROM alert_thresholds
            WHERE is_active = 1
              AND (department = :dept OR department IS NULL)
              AND (account_code = :acc OR account_code IS NULL)
            ORDER BY 
                CASE WHEN department IS NOT NULL AND account_code IS NOT NULL THEN 1
                     WHEN department IS NOT NULL THEN 2
                     WHEN account_code IS NOT NULL THEN 3
                     ELSE 4 END
        """), {"dept": department, "acc": account_code}).first()
        
        if result:
            return {
                "info": float(result[0] or VarianceThreshold.INFO),
                "warning": float(result[1] or VarianceThreshold.WARNING),
                "critical": float(result[2] or VarianceThreshold.CRITICAL),
                "notify_dept_head": bool(result[3]),
                "notify_cfo": bool(result[4])
            }
        
        return {
            "info": VarianceThreshold.INFO,
            "warning": VarianceThreshold.WARNING,
            "critical": VarianceThreshold.CRITICAL,
            "notify_dept_head": True,
            "notify_cfo": False
        }
    
    def _create_alert(
        self,
        line_item: BudgetLineItem,
        severity: AlertSeverity,
        thresholds: Dict
    ) -> Optional[Dict]:
        """Create a variance alert for a line item"""
        existing = self.db.execute(text("""
            SELECT id FROM variance_alerts
            WHERE budget_id = :budget_id
              AND line_item_id = :line_item_id
              AND status NOT IN ('RESOLVED')
        """), {
            "budget_id": line_item.budget_id,
            "line_item_id": line_item.id
        }).first()
        
        if existing:
            return None
        
        alert_code = f"VAR-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        
        variance_direction = "over" if line_item.variance > 0 else "under"
        message = (
            f"Budget variance alert: {line_item.account_name or line_item.account_code} "
            f"is {abs(float(line_item.variance_percent)):.1f}% {variance_direction} budget "
            f"for {line_item.budget.department} ({line_item.budget.fiscal_year}-{line_item.month:02d})"
        )
        
        self.db.execute(text("""
            INSERT INTO variance_alerts
            (alert_code, budget_id, line_item_id, account_code, department,
             fiscal_year, month, planned_amount, actual_amount, variance_amount,
             variance_percent, severity, status, message)
            VALUES
            (:alert_code, :budget_id, :line_item_id, :account_code, :department,
             :fiscal_year, :month, :planned, :actual, :variance,
             :variance_pct, :severity, 'PENDING', :message)
        """), {
            "alert_code": alert_code,
            "budget_id": line_item.budget_id,
            "line_item_id": line_item.id,
            "account_code": line_item.account_code,
            "department": line_item.budget.department,
            "fiscal_year": line_item.budget.fiscal_year,
            "month": line_item.month,
            "planned": float(line_item.amount or 0),
            "actual": float((line_item.amount or 0) + (line_item.variance or 0)),
            "variance": float(line_item.variance or 0),
            "variance_pct": float(line_item.variance_percent or 0),
            "severity": severity.value,
            "message": message
        })
        self.db.commit()
        
        if severity == AlertSeverity.CRITICAL or thresholds.get("notify_cfo"):
            self._queue_notification(alert_code, AlertChannel.IN_APP, is_cfo=True)
        
        if thresholds.get("notify_dept_head"):
            self._queue_notification(alert_code, AlertChannel.IN_APP, is_cfo=False)
        
        return {
            "alert_code": alert_code,
            "severity": severity.value,
            "message": message,
            "variance_percent": float(line_item.variance_percent or 0)
        }
    
    def _queue_notification(
        self,
        alert_code: str,
        channel: AlertChannel,
        is_cfo: bool = False
    ):
        """Queue a notification for an alert"""
        alert = self.db.execute(text("""
            SELECT id FROM variance_alerts WHERE alert_code = :code
        """), {"code": alert_code}).first()
        
        if not alert:
            return
        
        self.db.execute(text("""
            INSERT INTO alert_notifications
            (alert_id, channel, status)
            VALUES (:alert_id, :channel, 'PENDING')
        """), {
            "alert_id": alert[0],
            "channel": channel.value
        })
        self.db.commit()
    
    def get_pending_alerts(
        self,
        department: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get pending alerts"""
        query = """
            SELECT TOP (:limit)
                alert_code, budget_id, account_code, department,
                fiscal_year, month, planned_amount, actual_amount,
                variance_amount, variance_percent, severity, status,
                message, created_at
            FROM variance_alerts
            WHERE status IN ('PENDING', 'SENT')
        """
        params = {"limit": limit}
        
        if department:
            query += " AND department = :dept"
            params["dept"] = department
        if severity:
            query += " AND severity = :sev"
            params["sev"] = severity
        
        query += " ORDER BY CASE severity WHEN 'CRITICAL' THEN 1 WHEN 'WARNING' THEN 2 ELSE 3 END, created_at DESC"
        
        result = self.db.execute(text(query), params)
        
        return [
            {
                "alert_code": r[0],
                "budget_id": r[1],
                "account_code": r[2],
                "department": r[3],
                "fiscal_year": r[4],
                "month": r[5],
                "planned_amount": float(r[6] or 0),
                "actual_amount": float(r[7] or 0),
                "variance_amount": float(r[8] or 0),
                "variance_percent": float(r[9] or 0),
                "severity": r[10],
                "status": r[11],
                "message": r[12],
                "created_at": r[13].isoformat() if r[13] else None
            }
            for r in result.fetchall()
        ]
    
    def acknowledge_alert(
        self,
        alert_code: str,
        user_id: int,
        notes: Optional[str] = None
    ) -> Dict:
        """Acknowledge an alert"""
        self.db.execute(text("""
            UPDATE variance_alerts
            SET status = 'ACKNOWLEDGED',
                acknowledged_by_user_id = :user_id,
                acknowledged_at = GETUTCDATE(),
                resolution_notes = :notes,
                updated_at = GETUTCDATE()
            WHERE alert_code = :code
        """), {
            "code": alert_code,
            "user_id": user_id,
            "notes": notes
        })
        self.db.commit()
        
        return {"status": "acknowledged", "alert_code": alert_code}
    
    def resolve_alert(
        self,
        alert_code: str,
        user_id: int,
        resolution_notes: str
    ) -> Dict:
        """Resolve an alert"""
        self.db.execute(text("""
            UPDATE variance_alerts
            SET status = 'RESOLVED',
                acknowledged_by_user_id = COALESCE(acknowledged_by_user_id, :user_id),
                acknowledged_at = COALESCE(acknowledged_at, GETUTCDATE()),
                resolved_at = GETUTCDATE(),
                resolution_notes = :notes,
                updated_at = GETUTCDATE()
            WHERE alert_code = :code
        """), {
            "code": alert_code,
            "user_id": user_id,
            "notes": resolution_notes
        })
        self.db.commit()
        
        return {"status": "resolved", "alert_code": alert_code}
    
    def get_alert_summary(
        self,
        fiscal_year: Optional[int] = None
    ) -> Dict:
        """Get summary of alerts by severity and status"""
        where_clause = "WHERE 1=1"
        params = {}
        
        if fiscal_year:
            where_clause += " AND fiscal_year = :year"
            params["year"] = fiscal_year
        
        result = self.db.execute(text(f"""
            SELECT 
                severity,
                status,
                COUNT(*) as count
            FROM variance_alerts
            {where_clause}
            GROUP BY severity, status
        """), params)
        
        summary = {
            "by_severity": {"INFO": 0, "WARNING": 0, "CRITICAL": 0},
            "by_status": {"PENDING": 0, "SENT": 0, "ACKNOWLEDGED": 0, "RESOLVED": 0},
            "total": 0
        }
        
        for row in result.fetchall():
            severity, status, count = row
            summary["by_severity"][severity] = summary["by_severity"].get(severity, 0) + count
            summary["by_status"][status] = summary["by_status"].get(status, 0) + count
            summary["total"] += count
        
        return summary
    
    def set_threshold(
        self,
        department: Optional[str] = None,
        account_code: Optional[str] = None,
        info_threshold: float = 5.0,
        warning_threshold: float = 10.0,
        critical_threshold: float = 20.0,
        notify_department_head: bool = True,
        notify_cfo: bool = False
    ) -> Dict:
        """Set or update variance thresholds"""
        existing = self.db.execute(text("""
            SELECT id FROM alert_thresholds
            WHERE (department = :dept OR (department IS NULL AND :dept IS NULL))
              AND (account_code = :acc OR (account_code IS NULL AND :acc IS NULL))
        """), {"dept": department, "acc": account_code}).first()
        
        if existing:
            self.db.execute(text("""
                UPDATE alert_thresholds
                SET info_threshold = :info,
                    warning_threshold = :warning,
                    critical_threshold = :critical,
                    notify_department_head = :notify_dept,
                    notify_cfo = :notify_cfo,
                    updated_at = GETUTCDATE()
                WHERE id = :id
            """), {
                "id": existing[0],
                "info": info_threshold,
                "warning": warning_threshold,
                "critical": critical_threshold,
                "notify_dept": notify_department_head,
                "notify_cfo": notify_cfo
            })
        else:
            self.db.execute(text("""
                INSERT INTO alert_thresholds
                (department, account_code, info_threshold, warning_threshold,
                 critical_threshold, notify_department_head, notify_cfo)
                VALUES
                (:dept, :acc, :info, :warning, :critical, :notify_dept, :notify_cfo)
            """), {
                "dept": department,
                "acc": account_code,
                "info": info_threshold,
                "warning": warning_threshold,
                "critical": critical_threshold,
                "notify_dept": notify_department_head,
                "notify_cfo": notify_cfo
            })
        
        self.db.commit()
        
        return {
            "status": "updated" if existing else "created",
            "department": department,
            "account_code": account_code,
            "thresholds": {
                "info": info_threshold,
                "warning": warning_threshold,
                "critical": critical_threshold
            }
        }
    
    def get_variance_report(
        self,
        fiscal_year: int,
        month: Optional[int] = None,
        department: Optional[str] = None
    ) -> Dict:
        """Generate variance report for Plan vs Fact analysis"""
        query = self.db.query(BudgetLineItem).join(Budget).filter(
            Budget.fiscal_year == fiscal_year,
            Budget.status == BudgetStatus.APPROVED
        )
        
        if month:
            query = query.filter(BudgetLineItem.month == month)
        if department:
            query = query.filter(Budget.department == department)
        
        items = query.all()
        
        report = {
            "fiscal_year": fiscal_year,
            "month": month,
            "department": department,
            "summary": {
                "total_planned": 0,
                "total_actual": 0,
                "total_variance": 0,
                "favorable_count": 0,
                "unfavorable_count": 0,
                "on_target_count": 0
            },
            "by_account": [],
            "top_variances": []
        }
        
        variances = []
        
        for item in items:
            planned = float(item.amount or 0)
            variance = float(item.variance or 0)
            actual = planned + variance
            variance_pct = float(item.variance_percent or 0)
            
            report["summary"]["total_planned"] += planned
            report["summary"]["total_actual"] += actual
            report["summary"]["total_variance"] += variance
            
            if variance_pct > 5:
                report["summary"]["unfavorable_count"] += 1
            elif variance_pct < -5:
                report["summary"]["favorable_count"] += 1
            else:
                report["summary"]["on_target_count"] += 1
            
            variances.append({
                "account_code": item.account_code,
                "account_name": item.account_name,
                "month": item.month,
                "planned": planned,
                "actual": actual,
                "variance": variance,
                "variance_percent": variance_pct
            })
        
        variances.sort(key=lambda x: abs(x["variance_percent"]), reverse=True)
        report["top_variances"] = variances[:10]
        
        return report
