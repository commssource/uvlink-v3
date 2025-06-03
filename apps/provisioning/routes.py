from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session
from typing import List, Optional
from shared.database import get_db
from .models import Provisioning
from .services import YealinkConfig
from pydantic import BaseModel
import os
import logging
import traceback
from config import (
    AZURE_STORAGE_CONNECTION_STRING,
    AZURE_STORAGE_CONTAINER,
    BASE_URL
)
from .schemas import ProvisioningUpdate, ProvisioningResponse
from azure.storage.blob import BlobServiceClient
from sqlalchemy import Column, DateTime, func
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# API v1 router for provisioning management
router = APIRouter(prefix="/api/v1/provisioning", tags=["provisioning"])

# Root router for phone configuration access
config_router = APIRouter(prefix="/provisioning", tags=["phone-config"])

# New router for authenticated configuration access
prov_router = APIRouter(prefix="/prov", tags=["phone-config"])

security = HTTPBasic()

class ProvisioningCreate(BaseModel):
    endpoint: str
    make: str
    model: str
    mac_address: str
    status: bool = True

class ProvisioningResponse(BaseModel):
    id: int
    endpoint: str
    make: str
    model: str
    mac_address: str
    status: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    approved: Optional[bool] = False
    provisioning_request: Optional[str]
    ip_address: Optional[str]
    provisioning_status: Optional[str]
    last_provisioning_attempt: Optional[datetime]
    request_date: Optional[datetime]

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat() if dt else None
        }

    def model_post_init(self, __context):
        """Convert UTC times to local timezone after model initialization"""
        uk_tz = ZoneInfo("Europe/London")
        
        def convert_to_uk_time(dt: Optional[datetime]) -> Optional[datetime]:
            if dt is None:
                return None
            # If datetime is naive (no timezone), assume it's UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ZoneInfo("UTC"))
            return dt.astimezone(uk_tz)
        
        # Convert all datetime fields to UK time
        self.created_at = convert_to_uk_time(self.created_at)
        self.updated_at = convert_to_uk_time(self.updated_at)
        self.last_provisioning_attempt = convert_to_uk_time(self.last_provisioning_attempt)
        self.request_date = convert_to_uk_time(self.request_date)

@router.post("/", response_model=ProvisioningResponse)
async def create_provisioning(
    provisioning: ProvisioningCreate,
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Creating/updating provisioning entry for MAC: {provisioning.mac_address}")
        logger.info(f"Using BASE_URL: {BASE_URL}")
        
        # Validate MAC address format
        if not provisioning.mac_address.isalnum() or len(provisioning.mac_address) != 12:
            raise HTTPException(
                status_code=400,
                detail="MAC address must be 12 alphanumeric characters without separators"
            )

        # Check if MAC address already exists
        existing = db.query(Provisioning).filter(
            Provisioning.mac_address == provisioning.mac_address
        ).first()
        
        if existing:
            logger.info(f"Updating existing record for MAC: {provisioning.mac_address}")
            # Update existing record with new values
            for field, value in provisioning.model_dump().items():
                setattr(existing, field, value)
            existing.updated_at = datetime.now(ZoneInfo("UTC"))
            db.commit()
            db.refresh(existing)
            db_provisioning = existing
        else:
            # Create new provisioning entry
            try:
                db_provisioning = Provisioning(
                    **provisioning.model_dump(),
                    created_at=datetime.now(ZoneInfo("UTC")),
                    approved=False,  # Set approved to False by default
                    username="",     # Set default empty values
                    password="",     # Set default empty values
                    provisioning_request=None,
                    ip_address=None,
                    provisioning_status=None,
                    last_provisioning_attempt=None,
                    request_date=None
                )
                db.add(db_provisioning)
                db.commit()
                db.refresh(db_provisioning)
                logger.info(f"Successfully created provisioning entry with ID: {db_provisioning.id}")
            except Exception as db_error:
                logger.error(f"Database error: {str(db_error)}")
                logger.error(traceback.format_exc())
                raise HTTPException(
                    status_code=500,
                    detail=f"Database error: {str(db_error)}"
                )

        # If it's a Yealink phone, generate configuration files
        if provisioning.make.lower() == "yealink":
            try:
                # Check required configuration
                if not AZURE_STORAGE_CONNECTION_STRING:
                    raise HTTPException(
                        status_code=500,
                        detail="Azure Storage connection string is not configured"
                    )

                yealink_config = YealinkConfig(
                    connection_string=AZURE_STORAGE_CONNECTION_STRING,
                    container_name=AZURE_STORAGE_CONTAINER
                )
                
                logger.info(f"Generating Yealink configuration for MAC: {provisioning.mac_address}")
                logger.info(f"Using endpoint ID: {provisioning.endpoint}")
                logger.info(f"Using BASE_URL: {BASE_URL}")
                
                try:
                    # Generate configuration files
                    await yealink_config.generate_config_files(
                        mac_address=provisioning.mac_address,
                        endpoint_id=provisioning.endpoint,
                        base_url=BASE_URL
                    )
                    
                    # Set approved to True only after successful Azure storage
                    db_provisioning.approved = True
                    db_provisioning.provisioning_status = 'OK'
                    db_provisioning.last_provisioning_attempt = datetime.now(ZoneInfo("UTC"))
                    db.commit()
                    logger.info("Successfully generated Yealink configuration and updated approval status")
                except HTTPException as config_http_error:
                    # Log the error details
                    logger.error(f"Configuration HTTP error: {config_http_error.detail}")
                    logger.error(f"Status code: {config_http_error.status_code}")
                    # Update provisioning status to FAILED
                    db_provisioning.provisioning_status = 'FAILED'
                    db_provisioning.last_provisioning_attempt = datetime.now(ZoneInfo("UTC"))
                    db.commit()
                    # Re-raise with the original error details
                    raise HTTPException(
                        status_code=config_http_error.status_code,
                        detail=config_http_error.detail
                    )
                
            except Exception as config_error:
                logger.error(f"Configuration generation error: {str(config_error)}")
                logger.error(traceback.format_exc())
                # Update provisioning status to FAILED
                db_provisioning.provisioning_status = 'FAILED'
                db_provisioning.last_provisioning_attempt = datetime.now(ZoneInfo("UTC"))
                db.commit()
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to generate configuration: {str(config_error)}"
                )

        return db_provisioning

    except HTTPException:
        # Re-raise HTTP exceptions without wrapping
        raise
    except Exception as e:
        logger.error(f"Unexpected error in create_provisioning: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/{mac_address}", response_model=ProvisioningResponse)
