from datetime import date
from typing import List, Tuple
from sqlmodel import Session, select
from app.models.document import VehicleDocument, DocumentStatus, VehicleDocumentRead
from app.config import settings

class DocumentService:
    @staticmethod
    def evaluate_status(doc: VehicleDocument, current_date: date = None) -> Tuple[DocumentStatus, int]:
        """
        Calculates the document status and remaining days until expiration.
        """
        if current_date is None:
            current_date = date.today()
        
        days_remaining = (doc.expiration_date - current_date).days
        lead_days = doc.lead_alert_days or settings.document_warning_lead_days

        if days_remaining < 0:
            status = DocumentStatus.EXPIRED
        elif days_remaining <= settings.document_critical_lead_days:
            status = DocumentStatus.EXPIRING_CRITICAL
        elif days_remaining <= lead_days:
            status = DocumentStatus.EXPIRING_WARNING
        else:
            status = DocumentStatus.ACTIVE

        return status, days_remaining

    @staticmethod
    def enrich_document_read(doc: VehicleDocument, current_date: date = None) -> VehicleDocumentRead:
        status, days_remaining = DocumentService.evaluate_status(doc, current_date)
        return VehicleDocumentRead(
            id=doc.id,
            vehicle_id=doc.vehicle_id,
            doc_type=doc.doc_type,
            document_number=doc.document_number,
            issuer=doc.issuer,
            effective_date=doc.effective_date,
            expiration_date=doc.expiration_date,
            lead_alert_days=doc.lead_alert_days,
            file_name=doc.file_name,
            file_content_type=doc.file_content_type,
            file_size=doc.file_size,
            notes=doc.notes,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            status=status,
            days_until_expiration=days_remaining,
            has_attachment=bool(doc.file_data),
        )

    @staticmethod
    def get_expiring_documents(session: Session, vehicle_id: int = None, current_date: date = None) -> List[VehicleDocumentRead]:
        """
        Returns all documents that are EXPIRED, EXPIRING_CRITICAL, or EXPIRING_WARNING.
        """
        stmt = select(VehicleDocument)
        if vehicle_id:
            stmt = stmt.where(VehicleDocument.vehicle_id == vehicle_id)
        
        docs = session.exec(stmt).all()
        expiring = []
        for doc in docs:
            enriched = DocumentService.enrich_document_read(doc, current_date)
            if enriched.status != DocumentStatus.ACTIVE:
                expiring.append(enriched)
        return expiring
