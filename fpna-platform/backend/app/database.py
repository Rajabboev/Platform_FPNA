"""Database connection and session management"""
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
