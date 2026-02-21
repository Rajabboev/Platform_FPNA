"""
DWH Database Setup Script
Creates DWH database, login, imports balance data, and creates clean integration table

Usage:
    python scripts/setup_dwh.py --csv-path "path/to/balance_snapshot.csv"
    
Or run interactively to set up the database structure first, then import data later.
"""

import argparse
import pyodbc
import pandas as pd
from datetime import datetime
import os
import sys

# Configuration
DWH_CONFIG = {
    "server": "localhost",
    "master_db": "master",
    "dwh_db": "dwh",
    "dwh_login": "dwh_user",
    "dwh_password": "DwhUser@2024!",  # Change in production
    "driver": "ODBC Driver 17 for SQL Server",
}

# Use Windows Authentication for admin operations
ADMIN_CONN_STR = (
    f"DRIVER={{{DWH_CONFIG['driver']}}};"
    f"SERVER={DWH_CONFIG['server']};"
    f"DATABASE={DWH_CONFIG['master_db']};"
    f"Trusted_Connection=yes;"
)


def get_admin_connection(database="master"):
    """Get admin connection using Windows Authentication"""
    conn_str = (
        f"DRIVER={{{DWH_CONFIG['driver']}}};"
        f"SERVER={DWH_CONFIG['server']};"
        f"DATABASE={database};"
        f"Trusted_Connection=yes;"
    )
    return pyodbc.connect(conn_str, autocommit=True)


def create_dwh_database():
    """Create the DWH database"""
    print("=" * 60)
    print("Step 1: Creating DWH Database")
    print("=" * 60)
    
    conn = get_admin_connection("master")
    cursor = conn.cursor()
    
    try:
        # Check if database exists
        cursor.execute("SELECT name FROM sys.databases WHERE name = 'dwh'")
        if cursor.fetchone():
            print("  [INFO] Database 'dwh' already exists")
        else:
            cursor.execute("CREATE DATABASE dwh")
            print("  [OK] Database 'dwh' created successfully")
        
        conn.close()
        return True
    except Exception as e:
        print(f"  [ERROR] Failed to create database: {e}")
        return False


def create_dwh_login():
    """Create DWH login and user with appropriate roles"""
    print("\n" + "=" * 60)
    print("Step 2: Creating DWH Login and User")
    print("=" * 60)
    
    conn = get_admin_connection("master")
    cursor = conn.cursor()
    
    try:
        # Check if login exists
        cursor.execute(f"SELECT name FROM sys.server_principals WHERE name = '{DWH_CONFIG['dwh_login']}'")
        if cursor.fetchone():
            print(f"  [INFO] Login '{DWH_CONFIG['dwh_login']}' already exists")
        else:
            cursor.execute(f"""
                CREATE LOGIN [{DWH_CONFIG['dwh_login']}] 
                WITH PASSWORD = '{DWH_CONFIG['dwh_password']}',
                DEFAULT_DATABASE = [dwh],
                CHECK_POLICY = OFF
            """)
            print(f"  [OK] Login '{DWH_CONFIG['dwh_login']}' created")
        
        conn.close()
        
        # Create user in DWH database
        conn = get_admin_connection("dwh")
        cursor = conn.cursor()
        
        cursor.execute(f"SELECT name FROM sys.database_principals WHERE name = '{DWH_CONFIG['dwh_login']}'")
        if cursor.fetchone():
            print(f"  [INFO] User '{DWH_CONFIG['dwh_login']}' already exists in dwh database")
        else:
            cursor.execute(f"CREATE USER [{DWH_CONFIG['dwh_login']}] FOR LOGIN [{DWH_CONFIG['dwh_login']}]")
            print(f"  [OK] User '{DWH_CONFIG['dwh_login']}' created in dwh database")
        
        # Grant roles
        roles = ['db_datareader', 'db_datawriter', 'db_ddladmin']
        for role in roles:
            try:
                cursor.execute(f"ALTER ROLE [{role}] ADD MEMBER [{DWH_CONFIG['dwh_login']}]")
                print(f"  [OK] Added user to role: {role}")
            except:
                print(f"  [INFO] User already in role: {role}")
        
        conn.close()
        return True
    except Exception as e:
        print(f"  [ERROR] Failed to create login/user: {e}")
        return False


