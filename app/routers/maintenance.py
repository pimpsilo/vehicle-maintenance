from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Response
from sqlmodel import Session, select
from app.database import get_session
from app.models.maintenance import (
    ServiceDefinition,
    ServiceDefinitionCreate,
    ServiceDefinitionRead,
    ServiceRecord,
    ServiceRecordCreate,
    ServiceRecordRead,
    ServiceRecordUpdate,
    MaintenanceAcknowledgeRequest,
    MaintenanceForecast,
    PerformedByType,
    ServiceStatus,
    VehicleOilConfigRequest,
    VehicleOilConfigRead,
)
from app.models.vehicle import Vehicle
from app.models.consumable import ConsumableSpecification
from app.services.interval_engine import MaintenanceIntervalEngine
from app.services.attachment_service import AttachmentService

router = APIRouter(prefix="/api/v1/maintenance", tags=["Maintenance"])

def _enrich_record_read(rec: ServiceRecord) -> ServiceRecordRead:
    return ServiceRecordRead(
        id=rec.id,
        vehicle_id=rec.vehicle_id,
        service_definition_id=rec.service_definition_id,
        service_name=rec.service_name,
        completed_date=rec.completed_date,
        completed_mileage=rec.completed_mileage,
        performed_by_type=rec.performed_by_type,
        total_cost=rec.total_cost,
        labor_cost=rec.labor_cost,
        parts_cost=rec.parts_cost,
        service_shop_id=rec.service_shop_id,
        file_name=rec.file_name,
        file_content_type=rec.file_content_type,
        file_size=rec.file_size,
        notes=rec.notes,
        created_at=rec.created_at,
        has_attachment=bool(rec.file_data),
    )

@router.get("/definitions", response_model=List[ServiceDefinitionRead])
def list_service_definitions(session: Session = Depends(get_session)):
    return session.exec(select(ServiceDefinition).order_by(ServiceDefinition.interval_miles.asc())).all()

@router.post("/definitions", response_model=ServiceDefinitionRead, status_code=201)
def create_service_definition(payload: ServiceDefinitionCreate, session: Session = Depends(get_session)):
    sdef = ServiceDefinition.model_validate(payload)
    session.add(sdef)
    session.commit()
    session.refresh(sdef)
    return sdef

@router.get("/forecast/{vehicle_id}", response_model=List[MaintenanceForecast])
def get_maintenance_forecast(
    vehicle_id: int,
    session: Session = Depends(get_session)
):
    vehicle = session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found.")
    
    return MaintenanceIntervalEngine.calculate_forecasts(session, vehicle_id=vehicle_id)

@router.get("/fleet-next-due")
def get_fleet_next_due(session: Session = Depends(get_session)):
    vehicles = session.exec(select(Vehicle).order_by(Vehicle.id.asc())).all()
    results = []
    for v in vehicles:
        forecasts = MaintenanceIntervalEngine.calculate_forecasts(session, vehicle_id=v.id)
        next_req = next((f for f in forecasts if f.is_next_required), None)
        oil_f = next((f for f in forecasts if "oil" in f.service_name.lower()), None)
        results.append({
            "vehicle_id": v.id,
            "vehicle_name": f"{v.year} {v.make} {v.model} {v.trim or ''}".strip(),
            "current_mileage": v.current_mileage,
            "next_required": next_req,
            "oil_change": oil_f,
        })
    return results

@router.get("/vehicle/{vehicle_id}/oil-config", response_model=VehicleOilConfigRead)
def get_vehicle_oil_config(vehicle_id: int, session: Session = Depends(get_session)):
    vehicle = session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found.")

    consumables = session.exec(
        select(ConsumableSpecification).where(ConsumableSpecification.vehicle_id == vehicle_id)
    ).all()
    oil_spec = next((c for c in consumables if "oil" in c.item_name.lower() and "filter" not in c.item_name.lower()), None)

    forecasts = MaintenanceIntervalEngine.calculate_forecasts(session, vehicle_id=vehicle_id)
    oil_forecast = next((f for f in forecasts if "oil" in f.service_name.lower()), None)

    vehicle_name = f"{vehicle.year} {vehicle.make} {vehicle.model} {vehicle.trim or ''}".strip()

    if oil_forecast:
        return VehicleOilConfigRead(
            vehicle_id=vehicle.id,
            vehicle_name=vehicle_name,
            current_mileage=vehicle.current_mileage,
            service_definition_id=oil_forecast.service_definition_id,
            service_name=oil_forecast.service_name,
            interval_miles=oil_forecast.interval_miles,
            interval_months=oil_forecast.interval_months,
            last_completed_date=oil_forecast.last_completed_date,
            last_completed_mileage=oil_forecast.last_completed_mileage,
            next_due_mileage=oil_forecast.next_due_mileage,
            next_due_date=oil_forecast.next_due_date,
            projected_due_date_by_mileage=oil_forecast.projected_due_date_by_mileage,
            miles_remaining=oil_forecast.miles_remaining,
            days_remaining=oil_forecast.days_remaining,
            status=oil_forecast.status,
            mileage_progress_pct=oil_forecast.mileage_progress_pct,
            time_progress_pct=oil_forecast.time_progress_pct,
            oil_specification=oil_spec.specification if oil_spec else None,
            oil_part_number=oil_spec.oem_part_number if oil_spec else None,
            notes=oil_forecast.action_summary,
        )
    else:
        return VehicleOilConfigRead(
            vehicle_id=vehicle.id,
            vehicle_name=vehicle_name,
            current_mileage=vehicle.current_mileage,
            service_name="Engine Oil & Filter Change",
            interval_miles=10000,
            interval_months=12,
            next_due_mileage=vehicle.current_mileage + 10000,
            next_due_date=date.today(),
            projected_due_date_by_mileage=date.today(),
            miles_remaining=10000,
            days_remaining=365,
            status=ServiceStatus.OK,
            mileage_progress_pct=0.0,
            time_progress_pct=0.0,
            oil_specification=oil_spec.specification if oil_spec else None,
            oil_part_number=oil_spec.oem_part_number if oil_spec else None,
        )

