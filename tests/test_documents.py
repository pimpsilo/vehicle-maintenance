from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.models.vehicle import Vehicle
from app.models.document import VehicleDocument, DocumentType, DocumentStatus
from app.services.document_service import DocumentService

def test_document_status_evaluator():
    today = date.today()
    doc_active = VehicleDocument(
        vehicle_id=1,
        doc_type=DocumentType.INSURANCE,
        document_number="POL-123",
        issuer="Geico",
        effective_date=today - timedelta(days=30),
        expiration_date=today + timedelta(days=60),
        lead_alert_days=30
    )
    status, days = DocumentService.evaluate_status(doc_active, today)
    assert status == DocumentStatus.ACTIVE
    assert days == 60

    doc_warning = VehicleDocument(
        vehicle_id=1,
        doc_type=DocumentType.REGISTRATION,
        document_number="REG-123",
        issuer="DMV",
        effective_date=today - timedelta(days=300),
        expiration_date=today + timedelta(days=20),
        lead_alert_days=30
    )
    status, days = DocumentService.evaluate_status(doc_warning, today)
    assert status == DocumentStatus.EXPIRING_WARNING
    assert days == 20

    doc_critical = VehicleDocument(
        vehicle_id=1,
        doc_type=DocumentType.EMISSIONS_INSPECTION,
        document_number="INSP-123",
        issuer="State Smog",
        effective_date=today - timedelta(days=360),
        expiration_date=today + timedelta(days=5),
        lead_alert_days=30
    )
    status, days = DocumentService.evaluate_status(doc_critical, today)
    assert status == DocumentStatus.EXPIRING_CRITICAL
    assert days == 5

    doc_expired = VehicleDocument(
        vehicle_id=1,
        doc_type=DocumentType.REGISTRATION,
        document_number="REG-OLD",
        issuer="DMV",
        effective_date=today - timedelta(days=400),
        expiration_date=today - timedelta(days=1),
        lead_alert_days=30
    )
    status, days = DocumentService.evaluate_status(doc_expired, today)
    assert status == DocumentStatus.EXPIRED
    assert days == -1

def test_document_api_endpoints(client: TestClient, sample_vehicle: Vehicle):
    today = date.today()
    payload = {
        "vehicle_id": sample_vehicle.id,
        "doc_type": "REGISTRATION",
        "document_number": "REG-TEST-99",
        "issuer": "CA DMV",
        "effective_date": (today - timedelta(days=300)).isoformat(),
        "expiration_date": (today + timedelta(days=15)).isoformat(),
        "lead_alert_days": 30
    }
    create_res = client.post("/api/v1/documents", json=payload)
    assert create_res.status_code == 201
    doc_data = create_res.json()
    assert doc_data["status"] == "EXPIRING_WARNING"
    assert doc_data["days_until_expiration"] == 15

    # Check expiring list
    expiring_res = client.get(f"/api/v1/documents/expiring?vehicle_id={sample_vehicle.id}")
    assert expiring_res.status_code == 200
    assert len(expiring_res.json()) >= 1
