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
