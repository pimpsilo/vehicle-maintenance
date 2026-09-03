from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlmodel import Session, select
from app.database import get_session
from app.config import settings
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


class OAuthCodeRequest(BaseModel):
    code: str
    redirect_uri: Optional[str] = None


@router.get("/status")
def get_calendar_status():
    """Returns Google Calendar connection and authorization state."""
    is_conn = GoogleCalendarService.is_connected()
    return {
        "connected": is_conn,
        "calendar_id": settings.google_calendar_id,
        "client_id_configured": bool(settings.google_client_id and "mock" not in settings.google_client_id),
        "token_file": settings.google_token_file,
    }


@router.get("/oauth/url")
def get_oauth_authorization_url(request: Request, redirect_uri: Optional[str] = None):
    """
    Returns the Google OAuth consent URL.
    Defaults redirect_uri to the current host or localhost callback.
    """
    if not redirect_uri:
        # Default to /api/v1/calendar/oauth/callback on current server or localhost
        base_url = str(request.base_url).rstrip("/")
        redirect_uri = f"{base_url}/api/v1/calendar/oauth/callback"

    auth_url = GoogleCalendarService.get_auth_url(redirect_uri=redirect_uri)
    return {"auth_url": auth_url, "redirect_uri": redirect_uri}


@router.get("/oauth/callback")
def oauth_callback(code: str, request: Request, state: Optional[str] = None):
    """
    Catches the authorization code callback from Google and exchanges it for tokens.
    """
    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/v1/calendar/oauth/callback"

    try:
        GoogleCalendarService.exchange_code_for_token(code=code, redirect_uri=redirect_uri)
        return RedirectResponse(url="/dashboard?status=gcal_connected", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth code exchange failed: {str(e)}")


@router.post("/oauth/code")
def exchange_manual_code(req: OAuthCodeRequest, request: Request):
    """
    Accepts an authorization code directly from the UI or CLI to complete OAuth setup.
    """
    redirect_uri = req.redirect_uri or f"{str(request.base_url).rstrip('/')}/api/v1/calendar/oauth/callback"
    try:
        token_data = GoogleCalendarService.exchange_code_for_token(code=req.code, redirect_uri=redirect_uri)
        return {"success": True, "message": "Google Calendar connected successfully!", "expires_in": token_data.get("expires_in")}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sync/all")
def sync_all_events(session: Session = Depends(get_session)):
    """
    Synchronizes all active vehicle documents and planned service orders to Google Calendar.
    """
    result = GoogleCalendarService.sync_all_upcoming(session)
    return result


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
