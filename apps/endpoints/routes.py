# ============================================================================
# apps/endpoints/routes.py - Simplified routes
# ============================================================================

from fastapi import APIRouter, Depends, HTTPException
from typing import List

from .schemas import (
    Endpoint, EndpointCreate, EndpointsList, 
    StatusResponse, ReloadResponse, ConfigResponse
)
from .services import EndpointService
from shared.auth import verify_api_key
from shared.utils import execute_asterisk_command
from datetime import datetime

router = APIRouter(prefix="/endpoints", tags=["endpoints"])

@router.post("/save", response_model=StatusResponse)
async def save_endpoints(
    endpoints_data: EndpointsList,
    api_key: str = Depends(verify_api_key)
):
    """Save endpoints configuration"""
    try:
        config_content = EndpointService.save_config(endpoints_data.endpoints)
        
        return StatusResponse(
            success=True,
            message=f"Saved {len(endpoints_data.endpoints)} endpoints successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/config", response_model=ConfigResponse)
async def get_current_config(api_key: str = Depends(verify_api_key)):
    """Get current PJSIP configuration"""
    config_content = EndpointService.get_current_config()
    
    return ConfigResponse(
        success=True,
        config=config_content,
        timestamp=datetime.now().isoformat()
    )

@router.post("/config/generate", response_model=ConfigResponse)
async def generate_config(
    endpoints_data: EndpointsList,
    api_key: str = Depends(verify_api_key)
):
    """Generate configuration without saving"""
    config_content = EndpointService.generate_config_content(endpoints_data.endpoints)
    
    return ConfigResponse(
        success=True,
        config=config_content,
        timestamp=datetime.now().isoformat()
    )

@router.post("/reload", response_model=ReloadResponse)
async def reload_endpoints(api_key: str = Depends(verify_api_key)):
    """Reload PJSIP configuration in Asterisk"""
    success, output = EndpointService.reload_pjsip()
    
    return ReloadResponse(
        success=success,
        message="PJSIP reloaded successfully" if success else "PJSIP reload failed",
        output=output
    )

@router.get("/show", response_model=ReloadResponse)
async def show_endpoints(api_key: str = Depends(verify_api_key)):
    """Show current PJSIP endpoints from Asterisk"""
    success, output = execute_asterisk_command("pjsip show endpoints")
    
    return ReloadResponse(
        success=success,
        message="Endpoints retrieved successfully" if success else "Failed to retrieve endpoints",
        output=output
    )
