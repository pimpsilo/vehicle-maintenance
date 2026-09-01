from app.config import get_utc_now
from datetime import datetime
from enum import Enum
from typing import Optional
from sqlmodel import SQLModel, Field

class NotificationChannel(str, Enum):
    LOCAL_DESKTOP = "LOCAL_DESKTOP"
    IN_APP_LOG = "IN_APP_LOG"
    SYSTEM_ALERT = "SYSTEM_ALERT"

class NotificationRecordBase(SQLModel):
    vehicle_id: Optional[int] = Field(default=None, index=True)
    event_type: str = Field(description="e.g. DOCUMENT_EXPIRATION, MAINTENANCE_DUE, SERVICE_REMINDER")
    entity_id: Optional[int] = Field(default=None, description="ID of document or service definition")
    title: str
    message: str
    channel: NotificationChannel = Field(default=NotificationChannel.LOCAL_DESKTOP)
    is_delivered: bool = Field(default=True)
    delivery_error: Optional[str] = None

class NotificationRecord(NotificationRecordBase, table=True):
    __tablename__ = "notification_records"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=get_utc_now)

class NotificationRecordRead(NotificationRecordBase):
    id: int
    created_at: datetime
