from fastapi.testclient import TestClient
from app.models.vehicle import Vehicle

def test_vehicle_knowledge_search_and_filtering(client: TestClient, sample_vehicle: Vehicle):
    # 1. Create knowledge record
    res = client.post(
        "/api/v1/knowledge",
        json={
            "vehicle_id": sample_vehicle.id,
            "category": "KNOWN_QUIRK",
            "component_system": "ENGINE",
            "title": "Cold Start VVT-i Gear Rattle (2GR-FE)",
            "description": "Brief 1-2 second metallic rattle on cold engine start.",
            "severity": "WATCH_ITEM",
            "real_world_data": "Observed in 40% of units above 80k miles.",
            "recommended_action": "Use OEM Toyota oil filter with anti-drainback valve."
        }
    )
    assert res.status_code == 201
    entry_id = res.json()["id"]

    # 2. Search by query
    search_res = client.get("/api/v1/knowledge?query=rattle")
    assert search_res.status_code == 200
    entries = search_res.json()
    assert len(entries) == 1
    assert "VVT-i" in entries[0]["title"]

    # 3. Filter by component system
    filter_res = client.get("/api/v1/knowledge?component_system=ENGINE&severity=WATCH_ITEM")
    assert filter_res.status_code == 200
    assert len(filter_res.json()) >= 1

def test_delete_knowledge_entry(client: TestClient, sample_vehicle: Vehicle):
    # 1. Create entry
    create_res = client.post(
        "/api/v1/knowledge",
        json={
            "vehicle_id": sample_vehicle.id,
            "category": "COMMUNITY_WISDOM",
            "component_system": "BODY_INTERIOR",
            "title": "Clearcoat UV Vulnerability",
            "description": "Roof and hood need ceramic sealant.",
            "severity": "INFO",
        }
    )
    assert create_res.status_code == 201
    k_id = create_res.json()["id"]

    # 2. Delete entry
    del_res = client.delete(f"/api/v1/knowledge/{k_id}")
    assert del_res.status_code == 200
    assert del_res.json()["message"] == "Knowledge entry deleted successfully."

    # 3. Verify 404 on get
    get_res = client.get(f"/api/v1/knowledge/{k_id}")
    assert get_res.status_code == 404