def create_raw_table():
    """Create the raw balance table (balans_ato) for CSV import"""
    print("\n" + "=" * 60)
    print("Step 3: Creating Raw Balance Table (balans_ato)")
    print("=" * 60)
    
    conn = get_admin_connection("dwh")
    cursor = conn.cursor()
    
    try:
        # Drop if exists and recreate
        cursor.execute("""
            IF OBJECT_ID('dbo.balans_ato', 'U') IS NOT NULL
                DROP TABLE dbo.balans_ato
        """)
        
        # Create raw table with flexible schema for CSV import
        cursor.execute("""
            CREATE TABLE dbo.balans_ato (
                id INT IDENTITY(1,1) PRIMARY KEY,
                report_date DATE,
                account_code NVARCHAR(50),
                account_name NVARCHAR(500),
                currency NVARCHAR(10),
                debit_balance DECIMAL(20,2),
                credit_balance DECIMAL(20,2),
                net_balance DECIMAL(20,2),
                branch_code NVARCHAR(50),
                branch_name NVARCHAR(200),
                import_date DATETIME DEFAULT GETDATE(),
                raw_data NVARCHAR(MAX)
            )
        """)
        print("  [OK] Table 'balans_ato' created")
        
        # Create indexes
        cursor.execute("CREATE INDEX ix_balans_ato_date ON dbo.balans_ato(report_date)")
        cursor.execute("CREATE INDEX ix_balans_ato_account ON dbo.balans_ato(account_code)")
        print("  [OK] Indexes created")
        
        conn.close()
        return True
    except Exception as e:
        print(f"  [ERROR] Failed to create raw table: {e}")
        return False


