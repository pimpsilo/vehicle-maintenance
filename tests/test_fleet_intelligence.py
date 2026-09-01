import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.models.vehicle import Vehicle
from app.models.consumable import ConsumableSpecification
from app.models.reference_doc import ReferenceDocument
from app.models.vehicle_knowledge import VehicleKnowledge
from app.services.nhtsa_service import NHTSAService
from app.services.community_crawler import CommunityCrawler
from app.services.fleet_intelligence import FleetIntelligenceService

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

def test_auto_discover_fleet_intelligence_endpoint(client: TestClient, session: Session):
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

    # 3. Verify SQLite DB was auto-populated with consumables, guides, and quirks
    consumables = session.exec(
        select(ConsumableSpecification).where(ConsumableSpecification.vehicle_id == vehicle_id)
    ).all()
    assert len(consumables) >= 5
    assert any("0W-20" in c.specification for c in consumables)
    assert any("FK20HR11" in (c.oem_part_number or "") for c in consumables)

    guides = session.exec(
        select(ReferenceDocument).where(ReferenceDocument.vehicle_id == vehicle_id)
    ).all()
    assert len(guides) >= 1
    assert any("Spark Plug" in g.title for g in guides)

    quirks = session.exec(
        select(VehicleKnowledge).where(VehicleKnowledge.vehicle_id == vehicle_id)
    ).all()
    assert len(quirks) >= 1
    assert any("VVT-i" in q.title or "Oil Cooler" in q.title for q in quirks)

    # 4. Check safety recalls endpoint
    recalls_res = client.get(f"/api/v1/vehicles/{vehicle_id}/recalls")
    assert recalls_res.status_code == 200
    assert "recalls" in recalls_res.json()

    # 5. Check decode-vin endpoint
    decode_res = client.get(f"/api/v1/vehicles/decode-vin/4T1BK1EB5EU999999")
    assert decode_res.status_code == 200
    assert decode_res.json()["vin"] == "4T1BK1EB5EU999999"
