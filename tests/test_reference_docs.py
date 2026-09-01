from fastapi.testclient import TestClient
from app.models.vehicle import Vehicle

def test_reference_docs_search_and_creation(client: TestClient, sample_vehicle: Vehicle):
    # 1. Create reference doc
    create_res = client.post(
        "/api/v1/reference-docs",
        json={
            "vehicle_id": sample_vehicle.id,
            "title": "2GR-FE Spark Plug Replacement Community Guide",
            "doc_category": "COMMUNITY_DIY_GUIDE",
            "source_name_or_url": "ToyotaNation",
            "difficulty": "INTERMEDIATE",
            "tools_required": "5/8 spark plug socket, 10mm socket, swivel ratchet",
            "estimated_hours": 2.5,
            "step_by_step_instructions": "Remove cowl tray, remove intake plenum, unbolt coils, replace spark plugs.",
            "early_service_community_tips": "Do this at 100k when doing coolant flush.",
            "tags": "spark-plugs, 2gr-fe, plenum"
        }
    )
    assert create_res.status_code == 201
    doc_id = create_res.json()["id"]

    # 2. Search by query
    search_res = client.get("/api/v1/reference-docs?query=plenum")
    assert search_res.status_code == 200
    results = search_res.json()
    assert len(results) == 1
    assert "Spark Plug" in results[0]["title"]

    # 3. Filter by category and difficulty
    cat_res = client.get("/api/v1/reference-docs?category=COMMUNITY_DIY_GUIDE&difficulty=INTERMEDIATE")
    assert cat_res.status_code == 200
    assert len(cat_res.json()) >= 1
