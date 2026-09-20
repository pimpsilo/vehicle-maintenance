from typing import Optional
import logging
from datetime import date
from sqlmodel import Session, select
from apscheduler.schedulers.background import BackgroundScheduler
from app.database import engine
from app.config import settings
from app.models.vehicle import Vehicle
from app.models.document import DocumentStatus
from app.models.maintenance import ServiceStatus
from app.services.document_service import DocumentService
from app.services.interval_engine import MaintenanceIntervalEngine
from app.services.notification_srv import NotificationService
from app.services.maintenance_alert_srv import MaintenanceAlertService
from app.services.gcal_service import GoogleCalendarService

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

def _execute_checks(session: Session):
    today = date.today()
    vehicles = session.exec(select(Vehicle)).all()

    for vehicle in vehicles:
        # 1. Document Expirations
        expiring_docs = DocumentService.get_expiring_documents(session, vehicle_id=vehicle.id, current_date=today)
        for doc in expiring_docs:
            doc_name = doc.doc_type.value.replace("_", " ").title()
            if doc.status == DocumentStatus.EXPIRED:
                title = f"EXPIRED: {vehicle.year} {vehicle.model} {doc_name}"
                msg = f"Your {doc_name} (#{doc.document_number}) expired on {doc.expiration_date.strftime('%b %d, %Y')}."
                sev = "CRITICAL"
            elif doc.status == DocumentStatus.EXPIRING_CRITICAL:
                title = f"CRITICAL: {vehicle.year} {vehicle.model} {doc_name} Expiring"
                msg = f"Your {doc_name} (#{doc.document_number}) expires in {doc.days_until_expiration} days!"
                sev = "CRITICAL"
            else:
                title = f"Renewal Alert: {vehicle.year} {vehicle.model} {doc_name}"
                msg = f"Your {doc_name} (#{doc.document_number}) is due for renewal in {doc.days_until_expiration} days."
                sev = "WARNING"

            NotificationService.notify(
                session=session,
                title=title,
                message=msg,
                event_type="DOCUMENT_EXPIRATION",
                vehicle_id=vehicle.id,
                entity_id=doc.id,
                severity=sev,
            )

    # 2. Planned Maintenance Alerts (All Tiers: Overdue, Due Soon, Advance Notice, Pace Surge)
    MaintenanceAlertService.evaluate_all_fleet_alerts(session, current_date=today)

    # 3. Google Calendar Synchronization
    try:
        GoogleCalendarService.sync_all_upcoming(session)
    except Exception as e:
        logger.error(f"Error during scheduled Google Calendar sync: {e}")

def run_scheduled_checks(session: Optional[Session] = None):
    """
    Periodic job: runs document expiration and maintenance milestone checks.
    """
    logger.info("Executing scheduled vehicle maintenance & document checks...")
    if session is not None:
        _execute_checks(session)
    else:
        with Session(engine) as s:
            _execute_checks(s)

def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(run_scheduled_checks, "interval", hours=6, id="vehicle_maintenance_checker", replace_existing=True)
        scheduler.start()
        logger.info("Background scheduler started successfully.")

def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Background scheduler shut down.")
