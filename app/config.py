import os
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR_PATH = os.getenv("DATA_DIR", str(BASE_DIR / "data"))
DATA_DIR = Path(DATA_DIR_PATH)
DATA_DIR.mkdir(parents=True, exist_ok=True)

def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)

class Settings(BaseModel):
    app_name: str = "Vehicle Maintenance & Operations Tracker"
    version: str = "1.0.0"
    debug: bool = os.getenv("DEBUG", "true").lower() == "true"
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/vehicle_maintenance.db")
    server_host: str = os.getenv("SERVER_HOST", "0.0.0.0")
    server_port: int = int(os.getenv("SERVER_PORT", "8000"))
    base_public_url: str = os.getenv("BASE_PUBLIC_URL", "http://localhost:8000")
    
    # Optional Defense-in-Depth Authentication
    enable_auth: bool = os.getenv("ENABLE_AUTH", "false").lower() == "true"
    auth_username: str = os.getenv("AUTH_USERNAME", "admin")
    auth_password: str = os.getenv("AUTH_PASSWORD", "changeme")

    # Notification & Cooldown Settings
    notification_cooldown_hours: int = int(os.getenv("NOTIFICATION_COOLDOWN_HOURS", "24"))
    document_warning_lead_days: int = 30
    document_critical_lead_days: int = 7
    maintenance_due_soon_miles: int = 500
    maintenance_due_soon_days: int = 30

    # Google Calendar Settings
    google_calendar_id: str = os.getenv("GOOGLE_CALENDAR_ID", "primary")
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "mock_client_id")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "mock_client_secret")
    google_token_file: str = os.getenv("GOOGLE_TOKEN_FILE", str(DATA_DIR / "gcal_token.json"))

settings = Settings()

