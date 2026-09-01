from app.config import get_utc_now
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from app.database import get_session
from app.models.vehicle_knowledge import (
    VehicleKnowledge,
    VehicleKnowledgeCreate,
    VehicleKnowledgeRead,
    VehicleKnowledgeUpdate,
    KnowledgeCategory,
    ComponentSystem,
    SeverityLevel,
)
from app.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/api/v1/knowledge", tags=["Vehicle Knowledge & Quirks"])

@router.get("", response_model=List[VehicleKnowledgeRead])
def search_knowledge(
    query: Optional[str] = Query(None, description="Search term in title, description, real-world data"),
    vehicle_id: Optional[int] = Query(None, description="Filter by vehicle ID"),
    category: Optional[KnowledgeCategory] = Query(None, description="Filter by category"),
    component_system: Optional[ComponentSystem] = Query(None, description="Filter by component system"),
    severity: Optional[SeverityLevel] = Query(None, description="Filter by severity level"),
    session: Session = Depends(get_session)
):
    return KnowledgeService.search_vehicle_knowledge(
        session=session,
        query=query,
        vehicle_id=vehicle_id,
        category=category,
        component_system=component_system,
        severity=severity,
    )

@router.post("", response_model=VehicleKnowledgeRead, status_code=201)
def create_knowledge_entry(payload: VehicleKnowledgeCreate, session: Session = Depends(get_session)):
    entry = VehicleKnowledge.model_validate(payload)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry

@router.get("/{entry_id}", response_model=VehicleKnowledgeRead)
def get_knowledge_entry(entry_id: int, session: Session = Depends(get_session)):
    entry = session.get(VehicleKnowledge, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Knowledge entry not found.")
    return entry

@router.put("/{entry_id}", response_model=VehicleKnowledgeRead)
def update_knowledge_entry(
    entry_id: int,
    payload: VehicleKnowledgeUpdate,
    session: Session = Depends(get_session)
):
    entry = session.get(VehicleKnowledge, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Knowledge entry not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(entry, k, v)

    entry.updated_at = get_utc_now()
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry

@router.delete("/{entry_id}")
def delete_knowledge_entry(entry_id: int, session: Session = Depends(get_session)):
    entry = session.get(VehicleKnowledge, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Knowledge entry not found.")
    session.delete(entry)
    session.commit()
    return {"message": "Knowledge entry deleted successfully."}
