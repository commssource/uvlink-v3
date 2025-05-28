# ============================================================================
# apps/system/routes.py - System routes
# ============================================================================

from fastapi import APIRouter, Depends
from .schemas import StatusResponse, SystemHealth
from shared.auth import verify_api_key
from config import APP_NAME, APP_VERSION, ENABLED_APPS

router = APIRouter(prefix="", tags=["system"])

@router.get("/", response_model=StatusResponse)
async def root():
    """API status endpoint"""
    return StatusResponse(
        success=True,
        message=f"{APP_NAME} is running",
        details={
            "version": APP_VERSION,
            "apps": ENABLED_APPS,
            "docs": "/docs",
            "redoc": "/redoc"
        }
    )

@router.get("/health", response_model=SystemHealth)
async def health_check():
    """Comprehensive health check"""
    # Implementation would check all systems
    return SystemHealth(
        status="healthy",
        asterisk_version="Asterisk 20.0.0",
        database_status="connected",
        disk_usage={"used": 45, "free": 55, "unit": "GB"},
        memory_usage={"used": 2048, "total": 8192, "unit": "MB"},
        active_apps=ENABLED_APPS
    )

