from app.config import get_utc_now
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlmodel import Session, select
from app.database import get_session
from app.models.external_service import (
    ServiceShop,
    ServiceShopCreate,
    ServiceShopRead,
    ServiceShopUpdate,
    ExternalServiceOrder,
    ExternalServiceOrderCreate,
    ExternalServiceOrderRead,
    ExternalServiceOrderUpdate,
    PartSourcing,
    PartSourcingCreate,
    PartSourcingRead,
    WorkOrderStatus,
)
from app.models.vehicle import Vehicle
from app.services.service_order import ServiceOrderService

router = APIRouter(prefix="/api/v1/external-services", tags=["External Services & Parts"])

# --- Mechanic Shops ---
@router.get("/shops", response_model=List[ServiceShopRead])
def list_shops(session: Session = Depends(get_session)):
    return session.exec(select(ServiceShop).order_by(ServiceShop.name.asc())).all()

@router.post("/shops", response_model=ServiceShopRead, status_code=201)
def create_shop(payload: ServiceShopCreate, session: Session = Depends(get_session)):
    shop = ServiceShop.model_validate(payload)
    session.add(shop)
    session.commit()
    session.refresh(shop)
    return shop

@router.get("/shops/{shop_id}", response_model=ServiceShopRead)
def get_shop(shop_id: int, session: Session = Depends(get_session)):
    shop = session.get(ServiceShop, shop_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Mechanic shop not found.")
    return shop

@router.put("/shops/{shop_id}", response_model=ServiceShopRead)
def update_shop(
    shop_id: int,
    payload: ServiceShopUpdate,
    session: Session = Depends(get_session)
):
    shop = session.get(ServiceShop, shop_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Mechanic shop not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(shop, k, v)

    session.add(shop)
    session.commit()
    session.refresh(shop)
    return shop

@router.delete("/shops/{shop_id}")
def delete_shop(shop_id: int, session: Session = Depends(get_session)):
    shop = session.get(ServiceShop, shop_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Mechanic shop not found.")
    session.delete(shop)
    session.commit()
    return {"message": "Mechanic shop deleted successfully."}

# --- Work Orders ---
@router.get("/orders", response_model=List[ExternalServiceOrderRead])
def list_orders(
    vehicle_id: Optional[int] = Query(None, description="Filter by vehicle ID"),
    session: Session = Depends(get_session)
):
    stmt = select(ExternalServiceOrder)
    if vehicle_id:
        stmt = stmt.where(ExternalServiceOrder.vehicle_id == vehicle_id)
    
    orders = session.exec(stmt.order_by(ExternalServiceOrder.scheduled_date.desc())).all()
    return [ServiceOrderService.enrich_order_read(session, o) for o in orders]

@router.post("/orders", response_model=ExternalServiceOrderRead, status_code=201)
def create_order(payload: ExternalServiceOrderCreate, session: Session = Depends(get_session)):
    vehicle = session.get(Vehicle, payload.vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Associated vehicle not found.")
    
    shop = session.get(ServiceShop, payload.shop_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Associated mechanic shop not found.")

    order = ExternalServiceOrder.model_validate(payload)
    session.add(order)
    session.commit()
    session.refresh(order)
    return ServiceOrderService.enrich_order_read(session, order)

@router.get("/orders/{order_id}", response_model=ExternalServiceOrderRead)
def get_order(order_id: int, session: Session = Depends(get_session)):
    order = session.get(ExternalServiceOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Work order not found.")
    return ServiceOrderService.enrich_order_read(session, order)

@router.put("/orders/{order_id}", response_model=ExternalServiceOrderRead)
def update_order(
    order_id: int,
    payload: Optional[ExternalServiceOrderUpdate] = Body(None),
    status: Optional[WorkOrderStatus] = Query(None),
    final_labor_cost: Optional[float] = Query(None),
    invoice_number: Optional[str] = Query(None),
    mechanic_notes: Optional[str] = Query(None),
    session: Session = Depends(get_session)
):
    order = session.get(ExternalServiceOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Work order not found.")

    # Apply body payload if provided
    if payload:
        update_data = payload.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            setattr(order, k, v)

    # Apply query params if explicitly passed
    if status is not None:
        order.status = status
    if final_labor_cost is not None:
        order.final_labor_cost = final_labor_cost
    if invoice_number is not None:
        order.invoice_number = invoice_number
    if mechanic_notes is not None:
        order.mechanic_notes = mechanic_notes

    order.updated_at = get_utc_now()
    session.add(order)
    session.commit()
    session.refresh(order)
    return ServiceOrderService.enrich_order_read(session, order)

@router.delete("/orders/{order_id}")
def delete_order(order_id: int, session: Session = Depends(get_session)):
    order = session.get(ExternalServiceOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Work order not found.")
    session.delete(order)
    session.commit()
    return {"message": "Work order deleted successfully."}

# --- Parts Sourcing ---
@router.post("/orders/{order_id}/parts", response_model=PartSourcingRead, status_code=201)
def add_part_to_order(
    order_id: int,
    payload: PartSourcingCreate,
    session: Session = Depends(get_session)
):
    order = session.get(ExternalServiceOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Work order not found.")

    part_dict = payload.model_dump()
    part_dict["work_order_id"] = order_id
    if not part_dict.get("vehicle_id"):
        part_dict["vehicle_id"] = order.vehicle_id

    part = PartSourcing(**part_dict)
    session.add(part)
    session.commit()
    session.refresh(part)

    return PartSourcingRead(
        id=part.id,
        work_order_id=part.work_order_id,
        vehicle_id=part.vehicle_id,
        part_name=part.part_name,
        oem_part_number=part.oem_part_number,
        supplier=part.supplier,
        order_status=part.order_status,
        tracking_number=part.tracking_number,
        unit_cost=part.unit_cost,
        quantity=part.quantity,
        order_date=part.order_date,
        expected_delivery_date=part.expected_delivery_date,
        actual_delivery_date=part.actual_delivery_date,
        notes=part.notes,
        created_at=part.created_at,
        total_cost=part.unit_cost * part.quantity,
    )

@router.get("/parts", response_model=List[PartSourcingRead])
def list_parts(
    vehicle_id: Optional[int] = Query(None, description="Filter by vehicle ID"),
    session: Session = Depends(get_session)
):
    stmt = select(PartSourcing)
    if vehicle_id:
        stmt = stmt.where(PartSourcing.vehicle_id == vehicle_id)
    
    parts = session.exec(stmt.order_by(PartSourcing.created_at.desc())).all()
    return [
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
            total_cost=p.unit_cost * p.quantity,
        )
        for p in parts
    ]

# --- Work Order Attachments (Invoices, Estimates, Inspection Reports) ---
from fastapi import UploadFile, File, Response
from app.services.attachment_service import AttachmentService

@router.post("/orders/{order_id}/attachment", response_model=ExternalServiceOrderRead)
async def upload_work_order_attachment(
    order_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    order = session.get(ExternalServiceOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Work order not found.")
    
    if not AttachmentService.is_allowed_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail="File type not supported. Allowed formats: PDF, PNG, JPG, TIF, XLS/XLSX, DOC/DOCX, TXT, RTF, HTML, MD"
        )
    
    file_bytes = await file.read()
    content_type = AttachmentService.detect_content_type(file.filename, file.content_type or "application/octet-stream")
    
    order.file_data = file_bytes
    order.file_name = file.filename
    order.file_content_type = content_type
    order.file_size = len(file_bytes)
    order.updated_at = get_utc_now()
    
    session.add(order)
    session.commit()
    session.refresh(order)
    return ServiceOrderService.enrich_order_read(session, order)

@router.get("/orders/{order_id}/attachment")
def download_work_order_attachment(
    order_id: int,
    download: bool = Query(False, description="Set True to force download attachment"),
    session: Session = Depends(get_session)
):
    order = session.get(ExternalServiceOrder, order_id)
    if not order or not order.file_data:
        raise HTTPException(status_code=404, detail="No attachment found for this work order.")
    
    disposition = "attachment" if download else "inline"
    content_type = order.file_content_type or "application/octet-stream"
    
    return Response(
        content=order.file_data,
        media_type=content_type,
        headers={
            "Content-Disposition": f'{disposition}; filename="{order.file_name or "work_order"}"',
            "Content-Length": str(order.file_size or len(order.file_data)),
        }
    )

@router.delete("/orders/{order_id}/attachment", response_model=ExternalServiceOrderRead)
def delete_work_order_attachment(order_id: int, session: Session = Depends(get_session)):
    order = session.get(ExternalServiceOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Work order not found.")
    
    order.file_data = None
    order.file_name = None
    order.file_content_type = None
    order.file_size = None
    order.updated_at = get_utc_now()
    
    session.add(order)
    session.commit()
    session.refresh(order)
    return ServiceOrderService.enrich_order_read(session, order)
