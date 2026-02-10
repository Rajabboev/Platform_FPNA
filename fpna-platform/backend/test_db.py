"""
Database Connection Test Script
Run this to verify your SQL Server connection
"""

import pyodbc
import sys


def test_connection():
    """Test SQL Server connection with different configurations"""

    print("=" * 60)
    print("SQL SERVER CONNECTION TEST")
    print("=" * 60)

    # Test configurations to try
    test_configs = [
        {
            "name": "DESKTOP-L3U2E1I",
            "server": "localhost",
            "database": "fpna_db",
            "username": "fpna_user",
            "password": "fpna_admin"
        }

    ]

    drivers = []
    try:
        drivers = pyodbc.drivers()
        print(f"\n📋 Available ODBC Drivers:")
        for driver in drivers:
            print(f"   - {driver}")
    except Exception as e:
        print(f"❌ Error getting drivers: {e}")

    if not drivers:
        print("\n❌ No ODBC drivers found!")
        print("   Install ODBC Driver 17 for SQL Server")
        return

    # Find SQL Server driver
    sql_driver = None
    for driver in drivers:
        if 'SQL Server' in driver:
            sql_driver = driver
            break

    if not sql_driver:
        print("\n❌ SQL Server ODBC driver not found!")
        return

    print(f"\n✅ Using driver: {sql_driver}")

    # Test each configuration
    print("\n" + "=" * 60)
    print("TESTING CONNECTIONS")
    print("=" * 60)

    for config in test_configs:
        print(f"\n🔍 Testing: {config['name']}")
        print(f"   Server: {config['server']}")
        print(f"   Database: {config['database']}")

        try:
            if config['username']:
                # SQL Server Authentication
                connection_string = (
                    f"DRIVER={{{sql_driver}}};"
                    f"SERVER={config['server']};"
                    f"DATABASE={config['database']};"
                    f"UID={config['username']};"
                    f"PWD={config['password']};"
                )
            else:
                # Windows Authentication
                connection_string = (
                    f"DRIVER={{{sql_driver}}};"
                    f"SERVER={config['server']};"
                    f"DATABASE={config['database']};"
                    f"Trusted_Connection=yes;"
                )

            conn = pyodbc.connect(connection_string, timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT @@VERSION")
            version = cursor.fetchone()[0]

            print(f"   ✅ SUCCESS!")
            print(f"   Version: {version[:60]}...")

            cursor.close()
            conn.close()

            print(f"\n🎉 WORKING CONNECTION FOUND!")
            print(f"   Update your .env file with:")
            print(f"   DATABASE_SERVER={config['server']}")
            print(f"   DATABASE_NAME={config['database']}")
            if config['username']:
                print(f"   DATABASE_USER={config['username']}")
                print(f"   DATABASE_PASSWORD={config['password']}")
            else:
                print(f"   Use Windows Authentication")

            return True

        except pyodbc.Error as e:
            print(f"   ❌ Failed: {e}")
            continue

    print("\n" + "=" * 60)
    print("❌ ALL CONNECTION ATTEMPTS FAILED")
    print("=" * 60)
    print("\n📝 Troubleshooting Steps:")
    print("1. Check if SQL Server is running:")
    print("   Get-Service -Name 'MSSQL*'")
    print("\n2. Verify SQL Server instance name")
    print("\n3. Create database and user:")
    print("   Run the SQL script in SSMS or sqlcmd")
    print("\n4. Enable SQL Server Authentication:")
    print("   SSMS → Right-click server → Properties → Security")
    print("   → Select 'SQL Server and Windows Authentication mode'")

    return False


def test_master_connection():
    """Test connection to master database (doesn't require fpna_db)"""
    print("\n" + "=" * 60)
    print("TESTING CONNECTION TO MASTER DATABASE")
    print("=" * 60)

    try:
        drivers = pyodbc.drivers()
        sql_driver = None
        for driver in drivers:
            if 'SQL Server' in driver:
                sql_driver = driver
                break

        if not sql_driver:
            print("❌ No SQL Server driver found")
            return False

        # Try connecting to master database
        servers = ["localhost", "localhost\\SQLEXPRESS", ".\\SQLEXPRESS"]

        for server in servers:
            try:
                print(f"\n🔍 Testing {server} with Windows Authentication...")
                connection_string = (
                    f"DRIVER={{{sql_driver}}};"
                    f"SERVER={server};"
                    f"DATABASE=master;"
                    f"Trusted_Connection=yes;"
                )

                conn = pyodbc.connect(connection_string, timeout=5)
                cursor = conn.cursor()

                # Check if fpna_db exists
                cursor.execute("SELECT name FROM sys.databases WHERE name = 'fpna_db'")
                db_exists = cursor.fetchone()

                if db_exists:
                    print(f"   ✅ fpna_db database EXISTS")
                else:
                    print(f"   ⚠️  fpna_db database DOES NOT EXIST")
                    print(f"   Run SQL script to create it")

                # Check if fpna_user login exists
                cursor.execute("SELECT name FROM sys.server_principals WHERE name = 'fpna_user'")
                login_exists = cursor.fetchone()

                if login_exists:
                    print(f"   ✅ fpna_user login EXISTS")
                else:
                    print(f"   ⚠️  fpna_user login DOES NOT EXIST")
                    print(f"   Run SQL script to create it")

                cursor.close()
                conn.close()

                print(f"\n✅ Connected to SQL Server on {server}")
                return True

            except pyodbc.Error as e:
                print(f"   ❌ Failed: {str(e)[:100]}")
                continue

        return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    print("\n🚀 Starting SQL Server Connection Tests...\n")

    # First test master database connection
    master_connected = test_master_connection()

    # Then test fpna_db connection
    if not test_connection():
        print("\n💡 TIP: If you can connect to master but not fpna_db,")
        print("   you need to create the database and user.")
        print("   Use SQL Server Management Studio or run:")
        print("   sqlcmd -S localhost -E -i create_database.sql")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60 + "\n")