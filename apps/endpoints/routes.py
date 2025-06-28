# ============================================================================
# apps/endpoints/pjsip_manager/api.py - Refactored PJSIP Configuration API
# ============================================================================

from fastapi import APIRouter, HTTPException, Depends, Query, status
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import logging

from config import Settings
from apps.endpoints.pjsip_manager.config_manager import ConfigManager
from apps.endpoints.pjsip_manager.template_manager import TemplateManager
from .schemas import (
    EndpointConfig, StructuredEndpoint, EndpointListResponse, 
    EndpointFilters, SortOptions, EndpointTypeFilter, EndpointCreateRequest, EndpointUpdateRequest
)
from shared.models import ConfigGenerationResult


# Initialize router
router = APIRouter(prefix="/api/v1/pjsip", tags=["PJSIP Configuration"])
logger = logging.getLogger(__name__)

# Global managers (will be initialized in startup)
template_manager: Optional[TemplateManager] = None
config_manager: Optional[ConfigManager] = None


# Dependency to get managers
async def get_managers():
    """Dependency to get initialized managers"""
    global template_manager, config_manager
    if not template_manager or not config_manager:
        raise HTTPException(status_code=500, detail="Managers not initialized")
    return template_manager, config_manager


# Startup function to initialize managers
async def initialize_managers(settings: Settings):
    """Initialize global managers"""
    global template_manager, config_manager
    try:
        template_manager = TemplateManager(settings.template_dir)
        config_manager = ConfigManager(settings, template_manager)
        logger.info("PJSIP managers initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize PJSIP managers: {e}")
        raise


# ============================================================================
# ENDPOINT ROUTES
# ============================================================================

