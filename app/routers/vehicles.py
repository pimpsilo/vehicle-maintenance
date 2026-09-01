from app.config import get_utc_now
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, File
from sqlmodel import Session, select
from app.database import get_session
from app.models.vehicle import (
    Vehicle,
    VehicleCreate,
    VehicleRead,
    VehicleUpdate,
    OdometerUpdate,
)
from app.models.document import VehicleDocument
from app.models.maintenance import ServiceRecord
from app.models.external_service import ExternalServiceOrder, PartSourcing
from app.models.consumable import ConsumableSpecification
from app.models.reference_doc import ReferenceDocument
from app.models.vehicle_knowledge import VehicleKnowledge
from app.services.qr_service import QRService
from app.services.nhtsa_service import NHTSAService
from app.services.fleet_intelligence import FleetIntelligenceService

router = APIRouter(prefix="/api/v1/vehicles", tags=["Vehicles"])

def _enrich_vehicle_read(v: Vehicle) -> VehicleRead:
    return VehicleRead(
        id=v.id,
        vin=v.vin,
        year=v.year,
        make=v.make,
        model=v.model,
        trim=v.trim,
        license_plate=v.license_plate,
        ezpass_transponder=v.ezpass_transponder,
        current_mileage=v.current_mileage,
        estimated_annual_mileage=v.estimated_annual_mileage,
        purchase_date=v.purchase_date,
        notes=v.notes,
        created_at=v.created_at,
        updated_at=v.updated_at,
        has_photo=bool(v.photo_data),
    )

@router.get("", response_model=List[VehicleRead])
def list_vehicles(session: Session = Depends(get_session)):
    vehicles = session.exec(select(Vehicle).order_by(Vehicle.id.asc())).all()
    return [_enrich_vehicle_read(v) for v in vehicles]

@router.post("", response_model=VehicleRead, status_code=201)
def create_vehicle(payload: VehicleCreate, session: Session = Depends(get_session)):
    existing = session.exec(select(Vehicle).where(Vehicle.vin == payload.vin)).first()
    if existing:
        raise HTTPException(status_code=400, detail="A vehicle with this VIN already exists.")
    
    vehicle = Vehicle.model_validate(payload)
    session.add(vehicle)
    session.commit()
    session.refresh(vehicle)
    
    # Auto-run discovery in background for new vehicle
    try:
        FleetIntelligenceService.auto_discover_vehicle(session, vehicle.id)
        session.refresh(vehicle)
    except Exception:
        pass

    return _enrich_vehicle_read(vehicle)

@router.get("/decode-vin/{vin}")
def decode_vin(vin: str):
    """
    Decodes a 17-character VIN via the NHTSA VPIC API on demand.
    """
    return NHTSAService.decode_vin(vin)

@router.get("/{vehicle_id}", response_model=VehicleRead)
def get_vehicle(vehicle_id: int, session: Session = Depends(get_session)):
    vehicle = session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found.")
    return _enrich_vehicle_read(vehicle)

@router.put("/{vehicle_id}", response_model=VehicleRead)
def update_vehicle(vehicle_id: int, payload: VehicleUpdate, session: Session = Depends(get_session)):
    vehicle = session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found.")
    
    update_data = payload.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(vehicle, k, v)
    
    vehicle.updated_at = get_utc_now()
    session.add(vehicle)
    session.commit()
    session.refresh(vehicle)
    return _enrich_vehicle_read(vehicle)

@router.delete("/{vehicle_id}")
def delete_vehicle(vehicle_id: int, session: Session = Depends(get_session)):
    vehicle = session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found.")
    
    # Explicitly clean up all related child records
    orders = session.exec(select(ExternalServiceOrder).where(ExternalServiceOrder.vehicle_id == vehicle_id)).all()
    for o in orders:
        parts = session.exec(select(PartSourcing).where(PartSourcing.work_order_id == o.id)).all()
        for p in parts:
            session.delete(p)
        session.delete(o)
    
    orphan_parts = session.exec(select(PartSourcing).where(PartSourcing.vehicle_id == vehicle_id)).all()
    for p in orphan_parts:
        session.delete(p)

    docs = session.exec(select(VehicleDocument).where(VehicleDocument.vehicle_id == vehicle_id)).all()
    for d in docs:
        session.delete(d)

    records = session.exec(select(ServiceRecord).where(ServiceRecord.vehicle_id == vehicle_id)).all()
    for r in records:
        session.delete(r)

    consumables = session.exec(select(ConsumableSpecification).where(ConsumableSpecification.vehicle_id == vehicle_id)).all()
    for c in consumables:
        session.delete(c)

    ref_docs = session.exec(select(ReferenceDocument).where(ReferenceDocument.vehicle_id == vehicle_id)).all()
    for rd in ref_docs:
        session.delete(rd)

    knowledge = session.exec(select(VehicleKnowledge).where(VehicleKnowledge.vehicle_id == vehicle_id)).all()
    for k in knowledge:
        session.delete(k)

    session.delete(vehicle)
    session.commit()
    return {"message": f"Vehicle {vehicle.year} {vehicle.make} {vehicle.model} (ID: {vehicle_id}) deleted successfully."}

