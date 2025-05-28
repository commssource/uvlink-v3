# ============================================================================
# main.py - Main FastAPI application
# ============================================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from config import (
    APP_NAME, APP_VERSION, APP_DESCRIPTION,
    CORS_ORIGINS, HOST, PORT, LOG_LEVEL, ENABLED_APPS
)
from shared.logging import setup_logging
from shared.database import engine, Base
from shared.utils import ensure_directories
from config import ASTERISK_BACKUP_PATH

# Import app routers
from apps import (
    endpoints_router,
    dids_router, 
    queues_router,
    reports_router,
    ivr_router,
    system_router
)

# Configure logging
setup_logging()

# Create database tables
Base.metadata.create_all(bind=engine)

# Create FastAPI app
app = FastAPI(
    title=APP_NAME,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers based on enabled apps
app.include_router(system_router)

if "endpoints" in ENABLED_APPS:
    app.include_router(endpoints_router, prefix="/api/v1")

if "dids" in ENABLED_APPS:
    app.include_router(dids_router, prefix="/api/v1")

if "queues" in ENABLED_APPS:
    app.include_router(queues_router, prefix="/api/v1")

if "reports" in ENABLED_APPS:
    app.include_router(reports_router, prefix="/api/v1")

if "ivr" in ENABLED_APPS:
    app.include_router(ivr_router, prefix="/api/v1")

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    # Ensure required directories exist
    ensure_directories(ASTERISK_BACKUP_PATH, "logs", "static")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=True,
        log_level=LOG_LEVEL
    )

