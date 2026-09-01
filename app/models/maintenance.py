from app.config import get_utc_now
from datetime import date, datetime
from enum import Enum
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship

class PerformedByType(str, Enum):
    DIY = "DIY"
    EXTERNAL_SHOP = "EXTERNAL_SHOP"
    DEALERSHIP = "DEALERSHIP"

class ServiceStatus(str, Enum):
    OK = "OK"
    DUE_SOON = "DUE_SOON"  # within threshold (e.g. 500 miles or 30 days)
    OVERDUE = "OVERDUE"    # past mileage or past calendar date

class ServiceDefinitionBase(SQLModel):
    service_name: str = Field(index=True)
    description: Optional[str] = None
    interval_miles: int = Field(default=5000, ge=500)
    interval_months: int = Field(default=6, ge=1)
    is_recurring: bool = Field(default=True)
    severe_duty_interval_miles: Optional[int] = None
    severe_duty_interval_months: Optional[int] = None
    category: str = Field(default="GENERAL")

class ServiceDefinition(ServiceDefinitionBase, table=True):
    __tablename__ = "service_definitions"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=get_utc_now)

    # Relationships
    service_records: List["ServiceRecord"] = Relationship(back_populates="service_definition")

class ServiceDefinitionCreate(ServiceDefinitionBase):
    pass

class ServiceDefinitionRead(ServiceDefinitionBase):
    id: int
    created_at: datetime

class ServiceRecordBase(SQLModel):
    vehicle_id: int = Field(foreign_key="vehicles.id", index=True)
    service_definition_id: Optional[int] = Field(default=None, foreign_key="service_definitions.id", index=True)
    service_name: str
    completed_date: date
    completed_mileage: int = Field(ge=0)
    performed_by_type: PerformedByType = Field(default=PerformedByType.DIY)
    total_cost: float = Field(default=0.0, ge=0.0)
    labor_cost: float = Field(default=0.0, ge=0.0)
    parts_cost: float = Field(default=0.0, ge=0.0)
    service_shop_id: Optional[int] = Field(default=None, foreign_key="service_shops.id")
    file_name: Optional[str] = None
    file_content_type: Optional[str] = None
    file_size: Optional[int] = None
    notes: Optional[str] = None

class ServiceRecord(ServiceRecordBase, table=True):
    __tablename__ = "service_records"

    id: Optional[int] = Field(default=None, primary_key=True)
    file_data: Optional[bytes] = Field(default=None)
    created_at: datetime = Field(default_factory=get_utc_now)

    # Relationships
    vehicle: Optional["Vehicle"] = Relationship(back_populates="service_records")
    service_definition: Optional[ServiceDefinition] = Relationship(back_populates="service_records")
    service_shop: Optional["ServiceShop"] = Relationship(back_populates="service_records")

class ServiceRecordCreate(ServiceRecordBase):
    pass

class ServiceRecordRead(ServiceRecordBase):
    id: int
    created_at: datetime
    has_attachment: bool = False

class ServiceRecordUpdate(SQLModel):
    service_name: Optional[str] = None
    completed_date: Optional[date] = None
    completed_mileage: Optional[int] = None
    performed_by_type: Optional[PerformedByType] = None
    total_cost: Optional[float] = None
    labor_cost: Optional[float] = None
    parts_cost: Optional[float] = None
    service_shop_id: Optional[int] = None
    notes: Optional[str] = None

class MaintenanceForecast(SQLModel):
    service_definition_id: int
    service_name: str
    interval_miles: int
    interval_months: int
    last_completed_date: Optional[date] = None
    last_completed_mileage: Optional[int] = None
    next_due_mileage: int
    next_due_date: date
    projected_due_date_by_mileage: date
    miles_remaining: int
    days_remaining: int
    status: ServiceStatus
    action_summary: str
