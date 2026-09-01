from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.models.vehicle import Vehicle
from app.models.notification import NotificationChannel
from app.services.notification_srv import NotificationService

def test_notification_dispatch_and_cooldown(session: Session, sample_vehicle: Vehicle):
    # 1. First notification should be dispatched and logged
    rec1 = NotificationService.notify(
        session=session,
        title="Test Alert",
        message="Registration renewal due in 10 days",
        event_type="DOCUMENT_EXPIRATION",
        vehicle_id=sample_vehicle.id,
        entity_id=101,
        channel=NotificationChannel.LOCAL_DESKTOP,
    )
    assert rec1 is not None
    assert rec1.is_delivered is True

    # 2. Second notification within cooldown window should be suppressed (return None)
    rec2 = NotificationService.notify(
        session=session,
        title="Test Alert",
        message="Registration renewal due in 10 days",
        event_type="DOCUMENT_EXPIRATION",
        vehicle_id=sample_vehicle.id,
        entity_id=101,
        channel=NotificationChannel.LOCAL_DESKTOP,
        bypass_cooldown=False,
    )
    assert rec2 is None

    # 3. With bypass_cooldown=True, it should dispatch
    rec3 = NotificationService.notify(
        session=session,
        title="Test Alert Forced",
        message="Forced alert",
        event_type="DOCUMENT_EXPIRATION",
        vehicle_id=sample_vehicle.id,
        entity_id=101,
        bypass_cooldown=True,
    )
    assert rec3 is not None

def test_notification_history_api(client: TestClient, sample_vehicle: Vehicle):
    test_res = client.post(
        "/api/v1/notifications/test",
        params={"title": "API Test Alert", "message": "API Notification body"}
    )
    assert test_res.status_code == 200

    hist_res = client.get("/api/v1/notifications/history")
    assert hist_res.status_code == 200
    records = hist_res.json()
    assert len(records) >= 1
    assert any(r["title"] == "API Test Alert" for r in records)
