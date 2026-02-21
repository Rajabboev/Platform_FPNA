"""
Setup DWH with exact source table structure
Creates table matching the original DWH schema and loads CSV as-is
"""

import pyodbc
import pandas as pd
from datetime import datetime

DWH_SERVER = "localhost"
DWH_DATABASE = "dwh"

def get_master_connection():
    """Connect to master database"""
    return pyodbc.connect(
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={DWH_SERVER};"
        f"DATABASE=master;"
        f"Trusted_Connection=yes;",
        autocommit=True
    )

def get_dwh_connection():
    """Connect to DWH database"""
    return pyodbc.connect(
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={DWH_SERVER};"
        f"DATABASE={DWH_DATABASE};"
        f"Trusted_Connection=yes;",
        autocommit=True
    )

def setup_database():
    """Create DWH database if not exists"""
    print("=" * 60)
    print("SETTING UP DWH DATABASE")
    print("=" * 60)
    
    conn = get_master_connection()
    cursor = conn.cursor()
    
    # Check if database exists
    cursor.execute("SELECT name FROM sys.databases WHERE name = 'dwh'")
    if not cursor.fetchone():
        print("[1] Creating database 'dwh'...")
        cursor.execute("CREATE DATABASE dwh")
        print("    Database created")
    else:
        print("[1] Database 'dwh' already exists")
    
    conn.close()

def create_balans_table():
    """Create balans_ato table with exact DWH schema"""
    print("\n[2] Creating balans_ato table with exact DWH schema...")
    
    conn = get_dwh_connection()
    cursor = conn.cursor()
    
    # Drop existing tables
    cursor.execute("IF OBJECT_ID('dbo.balans_ato', 'U') IS NOT NULL DROP TABLE dbo.balans_ato")
    cursor.execute("IF OBJECT_ID('dbo.balance_snapshot_26', 'U') IS NOT NULL DROP TABLE dbo.balance_snapshot_26")
    
    # Create table matching exact DWH schema from metadata
    # Using identity column as PK since original has composite natural key with potential nulls
    cursor.execute("""
        CREATE TABLE dbo.balans_ato (
            -- Surrogate key for local use
            id INT IDENTITY(1,1) PRIMARY KEY,
            
            -- Natural key columns (from DWH)
            KODBALANS CHAR(5) NOT NULL,               -- Account code
            CURDATE DATE NOT NULL,                    -- Operation date
            KODVALUTA INT NOT NULL DEFAULT 0,         -- Currency code (0=UZS, 840=USD, 978=EUR, etc.)
            OTDELENIE INT NOT NULL DEFAULT 0,         -- Branch code
            
            -- Outgoing balances
            OSTATALL NUMERIC(22,2) NULL,              -- Outgoing balance in sum equivalent
            OSTATALLVAL NUMERIC(22,2) NULL,           -- Outgoing balance in currency
            PRIZNALL CHAR(1) NULL,                    -- Sign of outgoing balance (0=has balance, 1=no balance)
            
            -- Resident balances in sum
            OSTATUZSREZ NUMERIC(22,2) NULL,           -- Outgoing balance in sum - residents
            PRIZNUZSREZ CHAR(1) NULL,                 -- Sign for resident sum accounts
            
            -- Non-resident balances in sum
            OSTATUZSNEREZ NUMERIC(22,2) NULL,         -- Outgoing balance in sum - non-residents
            PRIZNUZSNEREZ CHAR(1) NULL,               -- Sign for non-resident sum accounts
            
            -- Resident/Non-resident balances in currency
            OSTATVALREZ NUMERIC(22,2) NULL,           -- Outgoing balance in currency - residents
            OSTATVALNEREZ NUMERIC(22,2) NULL,         -- Outgoing balance in currency - non-residents
            
            -- Daily debit turnover
            OSTATALL_DT NUMERIC(22,2) NULL,           -- Debit turnover per day
            OSTATALLVAL_DT NUMERIC(22,2) NULL,        -- Debit turnover per day in currency
            OSTATUZSREZ_DT NUMERIC(22,2) NULL,        -- Debit turnover in sum - residents
            OSTATUZSNEREZ_DT NUMERIC(22,2) NULL,      -- Debit turnover in sum - non-residents
            OSTATVALREZ_DT NUMERIC(22,2) NULL,        -- Debit turnover in currency - residents
            OSTATVALNEREZ_DT NUMERIC(22,2) NULL,      -- Debit turnover in currency - non-residents
            
            -- Daily credit turnover
            OSTATALL_CT NUMERIC(22,2) NULL,           -- Credit turnover per day
            OSTATALLVAL_CT NUMERIC(22,2) NULL,        -- Credit turnover per day in currency
            OSTATUZSREZ_CT NUMERIC(22,2) NULL,        -- Credit turnover in sum - residents
            OSTATUZSNEREZ_CT NUMERIC(22,2) NULL,      -- Credit turnover in sum - non-residents
            OSTATVALREZ_CT NUMERIC(22,2) NULL,        -- Credit turnover in currency - residents
            OSTATVALNEREZ_CT NUMERIC(22,2) NULL,      -- Credit turnover in currency - non-residents
            
            -- Incoming balances
            OSTATALL_IN NUMERIC(22,2) NULL,           -- Incoming balance in sum equivalent
            OSTATALLVAL_IN NUMERIC(22,2) NULL,        -- Incoming balance in currency
            PRIZNALL_IN CHAR(1) NULL,                 -- Sign of incoming balance (0=has balance, 1=no balance)
            OSTATUZSREZ_IN NUMERIC(22,2) NULL,        -- Incoming balance in sum - residents
            PRIZNUZSREZ_IN CHAR(1) NULL,              -- Sign for incoming resident balance
            OSTATUZSNEREZ_IN NUMERIC(22,2) NULL,      -- Incoming balance in sum - non-residents
            PRIZNUZSNEREZ_IN CHAR(1) NULL,            -- Sign for incoming non-resident balance
            OSTATVALREZ_IN NUMERIC(22,2) NULL,        -- Incoming balance in currency - residents
            OSTATVALNEREZ_IN NUMERIC(22,2) NULL,      -- Incoming balance in currency - non-residents
            
            -- Additional columns from CSV
            OBU CHAR(5) NULL,                         -- OBU flag
            start_dt DATE NULL,                       -- SCD start date
            end_dt DATE NULL                          -- SCD end date
        )
    """)
    
    # Create indexes for common queries
    cursor.execute("""
        CREATE INDEX IX_balans_ato_curdate ON dbo.balans_ato (CURDATE)
    """)
    cursor.execute("""
        CREATE INDEX IX_balans_ato_kodbalans ON dbo.balans_ato (KODBALANS)
    """)
    
    print("    Table created with exact DWH schema")
    conn.close()

