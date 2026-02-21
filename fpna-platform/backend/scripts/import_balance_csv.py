"""
Import Balance Snapshot CSV to DWH
Specific for the Uzbek banking balance format

CSV Columns:
- KODBALANS: Account code (5 digits)
- KODVALUTA: Currency code (0=UZS, 840=USD, 978=EUR, etc.)
- OSTATALL: Outgoing balance in sum equivalent
- OSTATALLVAL: Outgoing balance in currency
- CURDATE: Operation date
- OTDELENIE: Branch code
"""

import pyodbc
import pandas as pd
from datetime import datetime
import sys

# Currency code mapping (ISO numeric to ISO alpha)
CURRENCY_MAP = {
    0: 'UZS',
    860: 'UZS',
    840: 'USD',
    978: 'EUR',
    643: 'RUB',
    756: 'CHF',
    826: 'GBP',
    392: 'JPY',
    156: 'CNY',
    398: 'KZT',
}

# FX Rates (approximate - should be updated with actual rates)
FX_RATES = {
    'UZS': 1.0,
    'USD': 12500.0,
    'EUR': 13500.0,
    'RUB': 140.0,
    'CHF': 14000.0,
    'GBP': 15800.0,
    'JPY': 83.0,
    'CNY': 1720.0,
    'KZT': 28.0,
}

DWH_CONFIG = {
    "server": "localhost",
    "database": "dwh",
    "driver": "ODBC Driver 17 for SQL Server",
}


def get_connection():
    """Get DWH connection using Windows Auth"""
    conn_str = (
        f"DRIVER={{{DWH_CONFIG['driver']}}};"
        f"SERVER={DWH_CONFIG['server']};"
        f"DATABASE={DWH_CONFIG['database']};"
        f"Trusted_Connection=yes;"
    )
    return pyodbc.connect(conn_str, autocommit=False)


