from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.models.vehicle import Vehicle
from app.models.document import VehicleDocument, DocumentType
from app.models.external_service import ServiceShop, ExternalServiceOrder, WorkOrderStatus
from app.services.gcal_service import GoogleCalendarService

def test_google_calendar_event_builders(session: Session, sample_vehicle: Vehicle):
    today = date.today()

    # 1. Document Renewal Event Builder
    doc = VehicleDocument(
        vehicle_id=sample_vehicle.id,
        doc_type=DocumentType.REGISTRATION,
        document_number="REG-2014-99",
        issuer="DMV",
        effective_date=today - timedelta(days=300),
        expiration_date=today + timedelta(days=30),
    )
    doc_payload = GoogleCalendarService.build_document_renewal_event(sample_vehicle, doc)
    assert "RENEWAL DUE" in doc_payload.summary
    assert "Toyota Avalon" in doc_payload.summary
    assert doc_payload.is_all_day is True
    assert len(doc_payload.reminder_overrides) == 3
    # Check 30-day reminder (43,200 min)
    assert any(r.minutes == 30 * 24 * 60 for r in doc_payload.reminder_overrides)

    # 2. External Service Order Event Builder
    shop = ServiceShop(
        name="Apex Japanese Auto",
        phone="555-0100",
        address="123 Mechanics St",
    )
    order = ExternalServiceOrder(
        vehicle_id=sample_vehicle.id,
        shop_id=1,
        service_summary="Spark Plug Replacement",
        scheduled_date=today + timedelta(days=10),
        status=WorkOrderStatus.PLANNED,
        quoted_labor_cost=200.0,
    )
    order_payload = GoogleCalendarService.build_service_order_event(sample_vehicle, order, shop)
    assert "Service Appointment" in order_payload.summary
    assert "Apex Japanese Auto" in order_payload.summary
    assert order_payload.location == "123 Mechanics St"
    assert len(order_payload.reminder_overrides) == 3
    # Check 24-hour reminder (1,440 min) and 2-hour reminder (120 min)
    assert any(r.minutes == 1440 for r in order_payload.reminder_overrides)
    assert any(r.minutes == 120 for r in order_payload.reminder_overrides)

def test_calendar_sync_api_endpoints(client: TestClient, sample_vehicle: Vehicle):
    today = date.today()

    # Create document
    doc_res = client.post(
        "/api/v1/documents",
        json={
            "vehicle_id": sample_vehicle.id,
            "doc_type": "INSURANCE",
            "document_number": "POL-992288",
            "issuer": "Geico",
            "effective_date": today.isoformat(),
            "expiration_date": (today + timedelta(days=180)).isoformat(),
            "lead_alert_days": 30
        }
    )
    doc_id = doc_res.json()["id"]

    # Sync document to calendar
    sync_res = client.post(f"/api/v1/calendar/sync/document/{doc_id}")
    assert sync_res.status_code == 200
    sync_data = sync_res.json()
    assert sync_data["sync_status"] == "SYNCED"
    assert sync_data["google_event_id"] is not None

    # List synced events
    events_res = client.get(f"/api/v1/calendar/events?vehicle_id={sample_vehicle.id}")
    assert events_res.status_code == 200
    assert len(events_res.json()) >= 1
