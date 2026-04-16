"""Load canonical SQL text shipped with the app (for parity with Python builders / DBA review)."""

from pathlib import Path

_SQL_ROOT = Path(__file__).resolve().parent.parent / "sql"


def load_app_sql(filename: str) -> str:
    path = _SQL_ROOT / filename
    if not path.is_file():
        raise FileNotFoundError(f"Missing SQL file: {path}")
    return path.read_text(encoding="utf-8")
