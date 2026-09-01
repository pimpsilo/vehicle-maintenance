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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
