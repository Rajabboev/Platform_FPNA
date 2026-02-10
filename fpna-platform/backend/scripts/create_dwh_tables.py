"""Create DWH connection and mapping tables in SQL Server"""
import sys
import os

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app.database import engine
from sqlalchemy import text


def run():
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
                created_by_user_id INT NULL REFERENCES users(id) ON DELETE SET NULL
            )
        """))
        conn.execute(text("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'dwh_table_mappings')
            CREATE TABLE dwh_table_mappings (
                id INT IDENTITY(1,1) PRIMARY KEY,
                connection_id INT NOT NULL REFERENCES dwh_connections(id) ON DELETE CASCADE,
                source_schema NVARCHAR(100) NULL,
                source_table NVARCHAR(255) NOT NULL,
                target_entity NVARCHAR(100) NOT NULL,
                target_description NVARCHAR(255) NULL,
                column_mapping NVARCHAR(MAX) NULL,
                is_active BIT DEFAULT 1,
                sync_enabled BIT DEFAULT 1,
                created_at DATETIMEOFFSET DEFAULT SYSDATETIMEOFFSET(),
                updated_at DATETIMEOFFSET NULL
            )
        """))
        print("DWH tables created or already exist.")


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
