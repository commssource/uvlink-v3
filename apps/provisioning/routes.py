from fastapi import APIRouter, Query, HTTPException, Depends, Header, Request, Response, status
import jwt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import Depends
from fastapi.responses import PlainTextResponse
from shared.database import get_db
from shared.auth.endpoint_auth import EndpointAuth
from shared.auth.combined_auth import verify_combined_auth
from .schemas import DeviceProvisionRequest, DeviceResponse, DeviceUpdateRequest
from .models import ProvisioningDevice
from .uvlink_client import UVLinkAPIClient, get_uvlink_client, map_endpoint_to_config
from typing import List, TypeVar, Generic, Optional, Dict, Any
from config import TENANT_NAME
from config import SIP_SERVER_HOST, SIP_SERVER_PORT
from .prov_record import AzureStorageRecordSaver, get_storage_saver, create_sample_record
from .schemas import RecordCreate, RecordResponse, RecordListItem

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/provisioning", tags=["provisioning"])
prov_router = APIRouter(prefix="/prov", tags=["phone-config"])

endpoint_auth = EndpointAuth()

@router.post("/records", response_model=RecordResponse)
async def create_record(
    record: RecordCreate,
    tenant_name: Optional[str] = Query(None, description="Tenant name override (can also be in request body)"),
    storage: AzureStorageRecordSaver = Depends(get_storage_saver)
):
    """Create a new provisioning record"""
    try:
        # Use tenant_name from query param or request body, with query param taking priority
        effective_tenant = tenant_name or record.tenant_name
        
        # Override tenant if provided
        if effective_tenant:
            storage = AzureStorageRecordSaver(tenant_name=effective_tenant)
        
        result = await storage.save_record(
            record_content=record.content,
            filename=record.filename
        )
        
        return RecordResponse(**result)
        
    except Exception as e:
        logger.error(f"Error creating record: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create record: {str(e)}")

