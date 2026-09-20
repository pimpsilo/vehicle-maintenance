import logging
from datetime import date
from typing import Optional, List, Dict, Any
from sqlmodel import Session, select

from app.config import settings
from app.models.vehicle import Vehicle
from app.models.maintenance import ServiceStatus, MaintenanceForecast
from app.models.notification import (
    NotificationRecord,
    NotificationChannel,
    MaintenanceAlertItem,
)
from app.services.interval_engine import MaintenanceIntervalEngine
from app.services.notification_srv import NotificationService

logger = logging.getLogger(__name__)


class MaintenanceAlertService:
    @staticmethod
    def classify_forecast_alert(
        vehicle: Vehicle,
        forecast: MaintenanceForecast,
        today: date,
    ) -> Optional[Dict[str, Any]]:
        """
        Classifies a maintenance forecast into an alert tier.
        Returns alert classification dict or None if normal/optimal.

        Tiers:
        - Tier 1: OVERDUE (Critical) -> Desktop notification
        - Tier 2: DUE_SOON (Warning) -> Desktop notification
        - Tier 4: PACE_SURGE (Warning) -> In-app only (No desktop notification)
        - Tier 3: ADVANCE_NOTICE (Info) -> In-app only (No desktop notification)
        """
        f = forecast
        progress_pct = max(f.mileage_progress_pct, f.time_progress_pct)

        # Tier 1: OVERDUE
        if f.status == ServiceStatus.OVERDUE or f.miles_remaining <= 0 or f.days_remaining <= 0:
            overdue_by_mi = abs(f.miles_remaining)
            overdue_by_days = abs(f.days_remaining)
            msg = f"{f.service_name} is OVERDUE by {overdue_by_mi:,} mi ({overdue_by_days} days). Immediate service required."
            return {
                "status": "OVERDUE",
                "severity": "CRITICAL",
                "event_type": "MAINTENANCE_DUE",
                "title": f"🚨 OVERDUE: {vehicle.year} {vehicle.model} - {f.service_name}",
                "message": msg,
                "channel": NotificationChannel.LOCAL_DESKTOP,
                "progress_pct": progress_pct,
            }

        # Tier 2: DUE SOON
        if (
            f.status == ServiceStatus.DUE_SOON
            or f.miles_remaining <= settings.maintenance_due_soon_miles
            or f.days_remaining <= settings.maintenance_due_soon_days
        ):
            msg = f"{f.service_name} due soon in {f.miles_remaining:,} mi ({f.days_remaining} days)."
            return {
                "status": "DUE_SOON",
                "severity": "WARNING",
                "event_type": "MAINTENANCE_DUE",
                "title": f"⚠️ Due Soon: {vehicle.year} {vehicle.model} - {f.service_name}",
                "message": msg,
                "channel": NotificationChannel.LOCAL_DESKTOP,
                "progress_pct": progress_pct,
            }

        # Tier 4: PACE SURGE
        if f.approaching_faster and f.projected_due_date_by_mileage:
            days_until_projected = (f.projected_due_date_by_mileage - today).days
            days_until_calendar = (f.next_due_date - today).days if f.next_due_date else 999
            if (
                days_until_projected <= settings.maintenance_due_soon_days
                and days_until_calendar > settings.maintenance_due_soon_days
            ):
                msg = (
                    f"Increased driving pace detected for {f.service_name}: projected due in "
                    f"{f.miles_remaining:,} mi (~{days_until_projected} days), ahead of calendar schedule."
                )
                return {
                    "status": "RATE_SURGE",
                    "severity": "WARNING",
                    "event_type": "RATE_SURGE",
                    "title": f"📈 Driving Pace Surge: {vehicle.year} {vehicle.model} - {f.service_name}",
                    "message": msg,
                    "channel": NotificationChannel.IN_APP_LOG,  # In-app only per user rule
                    "progress_pct": progress_pct,
                }

        # Tier 3: ADVANCE NOTICE (80% consumed OR within 1,000 miles / 45 days)
        if (
            progress_pct >= settings.maintenance_advance_notice_pct
            or f.miles_remaining <= settings.maintenance_advance_notice_miles
            or f.days_remaining <= settings.maintenance_advance_notice_days
        ):
            msg = (
                f"Approaching milestone for {f.service_name} ({progress_pct:.0f}% consumed, "
                f"{f.miles_remaining:,} mi / {f.days_remaining} days remaining)."
            )
            return {
                "status": "ADVANCE_NOTICE",
                "severity": "INFO",
                "event_type": "ADVANCE_NOTICE",
                "title": f"Upcoming Service: {vehicle.year} {vehicle.model} - {f.service_name}",
                "message": msg,
                "channel": NotificationChannel.IN_APP_LOG,  # In-app only per user rule
                "progress_pct": progress_pct,
            }

        return None

    @staticmethod
    def evaluate_vehicle_alerts(
        session: Session,
        vehicle_id: int,
        current_date: Optional[date] = None,
        bypass_cooldown: bool = False,
    ) -> List[NotificationRecord]:
        """
        Evaluates all planned maintenance forecasts for a vehicle and dispatches
        appropriate tiered notifications (Desktop or In-App).
        """
        if current_date is None:
            current_date = date.today()

        vehicle = session.get(Vehicle, vehicle_id)
        if not vehicle:
            return []

        forecasts = MaintenanceIntervalEngine.calculate_forecasts(
            session=session,
            vehicle_id=vehicle_id,
            current_date=current_date,
        )

        dispatched: List[NotificationRecord] = []

        for f in forecasts:
            classification = MaintenanceAlertService.classify_forecast_alert(vehicle, f, current_date)
            if not classification:
                continue

            record = NotificationService.notify(
                session=session,
                title=classification["title"],
                message=classification["message"],
                event_type=classification["event_type"],
                vehicle_id=vehicle.id,
                entity_id=f.service_definition_id,
                channel=classification["channel"],
                severity=classification["severity"],
                bypass_cooldown=bypass_cooldown,
                cooldown_hours=settings.maintenance_alert_cooldown_hours,
            )
            if record:
                dispatched.append(record)

        return dispatched

    @staticmethod
    def evaluate_all_fleet_alerts(
        session: Session,
        current_date: Optional[date] = None,
        bypass_cooldown: bool = False,
    ) -> Dict[str, Any]:
        """
        Evaluates planned maintenance alerts across all fleet vehicles.
        """
        if current_date is None:
            current_date = date.today()

        vehicles = session.exec(select(Vehicle)).all()
        total_notifications = 0
        vehicle_results = {}

        for vehicle in vehicles:
            records = MaintenanceAlertService.evaluate_vehicle_alerts(
                session=session,
                vehicle_id=vehicle.id,
                current_date=current_date,
                bypass_cooldown=bypass_cooldown,
            )
            total_notifications += len(records)
            vehicle_results[vehicle.id] = {
                "name": f"{vehicle.year} {vehicle.make} {vehicle.model}",
                "notifications_dispatched": len(records),
            }

        return {
            "total_vehicles_evaluated": len(vehicles),
            "total_notifications_dispatched": total_notifications,
            "vehicle_breakdown": vehicle_results,
        }

    @staticmethod
    def get_active_maintenance_alerts(
        session: Session,
        vehicle_id: Optional[int] = None,
        current_date: Optional[date] = None,
    ) -> List[MaintenanceAlertItem]:
        """
        Returns all active maintenance alerts across the fleet (or for a specific vehicle),
        ordered by severity and urgency.
        """
        if current_date is None:
            current_date = date.today()

        if vehicle_id is not None:
            vehicles = [session.get(Vehicle, vehicle_id)]
            vehicles = [v for v in vehicles if v]
        else:
            vehicles = session.exec(select(Vehicle)).all()

        alerts: List[MaintenanceAlertItem] = []

        severity_rank = {
            "CRITICAL": 0,
            "WARNING": 1,
            "INFO": 2,
        }

        for vehicle in vehicles:
            forecasts = MaintenanceIntervalEngine.calculate_forecasts(
                session=session,
                vehicle_id=vehicle.id,
                current_date=current_date,
            )

            for f in forecasts:
                classification = MaintenanceAlertService.classify_forecast_alert(vehicle, f, current_date)
                if not classification:
                    continue

                alerts.append(
                    MaintenanceAlertItem(
                        vehicle_id=vehicle.id,
                        vehicle_name=f"{vehicle.year} {vehicle.make} {vehicle.model}",
                        service_definition_id=f.service_definition_id,
                        service_name=f.service_name,
                        status=classification["status"],
                        severity=classification["severity"],
                        title=classification["title"],
                        message=classification["message"],
                        miles_remaining=f.miles_remaining,
                        days_remaining=f.days_remaining,
                        next_due_mileage=f.next_due_mileage,
                        next_due_date=f.next_due_date,
                        progress_pct=classification["progress_pct"],
                        is_next_required=f.is_next_required,
                        channel=classification["channel"],
                    )
                )

        # Sort alerts: CRITICAL first, then WARNING, then INFO; within tier, by miles remaining ascending
        alerts.sort(
            key=lambda a: (
                severity_rank.get(a.severity, 99),
                a.miles_remaining,
                a.days_remaining,
            )
        )

        return alerts
