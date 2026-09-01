from app.config import get_utc_now
from datetime import datetime
from enum import Enum
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship

class DocCategory(str, Enum):
    OFFICIAL_MANUAL = "OFFICIAL_MANUAL"
    COMMUNITY_DIY_GUIDE = "COMMUNITY_DIY_GUIDE"
    TSB_BULLETIN = "TSB_BULLETIN"
    VIDEO_TUTORIAL = "VIDEO_TUTORIAL"
    WIRING_DIAGRAM = "WIRING_DIAGRAM"
    PARTS_DIAGRAM = "PARTS_DIAGRAM"

class DifficultyRating(str, Enum):
    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"
    PROFESSIONAL = "PROFESSIONAL"

class ReferenceDocumentBase(SQLModel):
    vehicle_id: Optional[int] = Field(default=None, foreign_key="vehicles.id", index=True)
    service_definition_id: Optional[int] = Field(default=None, foreign_key="service_definitions.id", index=True)
    title: str = Field(index=True)
    doc_category: DocCategory = Field(default=DocCategory.COMMUNITY_DIY_GUIDE, index=True)
    source_name_or_url: str = Field(description="e.g. Toyota Owner Portal, ToyotaNation, YouTube")
    difficulty: DifficultyRating = Field(default=DifficultyRating.INTERMEDIATE)
    tools_required: Optional[str] = None
    estimated_hours: Optional[float] = Field(default=None, ge=0.0)
    step_by_step_instructions: str
    early_service_community_tips: Optional[str] = Field(
        default=None,
        description="Tips & experiences from owners who performed this repair earlier than scheduled"
    )
    tags: Optional[str] = Field(default=None, description="Comma-separated tags e.g. 'spark-plugs, 2gr-fe, intake-removal'")
    file_name: Optional[str] = None
    file_content_type: Optional[str] = None
    file_size: Optional[int] = None

class ReferenceDocument(ReferenceDocumentBase, table=True):
    __tablename__ = "reference_documents"

    id: Optional[int] = Field(default=None, primary_key=True)
    file_data: Optional[bytes] = Field(default=None)
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)

    # Relationships
    vehicle: Optional["Vehicle"] = Relationship(back_populates="reference_docs")

class ReferenceDocumentCreate(ReferenceDocumentBase):
    pass

class ReferenceDocumentRead(ReferenceDocumentBase):
    id: int
    created_at: datetime
    updated_at: datetime
    has_attachment: bool = False

class ReferenceDocumentUpdate(SQLModel):
    title: Optional[str] = None
    doc_category: Optional[DocCategory] = None
    source_name_or_url: Optional[str] = None
    difficulty: Optional[DifficultyRating] = None
    tools_required: Optional[str] = None
    estimated_hours: Optional[float] = None
    step_by_step_instructions: Optional[str] = None
    early_service_community_tips: Optional[str] = None
    tags: Optional[str] = None
    file_name: Optional[str] = None
    file_content_type: Optional[str] = None
    file_size: Optional[int] = None
