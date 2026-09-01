from datetime import date, datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from app.database import get_session
from app.models.vehicle import Vehicle, OdometerUpdate, VehicleRead
from app.models.consumable import ConsumableSpecification
from app.models.document import VehicleDocument
from app.models.maintenance import ServiceRecord
from app.services.document_service import DocumentService
from app.services.interval_engine import MaintenanceIntervalEngine

router = APIRouter(tags=["Mobile Vehicle Portal"])

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

@router.get("/v", response_class=HTMLResponse)
def render_mobile_fleet_hub(
    request: Request,
    session: Session = Depends(get_session)
):
    vehicles = session.exec(select(Vehicle).order_by(Vehicle.id.asc())).all()
    if not vehicles:
        return RedirectResponse(url="/dashboard")
    
    if len(vehicles) == 1:
        return RedirectResponse(url=f"/v/{vehicles[0].id}")
    
    return templates.TemplateResponse(
        request=request,
        name="mobile_fleet_hub.html",
        context={
            "vehicles": vehicles,
        }
    )

@router.get("/v/{vehicle_id}", response_class=HTMLResponse)
def render_mobile_portal(
    request: Request,
    vehicle_id: int,
    session: Session = Depends(get_session)
):
    vehicle = session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found.")

    all_vehicles = session.exec(select(Vehicle).order_by(Vehicle.id.asc())).all()

    # Consumables
    consumables = session.exec(
        select(ConsumableSpecification)
        .where(ConsumableSpecification.vehicle_id == vehicle_id)
        .order_by(ConsumableSpecification.category.asc())
    ).all()

    # Documents with enriched statuses
    raw_docs = session.exec(
        select(VehicleDocument)
        .where(VehicleDocument.vehicle_id == vehicle_id)
        .order_by(VehicleDocument.expiration_date.asc())
    ).all()
    documents = [DocumentService.enrich_document_read(d) for d in raw_docs]

    # Forecasts
    forecasts = MaintenanceIntervalEngine.calculate_forecasts(session, vehicle_id=vehicle_id)

    return templates.TemplateResponse(
        request=request,
        name="mobile_vehicle.html",
        context={
            "vehicle": vehicle,
            "all_vehicles": all_vehicles,
            "consumables": consumables,
            "documents": documents,
            "forecasts": forecasts,
        }
    )

@router.post("/v/{vehicle_id}/odometer", response_model=VehicleRead)
def mobile_update_odometer(
    vehicle_id: int,
    payload: OdometerUpdate,
    session: Session = Depends(get_session)
):
    vehicle = session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found.")

    if payload.current_mileage < vehicle.current_mileage:
        raise HTTPException(
            status_code=400,
            detail=f"New odometer reading ({payload.current_mileage}) cannot be lower than current reading ({vehicle.current_mileage})."
        )

    vehicle.current_mileage = payload.current_mileage
    vehicle.updated_at = datetime.now(timezone.utc)
    session.add(vehicle)
    session.commit()
    session.refresh(vehicle)
    return vehicle

@router.post("/v/{vehicle_id}/quick-service")
def mobile_quick_service(
    vehicle_id: int,
    payload: dict,
    session: Session = Depends(get_session)
):
    vehicle = session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found.")

    mileage = payload.get("completed_mileage", vehicle.current_mileage)
    if mileage > vehicle.current_mileage:
        vehicle.current_mileage = mileage
        session.add(vehicle)

    record = ServiceRecord(
        vehicle_id=vehicle_id,
        service_name=payload.get("service_name", "Maintenance Service"),
        completed_date=date.today(),
        completed_mileage=mileage,
        total_cost=float(payload.get("total_cost", 0.0)),
        performed_by_type="DIY",
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return {"message": "Service record created successfully", "record_id": record.id}
