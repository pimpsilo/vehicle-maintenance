from fastapi.testclient import TestClient
from app.models.vehicle import Vehicle

def test_root_redirects_to_dashboard(client: TestClient):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/dashboard"

def test_dashboard_renders_with_sample_vehicle(client: TestClient, sample_vehicle: Vehicle):
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "VehicleOps Tracker" in response.text
    assert "Overview & Quick Entry" in response.text
    assert sample_vehicle.model in response.text
    assert "Quick Odometer Update" in response.text

def test_dashboard_vehicle_filtering(client: TestClient, sample_vehicle: Vehicle):
    response = client.get(f"/dashboard?vehicle_id={sample_vehicle.id}")
    assert response.status_code == 200
    assert sample_vehicle.vin in response.text
