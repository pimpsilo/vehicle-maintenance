from app.config import get_utc_now
from datetime import datetime
from enum import Enum
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship

class KnowledgeCategory(str, Enum):
    KNOWN_QUIRK = "KNOWN_QUIRK"
    COMMON_FAILURE_POINT = "COMMON_FAILURE_POINT"
    REAL_WORLD_PERFORMANCE = "REAL_WORLD_PERFORMANCE"
    COMMUNITY_WISDOM = "COMMUNITY_WISDOM"
    MAINTENANCE_PRECAUTION = "MAINTENANCE_PRECAUTION"

class ComponentSystem(str, Enum):
    ENGINE = "ENGINE"
    TRANSMISSION = "TRANSMISSION"
    SUSPENSION = "SUSPENSION"
    BRAKES = "BRAKES"
    ELECTRICAL = "ELECTRICAL"
    HVAC = "HVAC"
    BODY_INTERIOR = "BODY_INTERIOR"
    EXHAUST = "EXHAUST"
    FUEL_SYSTEM = "FUEL_SYSTEM"
    GENERAL = "GENERAL"

class SeverityLevel(str, Enum):
    INFO = "INFO"
    WATCH_ITEM = "WATCH_ITEM"
    MODERATE_RISK = "MODERATE_RISK"
    CRITICAL_REPAIR = "CRITICAL_REPAIR"

class VehicleKnowledgeBase(SQLModel):
    vehicle_id: Optional[int] = Field(default=None, foreign_key="vehicles.id", index=True)
    category: KnowledgeCategory = Field(default=KnowledgeCategory.KNOWN_QUIRK, index=True)
    component_system: ComponentSystem = Field(default=ComponentSystem.GENERAL, index=True)
    title: str = Field(index=True)
    description: str
    mileage_onset_range: Optional[str] = Field(default=None, description="e.g. 80k - 120k miles")
    severity: SeverityLevel = Field(default=SeverityLevel.INFO)
    real_world_data: Optional[str] = Field(default=None, description="Observed MPG, census failure rates, owner survey results")
    recommended_action: Optional[str] = Field(default=None, description="Preventative tips, inspection steps, or replacement parts")
    source_community: Optional[str] = Field(default=None, description="e.g. ToyotaNation, ClubLexus, NHTSA complaints")

class VehicleKnowledge(VehicleKnowledgeBase, table=True):
    __tablename__ = "vehicle_knowledge"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)

    # Relationship
    vehicle: Optional["Vehicle"] = Relationship(back_populates="knowledge_records")

class VehicleKnowledgeCreate(VehicleKnowledgeBase):
    pass

class VehicleKnowledgeRead(VehicleKnowledgeBase):
    id: int
    created_at: datetime
    updated_at: datetime

class VehicleKnowledgeUpdate(SQLModel):
    category: Optional[KnowledgeCategory] = None
    component_system: Optional[ComponentSystem] = None
    title: Optional[str] = None
    description: Optional[str] = None
    mileage_onset_range: Optional[str] = None
    severity: Optional[SeverityLevel] = None
    real_world_data: Optional[str] = None
    recommended_action: Optional[str] = None
    source_community: Optional[str] = None
