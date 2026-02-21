"""Create DWH connection in FPNA database"""
import pyodbc

conn = pyodbc.connect(
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=localhost;'
    'DATABASE=fpna_db;'
    'Trusted_Connection=yes;',
    autocommit=True
)
cursor = conn.cursor()

# Check if connection exists
cursor.execute("SELECT id FROM dwh_connections WHERE name = 'DWH_Main'")
existing = cursor.fetchone()

if existing:
    print(f'DWH connection already exists (ID: {existing[0]})')
    cursor.execute("""
        UPDATE dwh_connections 
        SET host = 'localhost', port = 1433, database_name = 'dwh', 
            username = 'dwh_user', password_encrypted = 'DwhUser@2024!', 
            is_active = 1, updated_at = GETDATE()
        WHERE name = 'DWH_Main'
    """)
    print('Connection updated')
else:
    cursor.execute("""
        INSERT INTO dwh_connections 
        (name, db_type, host, port, database_name, username, password_encrypted, 
         schema_name, is_active, description)
        VALUES ('DWH_Main', 'sql_server', 'localhost', 1433, 'dwh', 'dwh_user', 
                'DwhUser@2024!', 'dbo', 1, 'Main DWH connection for balance snapshots')
    """)
    cursor.execute('SELECT SCOPE_IDENTITY()')
    new_id = cursor.fetchone()[0]
    print(f'DWH connection created (ID: {new_id})')

conn.close()
print('Done!')
