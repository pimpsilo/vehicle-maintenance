from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.database import get_session
from app.models.vehicle import Vehicle
from app.models.document import VehicleDocument
from app.models.maintenance import ServiceDefinition, ServiceRecord, ServiceStatus
from app.models.external_service import ServiceShop, ExternalServiceOrder, PartSourcing
from app.models.consumable import ConsumableSpecification
from app.models.reference_doc import ReferenceDocument
from app.models.vehicle_knowledge import VehicleKnowledge
from app.models.notification import NotificationRecord
from app.services.document_service import DocumentService
from app.services.interval_engine import MaintenanceIntervalEngine
from app.services.service_order import ServiceOrderService
from app.services.usage_service import UsageService

router = APIRouter(tags=["Web Dashboard"])

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

@router.get("/dashboard", response_class=HTMLResponse)
@router.get("/fleet", response_class=HTMLResponse)
def render_dashboard(
    request: Request,
    vehicle_id: Optional[int] = Query(None, description="Active vehicle ID"),
    session: Session = Depends(get_session)
):
    vehicles = session.exec(select(Vehicle).order_by(Vehicle.id.asc())).all()

    # 1. Neutral Fleet Landing Page (when no specific vehicle_id is requested)
    if vehicle_id is None:
        vehicle_summaries = []
        for v in vehicles:
            forecasts = MaintenanceIntervalEngine.calculate_forecasts(session, vehicle_id=v.id)

            # Next oil change forecast
            oil_forecast = next((f for f in forecasts if "oil" in f.service_name.lower()), None)
            if oil_forecast:
                if oil_forecast.status == ServiceStatus.OVERDUE:
                    oil_status = {
                        "status": "OVERDUE",
                        "label": "OVERDUE",
                        "badge_class": "event-badge-overdue",
                        "text": f"Overdue by {abs(oil_forecast.miles_remaining):,} mi"
                    }
                elif oil_forecast.status == ServiceStatus.DUE_SOON:
                    oil_status = {
                        "status": "DUE_SOON",
                        "label": "DUE SOON",
                        "badge_class": "event-badge-soon",
                        "text": f"Due in {oil_forecast.miles_remaining:,} mi"
                    }
                else:
                    due_date_str = f" (~{oil_forecast.next_due_date.strftime('%b %Y')})" if oil_forecast.next_due_date else ""
                    oil_status = {
                        "status": "OK",
                        "label": "OPTIMAL",
                        "badge_class": "health-good",
                        "text": f"{oil_forecast.miles_remaining:,} mi remaining{due_date_str}"
                    }
            else:
                oil_status = {
                    "status": "NOT_CONFIGURED",
                    "label": "NOT SET",
                    "badge_class": "",
                    "text": "No interval configured"
                }

            # Gather urgent maintenance items
            urgent_items = []
            for f in forecasts:
                if f.status == ServiceStatus.OVERDUE:
                    urgent_items.append({
                        "icon": "🔧",
                        "title": f.service_name,
                        "badge_text": f"Overdue by {abs(f.miles_remaining):,} mi",
                        "badge_class": "event-badge-overdue",
                        "severity": "CRITICAL"
                    })
                elif f.status == ServiceStatus.DUE_SOON:
                    urgent_items.append({
                        "icon": "🔧",
                        "title": f.service_name,
                        "badge_text": f"Due in {f.miles_remaining:,} mi",
                        "badge_class": "event-badge-soon",
                        "severity": "WARNING"
                    })

            # Documents check
            raw_docs = session.exec(
                select(VehicleDocument)
                .where(VehicleDocument.vehicle_id == v.id)
                .order_by(VehicleDocument.expiration_date.asc())
            ).all()
            enriched_docs = [DocumentService.enrich_document_read(d) for d in raw_docs]
            for d in enriched_docs:
                if d.status == "EXPIRED":
                    urgent_items.append({
                        "icon": "📄",
                        "title": f"{d.doc_type.value}: {d.title}",
                        "badge_text": f"Expired {abs(d.days_until_expiration)}d ago",
                        "badge_class": "event-badge-overdue",
                        "severity": "CRITICAL"
                    })
                elif d.status == "EXPIRING_SOON":
                    urgent_items.append({
                        "icon": "📄",
                        "title": f"{d.doc_type.value}: {d.title}",
                        "badge_text": f"Expires in {d.days_until_expiration}d",
                        "badge_class": "event-badge-soon",
                        "severity": "WARNING"
                    })

            # Active work orders check
            orders = ServiceOrderService.get_orders_for_vehicle(session, vehicle_id=v.id)
            active_orders = [o for o in orders if o.status in ("PLANNED", "IN_PROGRESS", "PARTS_SOURCING")]
            for o in active_orders:
                urgent_items.append({
                    "icon": "🛠️",
                    "title": o.service_summary or "Open Service Order",
                    "badge_text": o.status.value.replace("_", " "),
                    "badge_class": "event-badge-info",
                    "severity": "INFO"
                })

            # Overall vehicle health flag
            if any(item["severity"] == "CRITICAL" for item in urgent_items):
                health_class = "critical"
                health_label = "Action Required"
            elif any(item["severity"] == "WARNING" for item in urgent_items):
                health_class = "warning"
                health_label = "Due Soon"
            else:
                health_class = "good"
                health_label = "All Systems Good"

            # Usage pace
            usage_stats = UsageService.calculate_usage_stats(session, vehicle_id=v.id)
            usage_pace = f"{usage_stats.average_miles_per_day:.0f} mi/day" if (usage_stats and not usage_stats.insufficient_data and usage_stats.average_miles_per_day) else None

            vehicle_summaries.append({
                "vehicle": v,
                "oil_status": oil_status,
                "urgent_items": urgent_items,
                "active_orders": active_orders,
                "health_class": health_class,
                "health_label": health_label,
                "usage_pace": usage_pace,
            })

        fleet_stats = {
            "total_vehicles": len(vehicles),
            "total_mileage": sum(v.current_mileage for v in vehicles),
            "total_action_items": sum(len([i for i in s["urgent_items"] if i["severity"] in ("CRITICAL", "WARNING")]) for s in vehicle_summaries),
            "total_active_orders": sum(len(s["active_orders"]) for s in vehicle_summaries),
        }

        return templates.TemplateResponse(
            request=request,
            name="fleet_landing.html",
            context={
                "vehicles": vehicles,
                "vehicle_summaries": vehicle_summaries,
                "fleet_stats": fleet_stats,
            }
        )

    # 2. Vehicle-Specific Dashboard View (when vehicle_id is provided)
    active_vehicle = session.get(Vehicle, vehicle_id)
    if not active_vehicle:
        return RedirectResponse(url="/dashboard")

    v_id = active_vehicle.id

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

        usage_stats = UsageService.calculate_usage_stats(session, vehicle_id=v_id)
    else:
        usage_stats = None

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
            "usage_stats": usage_stats,
        }
    )
