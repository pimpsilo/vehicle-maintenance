from app.config import get_utc_now
from datetime import date, datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship

class VehicleBase(SQLModel):
    vin: str = Field(index=True, unique=True, min_length=11, max_length=17)
    year: int = Field(ge=1900, le=2100)
    make: str = Field(index=True)
    model: str = Field(index=True)
    trim: Optional[str] = None
    license_plate: Optional[str] = None
    ezpass_transponder: Optional[str] = Field(default=None, description="EZ-Pass / Toll Transponder Tag ID")
    current_mileage: int = Field(default=0, ge=0)
    estimated_annual_mileage: int = Field(default=12000, ge=1000)
    purchase_date: Optional[date] = None
    notes: Optional[str] = None

class Vehicle(VehicleBase, table=True):
    __tablename__ = "vehicles"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)

    # Relationships
    documents: List["VehicleDocument"] = Relationship(back_populates="vehicle", cascade_delete=True)
    service_records: List["ServiceRecord"] = Relationship(back_populates="vehicle", cascade_delete=True)
    external_service_orders: List["ExternalServiceOrder"] = Relationship(back_populates="vehicle", cascade_delete=True)
    consumables: List["ConsumableSpecification"] = Relationship(back_populates="vehicle", cascade_delete=True)
    reference_docs: List["ReferenceDocument"] = Relationship(back_populates="vehicle", cascade_delete=True)
    knowledge_records: List["VehicleKnowledge"] = Relationship(back_populates="vehicle", cascade_delete=True)

class VehicleCreate(VehicleBase):
    pass

class VehicleRead(VehicleBase):
    id: int
    created_at: datetime
    updated_at: datetime

class VehicleUpdate(SQLModel):
    vin: Optional[str] = None
    year: Optional[int] = None
    make: Optional[str] = None
    model: Optional[str] = None
    trim: Optional[str] = None
    license_plate: Optional[str] = None
    ezpass_transponder: Optional[str] = None
    current_mileage: Optional[int] = None
    estimated_annual_mileage: Optional[int] = None
    purchase_date: Optional[date] = None
    notes: Optional[str] = None

class OdometerUpdate(SQLModel):
    current_mileage: int = Field(ge=0)
    recorded_date: Optional[date] = None
