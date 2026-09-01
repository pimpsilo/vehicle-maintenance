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
    MaintenanceForecast,
)
from app.models.vehicle import Vehicle
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
