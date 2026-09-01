from app.config import get_utc_now
from datetime import date, datetime
from enum import Enum
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship

class DocumentType(str, Enum):
    REGISTRATION = "REGISTRATION"
    INSURANCE = "INSURANCE"
    EMISSIONS_INSPECTION = "EMISSIONS_INSPECTION"
    SAFETY_INSPECTION = "SAFETY_INSPECTION"
    TITLE = "TITLE"
    WARRANTY = "WARRANTY"
    OTHER = "OTHER"

class DocumentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    EXPIRING_WARNING = "EXPIRING_WARNING"    # e.g., within 30 days
    EXPIRING_CRITICAL = "EXPIRING_CRITICAL"  # e.g., within 7 days
    EXPIRED = "EXPIRED"

class VehicleDocumentBase(SQLModel):
    vehicle_id: int = Field(foreign_key="vehicles.id", index=True)
    doc_type: DocumentType = Field(default=DocumentType.REGISTRATION)
    document_number: str = Field(index=True)
    issuer: str = Field(description="e.g. State DMV, Geico, State Farm")
    effective_date: date
    expiration_date: date
    lead_alert_days: int = Field(default=30, ge=1)
    file_name: Optional[str] = None
    file_content_type: Optional[str] = None
    file_size: Optional[int] = None
    notes: Optional[str] = None

class VehicleDocument(VehicleDocumentBase, table=True):
    __tablename__ = "vehicle_documents"

    id: Optional[int] = Field(default=None, primary_key=True)
    file_data: Optional[bytes] = Field(default=None)
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)

    # Relationship
    vehicle: Optional["Vehicle"] = Relationship(back_populates="documents")

class VehicleDocumentCreate(VehicleDocumentBase):
    pass

class VehicleDocumentRead(VehicleDocumentBase):
    id: int
    created_at: datetime
    updated_at: datetime
    status: DocumentStatus = DocumentStatus.ACTIVE
    days_until_expiration: int = 0
    has_attachment: bool = False

class VehicleDocumentUpdate(SQLModel):
    doc_type: Optional[DocumentType] = None
    document_number: Optional[str] = None
    issuer: Optional[str] = None
    effective_date: Optional[date] = None
    expiration_date: Optional[date] = None
    lead_alert_days: Optional[int] = None
    file_name: Optional[str] = None
    file_content_type: Optional[str] = None
    file_size: Optional[int] = None
    notes: Optional[str] = None
