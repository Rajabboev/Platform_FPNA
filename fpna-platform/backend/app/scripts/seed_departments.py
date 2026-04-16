"""
Seed departments as FP&A *product owners* (not retail/corporate segments).

Each department owns a set of fpna_product_key buckets (Loans, Deposits, P&L / CFO, Risk, …).
Clears legacy CBU budgeting-group links and DWH segment filters for seeded rows.

Run:
  python -m app.scripts.seed_departments              # dry run
  python -m app.scripts.seed_departments --execute
"""

import logging
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models.department import Department, DepartmentProductAccess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Product-owner org design (segment-agnostic)
PRODUCT_OWNER_DEPARTMENTS = [
    {
        "code": "OWN_LOANS",
        "name_en": "Loans — Product Owner",
        "name_uz": "Kreditlar mahsulot egasi",
        "name_ru": "Владелец продукта «Кредиты»",
        "description": "Balance-sheet loan portfolio planning",
        "is_baseline_only": False,
        "display_order": 10,
        "product_keys": ["LOANS"],
    },
    {
        "code": "OWN_DEPOSITS",
        "name_en": "Deposits — Product Owner",
        "name_uz": "Depozitlar mahsulot egasi",
        "name_ru": "Владелец продукта «Депозиты»",
        "description": "Deposit & funding liabilities planning",
        "is_baseline_only": False,
        "display_order": 20,
        "product_keys": ["DEPOSITS"],
    },
    {
        "code": "OWN_CFO_PL",
        "name_en": "P&L — CFO",
        "name_uz": "F&N — moliya direktori",
        "name_ru": "ОиП — CFO",
        "description": "Interest & non-interest revenue/expense, OPEX, tax, depreciation P&L",
        "is_baseline_only": False,
        "display_order": 30,
        "product_keys": [
            "REV_INTEREST",
            "REV_NONINTEREST",
            "EXP_INTEREST",
            "EXP_NONINTEREST",
            "OPEX",
            "CAPEX_PNL",
            "TAX",
        ],
    },
    {
        "code": "OWN_RISK",
        "name_en": "Risk & Reserves",
        "name_uz": "Risk va zaxiralar",
        "name_ru": "Риски и резервы",
        "description": "Provisions and reserve balances (BS)",
        "is_baseline_only": False,
        "display_order": 40,
        "product_keys": ["RESERVES"],
    },
    {
        "code": "OWN_TREASURY",
        "name_en": "Treasury & Markets",
        "name_uz": "G'azna va bozorlar",
        "name_ru": "Казначейство и рынки",
        "description": "Cash, securities, CBU/card/other liability buckets",
        "is_baseline_only": False,
        "display_order": 50,
        "product_keys": [
            "CASH_LIQUID",
            "SECURITIES_INVEST",
            "LIABS_CBU",
            "LIABS_CARDS",
            "LIABS_OTHER",
        ],
    },
    {
        "code": "OWN_CAPITAL",
        "name_en": "Capital & Equity",
        "name_uz": "Kapital va kapital",
        "name_ru": "Капитал",
        "description": "Equity / capital planning",
        "is_baseline_only": False,
        "display_order": 60,
        "product_keys": ["CAPITAL"],
    },
    {
        "code": "OWN_OPERATIONS",
        "name_en": "Operations & Other BS",
        "name_uz": "Operatsiyalar va boshqa aktivlar",
        "name_ru": "Операции и прочий баланс",
        "description": "Fixed assets, other assets, off-balance, unclassified",
        "is_baseline_only": False,
        "display_order": 70,
        "product_keys": ["FIXED_ASSETS", "ASSETS_OTHER", "OFF_BALANCE", "UNCLASSIFIED"],
    },
    {
        "code": "BASELINE_REF",
        "name_en": "Baseline Reference (read-only)",
        "name_uz": "Bazaviy ma'lumot (faqat o'qish)",
        "name_ru": "Базовая справка (только чтение)",
        "description": "Consolidated view — all products, no adjustments",
        "is_baseline_only": True,
        "display_order": 99,
        "product_keys": [],
    },
]


def _set_product_access(db, dept: Department, product_keys: list) -> None:
    db.query(DepartmentProductAccess).filter(
        DepartmentProductAccess.department_id == dept.id
    ).delete(synchronize_session=False)
    now = datetime.now(timezone.utc)
    for pk in product_keys:
        db.add(
            DepartmentProductAccess(
                department_id=dept.id,
                product_key=pk,
                can_edit=True,
                can_submit=True,
                assigned_at=now,
            )
        )


def seed_departments(dry_run: bool = True, retire_segment_depts: bool = True):
    db = SessionLocal()
    try:
        logger.info("=" * 60)
        logger.info("Product-owner departments seed")
        logger.info("=" * 60)
        if dry_run:
            logger.info("DRY RUN — no DB writes")

        created = 0
        updated = 0

        if not dry_run and retire_segment_depts:
            for code in ("RETAIL", "CORPORATE"):
                leg = db.query(Department).filter(Department.code == code).first()
                if leg and leg.is_active:
                    leg.is_active = False
                    logger.info("  [RETIRED] %s (segment-based owner — use product owners)", code)

        for row in PRODUCT_OWNER_DEPARTMENTS:
            code = row["code"]
            existing = db.query(Department).filter(Department.code == code).first()
            pks = row["product_keys"]

            if dry_run:
                logger.info("  [DRY] %s — %d products", code, len(pks))
                continue

            if existing:
                existing.name_en = row["name_en"]
                existing.name_uz = row["name_uz"]
                existing.name_ru = row["name_ru"]
                existing.description = row["description"]
                existing.is_baseline_only = row["is_baseline_only"]
                existing.display_order = row["display_order"]
                existing.is_active = True
                existing.dwh_segment_value = None
                existing.budgeting_groups = []
                _set_product_access(db, existing, pks)
                updated += 1
                logger.info("  [UPDATED] %s (%d products)", code, len(pks))
            else:
                dept = Department(
                    code=code,
                    name_en=row["name_en"],
                    name_uz=row["name_uz"],
                    name_ru=row["name_ru"],
                    description=row["description"],
                    is_baseline_only=row["is_baseline_only"],
                    display_order=row["display_order"],
                    is_active=True,
                    dwh_segment_value=None,
                )
                db.add(dept)
                db.flush()
                dept.budgeting_groups = []
                _set_product_access(db, dept, pks)
                created += 1
                logger.info("  [CREATED] %s (%d products)", code, len(pks))

        if not dry_run:
            db.commit()

        logger.info("=" * 60)
        logger.info("Done: created=%s updated=%s", created, updated)
        return {"created": created, "updated": updated}
    finally:
        db.close()


def list_departments():
    db = SessionLocal()
    try:
        for dept in db.query(Department).order_by(Department.display_order).all():
            pks = [r.product_key for r in (dept.product_access_rows or [])]
            print(f"{dept.code}\tactive={dept.is_active}\tsegment={dept.dwh_segment_value!r}\tproducts={pks}")
    finally:
        db.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--execute":
        seed_departments(dry_run=False)
    elif len(sys.argv) > 1 and sys.argv[1] == "--list":
        list_departments()
    else:
        seed_departments(dry_run=True)
        print("\nApply: python -m app.scripts.seed_departments --execute")
