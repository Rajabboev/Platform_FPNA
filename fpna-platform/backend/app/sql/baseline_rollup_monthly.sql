-- Roll up baseline_data to one row per (account_code, fiscal_year, fiscal_month).
-- Mirrors BudgetPlanningService._rollup_baseline_for_segment (SQLAlchemy select).
--
-- Optional filters (add as AND clauses):
--   account_code IN (...)
--   segment: UPPER(LTRIM(RTRIM(ISNULL(segment_key, '')))) = UPPER(LTRIM(RTRIM(@segment)))
-- When segment filter is omitted, all segment_key values are consolidated (SUM).
--
SELECT
    account_code,
    fiscal_year,
    fiscal_month,
    SUM(CAST(COALESCE(balance_uzs, 0) AS DECIMAL(28, 4))) AS balance_uzs,
    SUM(CAST(COALESCE(balance, 0) AS DECIMAL(28, 4))) AS balance
FROM baseline_data
WHERE fiscal_year IN (2023, 2024, 2025)  -- example; bind from application
GROUP BY account_code, fiscal_year, fiscal_month
ORDER BY account_code, fiscal_year, fiscal_month;