@router.get("/endpoints", response_model=EndpointListResponse)
async def list_endpoints(
    id: Optional[str] = Query(None, description="Filter by ID"),
    context: Optional[str] = Query(None, description="Filter by context"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Items per page"),
    sort_by: SortOptions = Query(SortOptions.ID_ASC, description="Sort order"),
    managers: tuple = Depends(get_managers)
) -> EndpointListResponse:
    """List all endpoints with structured data (excludes trunks)"""
    _, config_manager = managers
    
    try:
        filters = EndpointFilters(
            id=id,
            context=context,
            type=EndpointTypeFilter.ENDPOINT
        )
        
        response = await config_manager.list_structured_endpoints_with_filters(
            filters=filters,
            sort_by=sort_by,
            page=page,
            page_size=page_size
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to list endpoints: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list endpoints: {e}")


@router.get("/endpoints/{endpoint_id}", response_model=StructuredEndpoint)
async def get_endpoint(
    endpoint_id: str,
    managers: tuple = Depends(get_managers)
) -> StructuredEndpoint:
    """Get single endpoint details"""
    _, config_manager = managers
    
    try:
        endpoint = await config_manager.parse_endpoint_config(endpoint_id)
        if not endpoint:
            raise HTTPException(status_code=404, detail=f"Endpoint '{endpoint_id}' not found")
        
        return endpoint
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get endpoint {endpoint_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get endpoint: {e}")


@router.post("/endpoints", response_model=ConfigGenerationResult, status_code=status.HTTP_201_CREATED)
async def create_endpoint(
    request: EndpointCreateRequest,
    managers: tuple = Depends(get_managers)
) -> ConfigGenerationResult:
    """Create a new endpoint"""
    _, config_manager = managers
    
    try:
        endpoint_config = request.to_endpoint_config()
        result = await config_manager.generate_endpoint_config(endpoint_config)
        logger.info(f"Created endpoint: {request.id}")
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create endpoint {request.id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create endpoint: {e}")


@router.put("/endpoints/{endpoint_id}", response_model=ConfigGenerationResult)
async def update_endpoint(
    endpoint_id: str,
    request: EndpointUpdateRequest,
    managers: tuple = Depends(get_managers)
) -> ConfigGenerationResult:
    """Update an endpoint (supports ID changes)"""
    _, config_manager = managers
    
    try:
        # Get current endpoint
        current_endpoint = await config_manager.parse_endpoint_config(endpoint_id)
        if not current_endpoint:
            raise HTTPException(status_code=404, detail=f"Endpoint '{endpoint_id}' not found")
        
        # Check if ID is being changed
        new_id = request.id or endpoint_id
        id_changed = new_id != endpoint_id
        
        # If ID is changing, check if the new ID already exists
        if id_changed:
            existing_endpoint = await config_manager.parse_endpoint_config(new_id)
            if existing_endpoint:
                raise HTTPException(status_code=409, detail=f"Endpoint with ID '{new_id}' already exists")
        
        # Convert request to EndpointConfig
        endpoint_config = request.to_endpoint_config(
            new_id, 
            current_endpoint.template_used or "endpoint-basic"
        )
        
        # Auto-update caller ID and mailboxes if ID changed
        if id_changed and endpoint_config.variables:
            variables = endpoint_config.variables.copy()
            
            # Update caller ID if it contains the old ID
            if variables.get("callerid"):
                callerid = variables["callerid"]
                if f"<{endpoint_id}>" in callerid:
                    variables["callerid"] = callerid.replace(f"<{endpoint_id}>", f"<{new_id}>")
                elif endpoint_id in callerid and new_id not in callerid:
                    variables["callerid"] = callerid.replace(endpoint_id, new_id)
            
            # Update mailboxes if they contain the old ID
            if variables.get("mailboxes"):
                mailboxes = variables["mailboxes"]
                if f"{endpoint_id}@" in mailboxes:
                    variables["mailboxes"] = mailboxes.replace(f"{endpoint_id}@", f"{new_id}@")
            
            endpoint_config.variables = variables
        
        # Generate the new/updated configuration
        result = await config_manager.generate_endpoint_config(endpoint_config)
        
        # If ID changed, delete the old endpoint configuration
        if id_changed:
            delete_success = await config_manager.delete_endpoint_config(endpoint_id)
            if not delete_success:
                logger.warning(f"Failed to delete old endpoint '{endpoint_id}' after ID change")
            else:
                logger.info(f"Deleted old endpoint '{endpoint_id}' after changing ID to '{new_id}'")
        
        logger.info(f"Updated endpoint: {endpoint_id} -> {new_id}")
        return result
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update endpoint {endpoint_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update endpoint: {e}")


@router.delete("/endpoints/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_endpoint(
    endpoint_id: str,
    managers: tuple = Depends(get_managers)
):
    """Delete an endpoint"""
    _, config_manager = managers
    
    try:
        success = await config_manager.delete_endpoint_config(endpoint_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Endpoint '{endpoint_id}' not found")
        
        logger.info(f"Deleted endpoint: {endpoint_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete endpoint {endpoint_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete endpoint: {e}")


# ============================================================================
# TRUNK ROUTES
# ============================================================================

@router.get("/trunks", response_model=EndpointListResponse)
async def list_trunks(
    id: Optional[str] = Query(None, description="Filter by ID"),
    accountcode: Optional[str] = Query(None, description="Filter by account code"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Items per page"),
    sort_by: SortOptions = Query(SortOptions.ID_ASC, description="Sort order"),
    managers: tuple = Depends(get_managers)
) -> EndpointListResponse:
    """List all trunks with structured data"""
    _, config_manager = managers
    
    try:
        filters = EndpointFilters(
            id=id,
            accountcode=accountcode,
            type=EndpointTypeFilter.TRUNK
        )
        
        response = await config_manager.list_structured_endpoints_with_filters(
            filters=filters,
            sort_by=sort_by,
            page=page,
            page_size=page_size
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to list trunks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list trunks: {e}")


@router.get("/trunks/{trunk_id}", response_model=StructuredEndpoint)
async def get_trunk(
    trunk_id: str,
    managers: tuple = Depends(get_managers)
) -> StructuredEndpoint:
    """Get single trunk details"""
    _, config_manager = managers
    
    try:
        trunk = await config_manager.parse_endpoint_config(trunk_id)
        if not trunk:
            raise HTTPException(status_code=404, detail=f"Trunk '{trunk_id}' not found")
        
        # Verify it's actually a trunk
        trunk_type = config_manager._determine_endpoint_type(trunk)
        if trunk_type != "trunk":
            raise HTTPException(status_code=404, detail=f"'{trunk_id}' is not a trunk")
        
        return trunk
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get trunk {trunk_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get trunk: {e}")


@router.post("/trunks", response_model=ConfigGenerationResult, status_code=status.HTTP_201_CREATED)
async def create_trunk(
    request: EndpointCreateRequest,
    managers: tuple = Depends(get_managers)
) -> ConfigGenerationResult:
    """Create a new trunk"""
    _, config_manager = managers
    
    try:
        # Force trunk template if not specified
        if not request.template or "trunk" not in request.template.lower():
            request.template = "endpoint-trunk"
        
        # Force trunk context if not specified
        if not request.context or request.context == "internal":
            request.context = "from-trunk"
        
        # Add identify and registration configs for trunks
        endpoint_config = request.to_endpoint_config()
        
        # Add identify configuration
        if not endpoint_config.identify_config:
            endpoint_config.identify_config = {
                "template": "identify-basic",
                "match": request.variables.get("match", "")  # IP or pattern to match
            }
        
        # Add registration configuration  
        if not endpoint_config.registration_config:
            endpoint_config.registration_config = {
                "template": "registration-basic",
                "server_uri": request.variables.get("server_uri", ""),
                "client_uri": request.variables.get("client_uri", "")
            }
        
        result = await config_manager.generate_endpoint_config(endpoint_config)
        logger.info(f"Created trunk: {request.id}")
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create trunk {request.id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create trunk: {e}")


@router.put("/trunks/{trunk_id}", response_model=ConfigGenerationResult)
async def update_trunk(
    trunk_id: str,
    request: EndpointUpdateRequest,
    managers: tuple = Depends(get_managers)
) -> ConfigGenerationResult:
    """Update a trunk (supports ID changes)"""
    _, config_manager = managers
    
    try:
        # Get current trunk
        current_trunk = await config_manager.parse_endpoint_config(trunk_id)
        if not current_trunk:
            raise HTTPException(status_code=404, detail=f"Trunk '{trunk_id}' not found")
        
        # Verify it's actually a trunk
        trunk_type = config_manager._determine_endpoint_type(current_trunk)
        if trunk_type != "trunk":
            raise HTTPException(status_code=404, detail=f"'{trunk_id}' is not a trunk")
        
        # Check if ID is being changed
        new_id = request.id or trunk_id
        id_changed = new_id != trunk_id
        
        # If ID is changing, check if the new ID already exists
        if id_changed:
            existing_endpoint = await config_manager.parse_endpoint_config(new_id)
            if existing_endpoint:
                raise HTTPException(status_code=409, detail=f"Endpoint with ID '{new_id}' already exists")
        
        # Force trunk template if being changed to non-trunk
        if request.template and "trunk" not in request.template.lower():
            request.template = "endpoint-trunk"
        
        # Force trunk context if being changed to internal
        if request.context == "internal":
            request.context = "from-trunk"
        
        # Convert request to EndpointConfig
        endpoint_config = request.to_endpoint_config(
            new_id, 
            current_trunk.template_used or "endpoint-trunk"
        )
        
        # Auto-update caller ID and mailboxes if ID changed
        if id_changed and endpoint_config.variables:
            variables = endpoint_config.variables.copy()
            
            # Update caller ID if it contains the old ID
            if variables.get("callerid"):
                callerid = variables["callerid"]
                if f"<{trunk_id}>" in callerid:
                    variables["callerid"] = callerid.replace(f"<{trunk_id}>", f"<{new_id}>")
                elif trunk_id in callerid and new_id not in callerid:
                    variables["callerid"] = callerid.replace(trunk_id, new_id)
            
            endpoint_config.variables = variables
        
        # Generate the new/updated configuration
        result = await config_manager.generate_endpoint_config(endpoint_config)
        
        # If ID changed, delete the old trunk configuration
        if id_changed:
            delete_success = await config_manager.delete_endpoint_config(trunk_id)
            if not delete_success:
                logger.warning(f"Failed to delete old trunk '{trunk_id}' after ID change")
            else:
                logger.info(f"Deleted old trunk '{trunk_id}' after changing ID to '{new_id}'")
        
        logger.info(f"Updated trunk: {trunk_id} -> {new_id}")
        return result
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update trunk {trunk_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update trunk: {e}")


@router.delete("/trunks/{trunk_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trunk(
    trunk_id: str,
    managers: tuple = Depends(get_managers)
):
    """Delete a trunk"""
    _, config_manager = managers
    
    try:
        # Verify it's actually a trunk before deleting
        trunk = await config_manager.parse_endpoint_config(trunk_id)
        if not trunk:
            raise HTTPException(status_code=404, detail=f"Trunk '{trunk_id}' not found")
        
        trunk_type = config_manager._determine_endpoint_type(trunk)
        if trunk_type != "trunk":
            raise HTTPException(status_code=404, detail=f"'{trunk_id}' is not a trunk")
        
        success = await config_manager.delete_endpoint_config(trunk_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Trunk '{trunk_id}' not found")
        
        logger.info(f"Deleted trunk: {trunk_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete trunk {trunk_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete trunk: {e}")


# Exception handler functions (to be registered with the main app)
async def value_error_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc), "type": "validation_error"}
    )


async def file_not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"detail": "Resource not found", "type": "not_found"}
    )