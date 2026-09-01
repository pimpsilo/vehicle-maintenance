from app.config import get_utc_now
from datetime import datetime
from enum import Enum
from typing import Optional
from sqlmodel import SQLModel, Field

class SyncEntityType(str, Enum):
    DOCUMENT_EXPIRATION = "DOCUMENT_EXPIRATION"
    EXTERNAL_SERVICE_ORDER = "EXTERNAL_SERVICE_ORDER"
    MAINTENANCE_DUE = "MAINTENANCE_DUE"

class SyncStatus(str, Enum):
    PENDING = "PENDING"
    SYNCED = "SYNCED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class CalendarEventSyncBase(SQLModel):
    vehicle_id: int = Field(index=True)
    entity_type: SyncEntityType = Field(index=True)
    entity_id: int = Field(index=True)
    google_event_id: Optional[str] = Field(default=None, index=True)
    calendar_id: str = Field(default="primary")
    event_summary: str
    event_start: datetime
    event_end: datetime
    is_all_day: bool = Field(default=False)
    sync_status: SyncStatus = Field(default=SyncStatus.PENDING)
    last_synced_at: Optional[datetime] = None
    sync_error: Optional[str] = None

class CalendarEventSync(CalendarEventSyncBase, table=True):
    __tablename__ = "calendar_event_syncs"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)

class CalendarEventSyncRead(CalendarEventSyncBase):
    id: int
    created_at: datetime
    updated_at: datetime

class CalendarReminderOverride(SQLModel):
    method: str = "popup"  # popup or email
    minutes: int = 1440    # minutes before event

class GoogleCalendarEventPayload(SQLModel):
    summary: str
    description: str
    location: Optional[str] = None
    start_time: datetime
    end_time: datetime
    is_all_day: bool = False
    reminder_overrides: list[CalendarReminderOverride] = []
