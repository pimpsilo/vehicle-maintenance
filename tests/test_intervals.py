from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.models.vehicle import Vehicle
from app.models.maintenance import (
    ServiceDefinition,
    ServiceRecord,
    ServiceStatus,
    PerformedByType,
)
from app.services.interval_engine import MaintenanceIntervalEngine

def test_maintenance_forecast_calculations(session: Session, sample_vehicle: Vehicle):
    today = date.today()
    # sample_vehicle has 105,000 miles

    # Create service definition: Oil Change 10,000 mi / 12 mo
    sdef_oil = ServiceDefinition(
        service_name="Engine Oil & Filter",
        interval_miles=10000,
        interval_months=12,
    )
    session.add(sdef_oil)
    session.commit()
    session.refresh(sdef_oil)

    # 1. No service history -> next due at 10,000 mi -> OVERDUE since current is 105,000
    forecasts = MaintenanceIntervalEngine.calculate_forecasts(session, sample_vehicle.id, current_date=today)
    assert len(forecasts) == 1
    assert forecasts[0].status == ServiceStatus.OVERDUE
    assert forecasts[0].miles_remaining == 10000 - 105000  # negative

    # 2. Add service record completed at 100,000 miles (5,000 mi ago)
    record = ServiceRecord(
        vehicle_id=sample_vehicle.id,
        service_definition_id=sdef_oil.id,
        service_name=sdef_oil.service_name,
        completed_date=today - timedelta(days=60),
        completed_mileage=100000,
        performed_by_type=PerformedByType.DIY,
    )
    session.add(record)
    session.commit()

    # Now next due is at 110,000 miles -> 5,000 miles remaining -> OK
    forecasts2 = MaintenanceIntervalEngine.calculate_forecasts(session, sample_vehicle.id, current_date=today)
    assert len(forecasts2) == 1
    assert forecasts2[0].status == ServiceStatus.OK
    assert forecasts2[0].miles_remaining == 5000
    assert forecasts2[0].next_due_mileage == 110000

    # 3. Update vehicle current mileage to 109,700 (300 miles remaining -> DUE_SOON)
    sample_vehicle.current_mileage = 109700
    session.add(sample_vehicle)
    session.commit()

    forecasts3 = MaintenanceIntervalEngine.calculate_forecasts(session, sample_vehicle.id, current_date=today)
    assert len(forecasts3) == 1
    assert forecasts3[0].status == ServiceStatus.DUE_SOON
    assert forecasts3[0].miles_remaining == 300

def test_maintenance_api_endpoints(client: TestClient, sample_vehicle: Vehicle):
    today = date.today()
    # Create service definition via API
    sdef_res = client.post(
        "/api/v1/maintenance/definitions",
        json={
            "service_name": "Brake Fluid Flush",
            "interval_miles": 30000,
            "interval_months": 36
        }
    )
    assert sdef_res.status_code == 201
    sdef_id = sdef_res.json()["id"]

    # Log service record via API
    rec_res = client.post(
        "/api/v1/maintenance/records",
        json={
            "vehicle_id": sample_vehicle.id,
            "service_definition_id": sdef_id,
            "service_name": "Brake Fluid Flush",
            "completed_date": today.isoformat(),
            "completed_mileage": sample_vehicle.current_mileage,
            "labor_cost": 80.0,
            "parts_cost": 25.0
        }
    )
    assert rec_res.status_code == 201
    assert rec_res.json()["total_cost"] == 105.0

    # Check forecast endpoint
    forecast_res = client.get(f"/api/v1/maintenance/forecast/{sample_vehicle.id}")
    assert forecast_res.status_code == 200
    forecast_list = forecast_res.json()
    assert any(f["service_name"] == "Brake Fluid Flush" for f in forecast_list)

