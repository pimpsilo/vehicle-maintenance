from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
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

router = APIRouter(prefix="/api/v1/maintenance", tags=["Maintenance"])

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
    
    return session.exec(stmt.order_by(ServiceRecord.completed_date.desc(), ServiceRecord.completed_mileage.desc())).all()

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
    return record

@router.delete("/records/{record_id}")
def delete_service_record(record_id: int, session: Session = Depends(get_session)):
    record = session.get(ServiceRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Service record not found.")
    session.delete(record)
    session.commit()
    return {"message": "Service record deleted successfully."}