async def get_provisioning(mac_address: str, db: Session = Depends(get_db)):
    provisioning = db.query(Provisioning).filter(Provisioning.mac_address == mac_address).first()
    if not provisioning:
        raise HTTPException(status_code=404, detail="Provisioning not found")
    return provisioning

@router.get("/", response_model=List[ProvisioningResponse])
async def list_provisioning(db: Session = Depends(get_db)):
    try:
        logger.info("Fetching all provisioning records")
        records = db.query(Provisioning).all()
        logger.info(f"Found {len(records)} records")
        return records
    except Exception as e:
        logger.error(f"Error fetching provisioning records: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch provisioning records: {str(e)}"
        )

@router.put("/{mac_address}", response_model=ProvisioningResponse)
async def update_provisioning(mac_address: str, provisioning: ProvisioningUpdate, db: Session = Depends(get_db)):
    try:
        db_provisioning = db.query(Provisioning).filter(Provisioning.mac_address == mac_address).first()
        if not db_provisioning:
            raise HTTPException(status_code=404, detail="Provisioning not found")
        
        # Store old values for comparison
        old_mac_address = db_provisioning.mac_address
        old_endpoint = db_provisioning.endpoint
        
        # Update fields
        for field, value in provisioning.model_dump(exclude_unset=True).items():
            setattr(db_provisioning, field, value)
        
        # Always update the updated_at timestamp
        db_provisioning.updated_at = datetime.now(ZoneInfo("UTC"))
        
        # If it's a Yealink phone, update configuration files
        if db_provisioning.make.lower() == "yealink":
            try:
                # Check required configuration
                if not AZURE_STORAGE_CONNECTION_STRING:
                    raise HTTPException(
                        status_code=500,
                        detail="Azure Storage connection string is not configured"
                    )

                yealink_config = YealinkConfig(
                    connection_string=AZURE_STORAGE_CONNECTION_STRING,
                    container_name=AZURE_STORAGE_CONTAINER
                )
                
                logger.info(f"Updating Yealink configuration for MAC: {mac_address}")
                logger.info(f"Using endpoint ID: {db_provisioning.endpoint}")
                logger.info(f"Using BASE_URL: {BASE_URL}")
                
                try:
                    # Generate new configuration files
                    await yealink_config.generate_config_files(
                        mac_address=db_provisioning.mac_address,
                        endpoint_id=db_provisioning.endpoint,
                        base_url=BASE_URL
                    )
                    
                    # If MAC address changed, delete old files
                    if old_mac_address != db_provisioning.mac_address:
                        logger.info(f"MAC address changed from {old_mac_address} to {db_provisioning.mac_address}")
                        # Delete old configuration files
                        old_files = {
                            "config": f"{old_mac_address}.cfg",
                            "boot": f"{old_mac_address}.boot"
                        }
                        for file_type, filename in old_files.items():
                            try:
                                await yealink_config.delete_file(filename)
                                logger.info(f"Deleted old {file_type} file: {filename}")
                            except Exception as e:
                                logger.warning(f"Failed to delete old {file_type} file: {str(e)}")
                    
                    logger.info("Successfully updated Yealink configuration")
                except HTTPException as config_http_error:
                    # Log the error details
                    logger.error(f"Configuration HTTP error: {config_http_error.detail}")
                    logger.error(f"Status code: {config_http_error.status_code}")
                    # Rollback database changes
                    db.rollback()
                    # Re-raise with the original error details
                    raise HTTPException(
                        status_code=config_http_error.status_code,
                        detail=config_http_error.detail
                    )
                
            except Exception as config_error:
                logger.error(f"Configuration generation error: {str(config_error)}")
                logger.error(traceback.format_exc())
                # Rollback database changes
                db.rollback()
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to update configuration: {str(config_error)}"
                )
        
        # Commit database changes
        db.commit()
        db.refresh(db_provisioning)
        return db_provisioning

    except HTTPException:
        # Re-raise HTTP exceptions without wrapping
        raise
    except Exception as e:
        logger.error(f"Unexpected error in update_provisioning: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/storage/{mac_address}")