def create_clean_integration_table():
    """Create the clean integration table (balance_snapshot_26) for FPNA"""
    print("\n" + "=" * 60)
    print("Step 4: Creating Clean Integration Table (balance_snapshot_26)")
    print("=" * 60)
    
    conn = get_admin_connection("dwh")
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            IF OBJECT_ID('dbo.balance_snapshot_26', 'U') IS NOT NULL
                DROP TABLE dbo.balance_snapshot_26
        """)
        
        # Create clean table matching FPNA expected schema
        cursor.execute("""
            CREATE TABLE dbo.balance_snapshot_26 (
                id INT IDENTITY(1,1) PRIMARY KEY,
                snapshot_date DATE NOT NULL,
                account_code NVARCHAR(20) NOT NULL,
                account_name NVARCHAR(500),
                currency NVARCHAR(3) NOT NULL DEFAULT 'UZS',
                balance DECIMAL(20,2) NOT NULL DEFAULT 0,
                balance_uzs DECIMAL(20,2) NOT NULL DEFAULT 0,
                fx_rate DECIMAL(18,6) NOT NULL DEFAULT 1.0,
                branch_code NVARCHAR(50),
                data_source NVARCHAR(100) DEFAULT 'DWH_BALANS_ATO',
                created_at DATETIME DEFAULT GETDATE(),
                updated_at DATETIME
            )
        """)
        print("  [OK] Table 'balance_snapshot_26' created")
        
        # Create indexes for efficient querying
        cursor.execute("""
            CREATE UNIQUE INDEX ix_snapshot_date_account_currency 
            ON dbo.balance_snapshot_26(snapshot_date, account_code, currency)
        """)
        cursor.execute("CREATE INDEX ix_snapshot_date ON dbo.balance_snapshot_26(snapshot_date)")
        cursor.execute("CREATE INDEX ix_snapshot_account ON dbo.balance_snapshot_26(account_code)")
        print("  [OK] Indexes created")
        
        conn.close()
        return True
    except Exception as e:
        print(f"  [ERROR] Failed to create integration table: {e}")
        return False


def import_csv_to_raw(csv_path: str):
    """Import CSV file to balans_ato table"""
    print("\n" + "=" * 60)
    print(f"Step 5: Importing CSV to balans_ato")
    print(f"  Source: {csv_path}")
    print("=" * 60)
    
    if not os.path.exists(csv_path):
        print(f"  [ERROR] CSV file not found: {csv_path}")
        return False
    
    try:
        # Try different encodings
        encodings = ['utf-8', 'cp1251', 'latin1', 'utf-16']
        df = None
        
        for encoding in encodings:
            try:
                df = pd.read_csv(csv_path, encoding=encoding, low_memory=False)
                print(f"  [OK] CSV loaded with encoding: {encoding}")
                break
            except:
                continue
        
        if df is None:
            print("  [ERROR] Could not read CSV with any encoding")
            return False
        
        print(f"  [INFO] CSV columns: {list(df.columns)}")
        print(f"  [INFO] Total rows: {len(df)}")
        print(f"  [INFO] Sample data:")
        print(df.head(3).to_string())
        
        # Connect to DWH
        conn = get_admin_connection("dwh")
        cursor = conn.cursor()
        
        # Map columns (adjust based on actual CSV structure)
        # Common column name patterns
        column_mapping = {
            'date': ['date', 'report_date', 'sana', 'дата', 'DATE', 'SANA'],
            'account_code': ['account_code', 'account', 'schet', 'счет', 'kod', 'ACCOUNT_CODE', 'SCHET'],
            'account_name': ['account_name', 'name', 'nomi', 'наименование', 'NAME', 'NOMI'],
            'currency': ['currency', 'valyuta', 'валюта', 'CURRENCY', 'VALYUTA'],
            'debit': ['debit', 'debet', 'дебет', 'DEBIT', 'DEBET'],
            'credit': ['credit', 'kredit', 'кредит', 'CREDIT', 'KREDIT'],
            'balance': ['balance', 'qoldiq', 'остаток', 'saldo', 'BALANCE', 'QOLDIQ', 'SALDO'],
            'branch': ['branch', 'filial', 'филиал', 'BRANCH', 'FILIAL']
        }
        
        # Find matching columns
        found_columns = {}
        for target, patterns in column_mapping.items():
            for col in df.columns:
                if col.lower().strip() in [p.lower() for p in patterns]:
                    found_columns[target] = col
                    break
        
        print(f"\n  [INFO] Column mapping: {found_columns}")
        
        # Insert data
        inserted = 0
        batch_size = 1000
        
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i:i+batch_size]
            
            for _, row in batch.iterrows():
                try:
                    report_date = row.get(found_columns.get('date'), None)
                    account_code = str(row.get(found_columns.get('account_code'), ''))[:50]
                    account_name = str(row.get(found_columns.get('account_name'), ''))[:500]
                    currency = str(row.get(found_columns.get('currency'), 'UZS'))[:10]
                    debit = float(row.get(found_columns.get('debit'), 0) or 0)
                    credit = float(row.get(found_columns.get('credit'), 0) or 0)
                    balance = float(row.get(found_columns.get('balance'), 0) or 0)
                    branch = str(row.get(found_columns.get('branch'), ''))[:50]
                    
                    # Parse date
                    if pd.notna(report_date):
                        if isinstance(report_date, str):
                            for fmt in ['%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y', '%m/%d/%Y']:
                                try:
                                    report_date = datetime.strptime(report_date, fmt).date()
                                    break
                                except:
                                    continue
                    
                    cursor.execute("""
                        INSERT INTO dbo.balans_ato 
                        (report_date, account_code, account_name, currency, 
                         debit_balance, credit_balance, net_balance, branch_code, raw_data)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        report_date, account_code, account_name, currency,
                        debit, credit, balance, branch, str(row.to_dict())[:4000]
                    ))
                    inserted += 1
                except Exception as e:
                    pass  # Skip problematic rows
            
            print(f"  [PROGRESS] Inserted {inserted} rows...")
        
        conn.commit()
        conn.close()
        
        print(f"\n  [OK] Successfully imported {inserted} rows to balans_ato")
        return True
        
    except Exception as e:
        print(f"  [ERROR] Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def transform_to_clean_table():
    """Transform raw data to clean integration table"""
    print("\n" + "=" * 60)
    print("Step 6: Transforming Data to Clean Integration Table")
    print("=" * 60)
    
    conn = get_admin_connection("dwh")
    cursor = conn.cursor()
    
    try:
        # Clear existing data
        cursor.execute("TRUNCATE TABLE dbo.balance_snapshot_26")
        
        # Transform and insert
        cursor.execute("""
            INSERT INTO dbo.balance_snapshot_26 
            (snapshot_date, account_code, account_name, currency, balance, balance_uzs, fx_rate, branch_code)
            SELECT 
                EOMONTH(report_date) as snapshot_date,
                LEFT(account_code, 5) as account_code,
                MAX(account_name) as account_name,
                COALESCE(NULLIF(currency, ''), 'UZS') as currency,
                SUM(net_balance) as balance,
                SUM(CASE 
                    WHEN currency = 'UZS' OR currency IS NULL OR currency = '' THEN net_balance
                    WHEN currency = 'USD' THEN net_balance * 12500
                    WHEN currency = 'EUR' THEN net_balance * 13500
                    ELSE net_balance 
                END) as balance_uzs,
                CASE 
                    WHEN currency = 'USD' THEN 12500
                    WHEN currency = 'EUR' THEN 13500
                    ELSE 1.0 
                END as fx_rate,
                branch_code
            FROM dbo.balans_ato
            WHERE report_date IS NOT NULL 
              AND account_code IS NOT NULL 
              AND account_code != ''
            GROUP BY 
                EOMONTH(report_date),
                LEFT(account_code, 5),
                COALESCE(NULLIF(currency, ''), 'UZS'),
                branch_code
            ORDER BY snapshot_date, account_code
        """)
        
        rows_inserted = cursor.rowcount
        conn.commit()
        
        # Get summary
        cursor.execute("SELECT COUNT(*) FROM dbo.balance_snapshot_26")
        total = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT MIN(snapshot_date), MAX(snapshot_date), COUNT(DISTINCT account_code)
            FROM dbo.balance_snapshot_26
        """)
        min_date, max_date, account_count = cursor.fetchone()
        
        print(f"  [OK] Transformed {rows_inserted} rows")
        print(f"  [INFO] Date range: {min_date} to {max_date}")
        print(f"  [INFO] Unique accounts: {account_count}")
        print(f"  [INFO] Total records: {total}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"  [ERROR] Transformation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_fpna_connection():
    """Create DWH connection in FPNA database"""
    print("\n" + "=" * 60)
    print("Step 7: Creating DWH Connection in FPNA")
    print("=" * 60)
    
    try:
        # Connect to FPNA database
        fpna_conn_str = (
            f"DRIVER={{{DWH_CONFIG['driver']}}};"
            f"SERVER={DWH_CONFIG['server']};"
            f"DATABASE=FPNA_APP;"
            f"Trusted_Connection=yes;"
        )
        conn = pyodbc.connect(fpna_conn_str, autocommit=True)
        cursor = conn.cursor()
        
        # Check if connection already exists
        cursor.execute("SELECT id FROM dwh_connections WHERE name = 'DWH_Main'")
        existing = cursor.fetchone()
        
        if existing:
            print(f"  [INFO] DWH connection already exists (ID: {existing[0]})")
            cursor.execute("""
                UPDATE dwh_connections 
                SET host = ?, port = ?, database_name = ?, username = ?, 
                    password_encrypted = ?, is_active = 1, updated_at = GETDATE()
                WHERE name = 'DWH_Main'
            """, (
                DWH_CONFIG['server'], 1433, DWH_CONFIG['dwh_db'],
                DWH_CONFIG['dwh_login'], DWH_CONFIG['dwh_password']
            ))
            print("  [OK] Connection updated")
        else:
            cursor.execute("""
                INSERT INTO dwh_connections 
                (name, db_type, host, port, database_name, username, password_encrypted, 
                 schema_name, is_active, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'DWH_Main', 'sql_server', DWH_CONFIG['server'], 1433,
                DWH_CONFIG['dwh_db'], DWH_CONFIG['dwh_login'], DWH_CONFIG['dwh_password'],
                'dbo', 1, 'Main DWH connection for balance snapshots'
            ))
            print("  [OK] DWH connection created in FPNA")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"  [ERROR] Failed to create FPNA connection: {e}")
        return False