def load_csv_data(csv_path: str):
    """Load CSV data into balans_ato table"""
    print(f"\n[3] Loading CSV data from: {csv_path}")
    
    # Read CSV
    df = pd.read_csv(csv_path, encoding='utf-8', low_memory=False)
    print(f"    Total rows in CSV: {len(df)}")
    print(f"    Columns: {list(df.columns)}")
    
    # Clean up unnamed columns
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    
    # Parse dates
    def parse_date(val):
        if pd.isna(val):
            return None
        try:
            return datetime.strptime(str(val), '%m/%d/%Y').date()
        except:
            try:
                return datetime.strptime(str(val), '%Y-%m-%d').date()
            except:
                return None
    
    df['CURDATE'] = df['CURDATE'].apply(parse_date)
    df['start_dt'] = df['start_dt'].apply(parse_date)
    df['end_dt'] = df['end_dt'].apply(parse_date)
    
    # Convert KODBALANS to 5-char string
    df['KODBALANS'] = df['KODBALANS'].apply(lambda x: str(int(x)).zfill(5) if pd.notna(x) else None)
    
    # Connect to DWH
    conn = get_dwh_connection()
    cursor = conn.cursor()
    
    # Clear existing data
    cursor.execute("TRUNCATE TABLE dbo.balans_ato")
    
    # Insert data in batches
    print("    Inserting data...")
    inserted = 0
    errors = 0
    batch_size = 1000
    
    columns = [
        'KODBALANS', 'CURDATE', 'KODVALUTA', 'OTDELENIE',
        'OSTATALL', 'OSTATALLVAL', 'PRIZNALL',
        'OSTATUZSREZ', 'PRIZNUZSREZ', 'OSTATUZSNEREZ', 'PRIZNUZSNEREZ',
        'OSTATVALREZ', 'OSTATVALNEREZ',
        'OSTATALL_DT', 'OSTATALLVAL_DT', 'OSTATUZSREZ_DT', 'OSTATUZSNEREZ_DT',
        'OSTATVALREZ_DT', 'OSTATVALNEREZ_DT',
        'OSTATALL_CT', 'OSTATALLVAL_CT', 'OSTATUZSREZ_CT', 'OSTATUZSNEREZ_CT',
        'OSTATVALREZ_CT', 'OSTATVALNEREZ_CT',
        'OSTATALL_IN', 'OSTATALLVAL_IN', 'PRIZNALL_IN',
        'OSTATUZSREZ_IN', 'PRIZNUZSREZ_IN', 'OSTATUZSNEREZ_IN', 'PRIZNUZSNEREZ_IN',
        'OSTATVALREZ_IN', 'OSTATVALNEREZ_IN',
        'OBU', 'start_dt', 'end_dt'
    ]
    
    placeholders = ', '.join(['?' for _ in columns])
    insert_sql = f"INSERT INTO dbo.balans_ato ({', '.join(columns)}) VALUES ({placeholders})"
    
    batch = []
    for idx, row in df.iterrows():
        try:
            values = []
            for col in columns:
                val = row.get(col)
                if pd.isna(val):
                    values.append(None)
                elif col in ['PRIZNALL', 'PRIZNUZSREZ', 'PRIZNUZSNEREZ', 'PRIZNALL_IN', 
                            'PRIZNUZSREZ_IN', 'PRIZNUZSNEREZ_IN', 'OBU']:
                    values.append(str(int(val)) if val else None)
                elif col in ['OTDELENIE', 'KODVALUTA']:
                    values.append(int(val) if pd.notna(val) else 0)
                else:
                    values.append(val)
            
            batch.append(tuple(values))
            
            if len(batch) >= batch_size:
                cursor.executemany(insert_sql, batch)
                conn.commit()
                inserted += len(batch)
                batch = []
                print(f"    Progress: {inserted} rows inserted...")
                
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"    Error at row {idx}: {e}")
    
    # Insert remaining batch
    if batch:
        cursor.executemany(insert_sql, batch)
        conn.commit()
        inserted += len(batch)
    
    print(f"    Inserted: {inserted} rows")
    print(f"    Errors: {errors} rows")
    
    conn.close()

