"""
Migration script to add new columns to existing budget tables
Run this script to update the database schema for Phase 5 enhancements
"""

from sqlalchemy import text
from app.database import engine

def migrate():
    """Add missing columns to budgets and budget_line_items tables"""
    
    with engine.connect() as conn:
        # Check and add columns to budgets table
        budgets_columns = [
            ("business_unit_id", "INT NULL"),
            ("total_amount_uzs", "DECIMAL(20, 2) DEFAULT 0"),
            ("template_id", "INT NULL"),
            ("template_assignment_id", "INT NULL"),
            ("baseline_version", "INT NULL"),
            ("budget_type", "VARCHAR(20) DEFAULT 'BASELINE'"),
            ("is_baseline", "BIT DEFAULT 0"),
            ("parent_budget_id", "INT NULL"),
            ("version", "INT DEFAULT 1"),
            ("is_current_version", "BIT DEFAULT 1"),
        ]
        
        print("Migrating budgets table...")
        for col_name, col_def in budgets_columns:
            try:
                # Check if column exists
                result = conn.execute(text(f"""
                    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_NAME = 'budgets' AND COLUMN_NAME = '{col_name}'
                """))
                exists = result.scalar() > 0
                
                if not exists:
                    conn.execute(text(f"ALTER TABLE budgets ADD {col_name} {col_def}"))
                    print(f"  Added column: {col_name}")
                else:
                    print(f"  Column already exists: {col_name}")
            except Exception as e:
                print(f"  Error adding {col_name}: {e}")
        
        # Check and add columns to budget_line_items table
        line_items_columns = [
            ("amount_uzs", "DECIMAL(20, 2) NULL"),
            ("fx_rate_used", "DECIMAL(18, 6) NULL"),
            ("baseline_amount", "DECIMAL(18, 2) NULL"),
            ("baseline_amount_uzs", "DECIMAL(20, 2) NULL"),
            ("variance", "DECIMAL(18, 2) NULL"),
            ("variance_percent", "DECIMAL(8, 4) NULL"),
            ("is_driver_calculated", "BIT DEFAULT 0"),
            ("driver_code", "VARCHAR(50) NULL"),
        ]
        
        print("\nMigrating budget_line_items table...")
        for col_name, col_def in line_items_columns:
            try:
                result = conn.execute(text(f"""
                    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_NAME = 'budget_line_items' AND COLUMN_NAME = '{col_name}'
                """))
                exists = result.scalar() > 0
                
                if not exists:
                    conn.execute(text(f"ALTER TABLE budget_line_items ADD {col_name} {col_def}"))
                    print(f"  Added column: {col_name}")
                else:
                    print(f"  Column already exists: {col_name}")
            except Exception as e:
                print(f"  Error adding {col_name}: {e}")
        
        # Create budget_line_item_currencies table if not exists
        print("\nChecking budget_line_item_currencies table...")
        try:
            result = conn.execute(text("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = 'budget_line_item_currencies'
            """))
            exists = result.scalar() > 0
            
            if not exists:
                conn.execute(text("""
                    CREATE TABLE budget_line_item_currencies (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        budget_id INT NOT NULL,
                        line_item_id INT NOT NULL,
                        currency VARCHAR(3) NOT NULL,
                        amount_original DECIMAL(20, 2) NOT NULL,
                        amount_uzs DECIMAL(20, 2) NOT NULL,
                        fx_rate_used DECIMAL(18, 6) NOT NULL,
                        fx_rate_date DATETIME2 NULL,
                        fx_rate_source VARCHAR(50) NULL,
                        is_budget_rate BIT DEFAULT 0,
                        created_at DATETIME2 DEFAULT GETUTCDATE(),
                        updated_at DATETIME2 NULL,
                        CONSTRAINT FK_currency_budget FOREIGN KEY (budget_id) REFERENCES budgets(id) ON DELETE CASCADE,
                        CONSTRAINT FK_currency_line_item FOREIGN KEY (line_item_id) REFERENCES budget_line_items(id) ON DELETE NO ACTION
                    )
                """))
                conn.execute(text("CREATE INDEX ix_currency_line_item ON budget_line_item_currencies(line_item_id, currency)"))
                print("  Created budget_line_item_currencies table")
            else:
                print("  Table already exists: budget_line_item_currencies")
        except Exception as e:
            print(f"  Error creating budget_line_item_currencies: {e}")
        
        # Add indexes if they don't exist
        print("\nAdding indexes...")
        indexes = [
            ("ix_budget_year_bu", "budgets", "fiscal_year, business_unit_id"),
            ("ix_line_item_account_month", "budget_line_items", "budget_id, account_code, month"),
        ]
        
        for idx_name, table_name, columns in indexes:
            try:
                result = conn.execute(text(f"""
                    SELECT COUNT(*) FROM sys.indexes 
                    WHERE name = '{idx_name}' AND object_id = OBJECT_ID('{table_name}')
                """))
                exists = result.scalar() > 0
                
                if not exists:
                    conn.execute(text(f"CREATE INDEX {idx_name} ON {table_name}({columns})"))
                    print(f"  Created index: {idx_name}")
                else:
                    print(f"  Index already exists: {idx_name}")
            except Exception as e:
                print(f"  Error creating index {idx_name}: {e}")
        
        conn.commit()
        print("\nMigration completed!")


if __name__ == "__main__":
    migrate()
