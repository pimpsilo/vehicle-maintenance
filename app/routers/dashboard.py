from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.database import get_session
from app.models.vehicle import Vehicle
from app.models.document import VehicleDocument
from app.models.maintenance import ServiceDefinition, ServiceRecord
from app.models.external_service import ServiceShop, ExternalServiceOrder, PartSourcing
from app.models.consumable import ConsumableSpecification
from app.models.reference_doc import ReferenceDocument
from app.models.vehicle_knowledge import VehicleKnowledge
from app.models.notification import NotificationRecord
from app.services.document_service import DocumentService
from app.services.interval_engine import MaintenanceIntervalEngine
from app.services.service_order import ServiceOrderService

router = APIRouter(tags=["Web Dashboard"])

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

@router.get("/dashboard", response_class=HTMLResponse)
def render_dashboard(
    request: Request,
    vehicle_id: Optional[int] = Query(None, description="Active vehicle ID"),
    session: Session = Depends(get_session)
):
    vehicles = session.exec(select(Vehicle).order_by(Vehicle.id.asc())).all()

    active_vehicle = None
    if vehicle_id:
        active_vehicle = session.get(Vehicle, vehicle_id)
    if not active_vehicle and vehicles:
        active_vehicle = vehicles[0]

    v_id = active_vehicle.id if active_vehicle else None

    # Load data for active vehicle
    documents = []
    forecasts = []
    service_records = []
    work_orders = []
    consumables = []
    reference_docs = []
    knowledge_records = []

    if v_id:
        raw_docs = session.exec(
            select(VehicleDocument)
            .where(VehicleDocument.vehicle_id == v_id)
            .order_by(VehicleDocument.expiration_date.asc())
        ).all()
        documents = [DocumentService.enrich_document_read(d) for d in raw_docs]

        forecasts = MaintenanceIntervalEngine.calculate_forecasts(session, vehicle_id=v_id)

        service_records = session.exec(
            select(ServiceRecord)
            .where(ServiceRecord.vehicle_id == v_id)
            .order_by(ServiceRecord.completed_date.desc())
        ).all()

        work_orders = ServiceOrderService.get_orders_for_vehicle(session, vehicle_id=v_id)

        consumables = session.exec(
            select(ConsumableSpecification)
            .where(ConsumableSpecification.vehicle_id == v_id)
            .order_by(ConsumableSpecification.category.asc())
        ).all()

        reference_docs = session.exec(
            select(ReferenceDocument)
            .where((ReferenceDocument.vehicle_id == v_id) | (ReferenceDocument.vehicle_id == None))  # noqa: E711
            .order_by(ReferenceDocument.created_at.desc())
        ).all()

        knowledge_records = session.exec(
            select(VehicleKnowledge)
            .where((VehicleKnowledge.vehicle_id == v_id) | (VehicleKnowledge.vehicle_id == None))  # noqa: E711
            .order_by(VehicleKnowledge.created_at.desc())
        ).all()

    shops = session.exec(select(ServiceShop)).all()
    notifications = session.exec(select(NotificationRecord).order_by(NotificationRecord.created_at.desc()).limit(20)).all()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "vehicles": vehicles,
            "active_vehicle": active_vehicle,
            "documents": documents,
            "forecasts": forecasts,
            "service_records": service_records,
            "shops": shops,
            "work_orders": work_orders,
            "consumables": consumables,
            "reference_docs": reference_docs,
            "knowledge_records": knowledge_records,
            "notifications": notifications,
        }
    )
