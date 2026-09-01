import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.services.nhtsa_service import NHTSAService
from app.services.community_crawler import CommunityCrawler

def test_nhtsa_vin_decoder():
    vin = "4T1BK1EB5EU000001"
    res = NHTSAService.decode_vin(vin)
    assert res["vin"] == vin
    assert "valid" in res

def test_community_crawler_youtube_and_forums():
    # 1. YouTube video search generator
    yt_links = CommunityCrawler.generate_youtube_repair_links(
        year=2014, make="Toyota", model="Avalon", engine_desc="3.5L V6"
    )
    assert len(yt_links) >= 5
    assert any("spark plug" in link["query"] for link in yt_links)
    assert any("transmission fluid" in link["query"] for link in yt_links)
    assert "youtube.com" in yt_links[0]["url"]

    # 2. Forum sources
    toyota_forums = CommunityCrawler.generate_forum_sources("Toyota", "Avalon")
    assert any("ToyotaNation" in f["name"] for f in toyota_forums)
    assert any("Bob Is The Oil Guy" in f["name"] for f in toyota_forums)

    honda_forums = CommunityCrawler.generate_forum_sources("Honda", "Accord")
    assert any("Drive Accord" in f["name"] for f in honda_forums)

def test_auto_discover_fleet_intelligence_endpoint(client: TestClient):
    # 1. Create a fresh test vehicle
    veh_res = client.post(
        "/api/v1/vehicles",
        json={
            "vin": "4T1BK1EB5EU999999",
            "year": 2014,
            "make": "Toyota",
            "model": "Avalon",
            "trim": "XLE Touring",
            "current_mileage": 105000,
            "estimated_annual_mileage": 12000
        }
    )
    assert veh_res.status_code == 201
    vehicle_id = veh_res.json()["id"]

    # 2. Run auto-discovery API
    disc_res = client.post(f"/api/v1/vehicles/{vehicle_id}/auto-discover")
    assert disc_res.status_code == 200
    disc_data = disc_res.json()
    assert disc_data["success"] is True
    assert disc_data["vehicle_id"] == vehicle_id
    assert "community_sources" in disc_data
    assert "youtube_guides" in disc_data["community_sources"]
    assert "forums" in disc_data["community_sources"]

    # 3. Verify Consumables populated via API
    c_res = client.get(f"/api/v1/consumables?vehicle_id={vehicle_id}")
    assert c_res.status_code == 200
    consumables = c_res.json()
    assert len(consumables) >= 5
    assert any("0W-20" in c["specification"] for c in consumables)
    assert any("FK20HR11" in (c["oem_part_number"] or "") for c in consumables)

    # 4. Verify Guides populated via API
    g_res = client.get(f"/api/v1/reference-docs?vehicle_id={vehicle_id}")
    assert g_res.status_code == 200
    guides = g_res.json()
    assert len(guides) >= 1
    assert any("Spark Plug" in g["title"] for g in guides)

    # 5. Verify Quirks populated via API
    k_res = client.get(f"/api/v1/knowledge?vehicle_id={vehicle_id}")
    assert k_res.status_code == 200
    quirks = k_res.json()
    assert len(quirks) >= 1
    assert any("VVT-i" in q["title"] or "Oil Cooler" in q["title"] for q in quirks)

    # 6. Check safety recalls endpoint
    recalls_res = client.get(f"/api/v1/vehicles/{vehicle_id}/recalls")
    assert recalls_res.status_code == 200
    assert "recalls" in recalls_res.json()

    # 7. Check decode-vin endpoint
    decode_res = client.get(f"/api/v1/vehicles/decode-vin/4T1BK1EB5EU999999")
    assert decode_res.status_code == 200
    assert decode_res.json()["vin"] == "4T1BK1EB5EU999999"

def test_palisade_and_cascada_curated_fleet_intelligence(client: TestClient):
    # 1. Hyundai Palisade
    palisade_res = client.post(
        "/api/v1/vehicles",
        json={
            "vin": "KM8R7DGE6RU999999",
            "year": 2024,
            "make": "Hyundai",
            "model": "Palisade",
            "trim": "Calligraphy",
            "current_mileage": 15000
        }
    )
    assert palisade_res.status_code == 201
    p_id = palisade_res.json()["id"]

    client.post(f"/api/v1/vehicles/{p_id}/auto-discover")
    c_res = client.get(f"/api/v1/consumables?vehicle_id={p_id}")
    consumables = {c["category"]: c for c in c_res.json()}
    assert "26320-3N000" in (consumables["OIL_FILTER"]["oem_part_number"] or "")
    assert "18872-09085" in (consumables["SPARK_PLUGS"]["oem_part_number"] or "")
    assert "6.87 Quarts" in consumables["ENGINE_OIL"]["specification"]

    # 2. Buick Cascada
    cascada_res = client.post(
        "/api/v1/vehicles",
        json={
            "vin": "W04WH3N59KG999999",
            "year": 2019,
            "make": "Buick",
            "model": "Cascada",
            "trim": "Premium",
            "current_mileage": 35000
        }
    )
    assert cascada_res.status_code == 201
    c_id = cascada_res.json()["id"]

    client.post(f"/api/v1/vehicles/{c_id}/auto-discover")
    casc_res = client.get(f"/api/v1/consumables?vehicle_id={c_id}")
    c_items = {c["category"]: c for c in casc_res.json()}
    assert "PF64" in (c_items["OIL_FILTER"]["oem_part_number"] or "")
    assert "41-125" in (c_items["SPARK_PLUGS"]["oem_part_number"] or "")
    assert "Dex-Cool" in c_items["COOLANT"]["item_name"]
    assert "Convertible Top Hydraulic Fluid" in c_items["OTHER"]["item_name"]