def verify_data():
    """Verify loaded data"""
    print("\n[4] Verifying loaded data...")
    
    conn = get_dwh_connection()
    cursor = conn.cursor()
    
    # Summary statistics
    cursor.execute("""
        SELECT 
            COUNT(*) as total_rows,
            COUNT(DISTINCT KODBALANS) as unique_accounts,
            COUNT(DISTINCT CURDATE) as unique_dates,
            COUNT(DISTINCT KODVALUTA) as unique_currencies,
            COUNT(DISTINCT OTDELENIE) as unique_branches,
            MIN(CURDATE) as min_date,
            MAX(CURDATE) as max_date
        FROM dbo.balans_ato
    """)
    row = cursor.fetchone()
    
    print(f"""
    === DWH Data Summary ===
    Total Rows:       {row[0]:,}
    Unique Accounts:  {row[1]}
    Unique Dates:     {row[2]} (monthly snapshots)
    Unique Currencies: {row[3]}
    Unique Branches:  {row[4]}
    Date Range:       {row[5]} to {row[6]}
    """)
    
    # Sample data
    print("    Sample data (latest 5 records):")
    cursor.execute("""
        SELECT TOP 5 
            KODBALANS, CURDATE, KODVALUTA, OTDELENIE,
            FORMAT(OSTATALL, 'N2') as OSTATALL,
            FORMAT(OSTATALLVAL, 'N2') as OSTATALLVAL
        FROM dbo.balans_ato
        ORDER BY CURDATE DESC, OSTATALL DESC
    """)
    for r in cursor.fetchall():
        print(f"    {r[0]} | {r[1]} | Currency:{r[2]} | Branch:{r[3]} | {r[4]} | {r[5]}")
    
    # Account class distribution
    print("\n    Account class distribution (first digit):")
    cursor.execute("""
        SELECT 
            LEFT(KODBALANS, 1) as account_class,
            COUNT(DISTINCT KODBALANS) as account_count
        FROM dbo.balans_ato
        GROUP BY LEFT(KODBALANS, 1)
        ORDER BY account_class
    """)
    for r in cursor.fetchall():
        print(f"    Class {r[0]}xxxx: {r[1]} accounts")
    
    conn.close()

def main():
    csv_path = r"C:\Users\admin\Desktop\baseline_snap.csv"
    
    setup_database()
    create_balans_table()
    load_csv_data(csv_path)
    verify_data()
    
    print("\n" + "=" * 60)
    print("DWH SETUP COMPLETE!")
    print("=" * 60)
    print("""
Table 'balans_ato' created with exact DWH schema.

Key columns for FPNA integration:
- KODBALANS: Account code (maps to COA)
- CURDATE: Snapshot date (monthly)
- OSTATALL: Balance in UZS equivalent
- OSTATALLVAL: Balance in original currency
- KODVALUTA: Currency code (0=UZS, 840=USD, 978=EUR)
- OTDELENIE: Branch code

Next: Update DWH integration service to work with this schema.
""")

if __name__ == "__main__":
    main()
