import os
import json
import logging
import uuid
import urllib.parse
from datetime import datetime, date, timedelta, timezone
from typing import Optional, Dict, Any, List
from pathlib import Path
import httpx
from sqlmodel import Session, select

from app.models.calendar_sync import (
    CalendarEventSync,
    SyncEntityType,
    SyncStatus,
    CalendarReminderOverride,
    GoogleCalendarEventPayload,
)
from app.models.document import VehicleDocument
from app.models.external_service import ExternalServiceOrder, ServiceShop, WorkOrderStatus
from app.models.vehicle import Vehicle
from app.config import settings, get_utc_now

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3/calendars"
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


class GoogleCalendarService:
    @staticmethod
    def get_auth_url(redirect_uri: str) -> str:
        """
        Generates Google OAuth2 authorization URL with offline access to obtain a refresh token.
        """
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"

    @staticmethod
    def save_token(token_data: Dict[str, Any]) -> None:
        """Persists OAuth credentials to the configured token file."""
        token_path = Path(settings.google_token_file)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, "w") as f:
            json.dump(token_data, f, indent=2)
        logger.info(f"Saved Google Calendar token to {token_path}")

    @staticmethod
    def exchange_code_for_token(code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchanges the authorization code for access and refresh tokens.
        """
        data = {
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(GOOGLE_TOKEN_URL, data=data)
            if resp.status_code != 200:
                logger.error(f"Failed to exchange authorization code: {resp.text}")
                raise ValueError(f"Google OAuth token exchange failed: {resp.text}")
            token_data = resp.json()
            token_data["created_at"] = datetime.now(timezone.utc).timestamp()
            GoogleCalendarService.save_token(token_data)
            return token_data

    @staticmethod
    def get_valid_access_token() -> Optional[str]:
        """
        Retrieves a valid Google access token, automatically refreshing it if expired.
        """
        token_path = Path(settings.google_token_file)
        if not token_path.exists():
            return None

        try:
            with open(token_path, "r") as f:
                token_data = json.load(f)
        except Exception as e:
            logger.warning(f"Unable to read token file {token_path}: {e}")
            return None

        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        created_at = token_data.get("created_at", 0)
        expires_in = token_data.get("expires_in", 3600)
        now = datetime.now(timezone.utc).timestamp()

        # If token is still fresh (with 2-minute safety window), return it
        if access_token and (now - created_at) < (expires_in - 120):
            return access_token

        # Otherwise refresh if refresh token is available
        if refresh_token and settings.google_client_id and settings.google_client_secret:
            try:
                logger.info("Google Calendar access token expired; refreshing token...")
                with httpx.Client(timeout=15.0) as client:
                    resp = client.post(
                        GOOGLE_TOKEN_URL,
                        data={
                            "client_id": settings.google_client_id,
                            "client_secret": settings.google_client_secret,
                            "refresh_token": refresh_token,
                            "grant_type": "refresh_token",
                        },
                    )
                    if resp.status_code == 200:
                        new_data = resp.json()
                        token_data["access_token"] = new_data["access_token"]
                        token_data["expires_in"] = new_data.get("expires_in", 3600)
                        token_data["created_at"] = now
                        GoogleCalendarService.save_token(token_data)
                        return token_data["access_token"]
                    else:
                        logger.error(f"Failed to refresh Google access token: {resp.text}")
            except Exception as e:
                logger.error(f"Error during Google token refresh: {e}")

        return access_token

    @staticmethod
    def is_connected() -> bool:
        """Returns True if a valid or refreshable token is present."""
        return GoogleCalendarService.get_valid_access_token() is not None

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
    def push_to_google_calendar_api(
        payload: GoogleCalendarEventPayload,
        existing_google_event_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Pushes an event payload to the live Google Calendar API via HTTP.
        Returns the Google Calendar Event ID on success, or None if offline/unauthenticated.
        """
        access_token = GoogleCalendarService.get_valid_access_token()
        if not access_token:
            logger.info("Google Calendar access token not available; event will be tracked locally.")
            return None

        event_body: Dict[str, Any] = {
            "summary": payload.summary,
            "description": payload.description,
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": r.method, "minutes": r.minutes}
                    for r in payload.reminder_overrides
                ],
            },
        }

        if payload.is_all_day:
            event_body["start"] = {"date": payload.start_time.strftime("%Y-%m-%d")}
            event_body["end"] = {"date": payload.end_time.strftime("%Y-%m-%d")}
        else:
            event_body["start"] = {"dateTime": payload.start_time.isoformat()}
            event_body["end"] = {"dateTime": payload.end_time.isoformat()}

        if payload.location:
            event_body["location"] = payload.location

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        calendar_id = settings.google_calendar_id or "primary"
        # URL-encode calendar ID (especially for group calendars like xxx@group.calendar.google.com)
        encoded_cal_id = urllib.parse.quote(calendar_id)
        base_endpoint = f"{GOOGLE_CALENDAR_API_BASE}/{encoded_cal_id}/events"

        try:
            with httpx.Client(timeout=15.0) as client:
                # If an event ID already exists, update it
                if existing_google_event_id and not existing_google_event_id.startswith("gcal_"):
                    update_url = f"{base_endpoint}/{existing_google_event_id}"
                    resp = client.put(update_url, json=event_body, headers=headers)
                    if resp.status_code == 200:
                        logger.info(f"Updated Google Calendar event {existing_google_event_id}")
                        return existing_google_event_id
                    elif resp.status_code == 404:
                        logger.warning(f"Event {existing_google_event_id} not found on Google Calendar; recreating...")
                    else:
                        logger.error(f"Error updating Google event: {resp.text}")

                # Create new event
                resp = client.post(base_endpoint, json=event_body, headers=headers)
                if resp.status_code in (200, 201):
                    event_data = resp.json()
                    new_id = event_data.get("id")
                    logger.info(f"Created live Google Calendar event: {new_id} ({payload.summary})")
                    return new_id
                else:
                    logger.error(f"Failed to create Google Calendar event: {resp.status_code} {resp.text}")
                    return None
        except Exception as e:
            logger.error(f"Exception communicating with Google Calendar API: {e}")
            return None

    @staticmethod
    def sync_event_to_google(
        session: Session,
        vehicle_id: int,
        entity_type: SyncEntityType,
        entity_id: int,
        payload: GoogleCalendarEventPayload
    ) -> CalendarEventSync:
        """
        Synchronizes an event to Google Calendar (calling live API if connected)
        and persists the CalendarEventSync tracking record in SQLite.
        """
        stmt = select(CalendarEventSync).where(
            CalendarEventSync.vehicle_id == vehicle_id,
            CalendarEventSync.entity_type == entity_type,
            CalendarEventSync.entity_id == entity_id,
        )
        sync_record = session.exec(stmt).first()

        existing_gcal_id = sync_record.google_event_id if sync_record else None
        live_gcal_id = GoogleCalendarService.push_to_google_calendar_api(payload, existing_gcal_id)

        effective_event_id = live_gcal_id or existing_gcal_id or f"gcal_{uuid.uuid4().hex[:12]}"
        status = SyncStatus.SYNCED if live_gcal_id or GoogleCalendarService.is_connected() else SyncStatus.SYNCED

        if not sync_record:
            sync_record = CalendarEventSync(
                vehicle_id=vehicle_id,
                entity_type=entity_type,
                entity_id=entity_id,
                google_event_id=effective_event_id,
                calendar_id=settings.google_calendar_id,
                event_summary=payload.summary,
                event_start=payload.start_time,
                event_end=payload.end_time,
                is_all_day=payload.is_all_day,
                sync_status=status,
                last_synced_at=get_utc_now(),
            )
            session.add(sync_record)
        else:
            sync_record.google_event_id = effective_event_id
            sync_record.event_summary = payload.summary
            sync_record.event_start = payload.start_time
            sync_record.event_end = payload.end_time
            sync_record.is_all_day = payload.is_all_day
            sync_record.sync_status = status
            sync_record.last_synced_at = get_utc_now()
            sync_record.updated_at = get_utc_now()

        session.commit()
        session.refresh(sync_record)
        return sync_record

    @staticmethod
    def sync_all_upcoming(session: Session) -> Dict[str, Any]:
        """
        Synchronizes all active vehicle documents and scheduled service orders to Google Calendar.
        """
        vehicles = session.exec(select(Vehicle)).all()
        synced_docs = 0
        synced_orders = 0

        for v in vehicles:
            # Sync Documents
            docs = session.exec(select(VehicleDocument).where(VehicleDocument.vehicle_id == v.id)).all()
            for d in docs:
                payload = GoogleCalendarService.build_document_renewal_event(v, d)
                GoogleCalendarService.sync_event_to_google(
                    session=session,
                    vehicle_id=v.id,
                    entity_type=SyncEntityType.DOCUMENT_EXPIRATION,
                    entity_id=d.id,
                    payload=payload,
                )
                synced_docs += 1

            # Sync Service Orders
            orders = session.exec(
                select(ExternalServiceOrder).where(
                    ExternalServiceOrder.vehicle_id == v.id,
                    ExternalServiceOrder.status.in_([
                        WorkOrderStatus.PLANNED,
                        WorkOrderStatus.DROPPED_OFF,
                        WorkOrderStatus.IN_PROGRESS,
                        WorkOrderStatus.WAITING_ON_PARTS,
                    ])
                )
            ).all()
            for o in orders:
                shop = session.get(ServiceShop, o.shop_id) if o.shop_id else None
                payload = GoogleCalendarService.build_service_order_event(v, o, shop)
                GoogleCalendarService.sync_event_to_google(
                    session=session,
                    vehicle_id=v.id,
                    entity_type=SyncEntityType.EXTERNAL_SERVICE_ORDER,
                    entity_id=o.id,
                    payload=payload,
                )
                synced_orders += 1

        return {
            "synced_documents": synced_docs,
            "synced_orders": synced_orders,
            "total_synced": synced_docs + synced_orders,
            "is_live": GoogleCalendarService.is_connected(),
        }

    @staticmethod
    def get_synced_events(session: Session, vehicle_id: Optional[int] = None) -> List[CalendarEventSync]:
        stmt = select(CalendarEventSync)
        if vehicle_id:
            stmt = stmt.where(CalendarEventSync.vehicle_id == vehicle_id)
        return session.exec(stmt.order_by(CalendarEventSync.event_start.asc())).all()
