"""FastAPI application main entry point - FP&A Platform"""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
import time
import logging

from app.config import settings

logger = logging.getLogger(__name__)
from app.database import engine, Base

# Import models to register with Base before create_all
from app.models.budget import Budget, BudgetLineItem, BudgetApproval, BudgetLineItemCurrency  # noqa: F401
from app.models.user import User, Role  # noqa: F401
from app.models.notification import Notification  # noqa: F401
from app.models.dwh_connection import DWHConnection, DWHTableMapping  # noqa: F401
from app.models.etl_job import ETLJob, ETLRun  # noqa: F401
from app.models.coa import AccountClass, AccountGroup, AccountCategory, Account, AccountMapping  # noqa: F401
from app.models.business_unit import BusinessUnit, AccountResponsibility  # noqa: F401
from app.models.snapshot import BalanceSnapshot, BaselineBudget, SnapshotImportLog  # noqa: F401
from app.models.currency import Currency, CurrencyRate, BudgetFXRate  # noqa: F401
from app.models.driver import (  # noqa: F401
    Driver,
    DriverValue,
    DriverCalculationLog,
    DriverGroupAssignment,
    GoldenRule,
)
from app.models.template import BudgetTemplate, TemplateSection, TemplateAssignment, TemplateLineItem  # noqa: F401
from app.models.baseline import BaselineData, BudgetBaseline, BudgetPlanned, ApprovedBudgetFact  # noqa: F401
from app.models.coa_dimension import COADimension, BudgetingGroup, BSClass  # noqa: F401
from app.models.department import Department, DepartmentAssignment, DepartmentProductAccess  # noqa: F401
from app.models.budget_plan import BudgetPlan, BudgetPlanGroup, BudgetPlanDetail, BudgetPlanApproval  # noqa: F401
from app.models.scenario import BudgetScenario, ScenarioAdjustment, AIScenarioProjection  # noqa: F401
from app.models.metadata_logic import (  # noqa: F401
    MetadataLogicDriver,
    MetadataLogicRule,
    MetadataLogicRevision,
    MetadataExecutionLog,
)

# Create database tables (including dwh_connections, etl_jobs, etl_runs)
Base.metadata.create_all(bind=engine)
# Ensure DWH tables exist (idempotent; handles DB created before connections feature)
try:
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'dwh_connections')
            CREATE TABLE dwh_connections (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(100) NOT NULL,
                db_type NVARCHAR(50) NOT NULL,
                host NVARCHAR(255) NOT NULL,
                port INT NULL,
                database_name NVARCHAR(255) NOT NULL,
                username NVARCHAR(255) NOT NULL,
                password_encrypted NVARCHAR(500) NULL,
                schema_name NVARCHAR(100) NULL,
                use_ssl BIT DEFAULT 0,
                extra_params NVARCHAR(MAX) NULL,
                is_active BIT DEFAULT 1,
                description NVARCHAR(500) NULL,
                created_at DATETIMEOFFSET DEFAULT SYSDATETIMEOFFSET(),
                updated_at DATETIMEOFFSET NULL,
                created_by_user_id INT NULL
            )
        """))
        conn.execute(text("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'dwh_table_mappings')
            CREATE TABLE dwh_table_mappings (
                id INT IDENTITY(1,1) PRIMARY KEY,
                connection_id INT NOT NULL,
                source_schema NVARCHAR(100) NULL,
                source_table NVARCHAR(255) NOT NULL,
                target_entity NVARCHAR(100) NOT NULL,
                target_description NVARCHAR(255) NULL,
                column_mapping NVARCHAR(MAX) NULL,
                is_active BIT DEFAULT 1,
                sync_enabled BIT DEFAULT 1,
                created_at DATETIMEOFFSET DEFAULT SYSDATETIMEOFFSET(),
                updated_at DATETIMEOFFSET NULL,
                CONSTRAINT fk_dwh_tm_conn FOREIGN KEY (connection_id) REFERENCES dwh_connections(id) ON DELETE CASCADE
            )
        """))
        conn.execute(text("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'etl_jobs')
            CREATE TABLE etl_jobs (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(100) NOT NULL,
                description NVARCHAR(500) NULL,
                source_type NVARCHAR(20) NOT NULL,
                source_connection_id INT NULL REFERENCES dwh_connections(id) ON DELETE NO ACTION,
                source_schema NVARCHAR(100) NULL,
                source_table NVARCHAR(255) NOT NULL,
                target_type NVARCHAR(20) NOT NULL,
                target_connection_id INT NULL REFERENCES dwh_connections(id) ON DELETE NO ACTION,
                target_schema NVARCHAR(100) NULL,
                target_table NVARCHAR(255) NOT NULL,
                column_mapping NVARCHAR(MAX) NULL,
                create_target_if_missing BIT DEFAULT 0,
                load_mode NVARCHAR(30) NOT NULL DEFAULT 'full_replace',
                is_active BIT DEFAULT 1,
                created_at DATETIMEOFFSET DEFAULT SYSDATETIMEOFFSET(),
                updated_at DATETIMEOFFSET NULL,
                created_by_user_id INT NULL
            )
        """))
        conn.execute(text("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'etl_runs')
            CREATE TABLE etl_runs (
                id INT IDENTITY(1,1) PRIMARY KEY,
                job_id INT NOT NULL,
                status NVARCHAR(20) NOT NULL,
                rows_extracted INT DEFAULT 0,
                rows_loaded INT DEFAULT 0,
                error_message NVARCHAR(MAX) NULL,
                started_at DATETIMEOFFSET DEFAULT SYSDATETIMEOFFSET(),
                finished_at DATETIMEOFFSET NULL,
                CONSTRAINT fk_etl_run_job FOREIGN KEY (job_id) REFERENCES etl_jobs(id) ON DELETE CASCADE
            )
        """))
