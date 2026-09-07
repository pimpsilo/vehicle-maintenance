from fastapi.testclient import TestClient
from sqlmodel import Session
from app.models.vehicle import Vehicle
from app.models.maintenance import ServiceDefinition, ServiceRecord
from datetime import date, timedelta

def test_fleet_landing_overview_multi_vehicle(client: TestClient, session: Session):
    # 1. Create two test vehicles
    v1 = Vehicle(
        vin="1HGCR2F83HA000001",
        year=2017,
        make="Honda",
        model="Accord",
        trim="EX-L",
        current_mileage=65000,
        license_plate="7ACCORD"
    )
    v2 = Vehicle(
        vin="JTJHY7AX4H4000002",
        year=2018,
        make="Lexus",
        model="RX350",
        trim="AWD",
        current_mileage=45000,
        license_plate="8LEXUS"
    )
    session.add_all([v1, v2])
    session.commit()
    session.refresh(v1)
    session.refresh(v2)

    # 2. Add an oil change service definition and service record
    s_def = ServiceDefinition(
        service_name="Engine Oil & Filter",
        interval_miles=5000,
        interval_months=6,
        category="ENGINE"
    )
    session.add(s_def)
    session.commit()
    session.refresh(s_def)

    # v1 had oil changed at 62000 (3000 miles ago -> due in 2000 miles)
    rec1 = ServiceRecord(
        vehicle_id=v1.id,
        service_definition_id=s_def.id,
        service_name="Engine Oil & Filter",
        completed_date=date.today() - timedelta(days=60),
        completed_mileage=62000,
    )
    session.add(rec1)
    session.commit()

    # 3. Request /dashboard (fleet landing page)
    res = client.get("/dashboard")
    assert res.status_code == 200
    assert "Garage Fleet Overview" in res.text or "VehicleOps Tracker" in res.text
    assert "Select a Vehicle to Manage" in res.text
    assert "Honda Accord" in res.text
    assert "Lexus RX350" in res.text
    assert "7ACCORD" in res.text
    assert "8LEXUS" in res.text
    assert "Next Oil Change" in res.text
    assert f"/dashboard?vehicle_id={v1.id}" in res.text
    assert f"/dashboard?vehicle_id={v2.id}" in res.text

def test_fleet_landing_empty_state(client: TestClient):
    # When visiting /fleet or /dashboard with no vehicles, renders gracefully
    res = client.get("/fleet")
    assert res.status_code == 200
    assert "VehicleOps Tracker" in res.text