@router.post("/devices", response_model=DeviceResponse)
async def provision_device(
    device: DeviceProvisionRequest,
    tenant_name: Optional[str] = Query(None, description="Tenant name override"),
    db: Session = Depends(get_db),
    storage: AzureStorageRecordSaver = Depends(get_storage_saver),
    uvlink_client: UVLinkAPIClient = Depends(get_uvlink_client)
):
    """
    Provision a new device:
    1. Fetch endpoint config from UVLink API
    2. Generate config file and save to Azure Storage
    3. Save device info to database
    """
    try:
        # Override tenant if provided
        if tenant_name:
            storage = AzureStorageRecordSaver(tenant_name=tenant_name)
        
        # Check if MAC address already exists
        existing_device = db.query(ProvisioningDevice).filter(
            ProvisioningDevice.mac_address == device.mac_address
        ).first()
        
        if existing_device:
            raise HTTPException(
                status_code=409, 
                detail=f"Device with MAC address {device.mac_address} already exists"
            )
        
        # STEP 1: Fetch endpoint configuration from UVLink API
        logger.info(f"Fetching endpoint config for {device.endpoint}")
        endpoint_config = await uvlink_client.get_endpoint_config(device.endpoint)
        
        if not endpoint_config:
            # API call failed - rollback and return error
            logger.error(f"Failed to fetch endpoint config for {device.endpoint}")
            raise HTTPException(
                status_code=400,
                detail=f"Couldn't fetch the endpoint {device.endpoint}. Please check if the endpoint exists and try again."
            )
        
        # STEP 2: Map endpoint config to provisioning file format
        try:
            config_content = map_endpoint_to_config(
                endpoint_config, 
                SIP_SERVER_HOST, 
                SIP_SERVER_PORT
            )
        except ValueError as e:
            logger.error(f"Failed to map endpoint config: {e}")
            raise HTTPException(
                status_code=422,
                detail=f"Couldn't process endpoint configuration: {str(e)}"
            )
        
        # STEP 3: Save config file to Azure Storage (filename: mac_address.cfg)
        filename = f"{device.mac_address}.cfg"
        try:
            azure_result = await storage.save_record(
                record_content=config_content,
                filename=filename
            )
            logger.info(f"Saved config file to Azure: {azure_result['blob_path']}")
        except Exception as e:
            logger.error(f"Failed to save config file to Azure: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save configuration file to storage: {str(e)}"
            )
        
        # STEP 4: Save device info to database
        try:
            db_device = ProvisioningDevice(
                endpoint=device.endpoint,
                make=device.make,
                model=device.model,
                mac_address=device.mac_address,
                status=device.status,
                username=device.username,
                password=device.password
            )
            
            db.add(db_device)
            db.commit()
            db.refresh(db_device)
            
            logger.info(f"Saved device to database with ID: {db_device.id}")
            
        except IntegrityError:
            db.rollback()
            # If database save fails, try to cleanup Azure file
            try:
                await storage.delete_record(filename)
                logger.info(f"Cleaned up Azure file {filename} after database error")
            except Exception as cleanup_error:
                logger.error(f"Failed to cleanup Azure file after database error: {cleanup_error}")
            
            raise HTTPException(
                status_code=409,
                detail="Device with this MAC address already exists"
            )
        except Exception as e:
            db.rollback()
            # If database save fails, try to cleanup Azure file
            try:
                await storage.delete_record(filename)
                logger.info(f"Cleaned up Azure file {filename} after database error")
            except Exception as cleanup_error:
                logger.error(f"Failed to cleanup Azure file after database error: {cleanup_error}")
            
            logger.error(f"Database error while saving device: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save device to database: {str(e)}"
            )
        
        # STEP 5: Prepare and return response
        response_data = {
            'id': db_device.id,
            'endpoint': db_device.endpoint,
            'make': db_device.make,
            'model': db_device.model,
            'mac_address': db_device.mac_address,
            'status': db_device.status,
            'username': db_device.username,
            'password': db_device.password,
            'created_at': db_device.created_at.isoformat() if db_device.created_at else None,
            'updated_at': db_device.updated_at.isoformat() if db_device.updated_at else None,
            'config_file_url': azure_result['url']
        }
        
        return DeviceResponse(**response_data)
        
    except HTTPException:
        # HTTPExceptions are already handled, just re-raise
        raise
    except Exception as e:
        # Catch any unexpected errors
        logger.error(f"Unexpected error provisioning device: {e}")
        try:
            db.rollback()
        except:
            pass
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while provisioning the device"
        )

@router.get("/devices", response_model=List[DeviceResponse])
async def list_devices(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    endpoint: Optional[str] = Query(None, description="Filter by endpoint"),
    make: Optional[str] = Query(None, description="Filter by make"),
    db: Session = Depends(get_db)
):
    """List all provisioned devices"""
    try:
        query = db.query(ProvisioningDevice)
        
        if endpoint:
            query = query.filter(ProvisioningDevice.endpoint.ilike(f"%{endpoint}%"))
        if make:
            query = query.filter(ProvisioningDevice.make.ilike(f"%{make}%"))
        
        devices = query.offset(skip).limit(limit).all()
        
        return [DeviceResponse(**device.to_dict()) for device in devices]
        
    except Exception as e:
        logger.error(f"Error listing devices: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list devices: {str(e)}")

