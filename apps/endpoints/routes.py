# ============================================================================
# apps/endpoints/routes.py - Updated to Use Existing Schemas
# ============================================================================

from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import logging
import asyncio

# Import your existing schemas
from .schemas import (
    StructuredEndpoint, EndpointListResponse, EndpointFilters, SortOptions,
    EndpointTypeFilter, AudioMediaConfig, TransportNetworkConfig, RTPConfig,
    RecordingConfig, CallConfig, PresenceConfig, VoicemailConfig, AuthConfig, AORConfig
)

# Global managers - will be set by main.py
_template_manager = None
_config_manager = None
_settings = None

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/v1/pjsip", tags=["PJSIP Configuration"])

def set_managers(template_manager, config_manager, settings):
    """Set the global managers (called from main.py)"""
    global _template_manager, _config_manager, _settings
    _template_manager = template_manager
    _config_manager = config_manager
    _settings = settings
    logger.info("✅ PJSIP managers set successfully")

# Dependency to get managers
async def get_managers():
    """Dependency to get initialized managers"""
    if not _template_manager or not _config_manager:
        raise HTTPException(status_code=500, detail="PJSIP managers not initialized")
    return _template_manager, _config_manager

# ============================================================================
# Helper Functions to Parse Config into Existing Schema Format
# ============================================================================

async def parse_endpoint_to_structured(endpoint_id: str, config_manager) -> Optional[StructuredEndpoint]:
    """Parse endpoint configuration into StructuredEndpoint using existing schema"""
    try:
        # Use the existing parse_endpoint_config method from config_manager
        structured_endpoint = await config_manager.parse_endpoint_config(endpoint_id)
        return structured_endpoint
        
    except Exception as e:
        logger.warning(f"Failed to parse endpoint {endpoint_id}: {e}")
        return None

# ============================================================================
# Enhanced Endpoint Routes Using Existing Schemas
# ============================================================================

