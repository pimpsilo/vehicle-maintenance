from fastapi.testclient import TestClient
from app.models.vehicle import Vehicle

def test_qr_code_generation(client: TestClient, sample_vehicle: Vehicle):
    # PNG format
    png_res = client.get(f"/api/v1/vehicles/{sample_vehicle.id}/qr?format=png")
    assert png_res.status_code == 200
    assert png_res.headers["content-type"] == "image/png"
    assert len(png_res.content) > 100

    # SVG format
    svg_res = client.get(f"/api/v1/vehicles/{sample_vehicle.id}/qr?format=svg")
    assert svg_res.status_code == 200
    assert "image/svg+xml" in svg_res.headers["content-type"]
    assert "<svg" in svg_res.text

def test_mobile_portal_view_and_quick_updates(client: TestClient, sample_vehicle: Vehicle):
    # 1. Render mobile portal HTML
    html_res = client.get(f"/v/{sample_vehicle.id}")
    assert html_res.status_code == 200
    assert "2014 Toyota Avalon" in html_res.text
    assert "Quick Odometer Update" in html_res.text

    # 2. Update odometer via mobile endpoint
    odo_res = client.post(
        f"/v/{sample_vehicle.id}/odometer",
        json={"current_mileage": 105500}
    )
    assert odo_res.status_code == 200
    assert odo_res.json()["current_mileage"] == 105500

    # 3. Log quick service via mobile endpoint
    svc_res = client.post(
        f"/v/{sample_vehicle.id}/quick-service",
        json={
            "service_name": "Tire Pressure & Inspection",
            "completed_mileage": 105500,
            "total_cost": 0.0
        }
    )
    assert svc_res.status_code == 200
    assert "created successfully" in svc_res.json()["message"]
