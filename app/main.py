from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from app.config import settings
from app.database import init_db
from app.services.scheduler_srv import start_scheduler, shutdown_scheduler
from app.routers import (
    vehicles,
    documents,
    maintenance,
    external_services,
    consumables,
    reference_docs,
    knowledge,
    notifications,
    calendar,
    mobile_portal,
    dashboard,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    start_scheduler()
    yield
    # Shutdown
    shutdown_scheduler()

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Vehicle maintenance tracking, document renewals, maintenance interval forecasting, external service & parts sourcing, and calendar sync.",
    lifespan=lifespan,
)

import base64
import secrets
from fastapi import Request, Response, status

# HTTP Basic Auth middleware for optional defense-in-depth protection
@app.middleware("http")
async def basic_auth_middleware(request: Request, call_next):
    if not settings.enable_auth or request.url.path == "/healthz":
        return await call_next(request)

    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Basic "):
        try:
            encoded_credentials = auth_header.split(" ", 1)[1]
            decoded = base64.b64decode(encoded_credentials).decode("utf-8")
            username, _, password = decoded.partition(":")
            correct_user = secrets.compare_digest(username, settings.auth_username)
            correct_pass = secrets.compare_digest(password, settings.auth_password)
            if correct_user and correct_pass:
                return await call_next(request)
        except Exception:
            pass

    return Response(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content="Unauthorized - Vehicle Tracker Access Required",
        headers={"WWW-Authenticate": 'Basic realm="Vehicle Tracker"'},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz", tags=["Health"])
def health_check():
    """Lightweight health check probe for Docker / QNAP Container Station."""
    return {"status": "healthy", "version": settings.version}


# Include Dashboard & API routers
app.include_router(dashboard.router)
app.include_router(mobile_portal.router)
app.include_router(vehicles.router)
app.include_router(documents.router)
app.include_router(maintenance.router)
app.include_router(external_services.router)
app.include_router(consumables.router)
app.include_router(reference_docs.router)
app.include_router(knowledge.router)
app.include_router(notifications.router)
app.include_router(calendar.router)

@app.get("/", tags=["Dashboard"])
def root_redirect():
    return RedirectResponse(url="/dashboard")
