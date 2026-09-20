from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from sqlmodel import Session, select
from app.models.vehicle import Vehicle
from app.models.maintenance import (
    ServiceDefinition,
    ServiceRecord,
    MaintenanceForecast,
    ServiceStatus,
)
from app.config import settings
from app.services.usage_service import UsageService

class MaintenanceIntervalEngine:
    @staticmethod
    def calculate_forecasts(
        session: Session,
        vehicle_id: int,
        current_date: Optional[date] = None
    ) -> List[MaintenanceForecast]:
        """
        Evaluates all active ServiceDefinitions against the vehicle's current mileage
        and past ServiceRecords to produce a maintenance forecast for each service.
        Uses observed daily rate from OdometerEntry history if sufficient data exists.
        """
        if current_date is None:
            current_date = date.today()

        vehicle = session.get(Vehicle, vehicle_id)
        if not vehicle:
            return []

        # 1. Fetch service definitions: vehicle-specific definitions override global definitions
        all_defs = session.exec(
            select(ServiceDefinition).where(
                (ServiceDefinition.vehicle_id == vehicle_id) | (ServiceDefinition.vehicle_id == None)  # noqa: E711
            )
        ).all()

        vehicle_specific_defs = [d for d in all_defs if d.vehicle_id == vehicle_id]
        global_defs = [d for d in all_defs if d.vehicle_id is None]

        active_defs = []
        seen_service_keys = set()

        # Prioritize vehicle-specific definitions
        for sdef in vehicle_specific_defs:
            norm_name = sdef.service_name.strip().lower()
            active_defs.append(sdef)
            seen_service_keys.add(norm_name)
            # Also key by category for lubrication
            if sdef.category == "LUBRICATION" or "oil" in norm_name:
                seen_service_keys.add("oil_service")

        # Fallback to deduplicated global definitions
        for sdef in global_defs:
            norm_name = sdef.service_name.strip().lower()
            is_oil = sdef.category == "LUBRICATION" or "oil" in norm_name
            if is_oil and "oil_service" in seen_service_keys:
                continue
            if norm_name in seen_service_keys:
                continue

            active_defs.append(sdef)
            seen_service_keys.add(norm_name)
            if is_oil:
                seen_service_keys.add("oil_service")

        forecasts = []

        current_dt = datetime.combine(current_date, datetime.min.time(), tzinfo=timezone.utc)
        observed_rate = UsageService.get_observed_daily_rate(
            session=session,
            vehicle_id=vehicle_id,
            window_days=settings.usage_observation_window_days,
            as_of=current_dt,
        )

        estimated_daily_rate = max(1.0, vehicle.estimated_annual_mileage / 365.25)
        if observed_rate is not None and observed_rate > 0.1:
            daily_mileage_rate = observed_rate
            accrual_rate_source = "observed"
        else:
            daily_mileage_rate = estimated_daily_rate
            accrual_rate_source = "estimated"

        rate_delta_pct = None
        if vehicle.estimated_annual_mileage > 0:
            observed_annual = daily_mileage_rate * 365.25
            rate_delta_pct = round(
                ((observed_annual - vehicle.estimated_annual_mileage) / vehicle.estimated_annual_mileage) * 100.0,
                1,
            )

        # Pre-fetch all service records for this vehicle once
        all_vehicle_records = session.exec(
            select(ServiceRecord)
            .where(ServiceRecord.vehicle_id == vehicle_id)
            .order_by(ServiceRecord.completed_date.desc(), ServiceRecord.completed_mileage.desc())
        ).all()

        for sdef in active_defs:
            sdef_norm = sdef.service_name.strip().lower()
            is_oil = sdef.category == "LUBRICATION" or "oil" in sdef_norm

            # Match records:
            # 1. Exact foreign key match
            # 2. Or unlinked / sibling record with matching service_name or oil keyword
            matching_records = []
            for r in all_vehicle_records:
                if r.service_definition_id == sdef.id:
                    matching_records.append(r)
                elif r.service_definition_id is None:
                    r_norm = r.service_name.strip().lower()
                    if is_oil and "oil" in r_norm:
                        matching_records.append(r)
                    elif r_norm == sdef_norm:
                        matching_records.append(r)

            latest_record = matching_records[0] if matching_records else None

            if latest_record:
                last_date = latest_record.completed_date
                last_mileage = latest_record.completed_mileage
            else:
                last_date = vehicle.purchase_date or (current_date - timedelta(days=365))
                last_mileage = 0

            # Calculate target thresholds
            next_due_mileage = last_mileage + sdef.interval_miles
            approx_days_in_interval = int(sdef.interval_months * 30.4375)
            next_due_date = last_date + timedelta(days=approx_days_in_interval)

            miles_remaining = next_due_mileage - vehicle.current_mileage
            days_remaining = (next_due_date - current_date).days

            # Interval Progress calculation (% consumed)
            if sdef.interval_miles > 0:
                used_miles = vehicle.current_mileage - last_mileage
                mileage_progress_pct = round(min(100.0, max(0.0, (used_miles / sdef.interval_miles) * 100.0)), 1)
            else:
                mileage_progress_pct = 0.0

            if approx_days_in_interval > 0:
                elapsed_days = (current_date - last_date).days
                time_progress_pct = round(min(100.0, max(0.0, (elapsed_days / approx_days_in_interval) * 100.0)), 1)
            else:
                time_progress_pct = 0.0

            # Projection by daily mileage accrual
            projected_days_by_mileage = int(miles_remaining / daily_mileage_rate)
            projected_due_date = current_date + timedelta(days=max(0, projected_days_by_mileage))

            # Dominant threshold determination
            if miles_remaining <= 0 and days_remaining > 0:
                dominant_threshold = "MILEAGE"
            elif days_remaining <= 0 and miles_remaining > 0:
                dominant_threshold = "CALENDAR"
            elif projected_days_by_mileage <= days_remaining:
                dominant_threshold = "MILEAGE"
            else:
                dominant_threshold = "CALENDAR"

            # Status determination
            if miles_remaining <= 0 or days_remaining <= 0:
                status = ServiceStatus.OVERDUE
                action = f"OVERDUE: Service exceeded by {abs(miles_remaining)} miles or {abs(days_remaining)} days."
            elif (
                miles_remaining <= settings.maintenance_due_soon_miles
                or days_remaining <= settings.maintenance_due_soon_days
            ):
                status = ServiceStatus.DUE_SOON
                action = f"DUE SOON: Service due in {miles_remaining} miles or {days_remaining} days."
            else:
                status = ServiceStatus.OK
                action = f"OK: Service next due at {next_due_mileage:,} miles (~{projected_due_date.strftime('%b %d, %Y')})."

            approaching_faster = False
            if (
                accrual_rate_source == "observed"
                and rate_delta_pct is not None
                and rate_delta_pct >= settings.maintenance_rate_surge_pct
                and status != ServiceStatus.OVERDUE
            ):
                approaching_faster = True
                calendar_days_left = max(0, days_remaining)
                mileage_days_left = max(0, projected_days_by_mileage)
                days_sooner = max(0, calendar_days_left - mileage_days_left)
                action += f" ⚠️ Driving pace is ~{rate_delta_pct:.0f}% above plan; due ~{days_sooner} days sooner than the calendar interval."

            forecast = MaintenanceForecast(
                service_definition_id=sdef.id,
                service_name=sdef.service_name,
                interval_miles=sdef.interval_miles,
                interval_months=sdef.interval_months,
                last_completed_date=last_date if latest_record else None,
                last_completed_mileage=last_mileage if latest_record else None,
                next_due_mileage=next_due_mileage,
                next_due_date=next_due_date,
                projected_due_date_by_mileage=projected_due_date,
                miles_remaining=miles_remaining,
                days_remaining=days_remaining,
                status=status,
                action_summary=action,
                accrual_rate_source=accrual_rate_source,
                accrual_rate_mpd=round(daily_mileage_rate, 2),
                rate_delta_pct=rate_delta_pct,
                approaching_faster=approaching_faster,
                mileage_progress_pct=mileage_progress_pct,
                time_progress_pct=time_progress_pct,
                dominant_threshold=dominant_threshold,
            )
            forecasts.append(forecast)

        # Sort with OVERDUE first, then DUE_SOON, then OK
        status_priority = {ServiceStatus.OVERDUE: 0, ServiceStatus.DUE_SOON: 1, ServiceStatus.OK: 2}
        forecasts.sort(key=lambda f: (status_priority[f.status], f.miles_remaining))

        # Assign urgency ranking and flag immediate next required service
        for idx, f in enumerate(forecasts):
            f.urgency_rank = idx + 1
            f.is_next_required = (idx == 0)

        return forecasts
