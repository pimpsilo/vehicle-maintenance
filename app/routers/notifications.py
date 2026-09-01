from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from app.database import get_session
from app.models.notification import NotificationRecordRead, NotificationChannel
from app.services.notification_srv import NotificationService
from app.services.scheduler_srv import run_scheduled_checks

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications & Alerts"])

@router.get("/history", response_model=List[NotificationRecordRead])
def get_notification_history(
    vehicle_id: Optional[int] = Query(None, description="Filter by vehicle ID"),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session)
):
    return NotificationService.get_notification_history(session, vehicle_id=vehicle_id, limit=limit)

@router.post("/check-now")
def trigger_immediate_check():
    """
    Manually triggers the background evaluation of expiring documents and maintenance milestones.
    """
    run_scheduled_checks()
    return {"message": "Scheduled check executed successfully."}

@router.post("/test")
def send_test_notification(
    title: str = "Vehicle Maintenance Test",
    message: str = "Local desktop notification test is working properly.",
    session: Session = Depends(get_session)
):
    record = NotificationService.notify(
        session=session,
        title=title,
        message=message,
        event_type="TEST_NOTIFICATION",
        channel=NotificationChannel.LOCAL_DESKTOP,
        bypass_cooldown=True,
    )
    return {"message": "Test notification dispatched.", "record": record}
