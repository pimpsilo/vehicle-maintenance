from app.config import get_utc_now
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from app.database import get_session
from app.models.reference_doc import (
    ReferenceDocument,
    ReferenceDocumentCreate,
    ReferenceDocumentRead,
    ReferenceDocumentUpdate,
    DocCategory,
    DifficultyRating,
)
from app.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/api/v1/reference-docs", tags=["Reference Documents & Manuals"])

@router.get("", response_model=List[ReferenceDocumentRead])
def search_reference_docs(
    query: Optional[str] = Query(None, description="Search term in title, instructions, tools, tags"),
    vehicle_id: Optional[int] = Query(None, description="Filter by vehicle ID"),
    category: Optional[DocCategory] = Query(None, description="Filter by document category"),
    difficulty: Optional[DifficultyRating] = Query(None, description="Filter by difficulty"),
    session: Session = Depends(get_session)
):
    return KnowledgeService.search_reference_docs(
        session=session,
        query=query,
        vehicle_id=vehicle_id,
        category=category,
        difficulty=difficulty,
    )

@router.post("", response_model=ReferenceDocumentRead, status_code=201)
def create_reference_doc(payload: ReferenceDocumentCreate, session: Session = Depends(get_session)):
    doc = ReferenceDocument.model_validate(payload)
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc

@router.get("/{doc_id}", response_model=ReferenceDocumentRead)
def get_reference_doc(doc_id: int, session: Session = Depends(get_session)):
    doc = session.get(ReferenceDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Reference document not found.")
    return doc

@router.put("/{doc_id}", response_model=ReferenceDocumentRead)
def update_reference_doc(
    doc_id: int,
    payload: ReferenceDocumentUpdate,
    session: Session = Depends(get_session)
):
    doc = session.get(ReferenceDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Reference document not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(doc, k, v)

    doc.updated_at = get_utc_now()
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc

@router.delete("/{doc_id}")
def delete_reference_doc(doc_id: int, session: Session = Depends(get_session)):
    doc = session.get(ReferenceDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Reference document not found.")
    session.delete(doc)
    session.commit()
    return {"message": "Reference document deleted successfully."}
