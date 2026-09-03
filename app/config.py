import os
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent

def _load_env_file():
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v

_load_env_file()

raw_data_dir = os.getenv("DATA_DIR")
if not raw_data_dir or (raw_data_dir.startswith("/app") and not Path("/.dockerenv").exists()):
    DATA_DIR = BASE_DIR / "data"
else:
    DATA_DIR = Path(raw_data_dir)

try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    DATA_DIR = BASE_DIR / "data"
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
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    google_token_file: str = os.getenv("GOOGLE_TOKEN_FILE", str(DATA_DIR / "gcal_token.json"))

settings = Settings()

