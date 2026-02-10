#!/usr/bin/env python3
"""
FP&A Platform - Project Structure Generator
Run this script in your fpna-platform root directory
"""

import os
from pathlib import Path


def create_directory(path):
    """Create directory if it doesn't exist"""
    Path(path).mkdir(parents=True, exist_ok=True)
    print(f"✓ Created: {path}")


def create_file(path, content=""):
    """Create file with optional content"""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✓ Created: {path}")


def main():
    """Generate complete project structure"""
    print("\n" + "=" * 60)
    print("FP&A PLATFORM - PROJECT STRUCTURE GENERATOR")
    print("=" * 60 + "\n")

    # Project root
    root = Path.cwd()
    print(f"📁 Working in: {root}\n")

    # ==========================================
    # BACKEND STRUCTURE
    # ==========================================
    print("📦 Creating backend structure...\n")

    # Backend directories
    directories = [
        "backend/app/models",
        "backend/app/schemas",
        "backend/app/api",
        "backend/app/services",
        "backend/app/utils",
        "backend/app/middleware",
        "backend/tests",
        "backend/alembic/versions",
        "backend/scripts",
        "backend/uploads",
    ]

    for directory in directories:
        create_directory(directory)

    print("\n📄 Creating Python files...\n")

    # ==========================================
    # __init__.py files
    # ==========================================
    init_files = [
        "backend/app/__init__.py",
        "backend/app/models/__init__.py",
        "backend/app/schemas/__init__.py",
        "backend/app/api/__init__.py",
        "backend/app/services/__init__.py",
        "backend/app/utils/__init__.py",
        "backend/app/middleware/__init__.py",
        "backend/tests/__init__.py",
    ]

    for init_file in init_files:
        create_file(init_file, '"""Package initialization"""\n')

    # ==========================================
    # CONFIGURATION FILES
    # ==========================================

    # config.py
    config_content = '''"""Application configuration settings"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings"""

    # Application
    APP_NAME: str = "FP&A Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Database - SQL Server
    DATABASE_DRIVER: str = "ODBC Driver 17 for SQL Server"
    DATABASE_SERVER: str = "localhost"
    DATABASE_PORT: int = 1433
    DATABASE_NAME: str = "fpna_db"
    DATABASE_USER: str = "fpna_user"
    DATABASE_PASSWORD: str = "YourSecurePassword123!"

    # Security
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    # File Upload
    MAX_UPLOAD_SIZE: int = 10485760  # 10MB
    ALLOWED_EXTENSIONS: str = "xlsx,xls,csv"
    UPLOAD_FOLDER: str = "./uploads"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins into list"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(',')]

    @property
    def allowed_extensions_list(self) -> List[str]:
        """Parse allowed extensions into list"""
        return [ext.strip() for ext in self.ALLOWED_EXTENSIONS.split(',')]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
'''
    create_file("backend/app/config.py", config_content)

    # database.py
    database_content = '''"""Database connection and session management"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings
import urllib


# Build SQL Server connection string
params = urllib.parse.quote_plus(
    f"DRIVER={{{settings.DATABASE_DRIVER}}};"
    f"SERVER={settings.DATABASE_SERVER};"
    f"DATABASE={settings.DATABASE_NAME};"
    f"UID={settings.DATABASE_USER};"
    f"PWD={settings.DATABASE_PASSWORD};"
)

SQLALCHEMY_DATABASE_URL = f"mssql+pyodbc:///?odbc_connect={params}"

# Create engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Database session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
'''
    create_file("backend/app/database.py", database_content)

    # main.py
    main_content = '''"""FastAPI application main entry point"""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
import time

from app.config import settings
from app.database import engine, Base

# Import routers (will be uncommented as we create them)
# from app.api import auth, budgets, approvals, uploads

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
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
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Database Error",
            "message": "An error occurred while processing your request",
            "request_id": request.state.request_id
        }
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
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


# Include routers (uncomment as you create them)
# app.include_router(auth.router, prefix="/api/v1")
# app.include_router(budgets.router, prefix="/api/v1")
# app.include_router(approvals.router, prefix="/api/v1")
# app.include_router(uploads.router, prefix="/api/v1")


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
'''
    create_file("backend/app/main.py", main_content)

    # ==========================================
    # PLACEHOLDER FILES FOR MODELS
    # ==========================================

    create_file("backend/app/models/user.py",
                '"""User, Role, and Branch models"""\n# TODO: Add model implementations\n')
    create_file("backend/app/models/budget.py", '"""Budget and related models"""\n# TODO: Add model implementations\n')

    # ==========================================
    # PLACEHOLDER FILES FOR SCHEMAS
    # ==========================================

    create_file("backend/app/schemas/auth.py", '"""Authentication schemas"""\n# TODO: Add schema implementations\n')
    create_file("backend/app/schemas/user.py", '"""User schemas"""\n# TODO: Add schema implementations\n')
    create_file("backend/app/schemas/budget.py", '"""Budget schemas"""\n# TODO: Add schema implementations\n')

    # ==========================================
    # PLACEHOLDER FILES FOR API ROUTES
    # ==========================================

    create_file("backend/app/api/auth.py", '"""Authentication API routes"""\n# TODO: Add route implementations\n')
    create_file("backend/app/api/users.py", '"""User management API routes"""\n# TODO: Add route implementations\n')
    create_file("backend/app/api/budgets.py", '"""Budget API routes"""\n# TODO: Add route implementations\n')
    create_file("backend/app/api/approvals.py",
                '"""Approval workflow API routes"""\n# TODO: Add route implementations\n')
    create_file("backend/app/api/uploads.py", '"""File upload API routes"""\n# TODO: Add route implementations\n')

    # ==========================================
    # PLACEHOLDER FILES FOR SERVICES
    # ==========================================

    create_file("backend/app/services/auth_service.py",
                '"""Authentication service logic"""\n# TODO: Add service implementations\n')
    create_file("backend/app/services/budget_service.py",
                '"""Budget service logic"""\n# TODO: Add service implementations\n')
    create_file("backend/app/services/approval_service.py",
                '"""Approval service logic"""\n# TODO: Add service implementations\n')
    create_file("backend/app/services/excel_service.py",
                '"""Excel processing service"""\n# TODO: Add service implementations\n')

    # ==========================================
    # PLACEHOLDER FILES FOR UTILS
    # ==========================================

    create_file("backend/app/utils/dependencies.py",
                '"""FastAPI dependencies"""\n# TODO: Add dependency implementations\n')
    create_file("backend/app/utils/security.py", '"""Security utilities"""\n# TODO: Add security implementations\n')
    create_file("backend/app/utils/permissions.py",
                '"""Permission management"""\n# TODO: Add permission implementations\n')

    # ==========================================
    # PLACEHOLDER FILES FOR MIDDLEWARE
    # ==========================================

    create_file("backend/app/middleware/auth_middleware.py",
                '"""Authentication middleware"""\n# TODO: Add middleware implementations\n')

    # ==========================================
    # TEST FILES
    # ==========================================

    create_file("backend/tests/test_auth.py", '"""Authentication tests"""\n# TODO: Add test implementations\n')
    create_file("backend/tests/test_budgets.py", '"""Budget tests"""\n# TODO: Add test implementations\n')
    create_file("backend/tests/test_approvals.py", '"""Approval tests"""\n# TODO: Add test implementations\n')

    # ==========================================
    # REQUIREMENTS.TXT
    # ==========================================

    requirements_content = '''# FastAPI and Server
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6

# Database
sqlalchemy==2.0.23
pyodbc==5.0.1
alembic==1.12.1

# Authentication & Security
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-dotenv==1.0.0
bcrypt==4.1.1

# Excel Processing
openpyxl==3.1.2
pandas==2.1.3
xlrd==2.0.1

# Validation
pydantic==2.5.0
pydantic-settings==2.1.0
email-validator==2.1.0

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==0.21.1
httpx==0.25.2

# Utilities
python-dateutil==2.8.2
'''
    create_file("backend/requirements.txt", requirements_content)

    # ==========================================
    # .ENV.EXAMPLE
    # ==========================================

    env_example_content = '''# Application Settings
APP_NAME=FP&A Platform
APP_VERSION=1.0.0
DEBUG=True

# Database Configuration (SQL Server)
DATABASE_DRIVER=ODBC Driver 17 for SQL Server
DATABASE_SERVER=localhost
DATABASE_PORT=1433
DATABASE_NAME=fpna_db
DATABASE_USER=fpna_user
DATABASE_PASSWORD=YourSecurePassword123!

# Security Settings
SECRET_KEY=your-secret-key-change-this-in-production-use-openssl-rand-hex-32
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS Configuration
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# File Upload Settings
MAX_UPLOAD_SIZE=10485760
ALLOWED_EXTENSIONS=xlsx,xls,csv
UPLOAD_FOLDER=./uploads
'''
    create_file("backend/.env.example", env_example_content)
    create_file("backend/.env", env_example_content)  # Also create actual .env

    # ==========================================
    # BACKEND README
    # ==========================================

    backend_readme_content = '''# FP&A Platform - Backend

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env with your database credentials
```

3. Run the application:
```bash
uvicorn app.main:app --reload
```

4. Access API documentation:
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

## Project Structure

- `app/` - Main application code
  - `api/` - API route handlers
  - `models/` - Database models
  - `schemas/` - Pydantic schemas
  - `services/` - Business logic
  - `utils/` - Utility functions
  - `middleware/` - Custom middleware
- `tests/` - Test files
- `alembic/` - Database migrations
- `scripts/` - Utility scripts
'''
    create_file("backend/README.md", backend_readme_content)

    # ==========================================
    # ROOT README
    # ==========================================

    root_readme_content = '''# FP&A Platform

AI-Powered Financial Planning & Analysis Platform

## Features

- Multi-level budget approval workflow
- Role-based access control (RBAC)
- Excel file upload for budget data
- RESTful API with FastAPI
- SQL Server database integration
- JWT authentication

## Quick Start

### Prerequisites

- Python 3.10+
- SQL Server 2017+
- ODBC Driver 17 for SQL Server

### Installation

1. Clone the repository
2. Install dependencies:
```bash
cd backend
pip install -r requirements.txt
```

3. Configure database:
```bash
# Copy and edit .env file
cp backend/.env.example backend/.env
```

4. Initialize database:
```bash
# Run SQL Server scripts
sqlcmd -S localhost -U sa -i backend/scripts/init_database.sql
```

5. Run the application:
```bash
cd backend
uvicorn app.main:app --reload
```

6. Access API docs: http://localhost:8000/api/docs

## Project Structure

```
fpna-platform/
├── backend/           # FastAPI backend
│   ├── app/          # Application code
│   ├── tests/        # Test files
│   └── scripts/      # Utility scripts
├── frontend/         # Frontend (future)
└── README.md
```

## Documentation

See `backend/README.md` for backend-specific documentation.

## License

Proprietary - Westminster International University in Tashkent
'''
    create_file("README.md", root_readme_content)

    # ==========================================
    # .GITIGNORE
    # ==========================================

    gitignore_content = '''# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Environment
.env
.venv
.env.local

# IDE
.idea/
.vscode/
*.swp
*.swo
*~
.DS_Store

# Database
*.db
*.sqlite
*.sqlite3

# Logs
*.log
logs/

# Uploads
uploads/*
!uploads/.gitkeep

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# Alembic
alembic/versions/*.pyc
'''
    create_file(".gitignore", gitignore_content)

    # ==========================================
    # DOCKER COMPOSE (PLACEHOLDER)
    # ==========================================

    docker_compose_content = '''version: '3.8'

services:
  # SQL Server service (optional - if you want to run DB in Docker)
  # sqlserver:
  #   image: mcr.microsoft.com/mssql/server:2019-latest
  #   environment:
  #     SA_PASSWORD: "YourStrong@Passw0rd"
  #     ACCEPT_EULA: "Y"
  #   ports:
  #     - "1433:1433"
  #   volumes:
  #     - sqlserver_data:/var/opt/mssql

  # Backend API service
  api:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_SERVER=host.docker.internal
    volumes:
      - ./backend:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

volumes:
  sqlserver_data:
'''
    create_file("docker-compose.yml", docker_compose_content)

    # Create .gitkeep for uploads folder
    create_file("backend/uploads/.gitkeep", "")

    # ==========================================
    # SUMMARY
    # ==========================================

    print("\n" + "=" * 60)
    print("✅ PROJECT STRUCTURE CREATED SUCCESSFULLY!")
    print("=" * 60 + "\n")

    print("📁 Project structure:")
    print(f"   Root: {root}")
    print(f"   Backend: {root}/backend")
    print(f"   Config files: .env, requirements.txt, README.md\n")

    print("📋 Next steps:")
    print("   1. cd backend")
    print("   2. pip install -r requirements.txt")
    print("   3. Edit .env with your database credentials")
    print("   4. uvicorn app.main:app --reload")
    print("   5. Open http://localhost:8000/api/docs\n")

    print("📚 Documentation created:")
    print("   - README.md (root)")
    print("   - backend/README.md")
    print("   - .env.example\n")

    print("🎯 Ready to start coding!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()