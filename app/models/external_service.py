from app.config import get_utc_now
from datetime import date, datetime
from enum import Enum
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship

class WorkOrderStatus(str, Enum):
    PLANNED = "PLANNED"
    DROPPED_OFF = "DROPPED_OFF"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_ON_PARTS = "WAITING_ON_PARTS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class PartOrderStatus(str, Enum):
    RESEARCHING = "RESEARCHING"
    ORDERED = "ORDERED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    INSTALLED = "INSTALLED"
    RETURNED = "RETURNED"

class ServiceShopBase(SQLModel):
    name: str = Field(index=True)
    contact_name: Optional[str] = None
    phone: str
    email: Optional[str] = None
    address: str
    hourly_labor_rate: float = Field(default=0.0, ge=0.0)
    specialties: Optional[str] = None
    rating: Optional[float] = Field(default=None, ge=0.0, le=5.0)
    notes: Optional[str] = None

class ServiceShop(ServiceShopBase, table=True):
    __tablename__ = "service_shops"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=get_utc_now)

    # Relationships
    service_orders: List["ExternalServiceOrder"] = Relationship(back_populates="shop")
    service_records: List["ServiceRecord"] = Relationship(back_populates="service_shop")

class ServiceShopCreate(ServiceShopBase):
    pass

class ServiceShopRead(ServiceShopBase):
    id: int
    created_at: datetime

class ServiceShopUpdate(SQLModel):
    name: Optional[str] = None
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    hourly_labor_rate: Optional[float] = None
    specialties: Optional[str] = None
    rating: Optional[float] = None
    notes: Optional[str] = None

class PartSourcingBase(SQLModel):
    work_order_id: Optional[int] = Field(default=None, foreign_key="external_service_orders.id", index=True)
    vehicle_id: Optional[int] = Field(default=None, foreign_key="vehicles.id", index=True)
    part_name: str = Field(index=True)
    oem_part_number: Optional[str] = None
    supplier: str = Field(default="RockAuto", description="e.g. RockAuto, Toyota OEM Dealer, Advance Auto")
    order_status: PartOrderStatus = Field(default=PartOrderStatus.RESEARCHING)
    tracking_number: Optional[str] = None
    unit_cost: float = Field(default=0.0, ge=0.0)
    quantity: int = Field(default=1, ge=1)
    order_date: Optional[date] = None
    expected_delivery_date: Optional[date] = None
    actual_delivery_date: Optional[date] = None
    notes: Optional[str] = None

class PartSourcing(PartSourcingBase, table=True):
    __tablename__ = "part_sourcings"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=get_utc_now)

    # Relationship
    service_order: Optional["ExternalServiceOrder"] = Relationship(back_populates="parts")

class PartSourcingCreate(PartSourcingBase):
    pass

class PartSourcingRead(PartSourcingBase):
    id: int
    created_at: datetime
    total_cost: float = 0.0

class ExternalServiceOrderBase(SQLModel):
    vehicle_id: int = Field(foreign_key="vehicles.id", index=True)
    shop_id: int = Field(foreign_key="service_shops.id", index=True)
    service_summary: str
    scheduled_date: date
    drop_off_date: Optional[date] = None
    completion_date: Optional[date] = None
    status: WorkOrderStatus = Field(default=WorkOrderStatus.PLANNED)
    quoted_labor_cost: float = Field(default=0.0, ge=0.0)
    final_labor_cost: Optional[float] = Field(default=None, ge=0.0)
    invoice_number: Optional[str] = None
    mechanic_notes: Optional[str] = None
    file_name: Optional[str] = None
    file_content_type: Optional[str] = None
    file_size: Optional[int] = None

class ExternalServiceOrder(ExternalServiceOrderBase, table=True):
    __tablename__ = "external_service_orders"

    id: Optional[int] = Field(default=None, primary_key=True)
    file_data: Optional[bytes] = Field(default=None)
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)

    # Relationships
    vehicle: Optional["Vehicle"] = Relationship(back_populates="external_service_orders")
    shop: Optional[ServiceShop] = Relationship(back_populates="service_orders")
    parts: List[PartSourcing] = Relationship(back_populates="service_order", cascade_delete=True)

class ExternalServiceOrderCreate(ExternalServiceOrderBase):
    pass

class ExternalServiceOrderRead(ExternalServiceOrderBase):
    id: int
    created_at: datetime
    updated_at: datetime
    shop_name: Optional[str] = None
    parts: List[PartSourcingRead] = []
    total_parts_cost: float = 0.0
    total_order_cost: float = 0.0
    has_attachment: bool = False

class ExternalServiceOrderUpdate(SQLModel):
    shop_id: Optional[int] = None
    service_summary: Optional[str] = None
    scheduled_date: Optional[date] = None
    drop_off_date: Optional[date] = None
    completion_date: Optional[date] = None
    status: Optional[WorkOrderStatus] = None
    quoted_labor_cost: Optional[float] = None
    final_labor_cost: Optional[float] = None
    invoice_number: Optional[str] = None
    mechanic_notes: Optional[str] = None
    file_name: Optional[str] = None
    file_content_type: Optional[str] = None
    file_size: Optional[int] = None
