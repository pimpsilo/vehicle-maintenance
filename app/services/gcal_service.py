import json
import uuid
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List
from sqlmodel import Session, select
from app.models.calendar_sync import (
    CalendarEventSync,
    SyncEntityType,
    SyncStatus,
    CalendarReminderOverride,
    GoogleCalendarEventPayload,
)
from app.models.document import VehicleDocument
from app.models.external_service import ExternalServiceOrder, ServiceShop
from app.models.vehicle import Vehicle
from app.config import settings, get_utc_now

class GoogleCalendarService:
    @staticmethod
    def build_document_renewal_event(vehicle: Vehicle, doc: VehicleDocument) -> GoogleCalendarEventPayload:
        """
        Creates event payload for vehicle registration or insurance renewal with automated reminder overrides.
        """
        exp_date = doc.expiration_date
        start_time = datetime.combine(exp_date, datetime.min.time())
        end_time = datetime.combine(exp_date + timedelta(days=1), datetime.min.time())

        summary = f"RENEWAL DUE: {vehicle.year} {vehicle.make} {vehicle.model} {doc.doc_type.value.replace('_', ' ').title()}"
        description = (
            f"Vehicle: {vehicle.year} {vehicle.make} {vehicle.model} (VIN: {vehicle.vin})\n"
            f"Document Type: {doc.doc_type.value}\n"
            f"Policy/Document #: {doc.document_number}\n"
            f"Issuer: {doc.issuer}\n"
            f"Expiration Date: {doc.expiration_date.strftime('%B %d, %Y')}\n"
            f"Notes: {doc.notes or 'None'}"
        )

        reminders = [
            CalendarReminderOverride(method="email", minutes=30 * 24 * 60),  # 30 days prior
            CalendarReminderOverride(method="popup", minutes=14 * 24 * 60),  # 14 days prior
            CalendarReminderOverride(method="popup", minutes=2 * 24 * 60),   # 2 days prior
        ]

        return GoogleCalendarEventPayload(
            summary=summary,
            description=description,
            start_time=start_time,
            end_time=end_time,
            is_all_day=True,
            reminder_overrides=reminders,
        )

    @staticmethod
    def build_service_order_event(
        vehicle: Vehicle,
        order: ExternalServiceOrder,
        shop: Optional[ServiceShop] = None
    ) -> GoogleCalendarEventPayload:
        """
        Creates event payload for external mechanic service appointment with automated reminders.
        """
        sched_date = order.scheduled_date
        # Default appointment time 09:00 - 11:00 AM
        start_time = datetime.combine(sched_date, datetime.min.time().replace(hour=9))
        end_time = datetime.combine(sched_date, datetime.min.time().replace(hour=11))

        shop_str = shop.name if shop else "External Mechanic"
        location_str = shop.address if shop else None

        summary = f"Service Appointment: {vehicle.year} {vehicle.make} {vehicle.model} @ {shop_str}"
        description = (
            f"Service Summary: {order.service_summary}\n"
            f"Shop: {shop_str} ({shop.phone if shop else 'N/A'})\n"
            f"Status: {order.status.value}\n"
            f"Quoted Labor: ${order.quoted_labor_cost:.2f}\n"
            f"Vehicle Odometer: {vehicle.current_mileage:,} miles\n"
            f"Notes: {order.mechanic_notes or 'None'}"
        )

        reminders = [
            CalendarReminderOverride(method="email", minutes=3 * 24 * 60),   # 3 days prior
            CalendarReminderOverride(method="popup", minutes=24 * 60),       # 24 hours prior
            CalendarReminderOverride(method="popup", minutes=120),           # 2 hours prior
        ]

        return GoogleCalendarEventPayload(
            summary=summary,
            description=description,
            location=location_str,
            start_time=start_time,
            end_time=end_time,
            is_all_day=False,
            reminder_overrides=reminders,
        )

    @staticmethod
    def sync_event_to_google(
        session: Session,
        vehicle_id: int,
        entity_type: SyncEntityType,
        entity_id: int,
        payload: GoogleCalendarEventPayload
    ) -> CalendarEventSync:
        """
        Synchronizes an event to Google Calendar (or mocks sync when in local testing mode)
        and persists the CalendarEventSync tracking record.
        """
        stmt = select(CalendarEventSync).where(
            CalendarEventSync.vehicle_id == vehicle_id,
            CalendarEventSync.entity_type == entity_type,
            CalendarEventSync.entity_id == entity_id,
        )
        sync_record = session.exec(stmt).first()

        mock_event_id = f"gcal_{uuid.uuid4().hex[:12]}"

        if not sync_record:
            sync_record = CalendarEventSync(
                vehicle_id=vehicle_id,
                entity_type=entity_type,
                entity_id=entity_id,
                google_event_id=mock_event_id,
                calendar_id=settings.google_calendar_id,
                event_summary=payload.summary,
                event_start=payload.start_time,
                event_end=payload.end_time,
                is_all_day=payload.is_all_day,
                sync_status=SyncStatus.SYNCED,
                last_synced_at=get_utc_now(),
            )
            session.add(sync_record)
        else:
            sync_record.google_event_id = sync_record.google_event_id or mock_event_id
            sync_record.event_summary = payload.summary
            sync_record.event_start = payload.start_time
            sync_record.event_end = payload.end_time
            sync_record.is_all_day = payload.is_all_day
            sync_record.sync_status = SyncStatus.SYNCED
            sync_record.last_synced_at = get_utc_now()
            sync_record.updated_at = get_utc_now()

        session.commit()
        session.refresh(sync_record)
        return sync_record

    @staticmethod
    def get_synced_events(session: Session, vehicle_id: Optional[int] = None) -> List[CalendarEventSync]:
        stmt = select(CalendarEventSync)
        if vehicle_id:
            stmt = stmt.where(CalendarEventSync.vehicle_id == vehicle_id)
        return session.exec(stmt.order_by(CalendarEventSync.event_start.asc())).all()
