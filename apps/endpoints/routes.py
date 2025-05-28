# ============================================================================
# apps/endpoints/routes.py - Endpoint routes
# ============================================================================

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from .schemas import Endpoint, EndpointCreate, EndpointUpdate, EndpointsList, EndpointValidation
from .services import EndpointService
from shared.database import get_db
from shared.auth import verify_api_key
from shared.utils import execute_asterisk_command

router = APIRouter(prefix="/endpoints", tags=["endpoints"])

@router.post("/", response_model=Endpoint)
async def create_endpoint(
    endpoint_data: EndpointCreate,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Create a new endpoint"""
    return EndpointService.create_endpoint(db, endpoint_data)

@router.get("/", response_model=List[Endpoint])
async def get_endpoints(
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Get all endpoints"""
    endpoints = EndpointService.get_endpoints(db)
    return [
        Endpoint(
            id=ep.id,
            username=ep.username,
            password=ep.password,
            context=ep.context,
            codecs=json.loads(ep.codecs) if ep.codecs else ["ulaw", "alaw"],
            max_contacts=ep.max_contacts,
            callerid=ep.callerid,
            created_at=ep.created_at.isoformat() if ep.created_at else None,
            updated_at=ep.updated_at.isoformat() if ep.updated_at else None
        )
        for ep in endpoints
    ]

@router.get("/{endpoint_id}", response_model=Endpoint)
async def get_endpoint(
    endpoint_id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Get endpoint by ID"""
    endpoint = EndpointService.get_endpoint(db, endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    
    return Endpoint(
        id=endpoint.id,
        username=endpoint.username,
        password=endpoint.password,
        context=endpoint.context,
        codecs=json.loads(endpoint.codecs) if endpoint.codecs else ["ulaw", "alaw"],
        max_contacts=endpoint.max_contacts,
        callerid=endpoint.callerid
    )

@router.put("/{endpoint_id}", response_model=Endpoint)
async def update_endpoint(
    endpoint_id: str,
    endpoint_data: EndpointUpdate,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Update an endpoint"""
    return EndpointService.update_endpoint(db, endpoint_id, endpoint_data)

@router.delete("/{endpoint_id}")
async def delete_endpoint(
    endpoint_id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Delete an endpoint"""
    EndpointService.delete_endpoint(db, endpoint_id)
    return {"message": "Endpoint deleted successfully"}

@router.post("/reload")
async def reload_endpoints(
    api_key: str = Depends(verify_api_key)
):
    """Reload PJSIP configuration in Asterisk"""
    success, output = EndpointService.reload_pjsip()
    return {
        "success": success,
        "message": "PJSIP reloaded successfully" if success else "PJSIP reload failed",
        "output": output
    }

@router.get("/validate/{endpoint_id}", response_model=EndpointValidation)
async def validate_endpoint_id(
    endpoint_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Validate if endpoint ID is available in Asterisk"""
    success, output = execute_asterisk_command(f"pjsip show endpoint {endpoint_id}")
    exists = success and "Not found" not in output
    
    return EndpointValidation(
        endpoint_id=endpoint_id,
        exists=exists,
        available=not exists
    )

