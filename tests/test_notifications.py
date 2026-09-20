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

def test_maintenance_alert_tiers(session: Session, sample_vehicle: Vehicle):
    from datetime import date
    from app.models.maintenance import MaintenanceForecast, ServiceStatus
    from app.services.maintenance_alert_srv import MaintenanceAlertService

    today = date.today()

    # Tier 1: Overdue -> CRITICAL + LOCAL_DESKTOP
    overdue_forecast = MaintenanceForecast(
        service_definition_id=1,
        service_name="Engine Oil & Filter Change",
        interval_miles=10000,
        interval_months=12,
        current_mileage=sample_vehicle.current_mileage,
        next_due_mileage=sample_vehicle.current_mileage - 100,
        next_due_date=today - timedelta(days=5),
        projected_due_date_by_mileage=today - timedelta(days=5),
        miles_remaining=-100,
        days_remaining=-5,
        status=ServiceStatus.OVERDUE,
        action_summary="OVERDUE by 100 miles",
    )
    c1 = MaintenanceAlertService.classify_forecast_alert(sample_vehicle, overdue_forecast, today)
    assert c1 is not None
    assert c1["severity"] == "CRITICAL"
    assert c1["channel"] == NotificationChannel.LOCAL_DESKTOP
    assert "OVERDUE" in c1["title"]

    # Tier 2: Due Soon -> WARNING + LOCAL_DESKTOP
    due_soon_forecast = MaintenanceForecast(
        service_definition_id=2,
        service_name="Tire Rotation",
        interval_miles=5000,
        interval_months=6,
        current_mileage=sample_vehicle.current_mileage,
        next_due_mileage=sample_vehicle.current_mileage + 300,
        next_due_date=today + timedelta(days=15),
        projected_due_date_by_mileage=today + timedelta(days=15),
        miles_remaining=300,
        days_remaining=15,
        status=ServiceStatus.DUE_SOON,
        action_summary="Due in 300 miles",
    )
    c2 = MaintenanceAlertService.classify_forecast_alert(sample_vehicle, due_soon_forecast, today)
    assert c2 is not None
    assert c2["severity"] == "WARNING"
    assert c2["channel"] == NotificationChannel.LOCAL_DESKTOP
    assert "Due Soon" in c2["title"]

    # Tier 3: Advance Notice (80% / 1000 mi) -> INFO + IN_APP_LOG (No Desktop Popup per user rule)
    advance_forecast = MaintenanceForecast(
        service_definition_id=3,
        service_name="Cabin Air Filter",
        interval_miles=15000,
        interval_months=12,
        current_mileage=sample_vehicle.current_mileage,
        next_due_mileage=sample_vehicle.current_mileage + 850,
        next_due_date=today + timedelta(days=35),
        projected_due_date_by_mileage=today + timedelta(days=35),
        miles_remaining=850,
        days_remaining=35,
        mileage_progress_pct=85.0,
        status=ServiceStatus.OK,
        action_summary="850 miles remaining",
    )
    c3 = MaintenanceAlertService.classify_forecast_alert(sample_vehicle, advance_forecast, today)
    assert c3 is not None
    assert c3["severity"] == "INFO"
    assert c3["channel"] == NotificationChannel.IN_APP_LOG
    assert "Upcoming Service" in c3["title"]

    # Tier 4: Pace Surge -> WARNING + IN_APP_LOG (No Desktop Popup per user rule)
    surge_forecast = MaintenanceForecast(
        service_definition_id=4,
        service_name="Transmission Fluid Drain & Fill",
        interval_miles=60000,
        interval_months=60,
        current_mileage=sample_vehicle.current_mileage,
        next_due_mileage=sample_vehicle.current_mileage + 2000,
        next_due_date=today + timedelta(days=90),
        projected_due_date_by_mileage=today + timedelta(days=20),
        miles_remaining=2000,
        days_remaining=90,
        approaching_faster=True,
        status=ServiceStatus.OK,
        action_summary="Projected sooner by mileage",
    )
    c4 = MaintenanceAlertService.classify_forecast_alert(sample_vehicle, surge_forecast, today)
    assert c4 is not None
    assert c4["severity"] == "WARNING"
    assert c4["channel"] == NotificationChannel.IN_APP_LOG
    assert "Driving Pace Surge" in c4["title"]

def test_per_vehicle_cooldown_scoping(session: Session, sample_vehicle: Vehicle):
    # Create second vehicle
    vehicle2 = Vehicle(
        year=2016,
        make="Buick",
        model="Cascada",
        vin="1G4GG16X0G4199999",
        current_mileage=24000,
        estimated_annual_mileage=6000,
    )
    session.add(vehicle2)
    session.commit()
    session.refresh(vehicle2)

    # 1. Alert for Vehicle 1 (entity_id=1, e.g. Oil Change)
    r1 = NotificationService.notify(
        session=session,
        title="Oil Change Vehicle 1",
        message="Overdue",
        event_type="MAINTENANCE_DUE",
        vehicle_id=sample_vehicle.id,
        entity_id=1,
    )
    assert r1 is not None

    # 2. Alert for Vehicle 2 with the SAME entity_id (1) should NOT be suppressed
    r2 = NotificationService.notify(
        session=session,
        title="Oil Change Vehicle 2",
        message="Due Soon",
        event_type="MAINTENANCE_DUE",
        vehicle_id=vehicle2.id,
        entity_id=1,
    )
    assert r2 is not None, "Vehicle 2 alert was mistakenly suppressed by Vehicle 1 alert!"

    # 3. Repeated alert for Vehicle 1 SHOULD be suppressed by cooldown
    r3 = NotificationService.notify(
        session=session,
        title="Oil Change Vehicle 1 Repeat",
        message="Overdue",
        event_type="MAINTENANCE_DUE",
        vehicle_id=sample_vehicle.id,
        entity_id=1,
    )
    assert r3 is None, "Repeated alert for same vehicle should be suppressed"

def test_active_alerts_and_evaluate_all_api(client: TestClient, sample_vehicle: Vehicle):
    # Call GET /api/v1/notifications/alerts
    res = client.get("/api/v1/notifications/alerts")
    assert res.status_code == 200
    alerts = res.json()
    assert isinstance(alerts, list)

    # Call POST /api/v1/notifications/evaluate-all
    eval_res = client.post("/api/v1/notifications/evaluate-all?bypass_cooldown=true")
    assert eval_res.status_code == 200
    eval_data = eval_res.json()
    assert "result" in eval_data
    assert "total_vehicles_evaluated" in eval_data["result"]
