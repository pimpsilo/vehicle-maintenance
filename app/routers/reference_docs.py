from app.config import get_utc_now
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Response
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
from app.services.attachment_service import AttachmentService

router = APIRouter(prefix="/api/v1/reference-docs", tags=["Reference Documents & Manuals"])

def _enrich_read(doc: ReferenceDocument) -> ReferenceDocumentRead:
    return ReferenceDocumentRead(
        id=doc.id,
        vehicle_id=doc.vehicle_id,
        service_definition_id=doc.service_definition_id,
        title=doc.title,
        doc_category=doc.doc_category,
        source_name_or_url=doc.source_name_or_url,
        difficulty=doc.difficulty,
        tools_required=doc.tools_required,
        estimated_hours=doc.estimated_hours,
        step_by_step_instructions=doc.step_by_step_instructions,
        early_service_community_tips=doc.early_service_community_tips,
        tags=doc.tags,
        file_name=doc.file_name,
        file_content_type=doc.file_content_type,
        file_size=doc.file_size,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        has_attachment=bool(doc.file_data),
    )

@router.get("", response_model=List[ReferenceDocumentRead])
def search_reference_docs(
    query: Optional[str] = Query(None, description="Search term in title, instructions, tools, tags"),
    vehicle_id: Optional[int] = Query(None, description="Filter by vehicle ID"),
    category: Optional[DocCategory] = Query(None, description="Filter by document category"),
    difficulty: Optional[DifficultyRating] = Query(None, description="Filter by difficulty"),
    session: Session = Depends(get_session)
):
    docs = KnowledgeService.search_reference_docs(
        session=session,
        query=query,
        vehicle_id=vehicle_id,
        category=category,
        difficulty=difficulty,
    )
    return [_enrich_read(d) if isinstance(d, ReferenceDocument) else d for d in docs]

@router.post("", response_model=ReferenceDocumentRead, status_code=201)
def create_reference_doc(payload: ReferenceDocumentCreate, session: Session = Depends(get_session)):
    doc = ReferenceDocument.model_validate(payload)
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return _enrich_read(doc)

@router.get("/{doc_id}", response_model=ReferenceDocumentRead)
def get_reference_doc(doc_id: int, session: Session = Depends(get_session)):
    doc = session.get(ReferenceDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Reference document not found.")
    return _enrich_read(doc)

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
    return _enrich_read(doc)

@router.delete("/{doc_id}")
def delete_reference_doc(doc_id: int, session: Session = Depends(get_session)):
    doc = session.get(ReferenceDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Reference document not found.")
    session.delete(doc)
    session.commit()
    return {"message": "Reference document deleted successfully."}

# --- Reference Doc Attachments (PDF, PNG, JPG, TIF, XLS, DOC, TXT, RTF, HTML, MD) ---
@router.post("/{doc_id}/attachment", response_model=ReferenceDocumentRead)
async def upload_reference_doc_attachment(
    doc_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    doc = session.get(ReferenceDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Reference document not found.")
    
    if not AttachmentService.is_allowed_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail="File type not supported. Allowed formats: PDF, PNG, JPG, TIF, XLS/XLSX, DOC/DOCX, TXT, RTF, HTML, MD"
        )
    
    file_bytes = await file.read()
    content_type = AttachmentService.detect_content_type(file.filename, file.content_type or "application/octet-stream")
    
    doc.file_data = file_bytes
    doc.file_name = file.filename
    doc.file_content_type = content_type
    doc.file_size = len(file_bytes)
    doc.updated_at = get_utc_now()
    
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return _enrich_read(doc)

@router.get("/{doc_id}/attachment")
def download_reference_doc_attachment(
    doc_id: int,
    download: bool = Query(False, description="Set True to force download attachment"),
    session: Session = Depends(get_session)
):
    doc = session.get(ReferenceDocument, doc_id)
    if not doc or not doc.file_data:
        raise HTTPException(status_code=404, detail="No attachment found for this reference document.")
    
    disposition = "attachment" if download else "inline"
    content_type = doc.file_content_type or "application/octet-stream"
    
    return Response(
        content=doc.file_data,
        media_type=content_type,
        headers={
            "Content-Disposition": f'{disposition}; filename="{doc.file_name or "manual"}"',
            "Content-Length": str(doc.file_size or len(doc.file_data)),
        }
    )

@router.delete("/{doc_id}/attachment", response_model=ReferenceDocumentRead)
def delete_reference_doc_attachment(doc_id: int, session: Session = Depends(get_session)):
    doc = session.get(ReferenceDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Reference document not found.")
    
    doc.file_data = None
    doc.file_name = None
    doc.file_content_type = None
    doc.file_size = None
    doc.updated_at = get_utc_now()
    
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return _enrich_read(doc)
