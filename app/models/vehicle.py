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
    photo_data: Optional[bytes] = Field(default=None)
    photo_content_type: Optional[str] = Field(default=None)
    photo_filename: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)

    # Relationships
    documents: List["VehicleDocument"] = Relationship(back_populates="vehicle", cascade_delete=True)
    service_records: List["ServiceRecord"] = Relationship(back_populates="vehicle", cascade_delete=True)
    external_service_orders: List["ExternalServiceOrder"] = Relationship(back_populates="vehicle", cascade_delete=True)
    consumables: List["ConsumableSpecification"] = Relationship(back_populates="vehicle", cascade_delete=True)
    reference_docs: List["ReferenceDocument"] = Relationship(back_populates="vehicle", cascade_delete=True)
    knowledge_records: List["VehicleKnowledge"] = Relationship(back_populates="vehicle", cascade_delete=True)
    odometer_entries: List["OdometerEntry"] = Relationship(back_populates="vehicle", cascade_delete=True)

    @property
    def photo_url(self) -> Optional[str]:
        if self.id and self.photo_data:
            return f"/api/v1/vehicles/{self.id}/photo"
        return None

    @property
    def has_photo(self) -> bool:
        return bool(self.photo_data)

class VehicleCreate(VehicleBase):
    pass

class VehicleRead(VehicleBase):
    id: int
    created_at: datetime
    updated_at: datetime
    has_photo: bool = False
    photo_url: Optional[str] = None

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

class OdometerEntryBase(SQLModel):
    vehicle_id: int = Field(foreign_key="vehicles.id", index=True)
    mileage: int = Field(ge=0)
    recorded_at: datetime = Field(default_factory=get_utc_now)

class OdometerEntry(OdometerEntryBase, table=True):
    __tablename__ = "odometer_entries"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Relationship
    vehicle: Optional["Vehicle"] = Relationship(back_populates="odometer_entries")

class OdometerEntryRead(OdometerEntryBase):
    id: int

class MonthMileagePoint(SQLModel):
    month: str  # YYYY-MM
    miles: float

class VehicleUsageStats(SQLModel):
    vehicle_id: int
    insufficient_data: bool = True
    total_miles: Optional[int] = None
    observation_span_days: Optional[float] = None
    average_miles_per_day: Optional[float] = None
    miles_per_week: Optional[float] = None
    miles_per_month: Optional[float] = None
    miles_per_year: Optional[float] = None
    last_30_days_miles: Optional[float] = None
    last_90_days_miles: Optional[float] = None
    last_365_days_miles: Optional[float] = None
    monthly_series: List[MonthMileagePoint] = []

