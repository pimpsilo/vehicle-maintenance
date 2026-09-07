# Odometer Logging & Usage Analytics Plan

## Context
The user wants to maintain a continuous diary of mileage updates to enable:
1. **Usage metrics** (miles per day/week/month/year).
2. **Observed-rate maintenance forecasting** — using real driving pace to estimate how quickly we are approaching mileage-based service intervals, instead of relying solely on the static `estimated_annual_mileage` field.

Today only `Vehicle.current_mileage` is preserved; every update overwrites the previous value, so historical analysis is impossible. The interval engine's sole rate input is the user-supplied estimate (`app/services/interval_engine.py:34`: `daily_mileage_rate = estimated_annual_mileage / 365.25`).

---

## Phase 1 — Odometer History Logging

### Data model changes
- Create `OdometerEntry` in `app/models/vehicle.py` (keeps it centralized alongside `Vehicle`).
- Fields:
  - `id`: Primary Key
  - `vehicle_id`: FK to `vehicles.id`
  - `mileage`: `int`, `ge=0` — the recorded value
  - `recorded_at`: `datetime`, default `get_utc_now`
- Add `odometer_entries: List["OdometerEntry"] = Relationship(back_populates="vehicle", cascade_delete=True)` to `Vehicle` (consistent with the existing child-relationship pattern).

### Implementation changes
- `update_odometer` (`app/routers/vehicles.py:143`) currently validates monotonic increase, sets `current_mileage`, and commits. Extend it to insert an `OdometerEntry(mileage=payload.current_mileage)` in the same transaction.
- Honor the existing-but-unused `OdometerUpdate.recorded_date`: when provided, stamp `recorded_at` with that date (supports backfilled readings); otherwise default to now.
- **Backdated readings are allowed** (decided): a `recorded_date` in the past appends history only for paper-log migration and does **not** change `current_mileage`. Reject backdated mileage greater than `current_mileage` to keep the timeline monotonic.
- Keep the monotonic guard for live readings (reject readings lower than `current_mileage`) unchanged.

### Files
- `app/models/vehicle.py`
- `app/routers/vehicles.py`

### Verification
- Test in `tests/test_vehicles.py`: calling `POST /api/v1/vehicles/{id}/odometer` persists an `OdometerEntry` **and** updates `current_mileage`; repeated updates produce multiple history entries.

---

## Phase 2 — Usage Stats & Reporting

### New endpoint
- `GET /api/v1/vehicles/{vehicle_id}/usage` (in `app/routers/vehicles.py`), computed from `OdometerEntry` history:
  - `total_miles`: latest − earliest reading.
  - `observation_span_days`: latest `recorded_at` − earliest `recorded_at`.
  - `average_miles_per_day`: `total_miles / span_days` (observed).
  - `miles_per_week` / `miles_per_month` / `miles_per_year`: observed daily average × 7 / 30.4375 / 365.25.
  - Trailing-window deltas: `last_30_days_miles`, `last_90_days_miles`, `last_365_days_miles` (interpolate between the entries bracketing each window boundary).
  - `monthly_series`: `[{month, miles}]` per **calendar month** (decided bucketing for the series; trailing windows serve the rates), for dashboard charting.
  - `insufficient_data: true` when there are < 2 entries or the span is < 14 days; rates return `null` in that case and consumers fall back to `estimated_annual_mileage`.
- Read-only: no DB writes.

### Dashboard
- Add a "Usage" section to `app/templates/dashboard.html`: KPI tiles (per day/week/month/year) plus a mileage-over-time chart. **Dependency-free SVG bar/line rendering (decided)** — no CDN, so QNAP stays offline-capable.

### Files
- `app/routers/vehicles.py`
- `app/services/usage_service.py` (new — pure math, unit-testable)
- `app/templates/dashboard.html`

### Verification
- Tests seed `OdometerEntry` rows at known dates/mileages and assert exact rate values, window deltas, and the `insufficient_data` path.

---

## Phase 3 — Rate-Based Maintenance Triggers

### Observed-rate forecasting in the interval engine
- `MaintenanceIntervalEngine.calculate_forecasts` currently derives the daily rate from `estimated_annual_mileage` only.
- Change to: compute an **observed** daily rate from `OdometerEntry` history over a trailing window (`usage_observation_window_days`, default 90), using a **span-delta estimator (decided)**: `(mileage_at_window_end − mileage_at_window_start) / window_days`, interpolating boundary readings. Use it when data suffices; otherwise fall back to the estimate. This makes `projected_due_date_by_mileage` reflect actual driving pace.

### Approach-rate warnings
- Extend the forecast payload (`app/models/maintenance.py`) with:
  - `accrual_rate_source`: `"observed"` | `"estimated"`
  - `accrual_rate_mpd`: miles/day used for the projection
  - `rate_delta_pct`: observed vs estimated annual mileage, in percent
  - `approaching_faster: true` when the observed rate exceeds the estimate by `maintenance_rate_surge_pct` (default 25%) and the forecast is not already overdue. The action summary gains a warning like "⚠️ Driving pace is ~X% above plan; due ~N days sooner than the calendar interval."
- Existing dual-threshold due-soon/overdue logic stays; this only sharpens the projection and adds the warning.

### Notifications
- `notification_srv.py` / `scheduler_srv.py` already scan forecasts for due-soon/overdue. Add a rate-surge check: when `approaching_faster` is true and the observed-rate projection falls inside the due-soon window while the calendar-date projection does not, emit a new notification type (`RATE_SURGE`) subject to the existing cooldown dedupe.

### Config
- `app/config.py`: `usage_observation_window_days` (default 90), `maintenance_rate_surge_pct` (default 25).

### Files
- `app/services/interval_engine.py`
- `app/models/maintenance.py`
- `app/services/notification_srv.py`
- `app/services/scheduler_srv.py`
- `app/config.py`

### Verification
- Engine test: with seeded entries, the observed rate drives the projection; without, it falls back to the estimate.
- Surge test: observed ≫ estimate sets `approaching_faster` and the notification pipeline emits `RATE_SURGE`.

---

## Decisions (resolved 2026-09-07)
1. **Backdated readings allowed**: `recorded_date` in the past is accepted for migrating paper logs; it appends history only and never moves `current_mileage` (backdated mileage > `current_mileage` is rejected).
2. **Bucketing**: calendar months for the dashboard series; trailing windows for the rates.
3. **Rate estimator**: span delta over the trailing window for v1; revisit linear regression later if jitter matters.
4. **Chart rendering**: dependency-free SVG, no CDN.

## Implementation Order
1. Phase 1 (model + router + test) — foundation.
2. Phase 2 (usage service + endpoint + tests; dashboard after the endpoint is stable).
3. Phase 3 (engine rate source → forecast fields → notifications → config).
