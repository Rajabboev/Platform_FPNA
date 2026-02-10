"""Fix budgets.status column - expand to fit PENDING_L1, PENDING_L2, etc. (9+ chars)"""
import sys
import os

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app.database import engine
from sqlalchemy import text

def run():
    with engine.begin() as conn:
        # Drop default constraint if exists (SQL Server)
        try:
            result = conn.execute(text("""
                SELECT name FROM sys.default_constraints
                WHERE parent_object_id = OBJECT_ID('budgets')
                AND parent_column_id = (SELECT column_id FROM sys.columns WHERE object_id = OBJECT_ID('budgets') AND name = 'status')
            """))
            row = result.fetchone()
            if row:
                constraint_name = row[0]
                conn.execute(text(f"ALTER TABLE budgets DROP CONSTRAINT [{constraint_name}]"))
                print(f"Dropped default constraint: {constraint_name}")
        except Exception as e:
            print(f"Note (constraint): {e}")

        # Expand column (NVARCHAR for Unicode, 20 chars for PENDING_L1..PENDING_L4)
        print("Expanding budgets.status column to NVARCHAR(20)...")
        conn.execute(text("ALTER TABLE budgets ALTER COLUMN status NVARCHAR(20) NOT NULL"))
        print("Done.")

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
