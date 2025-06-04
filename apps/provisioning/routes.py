from fastapi import APIRouter, Depends, HTTPException, Request, Response, Header, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials, HTTPBearer
from sqlalchemy.orm import Session
from typing import List, Optional, Union
from shared.database import get_db
from shared.auth import verify_auth
from shared.auth.provisioning import verify_basic_auth
from .models import Provisioning
from .services import YealinkConfig
from pydantic import BaseModel
import os
import logging
import traceback
from config import (
    AZURE_STORAGE_CONNECTION_STRING,
    AZURE_STORAGE_CONTAINER,
    BASE_URL,
    API_KEY,
    JWT_SECRET,
    JWT_ALGORITHM
)
from .schemas import ProvisioningUpdate, ProvisioningResponse
from azure.storage.blob import BlobServiceClient
from sqlalchemy import Column, DateTime, func
from datetime import datetime
from zoneinfo import ZoneInfo
import jwt
from jwt.exceptions import InvalidTokenError
import base64

logger = logging.getLogger(__name__)

# API v1 router for provisioning management
router = APIRouter(prefix="/api/v1/provisioning", tags=["provisioning"])

# Root router for phone configuration access
config_router = APIRouter(prefix="/provisioning", tags=["phone-config"])

# New router for authenticated configuration access
prov_router = APIRouter(prefix="/prov", tags=["phone-config"])

security = HTTPBasic()
bearer_scheme = HTTPBearer()

async def verify_api_key(x_api_key: str = Header(None)):
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    return x_api_key

async def verify_jwt_token(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing JWT token"
        )
    try:
        token = authorization.split(" ")[1]
        # Add your JWT verification logic here
        # For example: jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return token
    except InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid JWT token"
        )

async def verify_credentials(
    credentials: HTTPBasicCredentials = Depends(security),
    db: Session = Depends(get_db),
    filename: str = None
):
    if not filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required"
        )

    # Extract MAC address from filename
    mac_address = filename.split('.')[0]
    
    # Get the provisioning record
    provisioning = db.query(Provisioning).filter(
        Provisioning.mac_address == mac_address
    ).first()
    
    if not provisioning:
        raise HTTPException(
            status_code=404,
            detail=f"Provisioning record not found for MAC: {mac_address}"
        )

    # Verify credentials
    if not provisioning.username or not provisioning.password:
        raise HTTPException(
            status_code=401,
            detail="Provisioning record has no credentials configured"
        )

    # Check username and password
    if credentials.username != provisioning.username or credentials.password != provisioning.password:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"}
        )
    
    return credentials

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
                    username="",     # Will be set from endpoint data
                    password="",     # Will be set from endpoint data
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
                    
                    # Get endpoint data to update credentials
                    endpoint_data = await yealink_config._get_endpoint_data(provisioning.endpoint, BASE_URL)
                    
                    # Update provisioning record with credentials
                    db_provisioning.username = endpoint_data.get('username', '')
                    db_provisioning.password = endpoint_data.get('password', '')
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
async def update_provisioning(
    mac_address: str,
    provisioning: ProvisioningUpdate,
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Updating provisioning for MAC: {mac_address}")
        logger.info(f"Update data: {provisioning.model_dump()}")
        
        # Find the existing provisioning entry
        db_provisioning = db.query(Provisioning).filter(
            Provisioning.mac_address == mac_address
        ).first()
        
        if not db_provisioning:
            raise HTTPException(
                status_code=404,
                detail=f"Provisioning not found for MAC: {mac_address}"
            )

        # Store old MAC address for cleanup if it's being changed
        old_mac_address = db_provisioning.mac_address
        mac_address_changed = old_mac_address != provisioning.mac_address

        # If MAC address changed, delete old configuration files first
        if mac_address_changed and db_provisioning.make.lower() == "yealink":
            try:
                if not AZURE_STORAGE_CONNECTION_STRING:
                    raise HTTPException(
                        status_code=500,
                        detail="Azure Storage connection string is not configured"
                    )

                yealink_config = YealinkConfig(
                    connection_string=AZURE_STORAGE_CONNECTION_STRING,
                    container_name=AZURE_STORAGE_CONTAINER
                )

                logger.info(f"MAC address changed from {old_mac_address} to {provisioning.mac_address}")
                # Delete old configuration files
                await yealink_config.delete_config_files(old_mac_address)
                logger.info(f"Successfully deleted old configuration files for MAC: {old_mac_address}")
            except Exception as delete_error:
                logger.error(f"Error deleting old configuration files: {str(delete_error)}")
                logger.error(traceback.format_exc())
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to delete old configuration files: {str(delete_error)}"
                )

        # Update the provisioning entry
        update_data = provisioning.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_provisioning, field, value)
        
        db_provisioning.updated_at = datetime.now(ZoneInfo("UTC"))
        
        # If it's a Yealink phone, generate new configuration files
        if db_provisioning.make.lower() == "yealink":
            try:
                if not AZURE_STORAGE_CONNECTION_STRING:
                    raise HTTPException(
                        status_code=500,
                        detail="Azure Storage connection string is not configured"
                    )

                yealink_config = YealinkConfig(
                    connection_string=AZURE_STORAGE_CONNECTION_STRING,
                    container_name=AZURE_STORAGE_CONTAINER
                )
                
                # Generate new configuration files with latest endpoint data
                logger.info(f"Generating new Yealink configuration for MAC: {provisioning.mac_address}")
                await yealink_config.generate_config_files(
                    mac_address=provisioning.mac_address,
                    endpoint_id=provisioning.endpoint,
                    base_url=BASE_URL
                )
                
                # Update provisioning status
                db_provisioning.approved = True
                db_provisioning.provisioning_status = 'OK'
                db_provisioning.last_provisioning_attempt = datetime.now(ZoneInfo("UTC"))
                
            except Exception as config_error:
                logger.error(f"Configuration error: {str(config_error)}")
                logger.error(traceback.format_exc())
                db_provisioning.provisioning_status = 'FAILED'
                db_provisioning.last_provisioning_attempt = datetime.now(ZoneInfo("UTC"))
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to update configuration: {str(config_error)}"
                )

        db.commit()
        db.refresh(db_provisioning)
        return db_provisioning

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in update_provisioning: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/storage/list")
async def list_storage_files(
    authorization: str = Header(None)
):
    """List all files in Azure Storage"""
    try:
        logger.info("Listing all files in storage")
        
        # Check for authorization header
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authorization header"
            )

        # Check if it's a Bearer token or API key
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization format. Use 'Bearer <token>' or 'Bearer <api_key>'"
            )

        # Extract the token/key
        token = authorization.split(" ")[1]

        # Try to verify as JWT first
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            if payload.get("type") != "access":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type"
                )
        except jwt.PyJWTError:
            # If JWT verification fails, try as API key
            if token != API_KEY:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token or API key"
                )

        if not AZURE_STORAGE_CONNECTION_STRING:
            raise HTTPException(
                status_code=500,
                detail="Azure Storage connection string is not configured"
            )

        # Initialize Azure Storage client
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(AZURE_STORAGE_CONTAINER)

        # List all blobs
        files = []
        for blob in container_client.list_blobs():
            files.append(blob.name)

        # Return the list as plain text, one file per line
        return Response(
            content="\n".join(files),
            media_type="text/plain"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing storage files: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list storage files: {str(e)}"
        )

