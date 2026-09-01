import pytest
from datetime import date, timedelta
from typing import Generator
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_session
from app.models.vehicle import Vehicle
from app.models.document import VehicleDocument, DocumentType
from app.models.maintenance import ServiceDefinition, ServiceRecord, PerformedByType
from app.models.external_service import ServiceShop, ExternalServiceOrder, PartSourcing, WorkOrderStatus, PartOrderStatus
from app.models.consumable import ConsumableSpecification, ConsumableCategory
from app.models.reference_doc import ReferenceDocument, DocCategory, DifficultyRating
from app.models.vehicle_knowledge import VehicleKnowledge, KnowledgeCategory, ComponentSystem, SeverityLevel

@pytest.fixture(name="session")
def session_fixture() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

@pytest.fixture(name="client")
def client_fixture(session: Session) -> Generator[TestClient, None, None]:
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()

@pytest.fixture(name="sample_vehicle")
def sample_vehicle_fixture(session: Session) -> Vehicle:
    today = date.today()
    vehicle = Vehicle(
        vin="4T1BK1EB5EU999999",
        year=2014,
        make="Toyota",
        model="Avalon",
        trim="XLE Touring 3.5L V6",
        license_plate="7TYT999",
        current_mileage=105000,
        estimated_annual_mileage=12000,
        purchase_date=today - timedelta(days=1000),
        notes="Test Avalon vehicle"
    )
    session.add(vehicle)
    session.commit()
    session.refresh(vehicle)
    return vehicle
