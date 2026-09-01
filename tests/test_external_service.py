from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.models.vehicle import Vehicle

def test_shop_crud_operations(client: TestClient):
    # 1. Create shop
    shop_res = client.post(
        "/api/v1/external-services/shops",
        json={
            "name": "Bay Area European & Asian Auto",
            "contact_name": "Dave Miller",
            "phone": "555-4321",
            "email": "dave@bayareaauto.com",
            "address": "789 Willow St, San Jose, CA",
            "hourly_labor_rate": 160.0,
            "specialties": "Toyota, Lexus, Honda"
        }
    )
    assert shop_res.status_code == 201
    shop_id = shop_res.json()["id"]

    # 2. Get shop
    get_res = client.get(f"/api/v1/external-services/shops/{shop_id}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Bay Area European & Asian Auto"

    # 3. Update shop
    update_res = client.put(
        f"/api/v1/external-services/shops/{shop_id}",
        json={
            "hourly_labor_rate": 165.0,
            "notes": "Offers loaner vehicle upon request."
        }
    )
    assert update_res.status_code == 200
    assert update_res.json()["hourly_labor_rate"] == 165.0
    assert update_res.json()["notes"] == "Offers loaner vehicle upon request."

    # 4. Delete shop
    del_res = client.delete(f"/api/v1/external-services/shops/{shop_id}")
    assert del_res.status_code == 200
    assert "deleted successfully" in del_res.json()["message"]

def test_external_service_lifecycle_and_cost_rollup(client: TestClient, sample_vehicle: Vehicle):
    today = date.today()

    # 1. Create mechanic shop
    shop_res = client.post(
        "/api/v1/external-services/shops",
        json={
            "name": "Precision Toyota Care",
            "phone": "555-9000",
            "address": "100 Main St, San Jose, CA",
            "hourly_labor_rate": 150.0
        }
    )
    assert shop_res.status_code == 201
    shop_id = shop_res.json()["id"]

    # 2. Create work order
    order_res = client.post(
        "/api/v1/external-services/orders",
        json={
            "vehicle_id": sample_vehicle.id,
            "shop_id": shop_id,
            "service_summary": "120k Spark Plug & Transmission Service",
            "scheduled_date": (today + timedelta(days=7)).isoformat(),
            "quoted_labor_cost": 250.0
        }
    )
    assert order_res.status_code == 201
    order_id = order_res.json()["id"]

    # 3. Add parts to work order
    part1_res = client.post(
        f"/api/v1/external-services/orders/{order_id}/parts",
        json={
            "part_name": "Denso Iridium Plugs (6x)",
            "oem_part_number": "90919-01247",
            "supplier": "RockAuto",
            "unit_cost": 10.0,
            "quantity": 6,
            "order_status": "DELIVERED"
        }
    )
    assert part1_res.status_code == 201
    assert part1_res.json()["total_cost"] == 60.0

    part2_res = client.post(
        f"/api/v1/external-services/orders/{order_id}/parts",
        json={
            "part_name": "Toyota WS ATF Fluid (4 Qts)",
            "oem_part_number": "00289-ATFWS",
            "supplier": "Toyota Dealer",
            "unit_cost": 12.0,
            "quantity": 4,
            "order_status": "DELIVERED"
        }
    )
    assert part2_res.status_code == 201
    assert part2_res.json()["total_cost"] == 48.0

    # 4. Fetch enriched work order and verify total parts and order cost
    order_detail = client.get(f"/api/v1/external-services/orders/{order_id}").json()
    assert order_detail["total_parts_cost"] == 108.0  # 60 + 48
    assert order_detail["total_order_cost"] == 358.0  # 108 parts + 250 labor

    # 5. Full Edit/Update Appointment via JSON body
    new_date = (today + timedelta(days=10)).isoformat()
    update_res = client.put(
        f"/api/v1/external-services/orders/{order_id}",
        json={
            "service_summary": "120k Spark Plug & Transmission Flush (Rescheduled)",
            "scheduled_date": new_date,
            "status": "COMPLETED",
            "final_labor_cost": 220.0,
            "invoice_number": "INV-8891",
            "mechanic_notes": "All 6 plugs replaced, intake plenum gasket renewed."
        }
    )
    assert update_res.status_code == 200
    updated_order = update_res.json()
    assert updated_order["service_summary"] == "120k Spark Plug & Transmission Flush (Rescheduled)"
    assert updated_order["status"] == "COMPLETED"
    assert updated_order["total_order_cost"] == 328.0  # 108 parts + 220 final labor
    assert updated_order["invoice_number"] == "INV-8891"

    # 6. Test Delete work order
    del_res = client.delete(f"/api/v1/external-services/orders/{order_id}")
    assert del_res.status_code == 200
    assert "deleted successfully" in del_res.json()["message"]