def import_csv(csv_path: str):
    """Import balance snapshot CSV to DWH"""
    print("=" * 60)
    print("IMPORTING BALANCE SNAPSHOT CSV TO DWH")
    print("=" * 60)
    print(f"Source: {csv_path}")
    
    # Read CSV
    print("\n[1] Reading CSV file...")
    df = pd.read_csv(csv_path, encoding='utf-8', low_memory=False)
    print(f"    Total rows: {len(df)}")
    print(f"    Columns: {list(df.columns)}")
    
    # Connect to DWH
    print("\n[2] Connecting to DWH...")
    conn = get_connection()
    cursor = conn.cursor()
    print("    Connected successfully")
    
    # Clear existing data in raw table
    print("\n[3] Clearing existing data in balans_ato...")
    cursor.execute("TRUNCATE TABLE dbo.balans_ato")
    conn.commit()
    print("    Table cleared")
    
    # Import to raw table
    print("\n[4] Importing to balans_ato...")
    imported = 0
    errors = 0
    
    for idx, row in df.iterrows():
        try:
            # Parse date
            curdate = row.get('CURDATE')
            if pd.notna(curdate):
                try:
                    report_date = datetime.strptime(str(curdate), '%m/%d/%Y').date()
                except:
                    try:
                        report_date = datetime.strptime(str(curdate), '%Y-%m-%d').date()
                    except:
                        report_date = None
            else:
                report_date = None
            
            # Get values
            account_code = str(int(row.get('KODBALANS', 0))).zfill(5)
            currency_code = int(row.get('KODVALUTA', 0))
            currency = CURRENCY_MAP.get(currency_code, 'UZS')
            
            # Balance values
            ostatall = float(row.get('OSTATALL', 0) or 0)  # Sum equivalent
            ostatallval = float(row.get('OSTATALLVAL', 0) or 0)  # Currency amount
            
            branch_code = str(row.get('OTDELENIE', ''))
            
            cursor.execute("""
                INSERT INTO dbo.balans_ato 
                (report_date, account_code, account_name, currency, 
                 debit_balance, credit_balance, net_balance, branch_code, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report_date,
                account_code,
                f"Account {account_code}",  # Will be enriched later from COA
                currency,
                0,  # debit
                0,  # credit
                ostatall if currency == 'UZS' else ostatallval,  # net balance
                branch_code,
                str({
                    'OSTATALL': ostatall,
                    'OSTATALLVAL': ostatallval,
                    'KODVALUTA': currency_code
                })
            ))
            imported += 1
            
            if imported % 10000 == 0:
                conn.commit()
                print(f"    Progress: {imported} rows imported...")
                
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"    Error at row {idx}: {e}")
    
    conn.commit()
    print(f"    Imported: {imported} rows")
    print(f"    Errors: {errors} rows")
    
    # Transform to clean table
    print("\n[5] Transforming to balance_snapshot_26...")
    cursor.execute("TRUNCATE TABLE dbo.balance_snapshot_26")
    
    # Aggregate across all branches for each date/account/currency combination
    cursor.execute("""
        INSERT INTO dbo.balance_snapshot_26 
        (snapshot_date, account_code, account_name, currency, balance, balance_uzs, fx_rate, branch_code)
        SELECT 
            report_date as snapshot_date,
            account_code,
            MAX(account_name) as account_name,
            currency,
            SUM(net_balance) as balance,
            SUM(CASE 
                WHEN currency = 'UZS' THEN net_balance
                WHEN currency = 'USD' THEN net_balance * 12500
                WHEN currency = 'EUR' THEN net_balance * 13500
                WHEN currency = 'RUB' THEN net_balance * 140
                WHEN currency = 'CHF' THEN net_balance * 14000
                WHEN currency = 'GBP' THEN net_balance * 15800
                WHEN currency = 'CNY' THEN net_balance * 1720
                WHEN currency = 'KZT' THEN net_balance * 28
                ELSE net_balance 
            END) as balance_uzs,
            CASE 
                WHEN currency = 'USD' THEN 12500
                WHEN currency = 'EUR' THEN 13500
                WHEN currency = 'RUB' THEN 140
                WHEN currency = 'CHF' THEN 14000
                WHEN currency = 'GBP' THEN 15800
                WHEN currency = 'CNY' THEN 1720
                WHEN currency = 'KZT' THEN 28
                ELSE 1.0 
            END as fx_rate,
            'ALL' as branch_code  -- Aggregate all branches
        FROM dbo.balans_ato
        WHERE report_date IS NOT NULL 
          AND account_code IS NOT NULL 
          AND account_code != ''
          AND account_code != '00000'
        GROUP BY 
            report_date,
            account_code,
            currency
        ORDER BY report_date, account_code
    """)
    
    rows_transformed = cursor.rowcount
    conn.commit()
    print(f"    Transformed: {rows_transformed} rows")
    
    # Get summary
    print("\n[6] Summary:")
    cursor.execute("""
        SELECT 
            MIN(snapshot_date) as min_date,
            MAX(snapshot_date) as max_date,
            COUNT(DISTINCT snapshot_date) as date_count,
            COUNT(DISTINCT account_code) as account_count,
            COUNT(*) as total_rows
        FROM dbo.balance_snapshot_26
    """)
    row = cursor.fetchone()
    print(f"    Date range: {row[0]} to {row[1]}")
    print(f"    Unique dates: {row[2]}")
    print(f"    Unique accounts: {row[3]}")
    print(f"    Total records: {row[4]}")
    
    # Sample data
    print("\n[7] Sample data from balance_snapshot_26:")
    cursor.execute("""
        SELECT TOP 10 snapshot_date, account_code, currency, 
               FORMAT(balance, 'N2') as balance, 
               FORMAT(balance_uzs, 'N2') as balance_uzs
        FROM dbo.balance_snapshot_26
        ORDER BY snapshot_date DESC, balance_uzs DESC
    """)
    for r in cursor.fetchall():
        print(f"    {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]}")
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("IMPORT COMPLETE!")
    print("=" * 60)


def create_fpna_connection():
    """Create DWH connection in FPNA database"""
    print("\n[8] Creating DWH connection in FPNA...")
    
    fpna_conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER=localhost;"
        f"DATABASE=FPNA_APP;"
        f"Trusted_Connection=yes;"
    )
    conn = pyodbc.connect(fpna_conn_str, autocommit=True)
    cursor = conn.cursor()
    
    # Check if connection exists
    cursor.execute("SELECT id FROM dwh_connections WHERE name = 'DWH_Main'")
    existing = cursor.fetchone()
    
    if existing:
        print(f"    DWH connection already exists (ID: {existing[0]})")
        cursor.execute("""
            UPDATE dwh_connections 
            SET host = 'localhost', port = 1433, database_name = 'dwh', 
                username = 'dwh_user', password_encrypted = 'DwhUser@2024!', 
                is_active = 1, updated_at = GETDATE()
            WHERE name = 'DWH_Main'
        """)
        print("    Connection updated")
    else:
        cursor.execute("""
            INSERT INTO dwh_connections 
            (name, db_type, host, port, database_name, username, password_encrypted, 
             schema_name, is_active, description)
            VALUES ('DWH_Main', 'sql_server', 'localhost', 1433, 'dwh', 'dwh_user', 
                    'DwhUser@2024!', 'dbo', 1, 'Main DWH connection for balance snapshots')
        """)
        cursor.execute("SELECT SCOPE_IDENTITY()")
        new_id = cursor.fetchone()[0]
        print(f"    DWH connection created (ID: {new_id})")
    
    conn.close()


if __name__ == "__main__":
    csv_path = r"C:\Users\admin\Desktop\baseline_snap.csv"
    
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    
    import_csv(csv_path)
    create_fpna_connection()
    
    print("""
Next Steps:
-----------
1. Go to FPNA Frontend -> Data Integration -> DWH Integration
2. Select 'DWH_Main' connection  
3. Select 'balance_snapshot_26' table
4. Configure column mapping (should auto-detect)
5. Run ingestion to import data to FPNA
6. Generate baselines from imported snapshots
""")
