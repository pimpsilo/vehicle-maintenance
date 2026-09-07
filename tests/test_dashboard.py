from fastapi.testclient import TestClient
from app.models.vehicle import Vehicle

def test_root_redirects_to_dashboard(client: TestClient):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/dashboard"

def test_fleet_landing_renders_without_vehicle_id(client: TestClient, sample_vehicle: Vehicle):
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "VehicleOps Tracker" in response.text
    assert "Select a Vehicle to Manage" in response.text
    assert sample_vehicle.model in response.text
    assert "Current Odometer" in response.text

def test_dashboard_renders_with_sample_vehicle(client: TestClient, sample_vehicle: Vehicle):
    response = client.get(f"/dashboard?vehicle_id={sample_vehicle.id}")
    assert response.status_code == 200
    assert "VehicleOps Tracker" in response.text
    assert "Overview & Quick Entry" in response.text
    assert sample_vehicle.model in response.text
    assert "Quick Odometer Update" in response.text

def test_dashboard_vehicle_filtering(client: TestClient, sample_vehicle: Vehicle):
    response = client.get(f"/dashboard?vehicle_id={sample_vehicle.id}")
    assert response.status_code == 200
    assert sample_vehicle.vin in response.text

def test_dashboard_renders_usage_analytics_section(client: TestClient, sample_vehicle: Vehicle, session):
    from datetime import datetime, timezone, timedelta
    from app.models.vehicle import OdometerEntry

    # 1. Without sufficient data, shows baseline/insufficient notice
    res1 = client.get(f"/dashboard?vehicle_id={sample_vehicle.id}")
    assert res1.status_code == 200
    assert "Driving Usage &amp; Pace Analytics" in res1.text or "Driving Usage & Pace Analytics" in res1.text
    assert "Insufficient Driving History" in res1.text

    # 2. Add history spanning 30 days
    now = datetime.now(timezone.utc)
    e1 = OdometerEntry(vehicle_id=sample_vehicle.id, mileage=100000, recorded_at=now - timedelta(days=30))
    e2 = OdometerEntry(vehicle_id=sample_vehicle.id, mileage=101000, recorded_at=now)
    session.add_all([e1, e2])
    session.commit()

    res2 = client.get(f"/dashboard?vehicle_id={sample_vehicle.id}")
    assert res2.status_code == 200
    assert "Daily Average Pace" in res2.text
    assert "Monthly Rate" in res2.text
    assert "<svg" in res2.text
    assert "Dependency-free SVG rendering" in res2.text