@router.put("/devices/{device_identifier}", response_model=DeviceResponse)
async def update_device(
    device_identifier: str,
    device_update: DeviceUpdateRequest,
    tenant_name: Optional[str] = Query(None, description="Tenant name override"),
    db: Session = Depends(get_db),
    storage: AzureStorageRecordSaver = Depends(get_storage_saver),
    uvlink_client: UVLinkAPIClient = Depends(get_uvlink_client)
):
    """
    Update an existing device by ID or MAC address:
    1. Update device info in database
    2. If endpoint changed, fetch new config from UVLink API
    3. Regenerate and update config file in Azure Storage
    
    Args:
        device_identifier: Either device ID (numeric) or MAC address (string)
    """
    try:
        # Override tenant if provided
        if tenant_name:
            storage = AzureStorageRecordSaver(tenant_name=tenant_name)
        
        # Determine if identifier is ID (numeric) or MAC address (string)
        if device_identifier.isdigit():
            # Search by ID
            existing_device = db.query(ProvisioningDevice).filter(
                ProvisioningDevice.id == int(device_identifier)
            ).first()
            identifier_type = "ID"
        else:
            # Search by MAC address
            existing_device = db.query(ProvisioningDevice).filter(
                ProvisioningDevice.mac_address == device_identifier
            ).first()
            identifier_type = "MAC address"
        
        if not existing_device:
            raise HTTPException(
                status_code=404, 
                detail=f"Device not found with {identifier_type}: {device_identifier}"
            )
        
        # Store old MAC address for file operations
        old_mac_address = existing_device.mac_address
        
        # Check if new MAC address conflicts with another device
        if device_update.mac_address and device_update.mac_address != old_mac_address:
            existing_mac = db.query(ProvisioningDevice).filter(
                ProvisioningDevice.mac_address == device_update.mac_address,
                ProvisioningDevice.id != existing_device.id
            ).first()
            
            if existing_mac:
                raise HTTPException(
                    status_code=409,
                    detail=f"MAC address {device_update.mac_address} already exists for another device"
                )
        
        # Update device fields
        update_data = device_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(existing_device, field, value)
        
        # Determine which endpoint to use for config generation
        endpoint_for_config = device_update.endpoint or existing_device.endpoint
        
        # Fetch endpoint configuration from UVLink API
        print(f"Fetching updated endpoint config for {endpoint_for_config}")
        endpoint_config = await uvlink_client.get_endpoint_config(endpoint_for_config)
        
        if not endpoint_config:
            # Rollback database changes
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail=f"Couldn't fetch the endpoint {endpoint_for_config}. Please check if the endpoint exists and try again."
            )
        
        # Generate new config content
        try:
            config_content = map_endpoint_to_config(
                endpoint_config,
                SIP_SERVER_HOST,
                SIP_SERVER_PORT
            )
        except ValueError as e:
            db.rollback()
            raise HTTPException(
                status_code=422,
                detail=f"Couldn't process endpoint configuration: {str(e)}"
            )
        
        # Determine new filename (use new MAC if changed, otherwise use existing)
        new_mac_address = device_update.mac_address or existing_device.mac_address
        new_filename = f"{new_mac_address}.cfg"
        old_filename = f"{old_mac_address}.cfg"
        
        try:
            # Save new config file
            azure_result = await storage.save_record(
                record_content=config_content,
                filename=new_filename
            )
            
            # If MAC address changed, delete old file
            if new_filename != old_filename:
                await storage.delete_record(old_filename)
                print(f"Deleted old config file: {old_filename}")
            
            print(f"Updated config file: {new_filename}")
            
        except Exception as e:
            db.rollback()
            print(f"Failed to update config file: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update configuration file: {str(e)}"
            )
        
        # Commit database changes
        try:
            db.commit()
            db.refresh(existing_device)
            print(f"Updated device in database with ID: {existing_device.id}")
            
        except Exception as e:
            db.rollback()
            # Try to cleanup new file if database update fails
            try:
                await storage.delete_record(new_filename)
                # Restore old file if MAC changed
                if new_filename != old_filename:
                    # Note: We can't easily restore the old file content here
                    pass
            except Exception as cleanup_error:
                print(f"Failed to cleanup after database error: {cleanup_error}")
            
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update device in database: {str(e)}"
            )
        
        # Prepare response
        response_data = {
            'id': existing_device.id,
            'endpoint': existing_device.endpoint,
            'make': existing_device.make,
            'model': existing_device.model,
            'mac_address': existing_device.mac_address,
            'status': existing_device.status,
            'username': existing_device.username,
            'password': existing_device.password,
            'created_at': existing_device.created_at.isoformat() if existing_device.created_at else None,
            'updated_at': existing_device.updated_at.isoformat() if existing_device.updated_at else None,
            'config_file_url': azure_result['url']
        }
        
        return DeviceResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error updating device: {e}")
        try:
            db.rollback()
        except:
            pass
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while updating the device"
        )