async def get_storage_files(mac_address: str):
    # Use your config values
    connection_string = AZURE_STORAGE_CONNECTION_STRING
    container_name = AZURE_STORAGE_CONTAINER

    if not connection_string or not container_name:
        raise HTTPException(status_code=500, detail="Azure Storage configuration missing")

    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client(container_name)

    files = {
        "config": f"{mac_address}.cfg",
        "boot": f"{mac_address}.boot",
        "y000": "y000000000000.cfg"
    }

    result = {}
    for file_type, filename in files.items():
        blob_client = container_client.get_blob_client(filename)
        exists = blob_client.exists()
        result[file_type] = {
            "url": blob_client.url,
            "exists": exists
        }

    return result

# Phone configuration endpoints
@config_router.get("/{mac_address}.cfg")
async def get_phone_config(mac_address: str, db: Session = Depends(get_db)):
    provisioning = db.query(Provisioning).filter(Provisioning.mac_address == mac_address).first()
    if not provisioning:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    if provisioning.make.lower() == "yealink":
        try:
            yealink_config = YealinkConfig(
                connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
                container_name=os.getenv("AZURE_STORAGE_CONTAINER")
            )
            # Return the configuration content directly
            return await yealink_config._generate_config_content(
                await yealink_config._get_endpoint_data(provisioning.endpoint, os.getenv("BASE_URL"))
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    raise HTTPException(status_code=400, detail="Unsupported phone make")

@config_router.get("/{mac_address}.boot")
async def get_phone_boot(mac_address: str, db: Session = Depends(get_db)):
    provisioning = db.query(Provisioning).filter(Provisioning.mac_address == mac_address).first()
    if not provisioning:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    if provisioning.make.lower() == "yealink":
        try:
            yealink_config = YealinkConfig(
                connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
                container_name=os.getenv("AZURE_STORAGE_CONTAINER")
            )
            return await yealink_config._generate_boot_content(mac_address, os.getenv("BASE_URL"))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    raise HTTPException(status_code=400, detail="Unsupported phone make")

@config_router.get("/y000000000000.cfg")
async def get_y000_config(db: Session = Depends(get_db)):
    # This endpoint will return the default Yealink configuration
    try:
        yealink_config = YealinkConfig(
            connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
            container_name=os.getenv("AZURE_STORAGE_CONTAINER")
        )
        return await yealink_config._generate_y000_content("000000000000", os.getenv("BASE_URL"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@prov_router.get("/")
async def get_provisioning_root():
    """Root endpoint for provisioning access"""
    return {
        "message": "Please provide a MAC address to access configuration files",
        "example": "/prov/0015651234AP or /prov/0015651234AP.cfg"
    }

@prov_router.get("/{mac_address}")
@prov_router.get("/{mac_address}.cfg")
async def get_provisioning_config(
    mac_address: str,
    credentials: HTTPBasicCredentials = Depends(security),
    request: Request = None,
    db: Session = Depends(get_db)
):
    provisioning = None  # Initialize provisioning variable
    try:
        # Log request details
        logger.info("=== Phone Provisioning Request Details ===")
        logger.info(f"Request URL: {request.url}")
        logger.info(f"Request Method: {request.method}")
        logger.info(f"Request Headers: {dict(request.headers)}")
        logger.info(f"Client Host: {request.client.host if request.client else 'Unknown'}")
        logger.info(f"Requested MAC Address: {mac_address}")
        logger.info("=======================================")

        # Format MAC address: remove extensions and convert to uppercase
        mac_address = mac_address.replace('.cfg', '').replace('.boot', '').upper()
        logger.info(f"Processing request for MAC address: {mac_address}")
        
        # Skip database operations for special Yealink MAC addresses
        if mac_address in ['Y000000000000', 'Y000000000107']:
            logger.info(f"Skipping database operations for special Yealink MAC: {mac_address}")
            # Initialize Azure Storage client
            try:
                logger.info("Initializing Azure Storage client")
                yealink_config = YealinkConfig(
                    connection_string=AZURE_STORAGE_CONNECTION_STRING,
                    container_name=AZURE_STORAGE_CONTAINER
                )
                logger.info("Successfully initialized Azure Storage client")
                
                # Get the configuration file
                config_content = yealink_config.get_file_content(f"{mac_address}.cfg")
                if config_content:
                    return Response(
                        content=config_content,
                        media_type="text/plain; charset=utf-8"
                    )
                else:
                    raise HTTPException(
                        status_code=404,
                        detail="Configuration file not found"
                    )
            except Exception as e:
                logger.error(f"Error accessing Azure Storage: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to access configuration file: {str(e)}"
                )
        
        # Get or create provisioning record for normal MAC addresses
        provisioning = db.query(Provisioning).filter(Provisioning.mac_address == mac_address).first()
        current_time = datetime.now(ZoneInfo("UTC"))
        
        if not provisioning:
            logger.info(f"Creating new provisioning record for MAC: {mac_address}")
            # Create new record with just the MAC address
            provisioning = Provisioning(
                mac_address=mac_address,
                endpoint="",  # Empty string for now
                make="",      # Empty string for now
                model="",     # Empty string for now
                username="",  # Empty string for now
                password="",  # Empty string for now
                status=True,
                created_at=current_time,
                request_date=current_time,  # Set request_date only on first creation
                last_provisioning_attempt=current_time
            )
            db.add(provisioning)
            db.commit()
            db.refresh(provisioning)
            logger.info(f"Created new provisioning record with ID: {provisioning.id}")
        else:
            # Update only last_provisioning_attempt for subsequent requests
            provisioning.last_provisioning_attempt = current_time
            provisioning.provisioning_request = request.headers.get('user-agent')
            provisioning.ip_address = request.headers.get('x-forwarded-for')
            db.commit()
            logger.info(f"Updated last_provisioning_attempt for MAC: {mac_address}")
        
        # Initialize Azure Storage client
        try:
            logger.info("Initializing Azure Storage client")
            logger.info(f"Connection string length: {len(AZURE_STORAGE_CONNECTION_STRING) if AZURE_STORAGE_CONNECTION_STRING else 0}")
            logger.info(f"Container name: {AZURE_STORAGE_CONTAINER}")
            
            yealink_config = YealinkConfig(
                connection_string=AZURE_STORAGE_CONNECTION_STRING,
                container_name=AZURE_STORAGE_CONTAINER
            )
            logger.info("Successfully initialized Azure Storage client")
        except Exception as e:
            logger.error(f"Failed to initialize Azure Storage client: {str(e)}")
            logger.error(traceback.format_exc())
            if provisioning:
                provisioning.provisioning_status = 'FAILED'
                db.commit()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize storage connection: {str(e)}"
            )
        
        # Check if file exists in Azure Storage
        try:
            logger.info(f"Attempting to get file content for MAC: {mac_address}")
            config_content = yealink_config.get_file_content(f"{mac_address}.cfg")
            if config_content:
                logger.info(f"Successfully retrieved configuration for MAC: {mac_address}")
                # Update provisioning status to OK
                provisioning.provisioning_status = 'OK'
                db.commit()
                # File exists in Azure, return it directly
                return Response(
                    content=config_content,
                    media_type="text/plain; charset=utf-8"
                )
            else:
                logger.warning(f"No configuration found for MAC: {mac_address}")
                # Update provisioning status to FAILED
                provisioning.provisioning_status = 'FAILED'
                db.commit()
                # File doesn't exist in Azure
                raise HTTPException(
                    status_code=404,
                    detail="Provisioning config not found. Please create config file to provision this phone."
                )
        except HTTPException:
            if provisioning:
                provisioning.provisioning_status = 'FAILED'
                db.commit()
            raise
        except Exception as e:
            logger.error(f"Error accessing Azure Storage: {str(e)}")
            logger.error(traceback.format_exc())
            if provisioning:
                provisioning.provisioning_status = 'FAILED'
                db.commit()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to access configuration file: {str(e)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_provisioning_config: {str(e)}")
        logger.error(traceback.format_exc())
        if provisioning:
            provisioning.provisioning_status = 'FAILED'
            db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        ) 