@router.get("/storage/{filename}")
async def get_storage_file(
    filename: str,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """Get the content of a file from Azure Storage"""
    try:
        logger.info(f"Getting file content for: {filename}")
        
        # Extract MAC address from filename
        mac_address = filename.split('.')[0]
        
        # Check for authorization header
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authorization header",
                headers={"WWW-Authenticate": "Basic"}
            )

        # Parse authorization header
        try:
            auth_parts = authorization.split(" ", 1)
            auth_type = auth_parts[0].lower()
            auth_value = auth_parts[1] if len(auth_parts) > 1 else None

            if not auth_value:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authorization format. Use 'Basic <credentials>', 'Bearer <token>' or 'Bearer <api_key>'",
                    headers={"WWW-Authenticate": "Basic"}
                )

            if auth_type == "basic":
                # Handle Basic auth
                try:
                    # Decode base64 credentials
                    try:
                        decoded = base64.b64decode(auth_value).decode('utf-8')
                        username, password = decoded.split(':', 1)
                    except Exception as e:
                        logger.error(f"Failed to decode base64 credentials: {str(e)}")
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid basic auth credentials format",
                            headers={"WWW-Authenticate": "Basic"}
                        )
                    
                    # Get the provisioning record
                    provisioning = db.query(Provisioning).filter(
                        Provisioning.mac_address == mac_address
                    ).first()
                    
                    if not provisioning:
                        logger.error(f"Provisioning record not found for MAC: {mac_address}")
                        raise HTTPException(
                            status_code=404,
                            detail=f"Provisioning record not found for MAC: {mac_address}"
                        )

                    # Verify credentials
                    if not provisioning.username or not provisioning.password:
                        logger.error("Provisioning record has no credentials configured")
                        raise HTTPException(
                            status_code=401,
                            detail="Provisioning record has no credentials configured",
                            headers={"WWW-Authenticate": "Basic"}
                        )

                    # Check username and password
                    if username != provisioning.username or password != provisioning.password:
                        logger.error(f"Invalid credentials for MAC: {mac_address}")
                        raise HTTPException(
                            status_code=401,
                            detail="Incorrect username or password",
                            headers={"WWW-Authenticate": "Basic"}
                        )
                except HTTPException:
                    raise
                except Exception as e:
                    logger.error(f"Basic auth error: {str(e)}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid basic auth credentials",
                        headers={"WWW-Authenticate": "Basic"}
                    )
            elif auth_type == "bearer":
                # Handle Bearer token (JWT or API key)
                try:
                    # Try to verify as JWT first
                    payload = jwt.decode(auth_value, JWT_SECRET, algorithms=[JWT_ALGORITHM])
                    if payload.get("type") != "access":
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid token type"
                        )
                except jwt.PyJWTError:
                    # If JWT verification fails, try as API key
                    if auth_value != API_KEY:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid token or API key"
                        )
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authorization type. Use 'Basic' or 'Bearer'",
                    headers={"WWW-Authenticate": "Basic"}
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authorization parsing error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization format",
                headers={"WWW-Authenticate": "Basic"}
            )

        if not AZURE_STORAGE_CONNECTION_STRING:
            raise HTTPException(
                status_code=500,
                detail="Azure Storage connection string is not configured"
            )

        # Initialize Azure Storage client
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(AZURE_STORAGE_CONTAINER)
        blob_client = container_client.get_blob_client(filename)

        # Check if file exists
        if not blob_client.exists():
            raise HTTPException(
                status_code=404,
                detail=f"File not found: {filename}"
            )

        # Get file content
        download_stream = blob_client.download_blob()
        content = download_stream.readall().decode('utf-8')

        # Return the content as plain text
        return Response(
            content=content,
            media_type="text/plain"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file content: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get file content: {str(e)}"
        )

