"""
Compare SQL Server tables to tables registered on SQLAlchemy Base.metadata.

Run from backend directory:
  python scripts/audit_db_tables_vs_models.py

Requires DATABASE_* env / .env as in app.config.

Output:
  - ONLY_IN_DATABASE: tables with no ORM / Table() on Base — candidates for DROP after review
  - ONLY_IN_CODE: models exist but table missing (run migrations / create_all)

Does NOT execute DROP. Foreign keys and application usage must be verified manually.
"""
from __future__ import annotations

import importlib
import os
import pkgutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app.models as models_pkg  # noqa: E402

for _, name, _ in pkgutil.iter_modules(models_pkg.__path__):
    if name.startswith("_"):
        continue
    importlib.import_module(f"app.models.{name}")

from sqlalchemy import inspect as sa_inspect  # noqa: E402

from app.database import Base, engine  # noqa: E402

# Known non-application tables (migrations / tooling)
_IGNORE_DB_ONLY = frozenset({"alembic_version", "sysdiagrams"})

# Created/queried via raw SQL, not Base.metadata — NOT safe to drop
# See: app/services/alert_engine.py, app/services/dwh_integration_service.py, app/api/dwh_integration.py
_RAW_SQL_TABLES = frozenset({
    "alert_notifications",
    "alert_thresholds",
    "etl_audit_trail",
    "variance_alerts",
})


def main() -> None:
    insp = sa_inspect(engine)
    schema = os.environ.get("DATABASE_SCHEMA", "dbo")
    try:
        db_tables = set(insp.get_table_names(schema=schema))
    except TypeError:
        db_tables = set(insp.get_table_names())

    code_tables = set(Base.metadata.tables.keys())

    db_only = db_tables - code_tables - _IGNORE_DB_ONLY
    documented_raw = sorted(db_only & _RAW_SQL_TABLES)
    orphan_candidates = sorted(db_only - _RAW_SQL_TABLES)
    only_code = sorted(code_tables - db_tables)

    print("=== Documented raw-SQL tables (NOT in ORM; do not drop while features are used) ===")
    if not documented_raw:
        print("(none)")
    else:
        for t in documented_raw:
            print(t)

    print()
    print("=== Tables in database but NOT in app.models - orphan candidates (verify empty + no FKs) ===")
    if not orphan_candidates:
        print("(none)")
    else:
        for t in orphan_candidates:
            print(t)

    print()
    print("=== Tables in code but NOT in database (create_all / migrations needed) ===")
    if not only_code:
        print("(none)")
    else:
        for t in only_code:
            print(t)

    print()
    print(
        "Next: if orphan candidates exist, check row counts, sys.foreign_keys, and grep the repo "
        "for the table name before DROP (children first). Expand _RAW_SQL_TABLES in this script "
        "when you add new raw-SQL tables."
    )


if __name__ == "__main__":
    main()