def test_update_service_record(client: TestClient, sample_vehicle: Vehicle):
    # 1. Create a service record
    create_res = client.post(
        "/api/v1/maintenance/records",
        json={
            "vehicle_id": sample_vehicle.id,
            "service_name": "Cabin Air Filter Replacement",
            "completed_date": date.today().isoformat(),
            "completed_mileage": 105100,
            "performed_by_type": "DIY",
            "parts_cost": 15.00
        }
    )
    assert create_res.status_code == 201
    rec_id = create_res.json()["id"]
    assert create_res.json()["service_name"] == "Cabin Air Filter Replacement"
    assert create_res.json()["total_cost"] == 15.00

    # 2. Update the record (change service name, mileage, labor cost, notes)
    update_res = client.put(
        f"/api/v1/maintenance/records/{rec_id}",
        json={
            "service_name": "Cabin & Engine Air Filter Replacement",
            "completed_mileage": 105200,
            "parts_cost": 30.00,
            "labor_cost": 0.00,
            "notes": "Replaced both filters with OEM Denso elements"
        }
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["service_name"] == "Cabin & Engine Air Filter Replacement"
    assert updated["completed_mileage"] == 105200
    assert updated["total_cost"] == 30.00
    assert updated["notes"] == "Replaced both filters with OEM Denso elements"

    # 3. Retrieve individual record
    get_res = client.get(f"/api/v1/maintenance/records/{rec_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == rec_id
    assert get_res.json()["service_name"] == "Cabin & Engine Air Filter Replacement"

def test_acknowledge_overdue_maintenance(client: TestClient, sample_vehicle: Vehicle):
    # 1. Create a service definition with 10k interval
    sdef_res = client.post(
        "/api/v1/maintenance/definitions",
        json={
            "service_name": "Tire Rotation & Balance",
            "interval_miles": 5000,
            "interval_months": 6
        }
    )
    assert sdef_res.status_code == 201
    sdef_id = sdef_res.json()["id"]

    # 2. Before acknowledge, next due mileage is at 5,000 miles, so for vehicle at 105,000 it is OVERDUE
    forecast_before = client.get(f"/api/v1/maintenance/forecast/{sample_vehicle.id}").json()
    f_item = next(f for f in forecast_before if f["service_definition_id"] == sdef_id)
    assert f_item["status"] == "OVERDUE"

    # 3. Acknowledge at current odometer (105,000 miles)
    ack_res = client.post(
        "/api/v1/maintenance/acknowledge",
        json={
            "vehicle_id": sample_vehicle.id,
            "service_definition_id": sdef_id,
            "completed_mileage": sample_vehicle.current_mileage,
            "notes": "Acknowledged baseline without receipts"
        }
    )
    assert ack_res.status_code == 201
    assert ack_res.json()["completed_mileage"] == sample_vehicle.current_mileage
    assert ack_res.json()["total_cost"] == 0.0

    # 4. After acknowledge, next due is 105,000 + 5,000 = 110,000 miles -> status is now OK!
    forecast_after = client.get(f"/api/v1/maintenance/forecast/{sample_vehicle.id}").json()
    f_after_item = next(f for f in forecast_after if f["service_definition_id"] == sdef_id)
    assert f_after_item["status"] == "OK"
    assert f_after_item["next_due_mileage"] == 110000
    assert f_after_item["miles_remaining"] == 5000

def test_observed_rate_forecasting_and_surge(session: Session, sample_vehicle: Vehicle):
    from datetime import datetime, timezone
    from app.models.vehicle import OdometerEntry

    today = date.today()
    sdef = ServiceDefinition(
        service_name="Transmission Fluid Service",
        interval_miles=10000,
        interval_months=24,
    )
    session.add(sdef)
    session.commit()
    session.refresh(sdef)

    # 1. Without history: source is estimated, approaching_faster is False
    fc_init = MaintenanceIntervalEngine.calculate_forecasts(session, sample_vehicle.id, current_date=today)
    item_init = next(f for f in fc_init if f.service_definition_id == sdef.id)
    assert item_init.accrual_rate_source == "estimated"
    assert item_init.approaching_faster is False

    # 2. Add recent completed service to make status OK (5,000 miles remaining)
    rec = ServiceRecord(
        vehicle_id=sample_vehicle.id,
        service_definition_id=sdef.id,
        service_name=sdef.service_name,
        completed_date=today - timedelta(days=30),
        completed_mileage=100000,
        performed_by_type=PerformedByType.DIY,
    )
    session.add(rec)
    session.commit()

    # 3. Add high-rate odometer entries over 30 days (100 miles/day vs ~33 miles/day estimate)
    # 30 days ago: 102,000 -> today: 105,000 (3,000 mi in 30 days = 100 mi/day, +204% over 12k/yr)
    now = datetime.now(timezone.utc)
    e1 = OdometerEntry(vehicle_id=sample_vehicle.id, mileage=102000, recorded_at=now - timedelta(days=30))
    e2 = OdometerEntry(vehicle_id=sample_vehicle.id, mileage=105000, recorded_at=now)
    session.add_all([e1, e2])
    session.commit()

    fc_surge = MaintenanceIntervalEngine.calculate_forecasts(session, sample_vehicle.id, current_date=today)
    item_surge = next(f for f in fc_surge if f.service_definition_id == sdef.id)
    assert item_surge.accrual_rate_source == "observed"
    assert item_surge.accrual_rate_mpd >= 90.0
    assert item_surge.rate_delta_pct > 25.0
    assert item_surge.approaching_faster is True
    assert "above plan" in item_surge.action_summary

def test_scheduler_rate_surge_notification(session: Session, sample_vehicle: Vehicle):
    from datetime import datetime, timezone
    from sqlmodel import select
    from app.models.vehicle import OdometerEntry
    from app.models.notification import NotificationRecord
    from app.services.scheduler_srv import run_scheduled_checks

    today = date.today()
    # 1. Create a service definition with 5,000 mi interval, 12 months (calendar far away)
    sdef = ServiceDefinition(
        service_name="Differential Gear Oil",
        interval_miles=5000,
        interval_months=12,
    )
    session.add(sdef)
    session.commit()
    session.refresh(sdef)

    # 2. Service completed 30 days ago at 102,500 mi (next due at 107,500 mi)
    # Remaining miles: 107,500 - 105,000 = 2,500 mi
    rec = ServiceRecord(
        vehicle_id=sample_vehicle.id,
        service_definition_id=sdef.id,
        service_name=sdef.service_name,
        completed_date=today - timedelta(days=30),
        completed_mileage=102500,
        performed_by_type=PerformedByType.DIY,
    )
    session.add(rec)
    session.commit()

    # 3. Add heavy driving history: 100 mi/day over 30 days
    # At 100 mi/day, 2,500 miles will be covered in 25 days (<= 30 days due-soon threshold)
    # Calendar date is 11 months away (> 30 days)
    now = datetime.now(timezone.utc)
    e1 = OdometerEntry(vehicle_id=sample_vehicle.id, mileage=102000, recorded_at=now - timedelta(days=30))
    e2 = OdometerEntry(vehicle_id=sample_vehicle.id, mileage=105000, recorded_at=now)
    session.add_all([e1, e2])
    session.commit()

    # 4. Trigger scheduled checks
    run_scheduled_checks(session=session)

    # 5. Verify RATE_SURGE notification was recorded
    surge_notifications = session.exec(
        select(NotificationRecord).where(
            NotificationRecord.vehicle_id == sample_vehicle.id,
            NotificationRecord.event_type == "RATE_SURGE"
        )
    ).all()
    assert len(surge_notifications) >= 1
    assert "Driving Pace Surge" in surge_notifications[0].title

def test_next_required_flag_and_progress_math(session: Session, sample_vehicle: Vehicle):
    today = date.today()
    # Create two service definitions: Oil Change (5k) and Spark Plugs (100k)
    s1 = ServiceDefinition(service_name="Engine Oil & Filter", interval_miles=5000, interval_months=6, category="LUBRICATION")
    s2 = ServiceDefinition(service_name="Spark Plugs", interval_miles=100000, interval_months=120, category="IGNITION")
    session.add_all([s1, s2])
    session.commit()

    # Log service for oil change 2,500 miles ago
    r1 = ServiceRecord(
        vehicle_id=sample_vehicle.id,
        service_definition_id=s1.id,
        service_name=s1.service_name,
        completed_date=today - timedelta(days=90),
        completed_mileage=sample_vehicle.current_mileage - 2500,
        performed_by_type=PerformedByType.DIY,
    )
    # Log service for spark plugs at 100,000 miles (5,000 miles ago)
    r2 = ServiceRecord(
        vehicle_id=sample_vehicle.id,
        service_definition_id=s2.id,
        service_name=s2.service_name,
        completed_date=today - timedelta(days=90),
        completed_mileage=100000,
        performed_by_type=PerformedByType.DIY,
    )
    session.add_all([r1, r2])
    session.commit()

    forecasts = MaintenanceIntervalEngine.calculate_forecasts(session, sample_vehicle.id, current_date=today)
    assert len(forecasts) == 2
    
    # Oil change has 2,500 miles left; Spark plugs has 95,000 miles left
    # Oil change must be next required
    top = forecasts[0]
    assert top.service_name == "Engine Oil & Filter"
    assert top.is_next_required is True
    assert top.urgency_rank == 1
    assert top.miles_remaining == 2500
    assert top.mileage_progress_pct == 50.0
    assert top.dominant_threshold in ("MILEAGE", "CALENDAR")

    second = forecasts[1]
    assert second.service_name == "Spark Plugs"
    assert second.is_next_required is False
    assert second.urgency_rank == 2

def test_vehicle_specific_service_definition_override(session: Session, sample_vehicle: Vehicle):
    # Global oil change definition is 10,000 miles
    global_def = ServiceDefinition(vehicle_id=None, service_name="Engine Oil & Filter", interval_miles=10000, interval_months=12, category="LUBRICATION")
    # Vehicle-specific oil change definition is 5,000 miles
    vehicle_def = ServiceDefinition(vehicle_id=sample_vehicle.id, service_name="Engine Oil & Filter (dexos1)", interval_miles=5000, interval_months=6, category="LUBRICATION")
    session.add_all([global_def, vehicle_def])
    session.commit()

    forecasts = MaintenanceIntervalEngine.calculate_forecasts(session, sample_vehicle.id)
    # Should only have 1 oil forecast because vehicle-specific overrides global
    oil_forecasts = [f for f in forecasts if "oil" in f.service_name.lower()]
    assert len(oil_forecasts) == 1
    assert oil_forecasts[0].service_definition_id == vehicle_def.id
    assert oil_forecasts[0].interval_miles == 5000

def test_unlinked_service_record_fuzzy_matching(session: Session, sample_vehicle: Vehicle):
    today = date.today()
    sdef = ServiceDefinition(vehicle_id=sample_vehicle.id, service_name="Engine Oil & Filter Change", interval_miles=5000, interval_months=6, category="LUBRICATION")
    session.add(sdef)
    session.commit()

    # Record logged without service_definition_id (e.g. Carfax import or external shop)
    unlinked_rec = ServiceRecord(
        vehicle_id=sample_vehicle.id,
        service_definition_id=None,
        service_name="Oil & Filter Change",
        completed_date=today - timedelta(days=30),
        completed_mileage=sample_vehicle.current_mileage - 1000,
        performed_by_type=PerformedByType.EXTERNAL_SHOP,
    )
    session.add(unlinked_rec)
    session.commit()

    forecasts = MaintenanceIntervalEngine.calculate_forecasts(session, sample_vehicle.id, current_date=today)
    oil_f = next(f for f in forecasts if f.service_definition_id == sdef.id)
    assert oil_f.last_completed_mileage == sample_vehicle.current_mileage - 1000
    assert oil_f.miles_remaining == 4000
    assert oil_f.mileage_progress_pct == 20.0

def test_oil_config_and_fleet_next_due_api(client: TestClient, sample_vehicle: Vehicle):
    # 1. Get initial oil config
    get_res = client.get(f"/api/v1/maintenance/vehicle/{sample_vehicle.id}/oil-config")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["vehicle_id"] == sample_vehicle.id

    # 2. Update oil config: set interval to 7,500 mi and set baseline
    post_res = client.post(
        f"/api/v1/maintenance/vehicle/{sample_vehicle.id}/oil-config",
        json={
            "vehicle_id": sample_vehicle.id,
            "completed_date": "2026-08-01",
            "completed_mileage": sample_vehicle.current_mileage - 1500,
            "interval_miles": 7500,
            "interval_months": 12,
            "notes": "Mobil 1 Advanced Fuel Economy"
        }
    )
    assert post_res.status_code == 200
    updated = post_res.json()
    assert updated["interval_miles"] == 7500
    assert updated["last_completed_mileage"] == sample_vehicle.current_mileage - 1500
    assert updated["miles_remaining"] == 6000
    assert updated["mileage_progress_pct"] == 20.0

    # 3. Test fleet-next-due endpoint
    fleet_res = client.get("/api/v1/maintenance/fleet-next-due")
    assert fleet_res.status_code == 200
    fleet_data = fleet_res.json()
    assert len(fleet_data) >= 1
    v_entry = next(item for item in fleet_data if item["vehicle_id"] == sample_vehicle.id)
    assert v_entry["next_required"] is not None
    assert v_entry["oil_change"] is not None

