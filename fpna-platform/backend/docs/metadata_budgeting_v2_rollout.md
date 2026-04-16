# Metadata Budgeting V2 Rollout

## Feature Flag

- Flag: `BUDGETING_V2_METADATA_ENABLED`
- Location: `backend/app/config.py`
- Default: `False` (V1 logic remains active)

## Non-Production Rollout Steps

1. Deploy backend with flag `False`.
2. Seed metadata formulas:
   - `POST /api/v1/drivers/seed-metadata-logic`
3. Validate formulas on critical drivers:
   - `POST /api/v1/drivers/metadata-logic/{id}/validate`
4. Publish approved rows:
   - `POST /api/v1/drivers/metadata-logic/{id}/publish`
5. Turn flag `True` in non-prod.
6. Execute bulk apply and compare outputs to V1 baseline.

## Monitoring

- Runtime execution logs:
  - `GET /api/v1/drivers/metadata-logic/execution-logs`
- Filter options:
  - `logic_code`
  - `status` (`SUCCESS` or `FAILED`)

## Production Cutover

1. Confirm parity tests pass in CI.
2. Enable flag in production during low-traffic window.
3. Monitor execution logs for failures.
4. If needed, rollback by setting flag to `False` (instant V1 fallback).
