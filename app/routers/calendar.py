from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from app.database import get_session
from app.models.calendar_sync import (
    CalendarEventSync,
    CalendarEventSyncRead,
    SyncEntityType,
)
from app.models.document import VehicleDocument
from app.models.external_service import ExternalServiceOrder, ServiceShop
from app.models.vehicle import Vehicle
from app.services.gcal_service import GoogleCalendarService

router = APIRouter(prefix="/api/v1/calendar", tags=["Google Calendar Integration"])

@router.get("/events", response_model=List[CalendarEventSyncRead])
def list_synced_events(
    vehicle_id: Optional[int] = Query(None, description="Filter by vehicle ID"),
    session: Session = Depends(get_session)
):
    return GoogleCalendarService.get_synced_events(session, vehicle_id=vehicle_id)

@router.post("/sync/document/{document_id}", response_model=CalendarEventSyncRead)
def sync_document_to_calendar(document_id: int, session: Session = Depends(get_session)):
    doc = session.get(VehicleDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    vehicle = session.get(Vehicle, doc.vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found.")

    payload = GoogleCalendarService.build_document_renewal_event(vehicle, doc)
    sync_record = GoogleCalendarService.sync_event_to_google(
        session=session,
        vehicle_id=vehicle.id,
        entity_type=SyncEntityType.DOCUMENT_EXPIRATION,
        entity_id=doc.id,
        payload=payload,
    )
    return sync_record

@router.post("/sync/service-order/{order_id}", response_model=CalendarEventSyncRead)
def sync_service_order_to_calendar(order_id: int, session: Session = Depends(get_session)):
    order = session.get(ExternalServiceOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Service order not found.")

    vehicle = session.get(Vehicle, order.vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found.")

    shop = session.get(ServiceShop, order.shop_id) if order.shop_id else None
    payload = GoogleCalendarService.build_service_order_event(vehicle, order, shop)

    sync_record = GoogleCalendarService.sync_event_to_google(
        session=session,
        vehicle_id=vehicle.id,
        entity_type=SyncEntityType.EXTERNAL_SERVICE_ORDER,
        entity_id=order.id,
        payload=payload,
    )
    return sync_record
