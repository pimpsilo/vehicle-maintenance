from app.config import get_utc_now
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from app.database import get_session
from app.models.consumable import (
    ConsumableSpecification,
    ConsumableCreate,
    ConsumableRead,
    ConsumableUpdate,
    ConsumableCategory,
)
from app.models.vehicle import Vehicle

router = APIRouter(prefix="/api/v1/consumables", tags=["Consumable Specifications"])

@router.get("", response_model=List[ConsumableRead])
def list_consumables(
    vehicle_id: Optional[int] = Query(None, description="Filter by vehicle ID"),
    category: Optional[ConsumableCategory] = Query(None, description="Filter by consumable category"),
    session: Session = Depends(get_session)
):
    stmt = select(ConsumableSpecification)
    if vehicle_id:
        stmt = stmt.where(ConsumableSpecification.vehicle_id == vehicle_id)
    if category:
        stmt = stmt.where(ConsumableSpecification.category == category)
    
    return session.exec(stmt.order_by(ConsumableSpecification.category.asc())).all()

@router.post("", response_model=ConsumableRead, status_code=201)
def create_consumable(payload: ConsumableCreate, session: Session = Depends(get_session)):
    vehicle = session.get(Vehicle, payload.vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Associated vehicle not found.")

    item = ConsumableSpecification.model_validate(payload)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item

@router.get("/{item_id}", response_model=ConsumableRead)
def get_consumable(item_id: int, session: Session = Depends(get_session)):
    item = session.get(ConsumableSpecification, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Consumable specification not found.")
    return item

@router.put("/{item_id}", response_model=ConsumableRead)
def update_consumable(
    item_id: int,
    payload: ConsumableUpdate,
    session: Session = Depends(get_session)
):
    item = session.get(ConsumableSpecification, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Consumable specification not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(item, k, v)

    item.updated_at = get_utc_now()
    session.add(item)
    session.commit()
    session.refresh(item)
    return item

@router.delete("/{item_id}")
def delete_consumable(item_id: int, session: Session = Depends(get_session)):
    item = session.get(ConsumableSpecification, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Consumable specification not found.")
    session.delete(item)
    session.commit()
    return {"message": "Consumable specification deleted successfully."}