@router.delete("/devices/{device_identifier}")
async def delete_device(
    device_identifier: str,
    tenant_name: Optional[str] = Query(None, description="Tenant name override"),
    db: Session = Depends(get_db),
    storage: AzureStorageRecordSaver = Depends(get_storage_saver)
):
    """
    Delete a device by ID or MAC address:
    1. Delete config file from Azure Storage
    2. Delete device record from database
    
    Args:
        device_identifier: Either device ID (numeric) or MAC address (string)
    """
    try:
        # Override tenant if provided
        if tenant_name:
            storage = AzureStorageRecordSaver(tenant_name=tenant_name)
        
        # Determine if identifier is ID (numeric) or MAC address (string)
        if device_identifier.isdigit():
            # Search by ID
            device = db.query(ProvisioningDevice).filter(
                ProvisioningDevice.id == int(device_identifier)
            ).first()
            identifier_type = "ID"
        else:
            # Search by MAC address
            device = db.query(ProvisioningDevice).filter(
                ProvisioningDevice.mac_address == device_identifier
            ).first()
            identifier_type = "MAC address"
        
        if not device:
            raise HTTPException(
                status_code=404, 
                detail=f"Device not found with {identifier_type}: {device_identifier}"
            )
        
        # Store device info for response
        device_info = {
            'id': device.id,
            'endpoint': device.endpoint,
            'mac_address': device.mac_address
        }
        
        # Delete config file from Azure Storage first
        filename = f"{device.mac_address}.cfg"
        try:
            file_deleted = await storage.delete_record(filename)
            if file_deleted:
                print(f"Deleted config file: {filename}")
            else:
                print(f"Config file {filename} not found in storage (might already be deleted)")
        except Exception as e:
            print(f"Warning: Failed to delete config file {filename}: {e}")
            # Continue with database deletion even if file deletion fails
        
        # Delete device from database
        try:
            db.delete(device)
            db.commit()
            print(f"Deleted device from database: ID {device_info['id']}")
            
        except Exception as e:
            db.rollback()
            print(f"Failed to delete device from database: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete device from database: {str(e)}"
            )
        
        return {
            "message": f"Device {device_info['id']} (endpoint {device_info['endpoint']}, MAC {device_info['mac_address']}) deleted successfully",
            "deleted_device": device_info,
            "config_file_deleted": filename,
            "identifier_used": f"{identifier_type}: {device_identifier}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error deleting device: {e}")
        try:
            db.rollback()
        except:
            pass
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while deleting the device"
        )

