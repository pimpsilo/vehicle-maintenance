import logging
from datetime import date
from sqlmodel import Session, select
from apscheduler.schedulers.background import BackgroundScheduler
from app.database import engine
from app.models.vehicle import Vehicle
from app.models.document import DocumentStatus
from app.models.maintenance import ServiceStatus
from app.services.document_service import DocumentService
from app.services.interval_engine import MaintenanceIntervalEngine
from app.services.notification_srv import NotificationService
from app.services.gcal_service import GoogleCalendarService

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

def run_scheduled_checks():
    """
    Periodic job: runs document expiration and maintenance milestone checks.
    """
    logger.info("Executing scheduled vehicle maintenance & document checks...")
    with Session(engine) as session:
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
                elif doc.status == DocumentStatus.EXPIRING_CRITICAL:
                    title = f"CRITICAL: {vehicle.year} {vehicle.model} {doc_name} Expiring"
                    msg = f"Your {doc_name} (#{doc.document_number}) expires in {doc.days_until_expiration} days!"
                else:
                    title = f"Renewal Alert: {vehicle.year} {vehicle.model} {doc_name}"
                    msg = f"Your {doc_name} (#{doc.document_number}) is due for renewal in {doc.days_until_expiration} days."

                NotificationService.notify(
                    session=session,
                    title=title,
                    message=msg,
                    event_type="DOCUMENT_EXPIRATION",
                    vehicle_id=vehicle.id,
                    entity_id=doc.id,
                )

            # 2. Maintenance Intervals
            forecasts = MaintenanceIntervalEngine.calculate_forecasts(session, vehicle_id=vehicle.id, current_date=today)
            for f in forecasts:
                if f.status in (ServiceStatus.OVERDUE, ServiceStatus.DUE_SOON):
                    title = f"Service Alert: {vehicle.year} {vehicle.model} - {f.service_name}"
                    NotificationService.notify(
                        session=session,
                        title=title,
                        message=f.action_summary,
                        event_type="MAINTENANCE_DUE",
                        vehicle_id=vehicle.id,
                        entity_id=f.service_definition_id,
                    )

        # 3. Google Calendar Synchronization
        try:
            GoogleCalendarService.sync_all_upcoming(session)
        except Exception as e:
            logger.error(f"Error during scheduled Google Calendar sync: {e}")

def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(run_scheduled_checks, "interval", hours=6, id="vehicle_maintenance_checker", replace_existing=True)
        scheduler.start()
        logger.info("Background scheduler started successfully.")

def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Background scheduler shut down.")