@router.post("/vehicle/{vehicle_id}/oil-config", response_model=VehicleOilConfigRead)
def update_vehicle_oil_config(
    vehicle_id: int,
    payload: VehicleOilConfigRequest,
    session: Session = Depends(get_session)
):
    vehicle = session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found.")

    existing_defs = session.exec(
        select(ServiceDefinition)
        .where(ServiceDefinition.vehicle_id == vehicle_id)
        .where(ServiceDefinition.category == "LUBRICATION")
    ).all()
    if not existing_defs:
        existing_defs = [
            d for d in session.exec(select(ServiceDefinition).where(ServiceDefinition.vehicle_id == vehicle_id)).all()
            if "oil" in d.service_name.lower()
        ]

    if existing_defs:
        sdef = existing_defs[0]
        if payload.interval_miles:
            sdef.interval_miles = payload.interval_miles
        if payload.interval_months:
            sdef.interval_months = payload.interval_months
        if payload.service_name:
            sdef.service_name = payload.service_name
    else:
        sdef = ServiceDefinition(
            vehicle_id=vehicle_id,
            service_name=payload.service_name or "Engine Oil & Filter Change",
            interval_miles=payload.interval_miles or 7500,
            interval_months=payload.interval_months or 12,
            category="LUBRICATION",
            is_recurring=True,
        )
    session.add(sdef)
    session.commit()
    session.refresh(sdef)

    if payload.completed_date or payload.completed_mileage is not None:
        comp_date = payload.completed_date or date.today()
        comp_mileage = payload.completed_mileage if payload.completed_mileage is not None else vehicle.current_mileage
        
        record = ServiceRecord(
            vehicle_id=vehicle.id,
            service_definition_id=sdef.id,
            service_name=sdef.service_name,
            completed_date=comp_date,
            completed_mileage=comp_mileage,
            performed_by_type=PerformedByType.DIY,
            total_cost=payload.total_cost or 0.0,
            notes=payload.notes or "Updated oil change baseline"
        )
        session.add(record)
        session.commit()

    return get_vehicle_oil_config(vehicle_id=vehicle_id, session=session)

