-- Monthly series used by GET /budget-planning/department/{id}/pl-data for seasonality.
-- Python: _load_historic_monthly_by_accounts() in app/api/budget_planning.py
--
-- Parameters (replace literals):
--   :ref_year      = fiscal_year - 1 by default (e.g. 2025 for a 2026 plan), or seasonality_reference_year
--   :account_codes = COA codes on the active budget plan details
--   :segment       = departments.dwh_segment_value for the plan's department (NULL = consolidated)

-- Consolidated (no segment filter — sums all segment_key values per account/month)
SELECT
    account_code,
    fiscal_month,
    SUM(CAST(COALESCE(balance_uzs, 0) AS DECIMAL(22, 2))) AS balance_uzs_sum
FROM baseline_data
WHERE fiscal_year = 2025
  AND account_code IN ('00000' /* …plan COA list… */)
GROUP BY account_code, fiscal_month
ORDER BY account_code, fiscal_month;

-- Segmented (only when department.dwh_segment_value is set, match is case-insensitive in app)
SELECT
    account_code,
    fiscal_month,
    SUM(CAST(COALESCE(balance_uzs, 0) AS DECIMAL(22, 2))) AS balance_uzs_sum
FROM baseline_data
WHERE fiscal_year = 2025
  AND account_code IN ('00000' /* … */)
  AND UPPER(COALESCE(TRIM(segment_key), '')) = UPPER(TRIM('RETAIL'))
GROUP BY account_code, fiscal_month
ORDER BY account_code, fiscal_month;
