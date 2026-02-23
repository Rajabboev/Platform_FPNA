"""
Database Cleanup Script for FP&A Engine Redesign

Truncates old tables to prepare for the new COA hierarchy-based budgeting system.
Run this script before starting the new workflow.
"""

import logging
from sqlalchemy import text
from app.database import SessionLocal, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TABLES_TO_TRUNCATE = [
    "budget_baselines",
    "budget_planned", 
    "baseline_data",
    "template_assignments",
    "template_line_items",
    "driver_values",
    "driver_calculation_logs",
    "budget_approvals",
    "budget_line_item_currencies",
    "budget_line_items",
]

TABLES_TO_CHECK = [
    "coa_dimension",
    "budgeting_groups", 
    "bs_classes",
]


def truncate_tables(dry_run: bool = True):
    """
    Truncate old tables to prepare for new FP&A engine.
    
    Args:
        dry_run: If True, only show what would be done without executing
    """
    db = SessionLocal()
    
    try:
        logger.info("=" * 60)
        logger.info("FP&A Engine Cleanup Script")
        logger.info("=" * 60)
        
        if dry_run:
            logger.info("DRY RUN MODE - No changes will be made")
        
        # Check required tables exist
        logger.info("\nChecking required tables...")
        with engine.connect() as conn:
            for table in TABLES_TO_CHECK:
                result = conn.execute(text(f"""
                    SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
                    WHERE TABLE_NAME = '{table}'
                """))
                exists = result.scalar() > 0
                if exists:
                    count_result = conn.execute(text(f"SELECT COUNT(*) FROM [{table}]"))
                    count = count_result.scalar()
                    logger.info(f"  [OK] {table}: {count} rows")
                else:
                    logger.warning(f"  [MISSING] {table}")
        
        # Truncate old tables
        logger.info("\nTruncating old tables...")
        
        with engine.connect() as conn:
            for table in TABLES_TO_TRUNCATE:
                # Check if table exists
                result = conn.execute(text(f"""
                    SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
                    WHERE TABLE_NAME = '{table}'
                """))
                exists = result.scalar() > 0
                
                if not exists:
                    logger.info(f"  [SKIP] {table} - does not exist")
                    continue
                
                # Get row count
                count_result = conn.execute(text(f"SELECT COUNT(*) FROM [{table}]"))
                count = count_result.scalar()
                
                if dry_run:
                    logger.info(f"  [DRY] Would truncate {table} ({count} rows)")
                else:
                    try:
                        # Use DELETE instead of TRUNCATE to handle FK constraints
                        conn.execute(text(f"DELETE FROM [{table}]"))
                        conn.commit()
                        logger.info(f"  [DONE] Truncated {table} ({count} rows deleted)")
                    except Exception as e:
                        logger.error(f"  [ERROR] Failed to truncate {table}: {e}")
                        conn.rollback()
        
        logger.info("\n" + "=" * 60)
        if dry_run:
            logger.info("DRY RUN COMPLETE - Run with dry_run=False to execute")
        else:
            logger.info("CLEANUP COMPLETE")
        logger.info("=" * 60)
        
    finally:
        db.close()


def get_table_stats():
    """Get current row counts for all relevant tables."""
    all_tables = TABLES_TO_TRUNCATE + TABLES_TO_CHECK + [
        "departments",
        "department_assignments",
        "budget_plans",
        "budget_plan_groups",
        "budget_plan_details",
    ]
    
    stats = {}
    with engine.connect() as conn:
        for table in all_tables:
            result = conn.execute(text(f"""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = '{table}'
            """))
            exists = result.scalar() > 0
            
            if exists:
                count_result = conn.execute(text(f"SELECT COUNT(*) FROM [{table}]"))
                stats[table] = count_result.scalar()
            else:
                stats[table] = None
    
    return stats


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--execute":
        truncate_tables(dry_run=False)
    else:
        truncate_tables(dry_run=True)
        print("\nTo execute the cleanup, run: python -m app.scripts.cleanup_tables --execute")