except Exception as e:
    logger.warning("DWH tables init skipped or failed: %s", e)

# Schema migrations for new columns/tables
try:
    from sqlalchemy import text as _text, inspect as _inspect
    with engine.begin() as _conn:
        insp = _inspect(engine)
        # Add new columns to department_budgeting_groups
        if 'department_budgeting_groups' in insp.get_table_names():
            existing = {c['name'] for c in insp.get_columns('department_budgeting_groups')}
            if 'can_edit' not in existing:
                _conn.execute(_text("ALTER TABLE department_budgeting_groups ADD can_edit BIT DEFAULT 1"))
            if 'can_submit' not in existing:
                _conn.execute(_text("ALTER TABLE department_budgeting_groups ADD can_submit BIT DEFAULT 1"))
            if 'assigned_by_user_id' not in existing:
                _conn.execute(_text("ALTER TABLE department_budgeting_groups ADD assigned_by_user_id INT NULL"))
            if 'assigned_at' not in existing:
                _conn.execute(_text("ALTER TABLE department_budgeting_groups ADD assigned_at DATETIMEOFFSET NULL"))

        # Add new columns to notifications
        if 'notifications' in insp.get_table_names():
            existing = {c['name'] for c in insp.get_columns('notifications')}
            if 'plan_id' not in existing:
                _conn.execute(_text("ALTER TABLE notifications ADD plan_id INT NULL"))
            if 'plan_code' not in existing:
                _conn.execute(_text("ALTER TABLE notifications ADD plan_code NVARCHAR(100) NULL"))
            if 'link_step' not in existing:
                _conn.execute(_text("ALTER TABLE notifications ADD link_step INT NULL"))

        # Add missing columns to driver_values
        if 'driver_values' in insp.get_table_names():
            existing = {c['name'] for c in insp.get_columns('driver_values')}
            if 'budgeting_group_id' not in existing:
                _conn.execute(_text("ALTER TABLE driver_values ADD budgeting_group_id INT NULL"))
            if 'bs_group' not in existing:
                _conn.execute(_text("ALTER TABLE driver_values ADD bs_group INT NULL"))

        # Add driver_type to budget_plan_groups
        if 'budget_plan_groups' in insp.get_table_names():
            existing = {c['name'] for c in insp.get_columns('budget_plan_groups')}
            if 'driver_type' not in existing:
                _conn.execute(_text("ALTER TABLE budget_plan_groups ADD driver_type NVARCHAR(50) NULL"))

        # Add CEO columns to budget_plans
        if 'budget_plans' in insp.get_table_names():
            existing = {c['name'] for c in insp.get_columns('budget_plans')}
            if 'ceo_approved_at' not in existing:
                _conn.execute(_text("ALTER TABLE budget_plans ADD ceo_approved_at DATETIMEOFFSET NULL"))
            if 'ceo_approved_by_user_id' not in existing:
                _conn.execute(_text("ALTER TABLE budget_plans ADD ceo_approved_by_user_id INT NULL"))
            if 'ceo_approval_comment' not in existing:
                _conn.execute(_text("ALTER TABLE budget_plans ADD ceo_approval_comment NVARCHAR(MAX) NULL"))

        # Create budget_scenarios if not exists
        if 'budget_scenarios' not in insp.get_table_names():
            _conn.execute(_text("""
                CREATE TABLE budget_scenarios (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    plan_fiscal_year INT NOT NULL,
                    name NVARCHAR(255) NOT NULL,
                    description NVARCHAR(MAX) NULL,
                    scenario_type NVARCHAR(50) DEFAULT 'what_if',
                    status NVARCHAR(30) DEFAULT 'draft',
                    parent_scenario_id INT NULL,
                    created_by_user_id INT NULL,
                    approved_by_user_id INT NULL,
                    approved_at DATETIMEOFFSET NULL,
                    created_at DATETIMEOFFSET DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIMEOFFSET NULL
                )
            """))

        # Create scenario_adjustments if not exists
        if 'scenario_adjustments' not in insp.get_table_names():
            _conn.execute(_text("""
                CREATE TABLE scenario_adjustments (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    scenario_id INT NOT NULL REFERENCES budget_scenarios(id) ON DELETE CASCADE,
                    budgeting_group_id INT NOT NULL,
                    department_id INT NULL,
                    month INT NULL,
                    adjustment_type NVARCHAR(30) DEFAULT 'percentage',
                    value DECIMAL(20,4) NOT NULL,
                    driver_code NVARCHAR(50) NULL,
                    notes NVARCHAR(MAX) NULL,
                    created_at DATETIMEOFFSET DEFAULT CURRENT_TIMESTAMP
                )
            """))

        # Add manager_user_id to departments (separate from head_user_id — manager submits, head approves)
        if 'departments' in insp.get_table_names():
            existing = {c['name'] for c in insp.get_columns('departments')}
            if 'manager_user_id' not in existing:
                _conn.execute(_text("ALTER TABLE departments ADD manager_user_id INT NULL REFERENCES users(id)"))

        # approved_budget_fact – account-level fact table for fact-vs-plan
        if 'approved_budget_fact' not in insp.get_table_names():
            _conn.execute(_text("""
                CREATE TABLE approved_budget_fact (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    coa_code NVARCHAR(10) NOT NULL,
                    fiscal_year INT NOT NULL,
                    fiscal_month INT NOT NULL,
                    currency NVARCHAR(3) DEFAULT 'UZS',
                    baseline_amount DECIMAL(22,2) DEFAULT 0,
                    adjusted_amount DECIMAL(22,2) DEFAULT 0,
                    variance DECIMAL(22,2) DEFAULT 0,
                    coa_name NVARCHAR(1000),
                    bs_flag INT,
                    bs_class_name NVARCHAR(255),
                    bs_group NVARCHAR(10),
                    bs_group_name NVARCHAR(255),
                    budgeting_group_id INT,
                    budgeting_group_name NVARCHAR(500),
                    department_code NVARCHAR(50),
                    department_name NVARCHAR(255),
                    driver_code NVARCHAR(50),
                    driver_rate DECIMAL(10,4),
                    driver_type NVARCHAR(50),
                    version INT DEFAULT 1,
                    plan_status NVARCHAR(30),
                    export_batch_id NVARCHAR(50),
                    submitted_at DATETIMEOFFSET NULL,
                    dept_approved_at DATETIMEOFFSET NULL,
                    cfo_approved_at DATETIMEOFFSET NULL,
                    ceo_approved_at DATETIMEOFFSET NULL,
                    exported_at DATETIMEOFFSET NULL,
                    created_at DATETIMEOFFSET DEFAULT CURRENT_TIMESTAMP
                )
            """))
            _conn.execute(_text("CREATE INDEX ix_abf_coa_year_month ON approved_budget_fact (coa_code, fiscal_year, fiscal_month)"))
            _conn.execute(_text("CREATE INDEX ix_abf_year_dept ON approved_budget_fact (fiscal_year, department_code)"))
            _conn.execute(_text("CREATE INDEX ix_abf_year_group ON approved_budget_fact (fiscal_year, budgeting_group_id)"))
            _conn.execute(_text("CREATE INDEX ix_abf_batch ON approved_budget_fact (export_batch_id)"))

        # FP&A product access (replaces budgeting-group-only assignment for new flows)
        if 'department_product_access' not in insp.get_table_names():
            _conn.execute(_text("""
                CREATE TABLE department_product_access (
                    department_id INT NOT NULL,
                    product_key NVARCHAR(50) NOT NULL,
                    can_edit BIT DEFAULT 1,
                    can_submit BIT DEFAULT 1,
                    assigned_by_user_id INT NULL,
                    assigned_at DATETIMEOFFSET NULL,
                    CONSTRAINT pk_dept_product PRIMARY KEY (department_id, product_key),
                    CONSTRAINT fk_dept_product_dept FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE
                )
            """))

        if 'budget_plan_groups' in insp.get_table_names():
            _bpg = {c['name'] for c in insp.get_columns('budget_plan_groups')}
            if 'fpna_product_key' not in _bpg:
                _conn.execute(_text(
                    "ALTER TABLE budget_plan_groups ADD fpna_product_key NVARCHAR(50) NULL"
                ))
            if 'fpna_product_label_en' not in _bpg:
                _conn.execute(_text(
                    "ALTER TABLE budget_plan_groups ADD fpna_product_label_en NVARCHAR(200) NULL"
                ))
            try:
                _conn.execute(_text(
                    "ALTER TABLE budget_plan_groups ALTER COLUMN budgeting_group_id INT NULL"
                ))
            except Exception:
                pass

        if 'driver_group_assignments' in insp.get_table_names():
            _dga = {c['name'] for c in insp.get_columns('driver_group_assignments')}
            if 'fpna_product_key' not in _dga:
                _conn.execute(_text(
                    "ALTER TABLE driver_group_assignments ADD fpna_product_key NVARCHAR(50) NULL"
                ))
            try:
                _conn.execute(_text(
                    "ALTER TABLE driver_group_assignments ALTER COLUMN budgeting_group_id INT NULL"
                ))
            except Exception:
                pass
            try:
                _conn.execute(_text(
                    "DROP INDEX IF EXISTS ix_driver_group_assignment ON driver_group_assignments"
                ))
            except Exception:
                pass
            try:
                _conn.execute(_text("""
                    CREATE UNIQUE NONCLUSTERED INDEX ix_dga_driver_bg_uq
                    ON driver_group_assignments(driver_id, budgeting_group_id)
                    WHERE budgeting_group_id IS NOT NULL
                """))
            except Exception:
                pass
            try:
                _conn.execute(_text("""
                    CREATE UNIQUE NONCLUSTERED INDEX ix_dga_driver_product_uq
                    ON driver_group_assignments(driver_id, fpna_product_key)
                    WHERE fpna_product_key IS NOT NULL
                """))
            except Exception:
                pass

        if 'driver_values' in insp.get_table_names():
            _dv = {c['name'] for c in insp.get_columns('driver_values')}
            if 'fpna_product_key' not in _dv:
                _conn.execute(_text("ALTER TABLE driver_values ADD fpna_product_key NVARCHAR(50) NULL"))

        if 'metadata_logic_drivers' not in insp.get_table_names():
            _conn.execute(_text("""
                CREATE TABLE metadata_logic_drivers (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    driver_id INT NULL REFERENCES drivers(id),
                    code NVARCHAR(100) NOT NULL,
                    name NVARCHAR(255) NOT NULL,
                    description NVARCHAR(MAX) NULL,
                    version INT NOT NULL DEFAULT 1,
                    is_active BIT DEFAULT 1,
                    is_published BIT DEFAULT 0,
                    scope_fields NVARCHAR(MAX) NULL,
                    formula_expr NVARCHAR(MAX) NOT NULL,
                    output_mode NVARCHAR(50) DEFAULT 'monthly_adjusted',
                    rounding_mode NVARCHAR(50) DEFAULT 'HALF_UP',
                    min_value DECIMAL(20,6) NULL,
                    max_value DECIMAL(20,6) NULL,
                    effective_from DATETIMEOFFSET NULL,
                    effective_to DATETIMEOFFSET NULL,
                    created_by_user_id INT NULL REFERENCES users(id),
                    approved_by_user_id INT NULL REFERENCES users(id),
                    published_at DATETIMEOFFSET NULL,
                    created_at DATETIMEOFFSET DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIMEOFFSET NULL
                )
            """))
            _conn.execute(_text("CREATE INDEX ix_mld_driver ON metadata_logic_drivers(driver_id, is_active, is_published)"))
            _conn.execute(_text("CREATE INDEX ix_mld_code ON metadata_logic_drivers(code)"))
        else:
            try:
                _conn.execute(_text("ALTER TABLE metadata_logic_drivers ALTER COLUMN driver_id INT NULL"))
            except Exception:
                pass

        if 'metadata_logic_rules' not in insp.get_table_names():
            _conn.execute(_text("""
                CREATE TABLE metadata_logic_rules (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    code NVARCHAR(100) NOT NULL,
                    name NVARCHAR(255) NOT NULL,
                    version INT NOT NULL DEFAULT 1,
                    priority INT NOT NULL DEFAULT 100,
                    condition_expr NVARCHAR(MAX) NOT NULL,
                    target_selector NVARCHAR(MAX) NULL,
                    action_type NVARCHAR(50) NOT NULL DEFAULT 'set',
                    action_payload NVARCHAR(MAX) NULL,
                    stop_on_match BIT DEFAULT 0,
                    is_active BIT DEFAULT 1,
                    is_published BIT DEFAULT 0,
                    created_by_user_id INT NULL REFERENCES users(id),
                    approved_by_user_id INT NULL REFERENCES users(id),
                    published_at DATETIMEOFFSET NULL,
                    created_at DATETIMEOFFSET DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIMEOFFSET NULL
                )
            """))
            _conn.execute(_text("CREATE INDEX ix_mlr_code ON metadata_logic_rules(code, is_active, is_published)"))

        if 'metadata_logic_revisions' not in insp.get_table_names():
            _conn.execute(_text("""
                CREATE TABLE metadata_logic_revisions (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    entity_type NVARCHAR(30) NOT NULL,
                    entity_id INT NOT NULL,
                    version INT NOT NULL,
                    change_type NVARCHAR(30) NOT NULL,
                    before_payload NVARCHAR(MAX) NULL,
                    after_payload NVARCHAR(MAX) NULL,
                    changed_by_user_id INT NULL REFERENCES users(id),
                    changed_at DATETIMEOFFSET DEFAULT CURRENT_TIMESTAMP
                )
            """))
            _conn.execute(_text("CREATE INDEX ix_mlr_entity ON metadata_logic_revisions(entity_type, entity_id, version)"))

        if 'metadata_execution_logs' not in insp.get_table_names():
            _conn.execute(_text("""
                CREATE TABLE metadata_execution_logs (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    run_id NVARCHAR(64) NOT NULL,
                    logic_code NVARCHAR(100) NOT NULL,
                    formula_used NVARCHAR(MAX) NULL,
                    context_json NVARCHAR(MAX) NULL,
                    result_value DECIMAL(20,6) NULL,
                    status NVARCHAR(20) DEFAULT 'SUCCESS',
                    error NVARCHAR(MAX) NULL,
                    created_at DATETIMEOFFSET DEFAULT CURRENT_TIMESTAMP
                )
            """))
            _conn.execute(_text("CREATE INDEX ix_mel_run ON metadata_execution_logs(run_id)"))
            _conn.execute(_text("CREATE INDEX ix_mel_logic ON metadata_execution_logs(logic_code, status)"))

        # Segment-aware baselines (DWH slice per department)
        if 'baseline_data' in insp.get_table_names():
            _bd = {c['name'] for c in insp.get_columns('baseline_data')}
            if 'segment_key' not in _bd:
                _conn.execute(_text("ALTER TABLE baseline_data ADD segment_key NVARCHAR(100) NULL"))
            try:
                _conn.execute(_text(
                    "IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'ix_baseline_data_year_segment' "
                    "AND object_id = OBJECT_ID('baseline_data')) "
                    "CREATE INDEX ix_baseline_data_year_segment ON baseline_data (fiscal_year, segment_key)"
                ))
            except Exception:
                pass

        if 'departments' in insp.get_table_names():
            _dep = {c['name'] for c in insp.get_columns('departments')}
            if 'dwh_segment_value' not in _dep:
                _conn.execute(_text("ALTER TABLE departments ADD dwh_segment_value NVARCHAR(100) NULL"))
            if 'primary_product_key' not in _dep:
                _conn.execute(_text("ALTER TABLE departments ADD primary_product_key NVARCHAR(50) NULL"))
            try:
                _conn.execute(_text(
                    "IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'uq_dept_primary_product_active' "
                    "AND object_id = OBJECT_ID('departments')) "
                    "CREATE UNIQUE NONCLUSTERED INDEX uq_dept_primary_product_active ON departments(primary_product_key) "
                    "WHERE primary_product_key IS NOT NULL AND is_active = 1"
                ))
            except Exception:
                pass

        if 'coa_dimension' in insp.get_table_names():
            _coa = {c['name'] for c in insp.get_columns('coa_dimension')}
            if 'fpna_product_key' not in _coa:
                _conn.execute(_text("ALTER TABLE coa_dimension ADD fpna_product_key NVARCHAR(50) NULL"))
            if 'fpna_product_label_en' not in _coa:
                _conn.execute(_text("ALTER TABLE coa_dimension ADD fpna_product_label_en NVARCHAR(500) NULL"))
            if 'fpna_product_pillar' not in _coa:
                _conn.execute(_text("ALTER TABLE coa_dimension ADD fpna_product_pillar NVARCHAR(50) NULL"))
            if 'fpna_display_group' not in _coa:
                _conn.execute(_text("ALTER TABLE coa_dimension ADD fpna_display_group NVARCHAR(1000) NULL"))
            try:
                _conn.execute(_text(
                    "IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'ix_coa_dim_fpna_product' "
                    "AND object_id = OBJECT_ID('coa_dimension')) "
                    "CREATE INDEX ix_coa_dim_fpna_product ON coa_dimension (fpna_product_key)"
                ))
            except Exception:
                pass

