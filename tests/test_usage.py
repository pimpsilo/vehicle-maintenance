from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.models.vehicle import Vehicle, OdometerEntry
from app.services.usage_service import UsageService

def test_usage_stats_insufficient_data(client: TestClient, session: Session):
    # 1. Create a test vehicle
    veh = Vehicle(
        vin="4T1BK1EB5EU000001",
        year=2015,
        make="Toyota",
        model="Avalon",
        current_mileage=100000,
        estimated_annual_mileage=12000,
    )
    session.add(veh)
    session.commit()
    session.refresh(veh)

    # With only 0 or 1 entry
    stats = UsageService.calculate_usage_stats(session, veh.id)
    assert stats.insufficient_data is True
    assert stats.average_miles_per_day is None

    # Add 1 entry
    now = datetime.now(timezone.utc)
    session.add(OdometerEntry(vehicle_id=veh.id, mileage=100000, recorded_at=now - timedelta(days=5)))
    session.commit()

    stats = UsageService.calculate_usage_stats(session, veh.id)
    assert stats.insufficient_data is True

    # Add 2nd entry only 5 days later (total span 5 days < 14 days minimum)
    session.add(OdometerEntry(vehicle_id=veh.id, mileage=100200, recorded_at=now))
    session.commit()

    stats = UsageService.calculate_usage_stats(session, veh.id)
    assert stats.insufficient_data is True
    assert stats.observation_span_days == 5.0
    assert stats.total_miles == 200

def test_usage_stats_calculation(client: TestClient, session: Session):
    veh = Vehicle(
        vin="4T1BK1EB5EU000002",
        year=2015,
        make="Toyota",
        model="Avalon",
        current_mileage=102000,
        estimated_annual_mileage=12000,
    )
    session.add(veh)
    session.commit()
    session.refresh(veh)

    now = datetime.now(timezone.utc)
    # 3 entries spanning 60 days
    # Day -60: 100,000
    # Day -30: 101,000
    # Day 0:   102,000
    e1 = OdometerEntry(vehicle_id=veh.id, mileage=100000, recorded_at=now - timedelta(days=60))
    e2 = OdometerEntry(vehicle_id=veh.id, mileage=101000, recorded_at=now - timedelta(days=30))
    e3 = OdometerEntry(vehicle_id=veh.id, mileage=102000, recorded_at=now)
    session.add_all([e1, e2, e3])
    session.commit()

    stats = UsageService.calculate_usage_stats(session, veh.id, as_of=now)
    assert stats.insufficient_data is False
    assert stats.total_miles == 2000
    assert 59.9 <= stats.observation_span_days <= 60.1
    assert 33.0 <= stats.average_miles_per_day <= 33.5
    assert 230.0 <= stats.miles_per_week <= 235.0
    assert 1000.0 <= stats.miles_per_month <= 1030.0
    assert 12000.0 <= stats.miles_per_year <= 12300.0

    # Trailing 30 days should be ~1000 miles
    assert 990.0 <= stats.last_30_days_miles <= 1010.0
    # Monthly series should have points
    assert len(stats.monthly_series) >= 2

    # Observed daily rate over 90 days
    rate = UsageService.get_observed_daily_rate(session, veh.id, window_days=90, as_of=now)
    assert rate is not None
    assert 33.0 <= rate <= 33.5

def test_usage_api_endpoint(client: TestClient, sample_vehicle: Vehicle, session: Session):
    now = datetime.now(timezone.utc)
    e1 = OdometerEntry(vehicle_id=sample_vehicle.id, mileage=100000, recorded_at=now - timedelta(days=30))
    e2 = OdometerEntry(vehicle_id=sample_vehicle.id, mileage=101500, recorded_at=now)
    session.add_all([e1, e2])
    session.commit()

    res = client.get(f"/api/v1/vehicles/{sample_vehicle.id}/usage")
    assert res.status_code == 200
    data = res.json()
    assert data["vehicle_id"] == sample_vehicle.id
    assert data["insufficient_data"] is False
    assert data["total_miles"] == 1500
    assert data["average_miles_per_day"] == 50.0