def verify_setup():
    """Verify the complete setup"""
    print("\n" + "=" * 60)
    print("Step 8: Verifying Setup")
    print("=" * 60)
    
    try:
        # Test DWH connection with new user
        dwh_conn_str = (
            f"DRIVER={{{DWH_CONFIG['driver']}}};"
            f"SERVER={DWH_CONFIG['server']};"
            f"DATABASE={DWH_CONFIG['dwh_db']};"
            f"UID={DWH_CONFIG['dwh_login']};"
            f"PWD={DWH_CONFIG['dwh_password']};"
        )
        conn = pyodbc.connect(dwh_conn_str)
        cursor = conn.cursor()
        
        print("  [OK] DWH login authentication successful")
        
        # Check tables
        cursor.execute("SELECT COUNT(*) FROM dbo.balans_ato")
        raw_count = cursor.fetchone()[0]
        print(f"  [INFO] balans_ato: {raw_count} rows")
        
        cursor.execute("SELECT COUNT(*) FROM dbo.balance_snapshot_26")
        clean_count = cursor.fetchone()[0]
        print(f"  [INFO] balance_snapshot_26: {clean_count} rows")
        
        if clean_count > 0:
            cursor.execute("""
                SELECT TOP 5 snapshot_date, account_code, currency, balance, balance_uzs
                FROM dbo.balance_snapshot_26
                ORDER BY snapshot_date DESC, account_code
            """)
            print("\n  [INFO] Sample data from balance_snapshot_26:")
            for row in cursor.fetchall():
                print(f"    {row}")
        
        conn.close()
        
        print("\n" + "=" * 60)
        print("SETUP COMPLETE!")
        print("=" * 60)
        print(f"""
DWH Database: dwh
DWH Login: {DWH_CONFIG['dwh_login']}
DWH Password: {DWH_CONFIG['dwh_password']}

Tables Created:
  - dbo.balans_ato (raw import table)
  - dbo.balance_snapshot_26 (clean integration table)

Next Steps:
  1. Go to FPNA Frontend -> Data Integration -> DWH Integration
  2. Select 'DWH_Main' connection
  3. Select 'balance_snapshot_26' table
  4. Run ingestion to import data to FPNA
  5. Generate baselines from imported snapshots
        """)
        return True
        
    except Exception as e:
        print(f"  [ERROR] Verification failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Setup DWH Database for FPNA')
    parser.add_argument('--csv-path', type=str, help='Path to balance snapshot CSV file')
    parser.add_argument('--skip-import', action='store_true', help='Skip CSV import step')
    parser.add_argument('--only-structure', action='store_true', help='Only create database structure')
    
    args = parser.parse_args()
    
    print("\n" + "=" * 60)
    print("   DWH DATABASE SETUP FOR FPNA PLATFORM")
    print("=" * 60)
    
    # Step 1: Create database
    if not create_dwh_database():
        return
    
    # Step 2: Create login and user
    if not create_dwh_login():
        return
    
    # Step 3: Create raw table
    if not create_raw_table():
        return
    
    # Step 4: Create clean integration table
    if not create_clean_integration_table():
        return
    
    if args.only_structure:
        print("\n[INFO] Structure created. Use --csv-path to import data.")
        return
    
    # Step 5: Import CSV if provided
    if args.csv_path and not args.skip_import:
        if not import_csv_to_raw(args.csv_path):
            print("\n[WARNING] CSV import failed, but database structure is ready")
    elif not args.skip_import:
        print("\n[INFO] No CSV path provided. Use --csv-path to import data.")
        print("       Example: python setup_dwh.py --csv-path 'C:\\path\\to\\balance.csv'")
    
    # Step 6: Transform to clean table
    transform_to_clean_table()
    
    # Step 7: Create FPNA connection
    create_fpna_connection()
    
    # Step 8: Verify
    verify_setup()


if __name__ == "__main__":
    main()
