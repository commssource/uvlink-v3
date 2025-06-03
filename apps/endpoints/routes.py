from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Query
from typing import List, Dict, Any, Union, Optional
import json

from .schemas import (
    AdvancedEndpoint, EndpointUpdate,
    StatusResponse, ConfigResponse, 
    EndpointValidation, EndpointListResponse
)
from .services import AdvancedEndpointService
from shared.auth import verify_api_key, verify_auth, create_access_token
from shared.utils import execute_asterisk_command
from datetime import datetime

router = APIRouter(prefix="/api/v1/endpoints", tags=["endpoints"])


@router.get("/", response_model=EndpointListResponse)
async def list_endpoints(
    auth: Union[str, dict] = Depends(verify_auth),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Number of items per page"),
    search: Optional[str] = Query(None, description="Search in endpoint ID and username"),
    context: Optional[str] = Query(None, description="Filter by context"),
    transport: Optional[str] = Query(None, description="Filter by transport type"),
    webrtc: Optional[bool] = Query(None, description="Filter by WebRTC support"),
    sort_by: Optional[str] = Query("id", description="Sort by field (id, created_at, updated_at)"),
    sort_order: Optional[str] = Query("asc", description="Sort order (asc or desc)")
):
    """
    List all endpoints with pagination and filtering options.
    
    Parameters:
    - page: Page number (default: 1)
    - limit: Items per page (default: 10, max: 100)
    - search: Search in endpoint ID and username
    - context: Filter by context
    - transport: Filter by transport type
    - webrtc: Filter by WebRTC support
    - sort_by: Sort by field (id, created_at, updated_at)
    - sort_order: Sort order (asc or desc)
    """
    try:
        # Get all endpoints
        all_endpoints = AdvancedEndpointService.list_endpoints()
        
        # Apply filters
        filtered_endpoints = all_endpoints
        
        if search:
            search = search.lower()
            filtered_endpoints = [
                ep for ep in filtered_endpoints
                if search in ep.get('id', '').lower() or 
                   search in ep.get('auth', {}).get('username', '').lower()
            ]
        
        if context:
            filtered_endpoints = [
                ep for ep in filtered_endpoints
                if ep.get('context') == context
            ]
        
        if transport:
            filtered_endpoints = [
                ep for ep in filtered_endpoints
                if ep.get('transport_network', {}).get('transport') == transport
            ]
        
        if webrtc is not None:
            filtered_endpoints = [
                ep for ep in filtered_endpoints
                if ep.get('webrtc', '').lower() == str(webrtc).lower()
            ]
        
        # Apply sorting
        if sort_by in ['id', 'created_at', 'updated_at']:
            reverse = sort_order.lower() == 'desc'
            filtered_endpoints.sort(
                key=lambda x: x.get(sort_by, ''),
                reverse=reverse
            )
        
        # Calculate pagination
        total = len(filtered_endpoints)
        start = (page - 1) * limit
        end = start + limit
        
        # Get paginated results
        paginated_endpoints = filtered_endpoints[start:end]
        
        return EndpointListResponse(
            success=True,
            count=total,
            endpoints=paginated_endpoints,
            page=page,
            limit=limit,
            total_pages=(total + limit - 1) // limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{endpoint_id}", response_model=dict)
async def get_endpoint(
    endpoint_id: str,
    auth: Union[str, dict] = Depends(verify_auth)
):
    """Get specific endpoint details"""
    endpoint = AdvancedEndpointService.get_endpoint(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    return endpoint

@router.post("/advanced", response_model=StatusResponse)
async def add_endpoint(
    endpoint_data: AdvancedEndpoint,
    auth: Union[str, dict] = Depends(verify_auth)
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
async def update_endpoint(endpoint_id: str, endpoint_data: EndpointUpdate):
    """Update an existing endpoint"""
    success, message = AdvancedEndpointService.update_endpoint(endpoint_id, endpoint_data)
    if not success:
        raise HTTPException(status_code=404, detail=message)
    return StatusResponse(success=True, message=message)

@router.delete("/{endpoint_id}", response_model=StatusResponse)
async def delete_endpoint(
    endpoint_id: str,
    auth: Union[str, dict] = Depends(verify_auth)
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
async def get_current_config(auth: Union[str, dict] = Depends(verify_auth)):
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
    auth: Union[str, dict] = Depends(verify_auth)
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
    auth: Union[str, dict] = Depends(verify_auth)
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
    