@router.get("/mac_record/{mac_address}")
@router.get("/mac_record/{mac_address}.cfg")
async def get_mac_record(
    mac_address: str,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """Get the content of a configuration file from Azure Storage"""
    try:
        # Remove .cfg extension if present
        mac_address = mac_address.replace('.cfg', '')
        logger.info(f"Fetching configuration content for MAC: {mac_address}")
        
        # Check for authorization header
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authorization header"
            )

        # Parse authorization header
        try:
            auth_parts = authorization.split(" ", 1)
            auth_type = auth_parts[0].lower()
            auth_value = auth_parts[1] if len(auth_parts) > 1 else None

            if not auth_value:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authorization format. Use 'Basic <credentials>', 'Bearer <token>' or 'Bearer <api_key>'"
                )

            if auth_type == "basic":
                # Handle Basic auth
                try:
                    # Decode base64 credentials
                    decoded = base64.b64decode(auth_value).decode('utf-8')
                    username, password = decoded.split(':', 1)
                    
                    # Get the provisioning record
                    provisioning = db.query(Provisioning).filter(
                        Provisioning.mac_address == mac_address
                    ).first()
                    
                    if not provisioning:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Provisioning record not found for MAC: {mac_address}"
                        )

                    # Verify credentials
                    if not provisioning.username or not provisioning.password:
                        raise HTTPException(
                            status_code=401,
                            detail="Provisioning record has no credentials configured"
                        )

                    # Check username and password
                    if username != provisioning.username or password != provisioning.password:
                        raise HTTPException(
                            status_code=401,
                            detail="Incorrect username or password",
                            headers={"WWW-Authenticate": "Basic"}
                        )
                except Exception as e:
                    logger.error(f"Basic auth error: {str(e)}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid basic auth credentials",
                        headers={"WWW-Authenticate": "Basic"}
                    )
            elif auth_type == "bearer":
                # Handle Bearer token (JWT or API key)
                try:
                    # Try to verify as JWT first
                    payload = jwt.decode(auth_value, JWT_SECRET, algorithms=[JWT_ALGORITHM])
                    if payload.get("type") != "access":
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid token type"
                        )
                except jwt.PyJWTError:
                    # If JWT verification fails, try as API key
                    if auth_value != API_KEY:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid token or API key"
                        )
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authorization type. Use 'Basic' or 'Bearer'"
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authorization parsing error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization format"
            )

        if not AZURE_STORAGE_CONNECTION_STRING:
            raise HTTPException(
                status_code=500,
                detail="Azure Storage connection string is not configured"
            )

        # Get the provisioning record to get the endpoint ID
        provisioning = db.query(Provisioning).filter(
            Provisioning.mac_address == mac_address
        ).first()
        
        if not provisioning:
            raise HTTPException(
                status_code=404,
                detail=f"Provisioning record not found for MAC: {mac_address}"
            )

        yealink_config = YealinkConfig(
            connection_string=AZURE_STORAGE_CONNECTION_STRING,
            container_name=AZURE_STORAGE_CONTAINER
        )

        # Fetch fresh endpoint data
        try:
            endpoint_data = await yealink_config._get_endpoint_data(provisioning.endpoint, BASE_URL)
            # Generate new config content with latest data
            config_content = yealink_config._generate_config_content(endpoint_data)
            
            # Return the content as plain text
            return Response(
                content=config_content,
                media_type="text/plain"
            )
        except Exception as e:
            logger.error(f"Error fetching endpoint data: {str(e)}")
            # If we can't get fresh data, fall back to stored config
            config_content = yealink_config.get_file_content(f"{mac_address}.cfg")
            if not config_content:
                raise HTTPException(
                    status_code=404,
                    detail=f"Configuration file not found for MAC: {mac_address}"
                )
            return Response(
                content=config_content,
                media_type="text/plain"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_mac_record: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch configuration content: {str(e)}"
        )

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