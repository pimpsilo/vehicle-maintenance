import platform
import subprocess
from datetime import datetime, timedelta
from typing import Optional, List
from sqlmodel import Session, select
from app.models.notification import (
    NotificationRecord,
    NotificationRecordRead,
    NotificationChannel,
)
from app.config import settings, get_utc_now

class NotificationService:
    @staticmethod
    def send_local_desktop_notification(title: str, message: str, subtitle: str = "Vehicle Maintenance") -> bool:
        """
        Dispatches a native desktop notification on macOS via AppleScript osascript.
        Falls back safely if on Linux/Windows or if subprocess fails.
        """
        system = platform.system()
        if system == "Darwin":
            try:
                # Escape double quotes
                safe_title = title.replace('"', '\\"')
                safe_msg = message.replace('"', '\\"')
                safe_sub = subtitle.replace('"', '\\"')
                script = f'display notification "{safe_msg}" with title "{safe_title}" subtitle "{safe_sub}"'
                subprocess.run(["osascript", "-e", script], check=True, capture_output=True, timeout=5)
                return True
            except Exception:
                return False
        else:
            # Safe fallback
            return True

    @staticmethod
    def should_suppress_notification(
        session: Session,
        event_type: str,
        entity_id: Optional[int],
        cooldown_hours: int = None
    ) -> bool:
        """
        Checks if a notification for this event/entity was already sent within the cooldown window.
        """
        if cooldown_hours is None:
            cooldown_hours = settings.notification_cooldown_hours

        cutoff = get_utc_now() - timedelta(hours=cooldown_hours)
        stmt = (
            select(NotificationRecord)
            .where(
                NotificationRecord.event_type == event_type,
                NotificationRecord.entity_id == entity_id,
                NotificationRecord.created_at >= cutoff,
            )
        )
        existing = session.exec(stmt).first()
        return existing is not None

    @staticmethod
    def notify(
        session: Session,
        title: str,
        message: str,
        event_type: str,
        vehicle_id: Optional[int] = None,
        entity_id: Optional[int] = None,
        channel: NotificationChannel = NotificationChannel.LOCAL_DESKTOP,
        bypass_cooldown: bool = False,
    ) -> Optional[NotificationRecord]:
        """
        Sends notification and logs it in the database if not suppressed by cooldown.
        """
        if not bypass_cooldown and NotificationService.should_suppress_notification(session, event_type, entity_id):
            return None

        delivered = True
        error_msg = None

        if channel == NotificationChannel.LOCAL_DESKTOP:
            delivered = NotificationService.send_local_desktop_notification(title, message)
            if not delivered:
                error_msg = "Desktop notification dispatch failed or was suppressed"

        record = NotificationRecord(
            vehicle_id=vehicle_id,
            event_type=event_type,
            entity_id=entity_id,
            title=title,
            message=message,
            channel=channel,
            is_delivered=delivered,
            delivery_error=error_msg,
            created_at=get_utc_now(),
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record

    @staticmethod
    def get_notification_history(session: Session, vehicle_id: Optional[int] = None, limit: int = 50) -> List[NotificationRecordRead]:
        stmt = select(NotificationRecord)
        if vehicle_id:
            stmt = stmt.where(NotificationRecord.vehicle_id == vehicle_id)
        records = session.exec(stmt.order_by(NotificationRecord.created_at.desc()).limit(limit)).all()
        return [NotificationRecordRead.model_validate(r) for r in records]