@router.get("/endpoints", response_model=EndpointListResponse)
async def list_endpoints(
    id: Optional[str] = Query(None, description="Filter by ID"),
    context: Optional[str] = Query(None, description="Filter by context"),
    type: Optional[str] = Query(None, description="Filter by type (endpoint, trunk, webrtc)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Items per page"),
    sort_by: SortOptions = Query(SortOptions.ID_ASC, description="Sort order"),
    managers: tuple = Depends(get_managers)
) -> EndpointListResponse:
    """List all endpoints with structured data using existing schemas"""
    _, config_manager = managers
    
    try:
        # Create filters object
        filters = EndpointFilters(
            id=id,
            context=context,
            type=EndpointTypeFilter(type) if type else EndpointTypeFilter.ALL
        )
        
        # Use the existing method from config_manager
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
    """Get single endpoint with structured data using existing schema"""
    _, config_manager = managers
    
    try:
        # Use the existing parse_endpoint_config method
        structured_endpoint = await config_manager.parse_endpoint_config(endpoint_id)
        
        if not structured_endpoint:
            raise HTTPException(status_code=404, detail=f"Endpoint '{endpoint_id}' not found")
        
        return structured_endpoint
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get endpoint {endpoint_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get endpoint: {e}")

# ============================================================================
# Trunk Routes Using Existing Schemas
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
    """List all trunks with structured data using existing schemas"""
    _, config_manager = managers
    
    try:
        # Create filters for trunks only
        filters = EndpointFilters(
            id=id,
            accountcode=accountcode,
            type=EndpointTypeFilter.TRUNK
        )
        
        # Use the existing method from config_manager
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
    """Get single trunk with structured data using existing schema"""
    _, config_manager = managers
    
    try:
        # Use the existing parse_endpoint_config method
        structured_endpoint = await config_manager.parse_endpoint_config(trunk_id)
        
        if not structured_endpoint:
            raise HTTPException(status_code=404, detail=f"Trunk '{trunk_id}' not found")
        
        # Verify it's actually a trunk
        endpoint_type = config_manager._determine_endpoint_type(structured_endpoint)
        if endpoint_type != "trunk":
            raise HTTPException(status_code=404, detail=f"'{trunk_id}' is not a trunk")
        
        return structured_endpoint
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get trunk {trunk_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get trunk: {e}")

# ============================================================================
# CRUD Operations (Create, Update, Delete)
# ============================================================================

# Request Models for CRUD operations
class EndpointCreateRequest(BaseModel):
    """Request model for creating endpoints"""
    id: str = Field(..., description="Unique identifier", min_length=1, max_length=50)
    template: str = Field(default="endpoint-basic", description="Template to use")
    context: Optional[str] = Field(default="internal", description="Dialplan context")
    callerid: Optional[str] = Field(None, description="Caller ID")
    accountcode: Optional[str] = Field(None, description="Account code")
    password: Optional[str] = Field(None, description="Password")
    transport: Optional[str] = Field(default="transport-udp", description="Transport")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Additional variables")
    auth_config: Optional[Dict[str, Any]] = Field(None, description="Auth configuration")
    aor_config: Optional[Dict[str, Any]] = Field(None, description="AOR configuration")
    transport_config: Optional[Dict[str, Any]] = Field(None, description="Transport configuration")
    identify_config: Optional[Dict[str, Any]] = Field(None, description="Identify configuration")
    registration_config: Optional[Dict[str, Any]] = Field(None, description="Registration configuration")

class EndpointUpdateRequest(BaseModel):
    """Request model for updating endpoints"""
    id: Optional[str] = Field(None, description="New ID (if changing)")
    template: Optional[str] = Field(None, description="Template")
    context: Optional[str] = Field(None, description="Context")
    callerid: Optional[str] = Field(None, description="Caller ID")
    accountcode: Optional[str] = Field(None, description="Account code")
    password: Optional[str] = Field(None, description="Password")
    transport: Optional[str] = Field(None, description="Transport")
    variables: Optional[Dict[str, Any]] = Field(None, description="Variables")
    auth_config: Optional[Dict[str, Any]] = Field(None, description="Auth config")
    aor_config: Optional[Dict[str, Any]] = Field(None, description="AOR config")
    transport_config: Optional[Dict[str, Any]] = Field(None, description="Transport config")
    identify_config: Optional[Dict[str, Any]] = Field(None, description="Identify configuration")
    registration_config: Optional[Dict[str, Any]] = Field(None, description="Registration configuration")

# Import your existing EndpointConfig from schemas
from .schemas import EndpointConfig

@router.post("/endpoints", status_code=status.HTTP_201_CREATED)
async def create_endpoint(
    request: EndpointCreateRequest,
    managers: tuple = Depends(get_managers)
):
    """Create a new endpoint"""
    _, config_manager = managers
    
    try:
        # Check if endpoint already exists
        existing_endpoints = await config_manager.list_endpoint_configs()
        if request.id in existing_endpoints:
            raise HTTPException(
                status_code=409, 
                detail=f"Endpoint '{request.id}' already exists"
            )
        
        # Create EndpointConfig using your existing schema
        endpoint_config = EndpointConfig(
            id=request.id,
            template=request.template,
            variables={
                "context": request.context,
                "callerid": request.callerid,
                "accountcode": request.accountcode,
                "password": request.password,
                "transport": request.transport,
                **request.variables
            },
            auth_config=request.auth_config,
            aor_config=request.aor_config,
            transport_config=request.transport_config,
            identify_config=request.identify_config,
            registration_config=request.registration_config
        )
        
        # Use your existing generate_endpoint_config method
        result = await config_manager.generate_endpoint_config(endpoint_config)
        logger.info(f"Created endpoint: {request.id}")
        
        return {
            "success": True,
            "message": f"Endpoint '{request.id}' created successfully",
            "endpoint_id": request.id,
            "file_path": getattr(result, 'file_path', None)
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create endpoint {request.id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create endpoint: {e}")

@router.put("/endpoints/{endpoint_id}")
async def update_endpoint(
    endpoint_id: str,
    request: EndpointUpdateRequest,
    managers: tuple = Depends(get_managers)
):
    """Update an endpoint"""
    _, config_manager = managers
    
    try:
        # Check if endpoint exists
        existing_endpoint = await config_manager.parse_endpoint_config(endpoint_id)
        if not existing_endpoint:
            raise HTTPException(status_code=404, detail=f"Endpoint '{endpoint_id}' not found")
        
        # Create updated EndpointConfig
        new_id = request.id or endpoint_id
        variables = {}
        
        if request.context is not None:
            variables["context"] = request.context
        if request.callerid is not None:
            variables["callerid"] = request.callerid
        if request.accountcode is not None:
            variables["accountcode"] = request.accountcode
        if request.password is not None:
            variables["password"] = request.password
        if request.transport is not None:
            variables["transport"] = request.transport
        if request.variables:
            variables.update(request.variables)
        
        endpoint_config = EndpointConfig(
            id=new_id,
            template=request.template or "endpoint-basic",
            variables=variables,
            auth_config=request.auth_config,
            aor_config=request.aor_config,
            transport_config=request.transport_config,
            identify_config=request.identify_config,
            registration_config=request.registration_config
        )
        
        # Use your existing generate_endpoint_config method
        result = await config_manager.generate_endpoint_config(endpoint_config)
        
        # If ID changed, delete old config
        if new_id != endpoint_id:
            await config_manager.delete_endpoint_config(endpoint_id)
        
        logger.info(f"Updated endpoint: {endpoint_id} -> {new_id}")
        
        return {
            "success": True,
            "message": f"Endpoint '{new_id}' updated successfully",
            "endpoint_id": new_id,
            "file_path": getattr(result, 'file_path', None)
        }
        
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
# Trunk CRUD Operations
# ============================================================================

@router.post("/trunks", status_code=status.HTTP_201_CREATED)
async def create_trunk(
    request: EndpointCreateRequest,
    managers: tuple = Depends(get_managers)
):
    """Create a new trunk"""
    _, config_manager = managers
    
    try:
        # Force trunk template and context
        if not request.template or "trunk" not in request.template.lower():
            request.template = "endpoint-trunk"
        
        if not request.context or request.context == "internal":
            request.context = "from-trunk"
        
        # Check if trunk already exists
        existing_endpoints = await config_manager.list_endpoint_configs()
        if request.id in existing_endpoints:
            raise HTTPException(
                status_code=409, 
                detail=f"Trunk '{request.id}' already exists"
            )
        
        # Create trunk EndpointConfig with identify and registration
        endpoint_config = EndpointConfig(
            id=request.id,
            template=request.template,
            variables={
                "context": request.context,
                "callerid": request.callerid,
                "accountcode": request.accountcode,
                "password": request.password,
                "transport": request.transport,
                **request.variables
            },
            auth_config=request.auth_config,
            aor_config=request.aor_config,
            transport_config=request.transport_config,
            identify_config=request.identify_config or {
                "template": "identify-basic",
                "identify_id": f"{request.id}-identify",
                "endpoint": request.id,
                "match": request.variables.get("match", "")
            },
            registration_config=request.registration_config or {
                "template": "registration-basic",
                "registration_id": f"{request.id}-reg",
                "transport": request.transport or "transport-udp",
                "outbound_auth": f"{request.id}-auth",
                "server_uri": request.variables.get("server_uri", ""),
                "client_uri": request.variables.get("client_uri", "")
            }
        )
        
        result = await config_manager.generate_endpoint_config(endpoint_config)
        logger.info(f"Created trunk: {request.id}")
        
        return {
            "success": True,
            "message": f"Trunk '{request.id}' created successfully",
            "trunk_id": request.id,
            "file_path": getattr(result, 'file_path', None)
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create trunk {request.id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create trunk: {e}")

# ============================================================================
# Template and Summary Routes
# ============================================================================

@router.get("/templates")
async def list_templates(managers: tuple = Depends(get_managers)):
    """List available templates"""
    template_manager, _ = managers
    
    try:
        templates = await template_manager.list_templates()
        # Filter for PJSIP templates only
        pjsip_templates = [t for t in templates if any(keyword in t for keyword in ['endpoint', 'auth', 'aor', 'trunk', 'transport', 'identify', 'registration'])]
        return {"templates": pjsip_templates}
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list templates: {e}")

@router.get("/summary")
async def get_endpoints_summary(managers: tuple = Depends(get_managers)):
    """Get summary statistics for all endpoints"""
    _, config_manager = managers
    
    try:
        # Use existing method to get all endpoints
        filters = EndpointFilters(type=EndpointTypeFilter.ALL)
        response = await config_manager.list_structured_endpoints_with_filters(
            filters=filters,
            sort_by=SortOptions.ID_ASC,
            page=1,
            page_size=1000  # Get all endpoints
        )
        
        endpoints = response.endpoints
        total_endpoints = len(endpoints)
        
        # Calculate statistics
        endpoints_by_type = {}
        endpoints_by_context = {}
        
        for endpoint in endpoints:
            # Count by type (use existing type determination)
            endpoint_type = config_manager._determine_endpoint_type(endpoint)
            endpoints_by_type[endpoint_type] = endpoints_by_type.get(endpoint_type, 0) + 1
            
            # Count by context
            context = endpoint.call.context if endpoint.call else "unknown"
            endpoints_by_context[context] = endpoints_by_context.get(context, 0) + 1
        
        return {
            "total_endpoints": total_endpoints,
            "endpoints_by_type": endpoints_by_type,
            "endpoints_by_context": endpoints_by_context,
            "features": {
                "with_auth": len([ep for ep in endpoints if ep.auth]),
                "with_aor": len([ep for ep in endpoints if ep.aor]),
                "with_recording": len([ep for ep in endpoints if ep.recording and ep.recording.record_calls == "yes"]),
                "with_voicemail": len([ep for ep in endpoints if ep.voicemail and ep.voicemail.mailboxes])
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get endpoints summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get summary: {e}")