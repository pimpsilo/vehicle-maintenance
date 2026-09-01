from datetime import date, timedelta
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
        """
        if current_date is None:
            current_date = date.today()

        vehicle = session.get(Vehicle, vehicle_id)
        if not vehicle:
            return []

        service_defs = session.exec(select(ServiceDefinition)).all()
        forecasts = []

        daily_mileage_rate = max(1.0, vehicle.estimated_annual_mileage / 365.25)

        for sdef in service_defs:
            # Query the latest service record for this service definition and vehicle
            stmt = (
                select(ServiceRecord)
                .where(
                    ServiceRecord.vehicle_id == vehicle_id,
                    ServiceRecord.service_definition_id == sdef.id,
                )
                .order_by(ServiceRecord.completed_date.desc(), ServiceRecord.completed_mileage.desc())
            )
            latest_record = session.exec(stmt).first()

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

            # Projection by daily mileage accrual
            projected_days_by_mileage = int(miles_remaining / daily_mileage_rate)
            projected_due_date = current_date + timedelta(days=max(0, projected_days_by_mileage))

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
            )
            forecasts.append(forecast)

        # Sort with OVERDUE first, then DUE_SOON, then OK
        status_priority = {ServiceStatus.OVERDUE: 0, ServiceStatus.DUE_SOON: 1, ServiceStatus.OK: 2}
        forecasts.sort(key=lambda f: (status_priority[f.status], f.miles_remaining))
        return forecasts
