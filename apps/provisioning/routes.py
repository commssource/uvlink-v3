from fastapi import APIRouter, Query, HTTPException, Depends, Header, Request, Response, status
import jwt
import traceback
from sqlalchemy import asc, desc, or_
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi import Depends
from shared.database import get_db
from shared.auth.endpoint_auth import EndpointAuth
from shared.auth.combined_auth import verify_combined_auth
from .schemas import ProvisioningResponse, ProvisioningCreate, ProvisioningUpdate
from .models import Provisioning
from .services import ProvisioningService
from typing import List, TypeVar, Generic, Optional, Dict, Any
from config import JWT_SECRET, JWT_ALGORITHM, API_KEY, AZURE_STORAGE_CONNECTION_STRING, AZURE_STORAGE_CONTAINER, BASE_URL, TENANT_NAME
from .storage import MACAddressStorage
from .prov_request import ProvisioningRequestLogger
from config import SIP_SERVER_HOST
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/provisioning", tags=["provisioning"])
prov_router = APIRouter(prefix="/prov", tags=["phone-config"])

endpoint_auth = EndpointAuth()

T = TypeVar('T')
class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    limit: int

@router.get("/", response_model=PaginatedResponse[ProvisioningResponse])
async def get_provisioning_list(
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(endpoint_auth),
    page: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(10, ge=1, description="Number of items to return"),
    id: Optional[int] = Query(None, description="Provisioning ID"),
    mac_address: Optional[str] = Query(None, description="12-character MAC address"),
    endpoint: Optional[str] = Query(None, description="Endpoint ID"),
    make: Optional[str] = Query(None, description="Phone make (e.g., Yealink)"),
    model: Optional[str] = Query(None, description="Phone model (e.g., T48S)"),
    status: Optional[bool] = Query(None, description="Provisioning status"),
    approved: Optional[bool] = Query(None, description="Provisioning approved status"),
):
    query = db.query(Provisioning)
    if id is not None:
        query = query.filter(Provisioning.id == id)
    if endpoint is not None:
        query = query.filter(Provisioning.endpoint.ilike(f"%{endpoint}%"))
    if mac_address is not None:
        query = query.filter(Provisioning.mac_address.ilike(f"%{mac_address}%"))
    if make is not None:
        query = query.filter(Provisioning.make.ilike(f"%{make}%"))
    if model is not None:
        query = query.filter(Provisioning.model.ilike(f"%{model}%"))
    if status is not None:
        query = query.filter(Provisioning.status == status)
    if approved is not None:
        query = query.filter(Provisioning.approved == approved)    

    total = query.count()
    provisioning_list = query.offset(page).limit(limit).all()

    return PaginatedResponse(
        items=provisioning_list,
        total=total,
        page=page,
        limit=limit
    )

@router.post("/", response_model=ProvisioningResponse)
async def create_provisioning(
    provisioning: ProvisioningCreate,
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(endpoint_auth)
):
    service = ProvisioningService(db)
    try:
        return await service.create_provisioning(provisioning)
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Unexpected error in create_provisioning: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while creating the provisioning record"
        )

@router.put("/{mac_address}", response_model=ProvisioningResponse)
async def update_provisioning(
    mac_address: str,
    provisioning: ProvisioningUpdate,
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(endpoint_auth)
):
    """Update a provisioning record"""
    service = ProvisioningService(db)
    return await service.update_provisioning(mac_address, provisioning)

@prov_router.get("/")
async def list_mac_addresses(
    request: Request,
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(endpoint_auth)
):
    """List all MAC addresses in Azure Storage"""
    try:
        logger.info("Listing all MAC addresses")
        
        storage = MACAddressStorage(
            connection_string=AZURE_STORAGE_CONNECTION_STRING,
            container_name=AZURE_STORAGE_CONTAINER
        )
        
        mac_addresses = await storage.list_mac_records()
        
        return Response(
            content="\n".join(mac_addresses),
            media_type="text/plain"
        )

    except Exception as e:
        logger.error(f"Error listing MAC addresses: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list MAC addresses: {str(e)}"
        )

@prov_router.get("/{mac_address}.{file_type}")
async def get_mac_address_record(
    mac_address: str,
    file_type: str,
    request: Request,
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(verify_combined_auth)
):
    """Get the configuration for a specific MAC address"""
    try:
        logger.info(f"Getting {file_type} configuration for MAC: {mac_address}")
        
        # Initialize request logger
        request_logger = ProvisioningRequestLogger(db)
        
        # Log the request regardless of file type
        provisioning_record = await request_logger.log_request(mac_address, request)
        
        # Only process .cfg files, return 404 for others
        if file_type != "cfg":
            request_logger.update_status(provisioning_record, "FAILED")
            raise HTTPException(
                status_code=404,
                detail=f"Configuration type {file_type} not supported"
            )
        
        try:
            # Initialize storage service
            storage = MACAddressStorage(
                connection_string=AZURE_STORAGE_CONNECTION_STRING,
                container_name=AZURE_STORAGE_CONTAINER
            )
            
            # Get the record
            record = await storage.get_mac_record(mac_address)
            
            if not record:
                request_logger.update_status(provisioning_record, "FAILED")
                raise HTTPException(
                    status_code=404,
                    detail=f"Configuration not found for MAC: {mac_address}"
                )
            
            # Format the record as Yealink config
            content = f"""#!version:1.0.0.1

account.1.enable = 1
account.1.label = {record.get('account.1.label', '')}
account.1.display_name = {record.get('account.1.display_name', '')}
account.1.auth_name = {record.get('account.1.auth_name', '')}
account.1.user_name = {record.get('account.1.user_name', '')}
account.1.password = {record.get('account.1.password', '')}
account.1.sip_server_host = {record.get('account.1.sip_server_host', '')}
account.1.sip_server_port = {record.get('account.1.sip_server_port', '')}
account.1.transport = {record.get('account.1.transport', '')}
account.1.expires = {record.get('account.1.expires', '')}
"""
            
            # Update status to OK since we successfully generated the config
            request_logger.update_status(provisioning_record, "OK")
            
            return Response(
                content=content,
                media_type="text/plain"
            )

        except Exception as e:
            # Update status to FAILED if there was an error
            request_logger.update_status(provisioning_record, "FAILED")
            raise

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting MAC address record: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get MAC address record: {str(e)}"
        )