@router.post("/acknowledge", response_model=ServiceRecordRead, status_code=201)
def acknowledge_maintenance_item(
    payload: MaintenanceAcknowledgeRequest,
    session: Session = Depends(get_session)
):
    vehicle = session.get(Vehicle, payload.vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found.")
    
    sdef = session.get(ServiceDefinition, payload.service_definition_id)
    if not sdef:
        raise HTTPException(status_code=404, detail="Service definition not found.")
    
    mileage = payload.completed_mileage if payload.completed_mileage is not None else vehicle.current_mileage
    service_date = payload.completed_date if payload.completed_date is not None else date.today()
    notes = payload.notes or "Acknowledged prior service / baseline reset (no receipt)"
    
    record = ServiceRecord(
        vehicle_id=vehicle.id,
        service_definition_id=sdef.id,
        service_name=sdef.service_name,
        completed_date=service_date,
        completed_mileage=mileage,
        performed_by_type=PerformedByType.DIY,
        total_cost=0.0,
        labor_cost=0.0,
        parts_cost=0.0,
        notes=notes
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return _enrich_record_read(record)

@router.get("/records", response_model=List[ServiceRecordRead])
def list_service_records(
    vehicle_id: Optional[int] = Query(None, description="Filter by vehicle ID"),
    session: Session = Depends(get_session)
):
    stmt = select(ServiceRecord)
    if vehicle_id:
        stmt = stmt.where(ServiceRecord.vehicle_id == vehicle_id)
    
    records = session.exec(stmt.order_by(ServiceRecord.completed_date.desc(), ServiceRecord.completed_mileage.desc())).all()
    return [_enrich_record_read(r) for r in records]

@router.post("/records", response_model=ServiceRecordRead, status_code=201)
def create_service_record(payload: ServiceRecordCreate, session: Session = Depends(get_session)):
    vehicle = session.get(Vehicle, payload.vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Associated vehicle not found.")
    
    # Auto-update vehicle mileage if recorded service mileage is higher
    if payload.completed_mileage > vehicle.current_mileage:
        vehicle.current_mileage = payload.completed_mileage
        session.add(vehicle)

    # Compute total cost if components provided
    total_cost = payload.total_cost
    if total_cost == 0.0 and (payload.labor_cost > 0 or payload.parts_cost > 0):
        total_cost = payload.labor_cost + payload.parts_cost

    record_dict = payload.model_dump()
    record_dict["total_cost"] = total_cost
    record = ServiceRecord(**record_dict)

    session.add(record)
    session.commit()
    session.refresh(record)
    return _enrich_record_read(record)

@router.get("/records/{record_id}", response_model=ServiceRecordRead)
def get_service_record(record_id: int, session: Session = Depends(get_session)):
    record = session.get(ServiceRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Service record not found.")
    return _enrich_record_read(record)

@router.put("/records/{record_id}", response_model=ServiceRecordRead)
def update_service_record(
    record_id: int,
    payload: ServiceRecordUpdate,
    session: Session = Depends(get_session)
):
    record = session.get(ServiceRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Service record not found.")
    
    update_data = payload.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(record, k, v)

    if ("labor_cost" in update_data or "parts_cost" in update_data) and "total_cost" not in update_data:
        record.total_cost = (record.labor_cost or 0.0) + (record.parts_cost or 0.0)

    # Auto-update vehicle mileage if new completed_mileage is higher
    if record.completed_mileage:
        vehicle = session.get(Vehicle, record.vehicle_id)
        if vehicle and record.completed_mileage > vehicle.current_mileage:
            vehicle.current_mileage = record.completed_mileage
            session.add(vehicle)

    session.add(record)
    session.commit()
    session.refresh(record)
    return _enrich_record_read(record)

@router.delete("/records/{record_id}")
def delete_service_record(record_id: int, session: Session = Depends(get_session)):
    record = session.get(ServiceRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Service record not found.")
    session.delete(record)
    session.commit()
    return {"message": "Service record deleted successfully."}

# --- Service Record Attachments (Receipts, Invoices, Worksheets) ---
@router.post("/records/{record_id}/attachment", response_model=ServiceRecordRead)
async def upload_service_record_attachment(
    record_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    rec = session.get(ServiceRecord, record_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Service record not found.")
    
    if not AttachmentService.is_allowed_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail="File type not supported. Allowed formats: PDF, PNG, JPG, TIF, XLS/XLSX, DOC/DOCX, TXT, RTF, HTML, MD"
        )
    
    file_bytes = await file.read()
    content_type = AttachmentService.detect_content_type(file.filename, file.content_type or "application/octet-stream")
    
    rec.file_data = file_bytes
    rec.file_name = file.filename
    rec.file_content_type = content_type
    rec.file_size = len(file_bytes)
    
    session.add(rec)
    session.commit()
    session.refresh(rec)
    return _enrich_record_read(rec)

@router.get("/records/{record_id}/attachment")
def download_service_record_attachment(
    record_id: int,
    download: bool = Query(False, description="Set True to force download attachment"),
    session: Session = Depends(get_session)
):
    rec = session.get(ServiceRecord, record_id)
    if not rec or not rec.file_data:
        raise HTTPException(status_code=404, detail="No attachment found for this service record.")
    
    disposition = "attachment" if download else "inline"
    content_type = rec.file_content_type or "application/octet-stream"
    
    return Response(
        content=rec.file_data,
        media_type=content_type,
        headers={
            "Content-Disposition": f'{disposition}; filename="{rec.file_name or "receipt"}"',
            "Content-Length": str(rec.file_size or len(rec.file_data)),
        }
    )

@router.delete("/records/{record_id}/attachment", response_model=ServiceRecordRead)
def delete_service_record_attachment(record_id: int, session: Session = Depends(get_session)):
    rec = session.get(ServiceRecord, record_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Service record not found.")
    
    rec.file_data = None
    rec.file_name = None
    rec.file_content_type = None
    rec.file_size = None
    
    session.add(rec)
    session.commit()
    session.refresh(rec)
    return _enrich_record_read(rec)
