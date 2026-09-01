from app.config import get_utc_now
from datetime import datetime
from enum import Enum
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship

class ConsumableCategory(str, Enum):
    WIPER_BLADES = "WIPER_BLADES"
    ENGINE_AIR_FILTER = "ENGINE_AIR_FILTER"
    CABIN_AIR_FILTER = "CABIN_AIR_FILTER"
    TIRES = "TIRES"
    TIRE_PRESSURE = "TIRE_PRESSURE"
    ENGINE_OIL = "ENGINE_OIL"
    OIL_FILTER = "OIL_FILTER"
    FUEL_GRADE = "FUEL_GRADE"
    BRAKE_FLUID = "BRAKE_FLUID"
    BRAKE_PADS = "BRAKE_PADS"
    COOLANT = "COOLANT"
    TRANSMISSION_FLUID = "TRANSMISSION_FLUID"
    SPARK_PLUGS = "SPARK_PLUGS"
    BATTERY = "BATTERY"
    OTHER = "OTHER"

class ConsumableSpecificationBase(SQLModel):
    vehicle_id: int = Field(foreign_key="vehicles.id", index=True)
    category: ConsumableCategory = Field(index=True)
    item_name: str = Field(index=True)
    specification: str = Field(description="e.g. 0W-20 Full Synthetic, 26 Inches, 33 PSI")
    oem_part_number: Optional[str] = None
    aftermarket_alternatives: Optional[str] = None
    capacity_or_size: Optional[str] = None
    replacement_interval_summary: Optional[str] = None
    notes: Optional[str] = None

class ConsumableSpecification(ConsumableSpecificationBase, table=True):
    __tablename__ = "consumable_specifications"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)

    # Relationship
    vehicle: Optional["Vehicle"] = Relationship(back_populates="consumables")

class ConsumableCreate(ConsumableSpecificationBase):
    pass

class ConsumableRead(ConsumableSpecificationBase):
    id: int
    created_at: datetime
    updated_at: datetime

class ConsumableUpdate(SQLModel):
    category: Optional[ConsumableCategory] = None
    item_name: Optional[str] = None
    specification: Optional[str] = None
    oem_part_number: Optional[str] = None
    aftermarket_alternatives: Optional[str] = None
    capacity_or_size: Optional[str] = None
    replacement_interval_summary: Optional[str] = None
    notes: Optional[str] = None