except Exception as e:
    logger.warning("Schema migration skipped or failed: %s", e)

# Initialize FastAPI app FIRST
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-Powered Financial Planning & Analysis Platform",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    request.state.request_id = f"{int(time.time() * 1000)}"

    response = await call_next(request)

    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-Request-ID"] = request.state.request_id

    return response

# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "detail": exc.errors(),
            "request_id": request.state.request_id
        }
    )

@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.exception("Database error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Database Error",
            "message": str(exc) if settings.DEBUG else "An error occurred while processing your request",
            "request_id": request.state.request_id
        }
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": str(exc) if settings.DEBUG else "An unexpected error occurred",
            "request_id": request.state.request_id
        }
    )

# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }

# Import routers AFTER app is created
from app.api import budgets_excel, budgets_upload, auth, approvals, notifications, connections, etl, coa
from app.api import snapshots, currencies, drivers, templates, dwh_integration, baseline, data_upload, planned_approvals
from app.api import coa_dimension
from app.api import departments, budget_planning, analysis
from app.api import ai as ai_router
from app.api import reports as reports_router

# Include routers
app.include_router(budgets_excel.router, prefix="/api/v1")
app.include_router(budgets_upload.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(approvals.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(connections.router, prefix="/api/v1")
app.include_router(etl.router, prefix="/api/v1")
app.include_router(coa.router, prefix="/api/v1")
app.include_router(snapshots.router, prefix="/api/v1")
app.include_router(currencies.router, prefix="/api/v1")
app.include_router(drivers.router, prefix="/api/v1")
app.include_router(templates.router, prefix="/api/v1")
app.include_router(dwh_integration.router, prefix="/api/v1")
app.include_router(baseline.router, prefix="/api/v1")
app.include_router(data_upload.router, prefix="/api/v1")
app.include_router(planned_approvals.router, prefix="/api/v1")
app.include_router(coa_dimension.router, prefix="/api/v1")
app.include_router(departments.router, prefix="/api/v1")
app.include_router(budget_planning.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(ai_router.router, prefix="/api/v1")
app.include_router(reports_router.router, prefix="/api/v1")

# Root endpoint
@app.get("/", tags=["root"])
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to FP&A Platform API",
        "version": settings.APP_VERSION,
        "docs": "/api/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )