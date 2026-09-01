import os
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)

class Settings(BaseModel):
    app_name: str = "Vehicle Maintenance & Operations Tracker"
    version: str = "1.0.0"
    debug: bool = True
    database_url: str = f"sqlite:///{DATA_DIR}/vehicle_maintenance.db"
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    base_public_url: str = "http://localhost:8000"
    
    # Notification & Cooldown Settings
    notification_cooldown_hours: int = 24
    document_warning_lead_days: int = 30
    document_critical_lead_days: int = 7
    maintenance_due_soon_miles: int = 500
    maintenance_due_soon_days: int = 30

    # Google Calendar Settings
    google_calendar_id: str = "primary"
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "mock_client_id")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "mock_client_secret")
    google_token_file: str = str(DATA_DIR / "gcal_token.json")

settings = Settings()
