from app.config import get_utc_now
from datetime import datetime, date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Response
from sqlmodel import Session, select
from app.database import get_session
from app.models.document import (
    VehicleDocument,
    VehicleDocumentCreate,
    VehicleDocumentRead,
    VehicleDocumentUpdate,
)
from app.models.vehicle import Vehicle
from app.services.document_service import DocumentService
from app.services.attachment_service import AttachmentService

router = APIRouter(prefix="/api/v1/documents", tags=["Documents"])

@router.get("", response_model=List[VehicleDocumentRead])
def list_documents(
    vehicle_id: Optional[int] = Query(None, description="Filter by vehicle ID"),
    session: Session = Depends(get_session)
):
    stmt = select(VehicleDocument)
    if vehicle_id:
        stmt = stmt.where(VehicleDocument.vehicle_id == vehicle_id)
    
    docs = session.exec(stmt).all()
    return [DocumentService.enrich_document_read(d) for d in docs]

@router.post("", response_model=VehicleDocumentRead, status_code=201)
def create_document(payload: VehicleDocumentCreate, session: Session = Depends(get_session)):
    vehicle = session.get(Vehicle, payload.vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Associated vehicle not found.")
    
    doc = VehicleDocument.model_validate(payload)
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return DocumentService.enrich_document_read(doc)

@router.get("/expiring", response_model=List[VehicleDocumentRead])
def get_expiring_documents(
    vehicle_id: Optional[int] = Query(None, description="Filter by vehicle ID"),
    session: Session = Depends(get_session)
):
    return DocumentService.get_expiring_documents(session, vehicle_id=vehicle_id)

@router.get("/{document_id}", response_model=VehicleDocumentRead)
def get_document(document_id: int, session: Session = Depends(get_session)):
    doc = session.get(VehicleDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentService.enrich_document_read(doc)

@router.put("/{document_id}", response_model=VehicleDocumentRead)
def update_document(
    document_id: int,
    payload: VehicleDocumentUpdate,
    session: Session = Depends(get_session)
):
    doc = session.get(VehicleDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    
    update_data = payload.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(doc, k, v)
    
    doc.updated_at = get_utc_now()
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return DocumentService.enrich_document_read(doc)

@router.delete("/{document_id}")
def delete_document(document_id: int, session: Session = Depends(get_session)):
    doc = session.get(VehicleDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    session.delete(doc)
    session.commit()
    return {"message": "Document deleted successfully."}

# --- Document Attachments (PDF, PNG, JPG, TIF, XLS, DOC, TXT, RTF, HTML, MD) ---
@router.post("/{document_id}/attachment", response_model=VehicleDocumentRead)
async def upload_document_attachment(
    document_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    doc = session.get(VehicleDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    
    if not AttachmentService.is_allowed_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"File type not supported. Allowed formats: PDF, PNG, JPG, TIF, XLS/XLSX, DOC/DOCX, TXT, RTF, HTML, MD"
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
    return DocumentService.enrich_document_read(doc)

@router.get("/{document_id}/attachment")
def download_document_attachment(
    document_id: int,
    download: bool = Query(False, description="Set True to force download attachment"),
    session: Session = Depends(get_session)
):
    doc = session.get(VehicleDocument, document_id)
    if not doc or not doc.file_data:
        raise HTTPException(status_code=404, detail="No attachment found for this document.")
    
    disposition = "attachment" if download else "inline"
    content_type = doc.file_content_type or "application/octet-stream"
    
    return Response(
        content=doc.file_data,
        media_type=content_type,
        headers={
            "Content-Disposition": f'{disposition}; filename="{doc.file_name or "document"}"',
            "Content-Length": str(doc.file_size or len(doc.file_data)),
        }
    )

@router.delete("/{document_id}/attachment", response_model=VehicleDocumentRead)
def delete_document_attachment(document_id: int, session: Session = Depends(get_session)):
    doc = session.get(VehicleDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    
    doc.file_data = None
    doc.file_name = None
    doc.file_content_type = None
    doc.file_size = None
    doc.updated_at = get_utc_now()
    
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return DocumentService.enrich_document_read(doc)
