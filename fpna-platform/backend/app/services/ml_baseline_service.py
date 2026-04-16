"""
ML Baseline Service - AI/ML-powered baseline forecasting

Two engines:
  1. Prophet (ai_forecast) - full time-series decomposition with trend + seasonality
  2. Linear Trend + Seasonality (ml_trend) - FP&A-standard approach:
       * Linear regression on annual totals → extrapolate Year N+1
       * Monthly seasonality factors from 3-year historical averages
       * Confidence interval from historical YoY volatility

Why not GradientBoosting for trend?
  Tree-based models cannot extrapolate outside training range.
  With 3 source years (year_idx 0,1,2), predictions for year_idx=3 collapse
  to the nearest leaf value — essentially a weighted average of recent history.
  Linear regression explicitly extrapolates the trend.
"""

import logging
import math
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _build_history_df(account_months: Dict[int, List[float]]) -> pd.DataFrame:
    """Convert {month: [values_across_years]} into a time-indexed DataFrame."""
    rows = []
    for month in sorted(account_months.keys()):
        for year_idx, value in enumerate(account_months[month]):
            rows.append({'year_idx': year_idx, 'month': month, 'value': value})
    if not rows:
        return pd.DataFrame(columns=['year_idx', 'month', 'value'])
    return pd.DataFrame(rows)


def forecast_prophet(
    account_months: Dict[int, List[float]],
    source_years: List[int],
    target_year: int,
) -> Dict[str, any]:
    """
    Prophet-based time-series forecast.

    Returns:
        {month: {'forecast': float, 'lower': float, 'upper': float}}
    """
    try:
        from prophet import Prophet
    except ImportError:
        logger.warning("prophet not installed, falling back to trend method")
        return forecast_sklearn(account_months, source_years, target_year)

    rows = []
    for month in sorted(account_months.keys()):
        for yr_idx, value in enumerate(account_months[month]):
            if yr_idx < len(source_years):
                yr = source_years[yr_idx]
                ds = pd.Timestamp(year=yr, month=month, day=15)
                rows.append({'ds': ds, 'y': float(value)})

    if len(rows) < 6:
        return forecast_sklearn(account_months, source_years, target_year)

    df = pd.DataFrame(rows).sort_values('ds')

    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        changepoint_prior_scale=0.1,
    )
    model.fit(df)

    future_dates = [pd.Timestamp(year=target_year, month=m, day=15) for m in range(1, 13)]
    future_df = pd.DataFrame({'ds': future_dates})
    forecast = model.predict(future_df)

    result = {}
    for _, row in forecast.iterrows():
        m = row['ds'].month
        result[m] = {
            'forecast': round(float(row['yhat']), 2),
            'lower': round(float(row['yhat_lower']), 2),
            'upper': round(float(row['yhat_upper']), 2),
        }
    return result


