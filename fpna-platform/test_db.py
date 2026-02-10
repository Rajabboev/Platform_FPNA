import pyodbc
import urllib.parse
from app.config import settings

try:
    params = urllib.parse.quote_plus(
        f"DRIVER={{{settings.DATABASE_DRIVER}}};"
        f"SERVER={settings.DATABASE_SERVER};"
        f"DATABASE={settings.DATABASE_NAME};"
        f"UID={settings.DATABASE_USER};"
        f"PWD={settings.DATABASE_PASSWORD};"
    )
    
    connection_string = f"mssql+pyodbc:///?odbc_connect={params}"
    print(f"Connection string: {connection_string}")
    
    # Try to connect
    conn = pyodbc.connect(
        f"DRIVER={{{settings.DATABASE_DRIVER}}};"
        f"SERVER={settings.DATABASE_SERVER};"
        f"DATABASE={settings.DATABASE_NAME};"
        f"UID={settings.DATABASE_USER};"
        f"PWD={settings.DATABASE_PASSWORD};"
    )
    
    print(" Database connection successful!")
    conn.close()
    
except Exception as e:
    print(f" Connection failed: {e}")
