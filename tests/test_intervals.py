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
