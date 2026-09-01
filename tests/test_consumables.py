from fastapi.testclient import TestClient
from app.models.vehicle import Vehicle

def test_consumables_crud_and_filtering(client: TestClient, sample_vehicle: Vehicle):
    # 1. Add Wiper Blade
    res_wiper = client.post(
        "/api/v1/consumables",
        json={
            "vehicle_id": sample_vehicle.id,
            "category": "WIPER_BLADES",
            "item_name": "Driver Side Wiper",
            "specification": "26 Inches",
            "oem_part_number": "85222-06130",
            "aftermarket_alternatives": "Bosch ICON 26A"
        }
    )
    assert res_wiper.status_code == 201
    wiper_id = res_wiper.json()["id"]

    # 2. Add Engine Oil
    res_oil = client.post(
        "/api/v1/consumables",
        json={
            "vehicle_id": sample_vehicle.id,
            "category": "ENGINE_OIL",
            "item_name": "Engine Motor Oil",
            "specification": "0W-20 Full Synthetic (6.4 US qt)",
            "oem_part_number": "00279-0W201-01"
        }
    )
    assert res_oil.status_code == 201

    # 3. Filter by category
    filter_res = client.get(f"/api/v1/consumables?vehicle_id={sample_vehicle.id}&category=WIPER_BLADES")
    assert filter_res.status_code == 200
    items = filter_res.json()
    assert len(items) == 1
    assert items[0]["item_name"] == "Driver Side Wiper"

    # 4. Update consumable
    put_res = client.put(f"/api/v1/consumables/{wiper_id}", json={"specification": "26 Inches (650mm)"})
    assert put_res.status_code == 200
    assert put_res.json()["specification"] == "26 Inches (650mm)"