@router.post("/{vehicle_id}/odometer", response_model=VehicleRead)
def update_odometer(vehicle_id: int, payload: OdometerUpdate, session: Session = Depends(get_session)):
    vehicle = session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found.")
    
    if payload.current_mileage < vehicle.current_mileage:
        raise HTTPException(
            status_code=400,
            detail=f"New odometer reading ({payload.current_mileage}) cannot be lower than current reading ({vehicle.current_mileage})."
        )
    
    vehicle.current_mileage = payload.current_mileage
    vehicle.updated_at = get_utc_now()
    session.add(vehicle)
    session.commit()
    session.refresh(vehicle)
    return _enrich_vehicle_read(vehicle)

@router.get("/{vehicle_id}/qr")
def get_vehicle_qr_code(vehicle_id: int, format: str = "png", session: Session = Depends(get_session)):
    vehicle = session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found.")
    
    if format.lower() == "svg":
        svg_content = QRService.generate_qr_svg(vehicle_id)
        return Response(content=svg_content, media_type="image/svg+xml")
    else:
        png_bytes = QRService.generate_qr_png_bytes(vehicle_id)
        return Response(content=png_bytes, media_type="image/png")

# --- Fleet Photos Endpoints ---
@router.post("/{vehicle_id}/photo", response_model=VehicleRead)
async def upload_vehicle_photo(
    vehicle_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    vehicle = session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found.")
    
    allowed = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
    ext = "." + file.filename.split(".")[-1].lower() if "." in file.filename else ""
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail="Unsupported image format. Allowed: JPG, PNG, WEBP, TIF."
        )
    
    file_bytes = await file.read()
    vehicle.photo_data = file_bytes
    vehicle.photo_filename = file.filename
    vehicle.photo_content_type = file.content_type or "image/jpeg"
    vehicle.updated_at = get_utc_now()
    
    session.add(vehicle)
    session.commit()
    session.refresh(vehicle)
    return _enrich_vehicle_read(vehicle)

@router.get("/{vehicle_id}/photo")
def get_vehicle_photo(vehicle_id: int, session: Session = Depends(get_session)):
    vehicle = session.get(Vehicle, vehicle_id)
    if not vehicle or not vehicle.photo_data:
        raise HTTPException(status_code=404, detail="Vehicle photo not found.")
    
    return Response(
        content=vehicle.photo_data,
        media_type=vehicle.photo_content_type or "image/jpeg",
        headers={
            "Content-Disposition": f'inline; filename="{vehicle.photo_filename or "vehicle_photo.jpg"}"',
            "Cache-Control": "public, max-age=86400"
        }
    )

@router.delete("/{vehicle_id}/photo", response_model=VehicleRead)
def delete_vehicle_photo(vehicle_id: int, session: Session = Depends(get_session)):
    vehicle = session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found.")
    
    vehicle.photo_data = None
    vehicle.photo_filename = None
    vehicle.photo_content_type = None
    vehicle.updated_at = get_utc_now()
    
    session.add(vehicle)
    session.commit()
    session.refresh(vehicle)
    return _enrich_vehicle_read(vehicle)

# --- Multi-Source Fleet Intelligence & Community Enrichment ---
@router.post("/{vehicle_id}/auto-discover")
def auto_discover_fleet_intelligence(vehicle_id: int, session: Session = Depends(get_session)):
    res = FleetIntelligenceService.auto_discover_vehicle(session, vehicle_id)
    if not res.get("success"):
        raise HTTPException(status_code=404, detail=res.get("message", "Auto-discovery failed."))
    return res

@router.get("/{vehicle_id}/recalls")
def get_vehicle_safety_recalls(vehicle_id: int, session: Session = Depends(get_session)):
    vehicle = session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found.")
    
    recalls = NHTSAService.get_recalls_by_vin(vehicle.vin)
    return {
        "vehicle_id": vehicle.id,
        "vin": vehicle.vin,
        "total_recalls": len(recalls),
        "recalls": recalls,
    }
