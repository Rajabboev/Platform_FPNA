"""
Signed balance from DWH balans_ato-style rows.

Per business rule (same as):
  (CASE WHEN priznall = 1 THEN ostatall ELSE 0 END)
  - (CASE WHEN priznall = 0 THEN ostatall ELSE 0 END)

Equivalent per-row signed amount:
  PRIZNALL = '1' -> +OSTATALL
  PRIZNALL = '0' -> -OSTATALL
  else (NULL / other) -> +OSTATALL (legacy when flag missing)

PRIZNALL is often CHAR(1) in SQL Server; we compare trimmed varchar.
"""


def _priznall_int_expr(priznall_col: str) -> str:
    """Normalize PRIZNALL (CHAR/BIT/INT) to compare as integer 0/1."""
    p = priznall_col.strip("[]")
    return (
        f"TRY_CONVERT(INT, LTRIM(RTRIM(REPLACE(CAST([{p}] AS VARCHAR(20)), CHAR(0), ''))))"
    )


def sql_signed_balance_row(balance_col: str, priznall_col: str) -> str:
    """Single-row expression (no SUM). Bracketed identifiers for SQL Server."""
    b, p = balance_col.strip("[]"), priznall_col.strip("[]")
    pi = _priznall_int_expr(p)
    return f"""(
        CASE
            WHEN {pi} = 1 THEN ISNULL([{b}], 0)
            WHEN {pi} = 0 THEN -ISNULL([{b}], 0)
            ELSE ISNULL([{b}], 0)
        END
    )"""


def sql_signed_balance_sum(balance_col: str, priznall_col: str) -> str:
    """Aggregated SUM(...) for GROUP BY queries."""
    return f"SUM({sql_signed_balance_row(balance_col, priznall_col)})"
