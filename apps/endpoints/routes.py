from fastapi import APIRouter, Depends, HTTPException
from typing import List

from .schemas import (
    Endpoint, EndpointCreate, EndpointUpdate,
    StatusResponse, ReloadResponse, ConfigResponse, EndpointValidation
)
from .services import SafeEndpointService
from shared.auth import verify_api_key
from shared.utils import execute_asterisk_command
from datetime import datetime

router = APIRouter(prefix="/endpoints", tags=["endpoints"])

@router.get("/", response_model=List[dict])
async def list_endpoints(api_key: str = Depends(verify_api_key)):
    """List all endpoints from current configuration"""
    try:
        endpoints = SafeEndpointService.list_endpoints()
        return endpoints
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{endpoint_id}", response_model=dict)
async def get_endpoint(
    endpoint_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Get specific endpoint details"""
    endpoint = SafeEndpointService.get_endpoint(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    return endpoint

@router.post("/", response_model=StatusResponse)
async def add_endpoint(
    endpoint_data: EndpointCreate,
    api_key: str = Depends(verify_api_key)
):
    """Add a new endpoint safely (preserves existing config)"""
    try:
        if SafeEndpointService.add_endpoint(endpoint_data):
            return StatusResponse(
                success=True,
                message=f"Endpoint {endpoint_data.id} added successfully"
            )
        else:
            raise HTTPException(status_code=400, detail="Failed to add endpoint (may already exist)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{endpoint_id}", response_model=StatusResponse)
async def update_endpoint(
    endpoint_id: str,
    endpoint_data: EndpointUpdate,
    api_key: str = Depends(verify_api_key)
):
    """Update an existing endpoint safely"""
    try:
        if SafeEndpointService.update_endpoint(endpoint_id, endpoint_data):
            return StatusResponse(
                success=True,
                message=f"Endpoint {endpoint_id} updated successfully"
            )
        else:
            raise HTTPException(status_code=404, detail="Endpoint not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{endpoint_id}", response_model=StatusResponse)
async def delete_endpoint(
    endpoint_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Delete an endpoint safely (preserves other config)"""
    try:
        if SafeEndpointService.delete_endpoint(endpoint_id):
            return StatusResponse(
                success=True,
                message=f"Endpoint {endpoint_id} deleted successfully"
            )
        else:
            raise HTTPException(status_code=404, detail="Endpoint not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/config/current", response_model=ConfigResponse)
async def get_current_config(api_key: str = Depends(verify_api_key)):
    """Get current PJSIP configuration"""
    config_content = SafeEndpointService.get_current_config()
    
    return ConfigResponse(
        success=True,
        config=config_content,
        timestamp=datetime.now().isoformat()
    )

@router.post("/reload", response_model=ReloadResponse)
async def reload_endpoints(api_key: str = Depends(verify_api_key)):
    """Reload PJSIP configuration in Asterisk"""
    success, output = SafeEndpointService.reload_pjsip()
    
    return ReloadResponse(
        success=success,
        message="PJSIP reloaded successfully" if success else "PJSIP reload failed",
        output=output
    )

@router.get("/show/asterisk", response_model=ReloadResponse)
async def show_asterisk_endpoints(api_key: str = Depends(verify_api_key)):
    """Show current PJSIP endpoints from Asterisk"""
    success, output = execute_asterisk_command("pjsip show endpoints")
    
    return ReloadResponse(
        success=success,
        message="Endpoints retrieved successfully" if success else "Failed to retrieve endpoints",
        output=output
    )

@router.get("/validate/{endpoint_id}", response_model=EndpointValidation)
async def validate_endpoint_id(
    endpoint_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Validate if endpoint ID is available"""
    # Check in config file
    endpoint = SafeEndpointService.get_endpoint(endpoint_id)
    config_exists = endpoint is not None
    
    # Check in running Asterisk
    success, output = execute_asterisk_command(f"pjsip show endpoint {endpoint_id}")
    asterisk_exists = success and "Not found" not in output
    
    return EndpointValidation(
        endpoint_id=endpoint_id,
        exists=config_exists or asterisk_exists,
        available=not (config_exists or asterisk_exists)
    )