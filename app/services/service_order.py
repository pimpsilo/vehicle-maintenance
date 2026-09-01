from typing import List, Optional
from sqlmodel import Session, select
from app.models.external_service import (
    ExternalServiceOrder,
    ExternalServiceOrderRead,
    PartSourcing,
    PartSourcingRead,
    ServiceShop,
)

class ServiceOrderService:
    @staticmethod
    def enrich_order_read(session: Session, order: ExternalServiceOrder) -> ExternalServiceOrderRead:
        # Fetch shop name
        shop_name = None
        if order.shop_id:
            shop = session.get(ServiceShop, order.shop_id)
            if shop:
                shop_name = shop.name

        # Fetch parts
        parts_stmt = select(PartSourcing).where(PartSourcing.work_order_id == order.id)
        parts = session.exec(parts_stmt).all()

        parts_read: List[PartSourcingRead] = []
        total_parts_cost = 0.0

        for p in parts:
            item_total = p.unit_cost * p.quantity
            total_parts_cost += item_total
            parts_read.append(
                PartSourcingRead(
                    id=p.id,
                    work_order_id=p.work_order_id,
                    vehicle_id=p.vehicle_id,
                    part_name=p.part_name,
                    oem_part_number=p.oem_part_number,
                    supplier=p.supplier,
                    order_status=p.order_status,
                    tracking_number=p.tracking_number,
                    unit_cost=p.unit_cost,
                    quantity=p.quantity,
                    order_date=p.order_date,
                    expected_delivery_date=p.expected_delivery_date,
                    actual_delivery_date=p.actual_delivery_date,
                    notes=p.notes,
                    created_at=p.created_at,
                    total_cost=item_total,
                )
            )

        effective_labor = order.final_labor_cost if order.final_labor_cost is not None else order.quoted_labor_cost
        total_order_cost = total_parts_cost + effective_labor

        return ExternalServiceOrderRead(
            id=order.id,
            vehicle_id=order.vehicle_id,
            shop_id=order.shop_id,
            service_summary=order.service_summary,
            scheduled_date=order.scheduled_date,
            drop_off_date=order.drop_off_date,
            completion_date=order.completion_date,
            status=order.status,
            quoted_labor_cost=order.quoted_labor_cost,
            final_labor_cost=order.final_labor_cost,
            invoice_number=order.invoice_number,
            mechanic_notes=order.mechanic_notes,
            file_name=order.file_name,
            file_content_type=order.file_content_type,
            file_size=order.file_size,
            created_at=order.created_at,
            updated_at=order.updated_at,
            shop_name=shop_name,
            parts=parts_read,
            total_parts_cost=total_parts_cost,
            total_order_cost=total_order_cost,
            has_attachment=bool(order.file_data),
        )

    @staticmethod
    def get_orders_for_vehicle(session: Session, vehicle_id: int) -> List[ExternalServiceOrderRead]:
        stmt = (
            select(ExternalServiceOrder)
            .where(ExternalServiceOrder.vehicle_id == vehicle_id)
            .order_by(ExternalServiceOrder.scheduled_date.desc())
        )
        orders = session.exec(stmt).all()
        return [ServiceOrderService.enrich_order_read(session, o) for o in orders]
