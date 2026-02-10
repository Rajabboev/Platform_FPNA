"""
Seed the DB_STAGE connection into FPNA so you can test Manage Connections.
Run create_db_stage_login.sql on SQL Server first, then run this script.

Usage (from backend dir, with correct Python env):
  python scripts/seed_db_stage_connection.py
"""
import sys
import os

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app.database import SessionLocal
from app.models.dwh_connection import DWHConnection

# Default: local SQL Server. Change host if your server is remote.
DEFAULT_HOST = os.environ.get("FPNA_DWH_HOST", "localhost")
CONNECTION = {
    "name": "DB_STAGE (Test)",
    "db_type": "sql_server",
    "host": DEFAULT_HOST,
    "port": 1433,
    "database_name": "DB_STAGE",
    "username": "fpna_stage_reader",
    "password_encrypted": "FPNA_Stage_Read_2024!",
    "schema_name": "dbo",
    "use_ssl": False,
    "description": "Test DWH connection - DB_STAGE",
    "is_active": True,
}


def main():
    db = SessionLocal()
    try:
        existing = db.query(DWHConnection).filter(DWHConnection.name == CONNECTION["name"]).first()
        if existing:
            for k, v in CONNECTION.items():
                setattr(existing, k, v)
            db.commit()
            print("Updated existing connection: DB_STAGE (Test)")
        else:
            db.add(DWHConnection(**CONNECTION))
            db.commit()
            print("Created connection: DB_STAGE (Test)")
        print("Go to FPNA → Manage Connections and select 'DB_STAGE (Test)' to explore tables.")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
