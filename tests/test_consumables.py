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

def test_consumable_part_number_updates_and_enrichment(client: TestClient, sample_vehicle: Vehicle):
    # 1. Create a bare consumable without part numbers
    create_res = client.post(
        "/api/v1/consumables",
        json={
            "vehicle_id": sample_vehicle.id,
            "category": "CABIN_AIR_FILTER",
            "item_name": "Cabin Air Filter",
            "specification": "Glovebox Filter"
        }
    )
    assert create_res.status_code == 201
    item_id = create_res.json()["id"]

    # 2. Update with exact OEM and aftermarket cross-reference part numbers
    update_res = client.put(
        f"/api/v1/consumables/{item_id}",
        json={
            "oem_part_number": "87139-YZZ20",
            "aftermarket_alternatives": "EPAuto CP285, Bosch 6055C HEPA, Fram CF10285",
            "replacement_interval_summary": "Every 15,000 miles / 12 months"
        }
    )
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["oem_part_number"] == "87139-YZZ20"
    assert "EPAuto CP285" in updated_data["aftermarket_alternatives"]

    # 3. Verify mobile view reflects these part numbers
    mobile_res = client.get(f"/v/{sample_vehicle.id}")
    assert mobile_res.status_code == 200
    assert "OEM: 87139-YZZ20" in mobile_res.text
    assert "EPAuto CP285" in mobile_res.text

    # 4. Delete consumable
    del_res = client.delete(f"/api/v1/consumables/{item_id}")
    assert del_res.status_code == 200
    assert "deleted successfully" in del_res.json()["message"]
