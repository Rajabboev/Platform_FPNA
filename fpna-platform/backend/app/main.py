"""FastAPI application main entry point"""
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
from app.models.budget import Budget, BudgetLineItem, BudgetApproval  # noqa: F401
from app.models.user import User, Role  # noqa: F401
from app.models.notification import Notification  # noqa: F401
from app.models.dwh_connection import DWHConnection, DWHTableMapping  # noqa: F401
from app.models.etl_job import ETLJob, ETLRun  # noqa: F401

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
from app.api import books, budgets_excel, auth, approvals, notifications, connections, etl

# Include routers
app.include_router(books.router, prefix="/api/v1")
app.include_router(budgets_excel.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(approvals.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(connections.router, prefix="/api/v1")
app.include_router(etl.router, prefix="/api/v1")

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