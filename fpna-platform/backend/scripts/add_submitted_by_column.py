"""Add submitted_by_user_id column to budgets table if missing"""
import sys
import os

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app.database import engine
from sqlalchemy import text

def run():
    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'budgets' AND COLUMN_NAME = 'submitted_by_user_id'
        """))
        if result.scalar() > 0:
            print("Column submitted_by_user_id already exists. Skipping.")
            return
        print("Adding submitted_by_user_id to budgets table...")
        conn.execute(text("ALTER TABLE budgets ADD submitted_by_user_id INT NULL"))
        print("Done.")

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