def forecast_sklearn(
    account_months: Dict[int, List[float]],
    source_years: List[int],
    target_year: int,
) -> Dict[str, any]:
    """
    FP&A-standard linear trend + monthly seasonality decomposition.

    Algorithm:
      1. Annual totals per year from historical monthly data
      2. Linear regression (polyfit) on annual totals → project Year N+1
      3. Cap extreme growth at ±50% (prevent outlier extrapolation)
      4. Monthly seasonality = avg monthly share of annual total across years
      5. Confidence = historical YoY volatility (MAPE) ± error band

    This correctly extrapolates trends unlike tree-based models.
    """
    n_years = len(source_years)
    if n_years == 0:
        return _simple_average_fallback(account_months)

    # --- Step 1: Annual totals per year ---
    annual_totals = []
    for yr_idx in range(n_years):
        total = 0.0
        for m in range(1, 13):
            vals = account_months.get(m, [])
            total += float(vals[yr_idx]) if yr_idx < len(vals) else 0.0
        annual_totals.append(total)

    y = np.array(annual_totals, dtype=float)
    nonzero_mask = y != 0

    if nonzero_mask.sum() == 0:
        return _simple_average_fallback(account_months)

    # --- Step 2: Linear trend extrapolation ---
    x = np.arange(n_years, dtype=float)
    if nonzero_mask.sum() >= 2:
        coeffs = np.polyfit(x[nonzero_mask], y[nonzero_mask], 1)
        projected_annual = float(np.polyval(coeffs, n_years))
    else:
        # Only 1 non-zero year — use that value flat
        projected_annual = float(y[nonzero_mask][0])

    # --- Step 3: Cap growth to prevent runaway extrapolation ---
    last_annual = float(y[nonzero_mask][-1])
    if last_annual != 0:
        raw_growth = (projected_annual - last_annual) / abs(last_annual)
        if raw_growth > 0.50:
            projected_annual = last_annual * 1.50
        elif raw_growth < -0.50:
            projected_annual = last_annual * 0.50

    # --- Step 4: Monthly seasonality factors ---
    monthly_shares: Dict[int, float] = {}
    for m in range(1, 13):
        shares = []
        for yr_idx in range(n_years):
            annual = annual_totals[yr_idx]
            if annual != 0:
                vals = account_months.get(m, [])
                mv = float(vals[yr_idx]) if yr_idx < len(vals) else 0.0
                shares.append(mv / annual)
        monthly_shares[m] = float(np.mean(shares)) if shares else 1.0 / 12

    # Normalize so shares sum to 1.0
    total_share = sum(monthly_shares.values())
    if total_share > 0:
        monthly_shares = {m: s / total_share for m, s in monthly_shares.items()}
    else:
        monthly_shares = {m: 1.0 / 12 for m in range(1, 13)}

    # --- Step 5: Historical YoY volatility for confidence ---
    yoy_errors = []
    nonzero_idx = np.where(nonzero_mask)[0]
    for i in range(1, len(nonzero_idx)):
        prev = y[nonzero_idx[i - 1]]
        curr = y[nonzero_idx[i]]
        if prev != 0:
            yoy_errors.append(abs((curr - prev) / prev))
    error_pct = float(np.mean(yoy_errors)) if yoy_errors else 0.05

    # --- Build per-month result ---
    result = {}
    for m in range(1, 13):
        forecast = projected_annual * monthly_shares[m]
        lower = forecast * (1.0 - error_pct)
        upper = forecast * (1.0 + error_pct)
        result[m] = {
            'forecast': round(float(forecast), 2),
            'lower': round(float(lower), 2),
            'upper': round(float(upper), 2),
        }

    return result


def _simple_average_fallback(
    account_months: Dict[int, List[float]],
) -> Dict[str, any]:
    """Fallback when data is too sparse for trend analysis."""
    result = {}
    for m in range(1, 13):
        values = account_months.get(m, [])
        avg = sum(values) / len(values) if values else 0
        result[m] = {
            'forecast': round(avg, 2),
            'lower': round(avg * 0.9, 2),
            'upper': round(avg * 1.1, 2),
        }
    return result


def compute_ml_baseline(
    method: str,
    account_months: Dict[int, List[float]],
    source_years: List[int],
    target_year: int,
) -> Tuple[Dict[int, float], Optional[Dict[int, float]], Optional[Dict[int, float]]]:
    """
    Unified entry point for ML baseline calculation.

    Args:
        method: 'ai_forecast' (Prophet) or 'ml_trend' (linear trend + seasonality)
        account_months: {month: [values_per_source_year]}
        source_years: list of source years used as training data
        target_year: target fiscal year to forecast

    Returns:
        (monthly_values, confidence_lower, confidence_upper)
        monthly_values: {1: val, 2: val, ..., 12: val}
    """
    if method == 'ai_forecast':
        raw = forecast_prophet(account_months, source_years, target_year)
    else:
        raw = forecast_sklearn(account_months, source_years, target_year)

    monthly = {}
    lower = {}
    upper = {}
    for m in range(1, 13):
        entry = raw.get(m, {'forecast': 0, 'lower': 0, 'upper': 0})
        monthly[m] = entry['forecast']
        lower[m] = entry['lower']
        upper[m] = entry['upper']

    return monthly, lower, upper
