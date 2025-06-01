from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from typing import List, Dict, Any, Union
import json

from .schemas import (
    AdvancedEndpoint, SimpleEndpoint, EndpointCreate, EndpointUpdate,
    BulkEndpointCreate, StatusResponse, ReloadResponse, ConfigResponse, 
    EndpointValidation, EndpointListResponse
)
from .services import AdvancedEndpointService
from shared.auth import verify_api_key, verify_auth, create_access_token
from shared.utils import execute_asterisk_command
from datetime import datetime

router = APIRouter(prefix="/api/v1/endpoints", tags=["endpoints"])


@router.get("/", response_model=EndpointListResponse)
async def list_endpoints(auth: Union[str, dict] = Depends(verify_auth)):
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
    auth: Union[str, dict] = Depends(verify_auth)
):
    """Get specific endpoint details"""
    endpoint = AdvancedEndpointService.get_endpoint(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    return endpoint

@router.post("/simple", response_model=StatusResponse)
async def add_simple_endpoint(
    endpoint_data: SimpleEndpoint,
    auth: Union[str, dict] = Depends(verify_auth)
):
    """Add a simple endpoint (basic configuration)"""
    try:
        if AdvancedEndpointService.add_simple_endpoint(endpoint_data):
            return StatusResponse(
                success=True,
                message=f"Simple endpoint {endpoint_data.id} added successfully"
            )
        else:
            raise HTTPException(status_code=400, detail="Failed to add endpoint (may already exist)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/advanced", response_model=StatusResponse)
async def add_advanced_endpoint(
    endpoint_data: AdvancedEndpoint,
    auth: Union[str, dict] = Depends(verify_auth)
):
    """Add an advanced endpoint (full configuration)"""
    try:
        endpoint_dict = endpoint_data.model_dump()
        if AdvancedEndpointService.add_endpoint_from_json(endpoint_dict):
            return StatusResponse(
                success=True,
                message=f"Advanced endpoint {endpoint_data.id} added successfully"
            )
        else:
            raise HTTPException(status_code=400, detail="Failed to add endpoint (may already exist)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/from-json", response_model=StatusResponse)
async def add_endpoint_from_json(
    endpoint_json: Dict[str, Any],
    auth: Union[str, dict] = Depends(verify_auth)
):
    """Add endpoint from your exact JSON format"""
    try:
        # Validate the data first
        validation = AdvancedEndpointService.validate_endpoint_data(endpoint_json)
        if not validation['valid']:
            return StatusResponse(
                success=False,
                message="Validation failed",
                details={
                    'errors': validation['errors'],
                    'warnings': validation['warnings']
                }
            )
        
        if AdvancedEndpointService.add_endpoint_from_json(endpoint_json):
            return StatusResponse(
                success=True,
                message=f"Endpoint {endpoint_json['id']} added successfully",
                details={'warnings': validation['warnings']} if validation['warnings'] else None
            )
        else:
            raise HTTPException(status_code=400, detail="Failed to add endpoint")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/bulk", response_model=StatusResponse)
async def add_bulk_endpoints(
    bulk_data: BulkEndpointCreate,
    auth: Union[str, dict] = Depends(verify_auth)
):
    """Add multiple endpoints at once"""
    try:
        results = AdvancedEndpointService.add_bulk_endpoints(bulk_data)
        
        total = len(bulk_data.endpoints)
        success_count = len(results['success'])
        failed_count = len(results['failed'])
        skipped_count = len(results['skipped'])
        
        return StatusResponse(
            success=success_count > 0,
            message=f"Bulk operation complete: {success_count} added, {failed_count} failed, {skipped_count} skipped",
            details=results
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/import", response_model=StatusResponse)
async def import_endpoints_json(
    endpoints_json: List[Dict[str, Any]],
    overwrite: bool = False,
    auth: Union[str, dict] = Depends(verify_auth)
):
    """Import multiple endpoints from JSON format"""
    try:
        results = AdvancedEndpointService.import_endpoints_from_json(endpoints_json, overwrite)
        
        success_count = len(results['success'])
        failed_count = len(results['failed'])
        skipped_count = len(results['skipped'])
        
        return StatusResponse(
            success=success_count > 0,
            message=f"Import complete: {success_count} imported, {failed_count} failed, {skipped_count} skipped",
            details=results
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/import-file", response_model=StatusResponse)
async def import_endpoints_file(
    file: UploadFile = File(...),
    overwrite: bool = False,
    auth: Union[str, dict] = Depends(verify_auth)
):
    """Import endpoints from JSON file"""
    try:
        # Read file content
        content = await file.read()
        
        # Parse JSON
        try:
            if file.filename.endswith('.json'):
                endpoints_json = json.loads(content.decode('utf-8'))
            else:
                raise ValueError("Only JSON files are supported")
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON format: {e}")
        
        # Ensure it's a list
        if not isinstance(endpoints_json, list):
            if isinstance(endpoints_json, dict):
                endpoints_json = [endpoints_json]  # Single endpoint
            else:
                raise HTTPException(status_code=400, detail="JSON must contain a list of endpoints")
        
        # Import endpoints
        results = AdvancedEndpointService.import_endpoints_from_json(endpoints_json, overwrite)
        
        success_count = len(results['success'])
        failed_count = len(results['failed'])
        skipped_count = len(results['skipped'])
        
        return StatusResponse(
            success=success_count > 0,
            message=f"File import complete: {success_count} imported, {failed_count} failed, {skipped_count} skipped",
            details=results
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export/json")
async def export_endpoints_json(auth: Union[str, dict] = Depends(verify_auth)):
    """Export all endpoints to JSON format"""
    try:
        endpoints = AdvancedEndpointService.export_endpoints_to_json()
        return {
            "success": True,
            "count": len(endpoints),
            "endpoints": endpoints,
            "exported_at": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{endpoint_id}", response_model=StatusResponse)
async def update_endpoint(
    endpoint_id: str,
    endpoint_data: EndpointUpdate,
    auth: Union[str, dict] = Depends(verify_auth)
):
    """Update an existing endpoint"""
    try:
        if AdvancedEndpointService.update_endpoint(endpoint_id, endpoint_data):
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

@router.post("/reload", response_model=ReloadResponse)
async def reload_endpoints(auth: Union[str, dict] = Depends(verify_auth)):
    """Reload PJSIP configuration in Asterisk"""
    success, output = AdvancedEndpointService.reload_pjsip()
    
    return ReloadResponse(
        success=success,
        message="PJSIP reloaded successfully" if success else "PJSIP reload failed",
        output=output
    )

@router.get("/show/asterisk", response_model=ReloadResponse)
async def show_asterisk_endpoints(auth: Union[str, dict] = Depends(verify_auth)):
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

# Legacy compatibility endpoints
@router.post("/", response_model=StatusResponse)
async def add_endpoint_legacy(
    endpoint_data: SimpleEndpoint,
    auth: Union[str, dict] = Depends(verify_auth)
):
    """Legacy endpoint for backward compatibility - adds simple endpoint"""
    return await add_simple_endpoint(endpoint_data, auth)