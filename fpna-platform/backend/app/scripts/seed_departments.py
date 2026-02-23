"""
Seed sample departments for FP&A Budget Planning

Creates departments based on the plan specification:
- TREASURY: Cash & Payment Documents, CBRU, Investments
- RETAIL: Loans, Deposits (Retail)
- CORPORATE: Loans, Deposits (Corporate)
- RISK: Provisions/Reserves
- OPERATIONS: Fixed Assets, Other
- BASELINE_ONLY: All groups (read-only reference)
"""

import logging
from sqlalchemy import text
from app.database import SessionLocal, engine

# Import all models to ensure relationships are resolved
from app.models.user import User  # noqa: F401
from app.models.budget_plan import BudgetPlan, BudgetPlanGroup, BudgetPlanDetail, BudgetPlanApproval  # noqa: F401
from app.models.department import Department, DepartmentAssignment, DepartmentRole
from app.models.coa_dimension import BudgetingGroup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SAMPLE_DEPARTMENTS = [
    {
        "code": "TREASURY",
        "name_en": "Treasury",
        "name_uz": "G'aznachilik",
        "name_ru": "Казначейство",
        "description": "Treasury department managing cash, CBRU relations, and investments",
        "is_baseline_only": False,
        "display_order": 1,
        "budgeting_groups": [1, 2, 3, 4, 5, 6, 7],  # Cash & Payment Documents, CBRU, Investments
    },
    {
        "code": "RETAIL",
        "name_en": "Retail Banking",
        "name_uz": "Chakana bank xizmatlari",
        "name_ru": "Розничный банкинг",
        "description": "Retail banking - consumer loans and deposits",
        "is_baseline_only": False,
        "display_order": 2,
        "budgeting_groups": [8, 20, 21],  # Loans, Deposits
    },
    {
        "code": "CORPORATE",
        "name_en": "Corporate Banking",
        "name_uz": "Korporativ bank xizmatlari",
        "name_ru": "Корпоративный банкинг",
        "description": "Corporate banking - business loans and deposits",
        "is_baseline_only": False,
        "display_order": 3,
        "budgeting_groups": [8, 20, 21],  # Loans, Deposits
    },
    {
        "code": "RISK",
        "name_en": "Risk Management",
        "name_uz": "Risklar boshqaruvi",
        "name_ru": "Управление рисками",
        "description": "Risk management - provisions and reserves",
        "is_baseline_only": False,
        "display_order": 4,
        "budgeting_groups": [9, 13, 19],  # Provisions/Reserves
    },
    {
        "code": "OPERATIONS",
        "name_en": "Operations",
        "name_uz": "Operatsiyalar",
        "name_ru": "Операции",
        "description": "Operations - fixed assets and other operational items",
        "is_baseline_only": False,
        "display_order": 5,
        "budgeting_groups": [10, 14, 18],  # Fixed Assets, Other
    },
    {
        "code": "BASELINE_REF",
        "name_en": "Baseline Reference",
        "name_uz": "Bazaviy ma'lumot",
        "name_ru": "Базовая справка",
        "description": "Baseline reference department - all groups, read-only",
        "is_baseline_only": True,
        "display_order": 99,
        "budgeting_groups": [],  # Will get all groups
    },
]


def seed_departments(dry_run: bool = True):
    """Seed sample departments"""
    db = SessionLocal()
    
    try:
        logger.info("=" * 60)
        logger.info("Seeding Sample Departments")
        logger.info("=" * 60)
        
        if dry_run:
            logger.info("DRY RUN MODE - No changes will be made")
        
        # Get all budgeting groups
        all_groups = db.query(BudgetingGroup).all()
        group_map = {g.group_id: g for g in all_groups}
        logger.info(f"Found {len(all_groups)} budgeting groups")
        
        created = 0
        updated = 0
        
        for dept_data in SAMPLE_DEPARTMENTS:
            code = dept_data["code"]
            
            # Check if exists
            existing = db.query(Department).filter(Department.code == code).first()
            
            if existing:
                logger.info(f"  [EXISTS] {code} - {dept_data['name_en']}")
                if not dry_run:
                    # Update
                    existing.name_en = dept_data["name_en"]
                    existing.name_uz = dept_data["name_uz"]
                    existing.name_ru = dept_data["name_ru"]
                    existing.description = dept_data["description"]
                    existing.is_baseline_only = dept_data["is_baseline_only"]
                    existing.display_order = dept_data["display_order"]
                    
                    # Update budgeting groups
                    group_ids = dept_data["budgeting_groups"]
                    if not group_ids and dept_data["is_baseline_only"]:
                        # Baseline-only gets all groups
                        existing.budgeting_groups = all_groups
                    else:
                        existing.budgeting_groups = [group_map[gid] for gid in group_ids if gid in group_map]
                    
                    updated += 1
            else:
                if dry_run:
                    logger.info(f"  [DRY] Would create {code} - {dept_data['name_en']}")
                else:
                    dept = Department(
                        code=code,
                        name_en=dept_data["name_en"],
                        name_uz=dept_data["name_uz"],
                        name_ru=dept_data["name_ru"],
                        description=dept_data["description"],
                        is_baseline_only=dept_data["is_baseline_only"],
                        display_order=dept_data["display_order"],
                    )
                    db.add(dept)
                    db.flush()  # Get ID
                    
                    # Assign budgeting groups
                    group_ids = dept_data["budgeting_groups"]
                    if not group_ids and dept_data["is_baseline_only"]:
                        dept.budgeting_groups = all_groups
                    else:
                        dept.budgeting_groups = [group_map[gid] for gid in group_ids if gid in group_map]
                    
                    logger.info(f"  [CREATED] {code} - {dept_data['name_en']} ({len(dept.budgeting_groups)} groups)")
                    created += 1
        
        if not dry_run:
            db.commit()
        
        logger.info("\n" + "=" * 60)
        if dry_run:
            logger.info("DRY RUN COMPLETE - Run with dry_run=False to execute")
        else:
            logger.info(f"SEEDING COMPLETE: {created} created, {updated} updated")
        logger.info("=" * 60)
        
        return {"created": created, "updated": updated}
        
    finally:
        db.close()


def list_departments():
    """List all departments with their budgeting groups"""
    db = SessionLocal()
    
    try:
        departments = db.query(Department).order_by(Department.display_order).all()
        
        print("\n" + "=" * 80)
        print("DEPARTMENTS")
        print("=" * 80)
        
        for dept in departments:
            groups = [g.group_id for g in dept.budgeting_groups]
            print(f"\n{dept.code} - {dept.name_en}")
            print(f"  Active: {dept.is_active}, Baseline Only: {dept.is_baseline_only}")
            print(f"  Budgeting Groups: {groups}")
        
        print("\n" + "=" * 80)
        
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--execute":
            seed_departments(dry_run=False)
        elif sys.argv[1] == "--list":
            list_departments()
    else:
        seed_departments(dry_run=True)
        print("\nTo execute, run: python -m app.scripts.seed_departments --execute")
        print("To list departments, run: python -m app.scripts.seed_departments --list")
