from app.config import get_utc_now
from datetime import datetime, date
from enum import Enum
from typing import Optional
from sqlmodel import SQLModel, Field

class NotificationChannel(str, Enum):
    LOCAL_DESKTOP = "LOCAL_DESKTOP"
    IN_APP_LOG = "IN_APP_LOG"
    SYSTEM_ALERT = "SYSTEM_ALERT"

class NotificationRecordBase(SQLModel):
    vehicle_id: Optional[int] = Field(default=None, index=True)
    event_type: str = Field(description="e.g. DOCUMENT_EXPIRATION, MAINTENANCE_DUE, SERVICE_REMINDER, ADVANCE_NOTICE, RATE_SURGE")
    entity_id: Optional[int] = Field(default=None, description="ID of document or service definition")
    title: str
    message: str
    channel: NotificationChannel = Field(default=NotificationChannel.LOCAL_DESKTOP)
    severity: str = Field(default="INFO", description="CRITICAL, WARNING, INFO")
    is_delivered: bool = Field(default=True)
    delivery_error: Optional[str] = None

class NotificationRecord(NotificationRecordBase, table=True):
    __tablename__ = "notification_records"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=get_utc_now)

class NotificationRecordRead(NotificationRecordBase):
    id: int
    created_at: datetime

class MaintenanceAlertItem(SQLModel):
    vehicle_id: int
    vehicle_name: str
    service_definition_id: int
    service_name: str
    status: str  # OVERDUE, DUE_SOON, ADVANCE_NOTICE, RATE_SURGE
    severity: str  # CRITICAL, WARNING, INFO
    title: str
    message: str
    miles_remaining: int
    days_remaining: int
    next_due_mileage: int
    next_due_date: Optional[date] = None
    progress_pct: float = 0.0
    is_next_required: bool = False
    channel: NotificationChannel = NotificationChannel.LOCAL_DESKTOP

