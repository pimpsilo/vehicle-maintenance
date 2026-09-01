from fastapi.testclient import TestClient
from sqlmodel import Session
from app.models.vehicle import Vehicle

def test_create_and_get_vehicle(client: TestClient):
    payload = {
        "vin": "4T1BK1EB5EU111111",
        "year": 2014,
        "make": "Toyota",
        "model": "Avalon",
        "trim": "Limited",
        "license_plate": "AVALON1",
        "ezpass_transponder": "02214988210",
        "current_mileage": 95000,
        "estimated_annual_mileage": 12000,
        "notes": "Test vehicle"
    }
    response = client.post("/api/v1/vehicles", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["vin"] == "4T1BK1EB5EU111111"
    assert data["ezpass_transponder"] == "02214988210"
    assert data["id"] is not None

    vehicle_id = data["id"]
    get_res = client.get(f"/api/v1/vehicles/{vehicle_id}")
    assert get_res.status_code == 200
    assert get_res.json()["model"] == "Avalon"
    assert get_res.json()["ezpass_transponder"] == "02214988210"

    # Test updating EZ-Pass tag
    put_res = client.put(f"/api/v1/vehicles/{vehicle_id}", json={"ezpass_transponder": "02299999999"})
    assert put_res.status_code == 200
    assert put_res.json()["ezpass_transponder"] == "02299999999"

def test_duplicate_vin_rejection(client: TestClient, sample_vehicle: Vehicle):
    payload = {
        "vin": sample_vehicle.vin,
        "year": 2014,
        "make": "Toyota",
        "model": "Avalon",
        "current_mileage": 50000,
    }
    response = client.post("/api/v1/vehicles", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]

def test_update_odometer(client: TestClient, sample_vehicle: Vehicle):
    res = client.post(
        f"/api/v1/vehicles/{sample_vehicle.id}/odometer",
        json={"current_mileage": 106500}
    )
    assert res.status_code == 200
    assert res.json()["current_mileage"] == 106500

    # Test decreasing odometer rejection
    fail_res = client.post(
        f"/api/v1/vehicles/{sample_vehicle.id}/odometer",
        json={"current_mileage": 104000}
    )
    assert fail_res.status_code == 400
    assert "cannot be lower" in fail_res.json()["detail"]

def test_delete_vehicle(client: TestClient):
    # 1. Create a disposable vehicle
    create_res = client.post(
        "/api/v1/vehicles",
        json={
            "vin": "4T1BK1EB5EU999999",
            "year": 2012,
            "make": "Toyota",
            "model": "Camry",
            "current_mileage": 140000
        }
    )
    assert create_res.status_code == 201
    vehicle_id = create_res.json()["id"]

    # 2. Delete the vehicle
    del_res = client.delete(f"/api/v1/vehicles/{vehicle_id}")
    assert del_res.status_code == 200
    assert "deleted successfully" in del_res.json()["message"]

    # 3. Confirm 404
    get_res = client.get(f"/api/v1/vehicles/{vehicle_id}")
    assert get_res.status_code == 404

def test_vehicle_photo_upload_and_lifecycle(client: TestClient, sample_vehicle: Vehicle):
    # 1. Initially vehicle has no photo
    get_res = client.get(f"/api/v1/vehicles/{sample_vehicle.id}")
    assert get_res.status_code == 200
    assert get_res.json()["has_photo"] is False

    photo_res = client.get(f"/api/v1/vehicles/{sample_vehicle.id}/photo")
    assert photo_res.status_code == 404

    # 2. Upload vehicle photo
    fake_img = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00"
    upload_res = client.post(
        f"/api/v1/vehicles/{sample_vehicle.id}/photo",
        files={"file": ("avalon.jpg", fake_img, "image/jpeg")}
    )
    assert upload_res.status_code == 200
    assert upload_res.json()["has_photo"] is True

    # 3. Retrieve vehicle photo
    download_res = client.get(f"/api/v1/vehicles/{sample_vehicle.id}/photo")
    assert download_res.status_code == 200
    assert download_res.content == fake_img
    assert download_res.headers["content-type"] == "image/jpeg"

    # 4. Delete vehicle photo
    del_photo_res = client.delete(f"/api/v1/vehicles/{sample_vehicle.id}/photo")
    assert del_photo_res.status_code == 200
    assert del_photo_res.json()["has_photo"] is False

    # 5. Confirm photo is gone
    check_res = client.get(f"/api/v1/vehicles/{sample_vehicle.id}/photo")
    assert check_res.status_code == 404
