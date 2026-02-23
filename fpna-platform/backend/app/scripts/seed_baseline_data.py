"""
Seed sample baseline data for testing FP&A Budget Planning

Creates sample historical balance data for COA accounts to enable
baseline calculation and budget planning workflow testing.
"""

import logging
import random
from decimal import Decimal
from datetime import datetime

from sqlalchemy import text
from app.database import SessionLocal

# Import all models to ensure relationships are resolved
from app.models.user import User  # noqa: F401
from app.models.budget_plan import BudgetPlan, BudgetPlanGroup, BudgetPlanDetail, BudgetPlanApproval  # noqa: F401
from app.models.department import Department, DepartmentAssignment  # noqa: F401
from app.models.coa_dimension import COADimension, BudgetingGroup
from app.models.baseline import BaselineData

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_baseline_data(dry_run: bool = True, years: list = None):
    """
    Seed sample baseline data for testing.
    
    Creates monthly balance data for each COA account for the specified years.
    """
    if years is None:
        years = [2023, 2024, 2025]
    
    db = SessionLocal()
    
    try:
        logger.info("=" * 60)
        logger.info("Seeding Sample Baseline Data")
        logger.info(f"Years: {years}")
        logger.info("=" * 60)
        
        if dry_run:
            logger.info("DRY RUN MODE - No changes will be made")
        
        # Get all active COA accounts
        coa_accounts = db.query(COADimension).filter(COADimension.is_active == True).all()
        logger.info(f"Found {len(coa_accounts)} active COA accounts")
        
        if not coa_accounts:
            logger.error("No COA accounts found. Please load COA dimension first.")
            return {"error": "No COA accounts"}
        
        # Clear existing baseline data for these years
        if not dry_run:
            deleted = db.query(BaselineData).filter(
                BaselineData.fiscal_year.in_(years)
            ).delete(synchronize_session=False)
            logger.info(f"Deleted {deleted} existing baseline records")
        
        # Generate sample data
        batch_id = f"SEED_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        total_records = 0
        
        # Base amounts by budgeting group (in millions UZS)
        group_base_amounts = {
            1: 500,    # Cash in hand
            2: 2000,   # Cash at CBRU
            3: 1500,   # Correspondent accounts
            4: 800,    # Placements with banks
            5: 300,    # Precious metals
            6: 1200,   # Fixed assets
            7: 400,    # Intangible assets
            8: 15000,  # Loans
            9: 2000,   # Provisions
            10: 500,   # Other assets
            11: 3000,  # Deposits
            12: 5000,  # Customer deposits
            13: 1000,  # Reserves
            14: 2500,  # Equity
            15: 800,   # Other liabilities
            # Add more as needed
        }
        
        for coa in coa_accounts:
            # Get base amount for this account's budgeting group
            group_id = coa.budgeting_groups if coa.budgeting_groups else 10
            base_amount = group_base_amounts.get(group_id, 100) * 1_000_000  # Convert to actual UZS
            
            # Add some randomness per account
            account_factor = random.uniform(0.1, 2.0)
            account_base = base_amount * account_factor
            
            for year in years:
                # Year-over-year growth factor
                year_factor = 1 + (year - min(years)) * 0.05  # 5% annual growth
                
                for month in range(1, 13):
                    # Seasonal variation
                    seasonal_factor = 1.0
                    if month in [1, 2]:  # Q1 lower
                        seasonal_factor = 0.9
                    elif month in [6, 7, 8]:  # Summer higher
                        seasonal_factor = 1.1
                    elif month in [11, 12]:  # Year-end higher
                        seasonal_factor = 1.15
                    
                    # Random monthly variation
                    random_factor = random.uniform(0.95, 1.05)
                    
                    # Calculate balance
                    balance = account_base * year_factor * seasonal_factor * random_factor
                    
                    # Round to reasonable precision
                    balance_uzs = Decimal(str(round(balance, 2)))
                    
                    if not dry_run:
                        baseline = BaselineData(
                            coa_code=coa.coa_code,
                            fiscal_year=year,
                            fiscal_month=month,
                            balance_uzs=balance_uzs,
                            balance_orig=balance_uzs,  # Same for UZS
                            currency='UZS',
                            import_batch_id=batch_id,
                        )
                        db.add(baseline)
                    
                    total_records += 1
            
            # Commit in batches
            if not dry_run and total_records % 5000 == 0:
                db.commit()
                logger.info(f"  Committed {total_records} records...")
        
        if not dry_run:
            db.commit()
        
        logger.info("\n" + "=" * 60)
        if dry_run:
            logger.info(f"DRY RUN: Would create {total_records} baseline records")
            logger.info("Run with dry_run=False to execute")
        else:
            logger.info(f"SEEDING COMPLETE: {total_records} records created")
            logger.info(f"Batch ID: {batch_id}")
        logger.info("=" * 60)
        
        return {
            "status": "success",
            "records": total_records,
            "batch_id": batch_id if not dry_run else None,
            "years": years,
        }
        
    finally:
        db.close()


def check_baseline_data():
    """Check baseline data statistics"""
    db = SessionLocal()
    
    try:
        print("\n" + "=" * 60)
        print("BASELINE DATA STATISTICS")
        print("=" * 60)
        
        # Count by year
        result = db.execute(text("""
            SELECT fiscal_year, COUNT(*) as record_count, 
                   SUM(balance_uzs) as total_balance
            FROM baseline_data
            GROUP BY fiscal_year
            ORDER BY fiscal_year
        """))
        
        print("\nBy Year:")
        for row in result:
            print(f"  {row.fiscal_year}: {row.record_count:,} records, Total: {row.total_balance:,.0f} UZS")
        
        # Count by month (latest year)
        result = db.execute(text("""
            SELECT TOP 12 fiscal_month, COUNT(*) as record_count
            FROM baseline_data
            WHERE fiscal_year = (SELECT MAX(fiscal_year) FROM baseline_data)
            GROUP BY fiscal_month
            ORDER BY fiscal_month
        """))
        
        print("\nBy Month (Latest Year):")
        for row in result:
            print(f"  Month {row.fiscal_month}: {row.record_count:,} records")
        
        print("\n" + "=" * 60)
        
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--execute":
            seed_baseline_data(dry_run=False)
        elif sys.argv[1] == "--check":
            check_baseline_data()
    else:
        seed_baseline_data(dry_run=True)
        print("\nTo execute, run: python -m app.scripts.seed_baseline_data --execute")
        print("To check data, run: python -m app.scripts.seed_baseline_data --check")