@router.get("/devices/{device_id}", response_model=DeviceResponse)
async def get_device(device_id: int, db: Session = Depends(get_db)):
    """Get a specific device by ID"""
    try:
        device = db.query(ProvisioningDevice).filter(ProvisioningDevice.id == device_id).first()
        
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        return DeviceResponse(**device.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting device: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get device: {str(e)}")

@router.delete("/devices/{device_id}")
async def delete_device(
    device_id: int,
    db: Session = Depends(get_db),
    storage: AzureStorageRecordSaver = Depends(get_storage_saver)
):
    """Delete a device and its config file"""
    try:
        device = db.query(ProvisioningDevice).filter(ProvisioningDevice.id == device_id).first()
        
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        # Delete config file from Azure Storage
        filename = f"{device.mac_address}.cfg"
        await storage.delete_record(filename)
        
        # Delete from database
        db.delete(device)
        db.commit()
        
        return {"message": f"Device {device_id} and config file deleted successfully"}
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting device: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete device: {str(e)}")

@router.get("/health")
async def health_check():
    """Health check endpoint to test Azure Storage connectivity"""
    try:
        storage = AzureStorageRecordSaver()
        # Simple test to check if we can connect
        container_client = storage.blob_service_client.get_container_client(storage.container_name)
        exists = container_client.exists()
        
        return {
            "status": "healthy",
            "container_exists": exists,
            "container_name": storage.container_name,
            "tenant_name": storage.tenant_name
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }

@router.get("/prov", response_model=List[RecordListItem])
async def list_records(
    tenant_name: Optional[str] = Query(None, description="Tenant name override"),
    storage: AzureStorageRecordSaver = Depends(get_storage_saver)
):
    """List all provisioning records for a tenant"""
    try:
        # Override tenant if provided
        if tenant_name:
            storage = AzureStorageRecordSaver(tenant_name=tenant_name)
        
        records = await storage.list_records()
        
        # Convert datetime to string for JSON serialization and handle None values
        serialized_records = []
        for record in records:
            # Create a copy to avoid modifying the original
            record_copy = record.copy()
            
            # Handle datetime serialization
            if record_copy.get('last_modified'):
                record_copy['last_modified'] = record_copy['last_modified'].isoformat()
            else:
                record_copy['last_modified'] = ""
            
            # Ensure all required fields exist
            record_copy.setdefault('filename', '')
            record_copy.setdefault('blob_path', '')
            record_copy.setdefault('size', 0)
            record_copy.setdefault('url', '')
            record_copy.setdefault('tenant', storage.tenant_name)
            
            serialized_records.append(record_copy)
        
        return [RecordListItem(**record) for record in serialized_records]
        
    except Exception as e:
        logger.error(f"Error listing records: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list records: {str(e)}")

# Phone config endpoint (short URL for devices)
@prov_router.get("/{filename}", response_class=PlainTextResponse)
async def get_phone_config(
    filename: str,
    tenant_name: Optional[str] = Query(None, description="Tenant name"),
    storage: AzureStorageRecordSaver = Depends(get_storage_saver),
    auth: Dict[str, Any] = Depends(verify_combined_auth)
):
    """
    Get provisioning config file for phones - short URL
    Example: GET /prov/249ad818cd92.cfg?tenant_name=t-200
    """
    try:
        # Override tenant if provided
        if tenant_name:
            storage = AzureStorageRecordSaver(tenant_name=tenant_name)
        
        content = await storage.get_record(filename)
        
        if content is None:
            raise HTTPException(status_code=404, detail="Config file not found")
        
        # Return plain text directly
        return content
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting phone config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get config file: {str(e)}")


@router.get("/records/{filename}", response_class=PlainTextResponse)
async def get_record(
    filename: str,
    tenant_name: Optional[str] = Query(None, description="Tenant name override"),
    storage: AzureStorageRecordSaver = Depends(get_storage_saver)
):
    """Get a specific provisioning record by filename - returns plain text content"""
    try:
        # Override tenant if provided
        if tenant_name:
            storage = AzureStorageRecordSaver(tenant_name=tenant_name)
        
        content = await storage.get_record(filename)
        
        if content is None:
            raise HTTPException(status_code=404, detail="Record not found")
        
        # Return plain text directly
        return content
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting record: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get record: {str(e)}")

@router.delete("/records/{filename}")
async def delete_record(
    filename: str,
    tenant_name: Optional[str] = Query(None, description="Tenant name override"),
    storage: AzureStorageRecordSaver = Depends(get_storage_saver)
):
    """Delete a specific provisioning record"""
    try:
        # Override tenant if provided
        if tenant_name:
            storage = AzureStorageRecordSaver(tenant_name=tenant_name)
        
        # Check if record exists first
        exists = await storage.record_exists(filename)
        if not exists:
            raise HTTPException(status_code=404, detail="Record not found")
        
        success = await storage.delete_record(filename)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete record")
        
        return {"message": f"Record '{filename}' deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting record: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete record: {str(e)}")

@router.head("/records/{filename}")
async def check_record_exists(
    filename: str,
    tenant_name: Optional[str] = Query(None, description="Tenant name override"),
    storage: AzureStorageRecordSaver = Depends(get_storage_saver)
):
    """Check if a provisioning record exists"""
    try:
        # Override tenant if provided
        if tenant_name:
            storage = AzureStorageRecordSaver(tenant_name=tenant_name)
        
        exists = await storage.record_exists(filename)
        
        if not exists:
            raise HTTPException(status_code=404, detail="Record not found")
        
        return {"exists": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking record existence: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to check record existence: {str(e)}")