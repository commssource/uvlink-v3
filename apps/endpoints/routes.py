from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from typing import List, Dict, Any, Union
import json

from .schemas import (
    AdvancedEndpoint, EndpointUpdate,
    StatusResponse, ConfigResponse, 
    EndpointValidation, EndpointListResponse
)
from .services import AdvancedEndpointService
from shared.auth.endpoint_auth import EndpointAuth
from shared.utils import execute_asterisk_command
from datetime import datetime

router = APIRouter(prefix="/api/v1/endpoints", tags=["endpoints"])


@router.get("/", response_model=EndpointListResponse)
async def list_endpoints(auth: Dict[str, Any] = Depends(EndpointAuth())):
    """List all endpoints from current configuration"""
    try:
        endpoints = AdvancedEndpointService.list_endpoints()
        return EndpointListResponse(
            success=True,
            count=len(endpoints),
            endpoints=endpoints
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{endpoint_id}", response_model=dict)
async def get_endpoint(
    endpoint_id: str,
    auth: Dict[str, Any] = Depends(EndpointAuth())
):
    """Get specific endpoint details"""
    endpoint = AdvancedEndpointService.get_endpoint(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    return endpoint

@router.post("/", response_model=StatusResponse)
async def add_endpoint(
    endpoint_data: AdvancedEndpoint,
    auth: Dict[str, Any] = Depends(EndpointAuth())
):
    """Add an endpoint with full configuration"""
    try:
        # Validate the data first
        validation = AdvancedEndpointService.validate_endpoint_data(endpoint_data.model_dump())
        if not validation['valid']:
            return StatusResponse(
                success=False,
                message="Validation failed",
                details={
                    'errors': validation['errors'],
                    'warnings': validation['warnings']
                }
            )
        
        # Check if endpoint already exists
        existing_endpoint = AdvancedEndpointService.get_endpoint(endpoint_data.id)
        if existing_endpoint:
            return StatusResponse(
                success=False,
                message=f"Endpoint {endpoint_data.id} already exists",
                details={'errors': [f"Endpoint ID '{endpoint_data.id}' is already in use"]}
            )
        
        if AdvancedEndpointService.add_endpoint_from_json(endpoint_data.model_dump()):
            return StatusResponse(
                success=True,
                message=f"Endpoint {endpoint_data.id} added successfully",
                details={'warnings': validation['warnings']} if validation['warnings'] else None
            )
        else:
            return StatusResponse(
                success=False,
                message="Failed to add endpoint",
                details={'errors': ["Failed to add endpoint to configuration"]}
            )
    except Exception as e:
        logger.error(f"Error adding endpoint: {str(e)}")
        return StatusResponse(
            success=False,
            message="Failed to add endpoint",
            details={'errors': [str(e)]}
        )

@router.put("/{endpoint_id}", response_model=StatusResponse)
async def update_endpoint(
    endpoint_id: str,
    endpoint_data: EndpointUpdate,
    auth: Dict[str, Any] = Depends(EndpointAuth())
):
    """Update an existing endpoint"""
    success, message = AdvancedEndpointService.update_endpoint(endpoint_id, endpoint_data)
    if not success:
        raise HTTPException(status_code=404, detail=message)
    return StatusResponse(success=True, message=message)

@router.delete("/{endpoint_id}", response_model=StatusResponse)
async def delete_endpoint(
    endpoint_id: str,
    auth: Dict[str, Any] = Depends(EndpointAuth())
):
    """Delete an endpoint safely (preserves other config)"""
    try:
        if AdvancedEndpointService.delete_endpoint(endpoint_id):
            return StatusResponse(
                success=True,
                message=f"Endpoint {endpoint_id} deleted successfully"
            )
        else:
            raise HTTPException(status_code=404, detail="Endpoint not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/config/current", response_model=ConfigResponse)
async def get_current_config(auth: Dict[str, Any] = Depends(EndpointAuth())):
    """Get current PJSIP configuration"""
    config_content = AdvancedEndpointService.get_current_config()
    
    return ConfigResponse(
        success=True,
        config=config_content,
        timestamp=datetime.now().isoformat()
    )

@router.get("/validate/{endpoint_id}", response_model=EndpointValidation)
async def validate_endpoint_id(
    endpoint_id: str,
    auth: Dict[str, Any] = Depends(EndpointAuth())
):
    """Validate if endpoint ID is available"""
    # Check in config file
    endpoint = AdvancedEndpointService.get_endpoint(endpoint_id)
    config_exists = endpoint is not None
    
    # Check in running Asterisk
    success, output = execute_asterisk_command(f"pjsip show endpoint {endpoint_id}")
    asterisk_exists = success and "Not found" not in output
    
    conflicts = []
    if config_exists:
        conflicts.append("exists in configuration")
    if asterisk_exists:
        conflicts.append("exists in running Asterisk")
    
    return EndpointValidation(
        endpoint_id=endpoint_id,
        exists=config_exists or asterisk_exists,
        available=not (config_exists or asterisk_exists),
        conflicts=conflicts if conflicts else None
    )

@router.post("/validate/data", response_model=Dict[str, Any])
async def validate_endpoint_data(
    endpoint_json: Dict[str, Any],
    auth: Dict[str, Any] = Depends(EndpointAuth())
):
    """Validate endpoint data before adding"""
    try:
        validation = AdvancedEndpointService.validate_endpoint_data(endpoint_json)
        return {
            "success": True,
            "validation": validation
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
