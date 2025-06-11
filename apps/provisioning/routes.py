from fastapi import APIRouter, Query, HTTPException, Depends, Header, Request, Response, status
import jwt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import Depends
from fastapi.responses import PlainTextResponse
from shared.database import get_db
from shared.auth.endpoint_auth import EndpointAuth
from shared.auth.combined_auth import verify_combined_auth
from .schemas import DeviceItem, DeviceProvisionRequest, DeviceResponse, DeviceUpdateRequest, PaginatedRecordsResponse, PaginatedRecordsResponse, PaginatedDevicesResponse
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
    storage: AzureStorageRecordSaver = Depends(get_storage_saver),
    auth: Dict[str, Any] = Depends(endpoint_auth)
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
    uvlink_client: UVLinkAPIClient = Depends(get_uvlink_client),
    auth: Dict[str, Any] = Depends(endpoint_auth)
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
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(endpoint_auth)
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
    uvlink_client: UVLinkAPIClient = Depends(get_uvlink_client),
    auth: Dict[str, Any] = Depends(endpoint_auth)
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
    storage: AzureStorageRecordSaver = Depends(get_storage_saver),
    auth: Dict[str, Any] = Depends(endpoint_auth)
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
async def get_device(device_id: int, db: Session = Depends(get_db), auth: Dict[str, Any] = Depends(endpoint_auth)):
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
    storage: AzureStorageRecordSaver = Depends(get_storage_saver),
    auth: Dict[str, Any] = Depends(endpoint_auth)
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

@router.get("/records", response_model=PaginatedRecordsResponse)
async def list_records(
    tenant_name: Optional[str] = Query(None, description="Tenant name override"),
    filename: Optional[str] = Query(None, description="Filter by filename (supports partial matching)"),
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    per_page: int = Query(50, ge=1, le=500, description="Items per page (max 500)"),
    storage: AzureStorageRecordSaver = Depends(get_storage_saver),
    auth: Dict[str, Any] = Depends(verify_combined_auth)
):
    """List all provisioning records for a tenant with optional filename filtering and pagination"""
    try:
        # Override tenant if provided
        if tenant_name:
            storage = AzureStorageRecordSaver(tenant_name=tenant_name)
        
        records = await storage.list_records()
        
        # Debug logging
        if filename:
            print(f"=== FILENAME FILTERING DEBUG ===")
            print(f"Filter parameter: '{filename}'")
            print(f"Total records before filtering: {len(records)}")
            for i, record in enumerate(records[:3]):  # Show first 3 records
                print(f"Record {i} structure: {record}")
            print(f"================================")
        
        # Convert datetime to string for JSON serialization and handle None values
        filtered_records = []
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
            
            # Apply filename filtering if provided
            if filename:
                record_filename = record_copy.get('filename', '')
                
                # Debug individual record
                print(f"Checking record filename: '{record_filename}' against filter: '{filename}'")
                
                # Case-insensitive partial matching
                if filename.lower() not in record_filename.lower():
                    print(f"SKIPPING: '{record_filename}' does not contain '{filename}'")
                    continue  # Skip this record if filename doesn't match
                else:
                    print(f"MATCHED: '{record_filename}' contains '{filename}'")
            
            filtered_records.append(record_copy)
        
        if filename:
            print(f"Total records after filtering: {len(filtered_records)}")
        
        # Calculate pagination
        total_records = len(filtered_records)
        total_pages = (total_records + per_page - 1) // per_page  # Ceiling division
        
        # Calculate start and end indices for pagination
        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        
        # Get paginated records
        paginated_records = filtered_records[start_index:end_index]
        
        # Convert to RecordListItem objects
        record_items = [RecordListItem(**record) for record in paginated_records]
        
        # Create pagination response
        response = PaginatedRecordsResponse(
            items=record_items,
            total=total_records,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        )
        
        print(f"Pagination: Page {page}/{total_pages}, showing {len(record_items)} of {total_records} total records")
        
        return response
        
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
    

# Enhanced database routes with all fields

# Enhanced database routes with all fields

@router.get("/database/devices", response_model=PaginatedDevicesResponse)
async def list_database_devices(
    # Pagination parameters
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=500, description="Items per page"),
    
    # Filtering parameters - Updated with all fields
    endpoint: Optional[str] = Query(None, description="Filter by endpoint"),
    make: Optional[str] = Query(None, description="Filter by make"),
    model: Optional[str] = Query(None, description="Filter by model"),
    mac_address: Optional[str] = Query(None, description="Filter by MAC address"),
    device: Optional[str] = Query(None, description="Filter by device name"),
    status: Optional[bool] = Query(None, description="Filter by status"),
    provisioning_status: Optional[str] = Query(None, description="Filter by provisioning status"),
    approved: Optional[bool] = Query(None, description="Filter by approved status"),
    ip_address: Optional[str] = Query(None, description="Filter by IP address"),
    username: Optional[str] = Query(None, description="Filter by username"),
    
    # Dependencies
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(verify_combined_auth)
):
    """List all provisioned devices with enhanced filtering"""
    try:
        # Start with base query
        query = db.query(ProvisioningDevice)
        
        # Apply all filters - FIXED Boolean filtering
        if endpoint:
            query = query.filter(ProvisioningDevice.endpoint.ilike(f"%{endpoint}%"))
        if make:
            query = query.filter(ProvisioningDevice.make.ilike(f"%{make}%"))
        if model:
            query = query.filter(ProvisioningDevice.model.ilike(f"%{model}%"))
        if mac_address:
            query = query.filter(ProvisioningDevice.mac_address.ilike(f"%{mac_address}%"))
        if device:
            query = query.filter(ProvisioningDevice.device.ilike(f"%{device}%"))
        if status is not None:
            query = query.filter(ProvisioningDevice.status == status)
        if provisioning_status:
            query = query.filter(ProvisioningDevice.provisioning_status.ilike(f"%{provisioning_status}%"))
        
        # FIXED: Proper boolean filtering for approved field
        if approved is not None:
            if approved:
                # When approved=true, only show records where approved IS true (not NULL)
                query = query.filter(ProvisioningDevice.approved == True)
            else:
                # When approved=false, show records where approved IS false OR NULL
                query = query.filter(
                    (ProvisioningDevice.approved == False) | 
                    (ProvisioningDevice.approved.is_(None))
                )
        
        if ip_address:
            query = query.filter(ProvisioningDevice.ip_address.ilike(f"%{ip_address}%"))
        if username:
            query = query.filter(ProvisioningDevice.username.ilike(f"%{username}%"))
        
        # Get total count
        total_count = query.count()
        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
        offset = (page - 1) * per_page
        
        # Apply pagination and ordering
        devices = query.order_by(ProvisioningDevice.created_at.desc()).offset(offset).limit(per_page).all()
        
        # Convert to response items with all fields
        device_items = []
        for device in devices:
            item = DeviceItem(
                id=device.id,
                endpoint=device.endpoint,
                make=device.make,
                model=device.model,
                mac_address=device.mac_address,
                device=device.device,
                status=device.status,
                provisioning_status=device.provisioning_status,
                approved=device.approved,
                ip_address=device.ip_address,
                username=device.username,
                password=device.password,
                created_at=device.created_at,      # Will be auto-formatted to UK
                updated_at=device.updated_at,     # Will be auto-formatted to UK
                request_date=device.request_date, # Will be auto-formatted to UK
                last_provisioning_attempt=device.last_provisioning_attempt, # Will be auto-formatted to UK
                config_file_url=None
            )
            device_items.append(item)
        
        response = PaginatedDevicesResponse(
            items=device_items,
            total=total_count,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error listing database devices: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list devices: {str(e)}")

# Example enhanced filtering endpoints - FIXED
@router.get("/database/devices/pending", response_model=PaginatedDevicesResponse)
async def list_pending_devices(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(verify_combined_auth)
):
    """List devices with pending provisioning status"""
    try:
        # Start with base query
        query = db.query(ProvisioningDevice)
        
        # Filter for pending status
        query = query.filter(ProvisioningDevice.provisioning_status.ilike("%pending%"))
        
        # Get total count
        total_count = query.count()
        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
        offset = (page - 1) * per_page
        
        # Apply pagination and ordering
        devices = query.order_by(ProvisioningDevice.created_at.desc()).offset(offset).limit(per_page).all()
        
        # Convert to response items
        device_items = []
        for device in devices:
            item = DeviceItem(
                id=device.id,
                endpoint=device.endpoint,
                make=device.make,
                model=device.model,
                mac_address=device.mac_address,
                device=device.device,
                status=device.status,
                provisioning_status=device.provisioning_status,
                approved=device.approved,
                ip_address=device.ip_address,
                username=device.username,
                password=device.password,
                created_at=device.created_at,
                updated_at=device.updated_at,
                request_date=device.request_date,
                last_provisioning_attempt=device.last_provisioning_attempt,
                config_file_url=None
            )
            device_items.append(item)
        
        response = PaginatedDevicesResponse(
            items=device_items,
            total=total_count,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error listing pending devices: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list pending devices: {str(e)}")

@router.get("/database/devices/approved", response_model=PaginatedDevicesResponse)
async def list_approved_devices(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(verify_combined_auth)
):
    """List approved devices only"""
    try:
        # Start with base query
        query = db.query(ProvisioningDevice)
        
        # Filter for approved devices only (excludes NULL)
        query = query.filter(ProvisioningDevice.approved == True)
        
        # Get total count
        total_count = query.count()
        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
        offset = (page - 1) * per_page
        
        # Apply pagination and ordering
        devices = query.order_by(ProvisioningDevice.created_at.desc()).offset(offset).limit(per_page).all()
        
        # Convert to response items
        device_items = []
        for device in devices:
            item = DeviceItem(
                id=device.id,
                endpoint=device.endpoint,
                make=device.make,
                model=device.model,
                mac_address=device.mac_address,
                device=device.device,
                status=device.status,
                provisioning_status=device.provisioning_status,
                approved=device.approved,
                ip_address=device.ip_address,
                username=device.username,
                password=device.password,
                created_at=device.created_at,
                updated_at=device.updated_at,
                request_date=device.request_date,
                last_provisioning_attempt=device.last_provisioning_attempt,
                config_file_url=None
            )
            device_items.append(item)
        
        response = PaginatedDevicesResponse(
            items=device_items,
            total=total_count,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error listing approved devices: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list approved devices: {str(e)}")

# Update and Delete endpoints for database devices

@router.put("/database/devices/{device_identifier}", response_model=DeviceItem)
async def update_database_device(
    device_identifier: str,
    device_update: DeviceUpdateRequest,
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(verify_combined_auth)
):
    """
    Update a device in the database by ID or MAC address
    
    Args:
        device_identifier: Either device ID (numeric) or MAC address (string)
        device_update: Fields to update
    """
    try:
        # Determine if identifier is ID (numeric) or MAC address (string)
        if device_identifier.isdigit():
            device = db.query(ProvisioningDevice).filter(
                ProvisioningDevice.id == int(device_identifier)
            ).first()
            identifier_type = "ID"
        else:
            device = db.query(ProvisioningDevice).filter(
                ProvisioningDevice.mac_address == device_identifier
            ).first()
            identifier_type = "MAC address"
        
        if not device:
            raise HTTPException(
                status_code=404, 
                detail=f"Device not found with {identifier_type}: {device_identifier}"
            )
        
        # Check if new MAC address conflicts with another device
        if device_update.mac_address and device_update.mac_address != device.mac_address:
            existing_mac = db.query(ProvisioningDevice).filter(
                ProvisioningDevice.mac_address == device_update.mac_address,
                ProvisioningDevice.id != device.id
            ).first()
            
            if existing_mac:
                raise HTTPException(
                    status_code=409,
                    detail=f"MAC address {device_update.mac_address} already exists for another device"
                )
        
        # Update device fields
        update_data = device_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(device, field):
                setattr(device, field, value)
        
        # Commit changes
        try:
            db.commit()
            db.refresh(device)
            print(f"Updated device in database: ID {device.id}")
            
        except Exception as e:
            db.rollback()
            print(f"Failed to update device in database: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update device in database: {str(e)}"
            )
        
        # Return updated device
        return DeviceItem(
            id=device.id,
            endpoint=device.endpoint,
            make=device.make,
            model=device.model,
            mac_address=device.mac_address,
            device=device.device,
            status=device.status,
            provisioning_status=device.provisioning_status,
            approved=device.approved,
            ip_address=device.ip_address,
            username=device.username,
            password=device.password,
            created_at=device.created_at,
            updated_at=device.updated_at,
            request_date=device.request_date,
            last_provisioning_attempt=device.last_provisioning_attempt,
            config_file_url=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating database device: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update device: {str(e)}")

@router.delete("/database/devices/{device_identifier}")
async def delete_database_device(
    device_identifier: str,
    delete_config_file: bool = Query(False, description="Also delete the config file from Azure Storage"),
    tenant_name: Optional[str] = Query(None, description="Tenant name for config file deletion"),
    db: Session = Depends(get_db),
    storage: AzureStorageRecordSaver = Depends(get_storage_saver),
    auth: Dict[str, Any] = Depends(verify_combined_auth)
):
    """
    Delete a device from database by ID or MAC address
    
    Args:
        device_identifier: Either device ID (numeric) or MAC address (string)
        delete_config_file: Whether to also delete the config file from Azure Storage
        tenant_name: Tenant name override for config file deletion
    """
    try:
        # Override tenant if provided
        if tenant_name:
            storage = AzureStorageRecordSaver(tenant_name=tenant_name)
        
        # Determine if identifier is ID (numeric) or MAC address (string)
        if device_identifier.isdigit():
            device = db.query(ProvisioningDevice).filter(
                ProvisioningDevice.id == int(device_identifier)
            ).first()
            identifier_type = "ID"
        else:
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
            'mac_address': device.mac_address,
            'make': device.make,
            'model': device.model
        }
        
        config_file_deleted = False
        config_file_error = None
        
        # Delete config file from Azure Storage if requested
        if delete_config_file:
            try:
                filename = f"{device.mac_address}.cfg"
                file_deleted = await storage.delete_record(filename)
                if file_deleted:
                    config_file_deleted = True
                    print(f"Deleted config file: {filename}")
                else:
                    config_file_error = f"Config file {filename} not found in storage"
                    print(config_file_error)
            except Exception as e:
                config_file_error = f"Failed to delete config file: {str(e)}"
                print(f"Warning: {config_file_error}")
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
        
        # Prepare response
        response = {
            "message": f"Device {device_info['id']} ({device_info['make']} {device_info['model']}, endpoint {device_info['endpoint']}, MAC {device_info['mac_address']}) deleted successfully",
            "deleted_device": device_info,
            "identifier_used": f"{identifier_type}: {device_identifier}",
            "config_file_deleted": config_file_deleted
        }
        
        if config_file_error:
            response["config_file_error"] = config_file_error
        elif delete_config_file and config_file_deleted:
            response["config_file_name"] = f"{device.mac_address}.cfg"
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting database device: {e}")
        try:
            db.rollback()
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to delete device: {str(e)}")

# Bulk operations
@router.put("/database/devices/bulk-update")
async def bulk_update_devices(
    device_ids: List[int],
    device_update: DeviceUpdateRequest,
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(verify_combined_auth)
):
    """
    Update multiple devices at once
    
    Args:
        device_ids: List of device IDs to update
        device_update: Fields to update for all devices
    """
    try:
        # Get all devices
        devices = db.query(ProvisioningDevice).filter(
            ProvisioningDevice.id.in_(device_ids)
        ).all()
        
        if not devices:
            raise HTTPException(status_code=404, detail="No devices found with provided IDs")
        
        updated_count = 0
        update_data = device_update.dict(exclude_unset=True)
        
        # Update each device
        for device in devices:
            for field, value in update_data.items():
                if hasattr(device, field):
                    setattr(device, field, value)
            updated_count += 1
        
        # Commit all changes
        try:
            db.commit()
            print(f"Bulk updated {updated_count} devices")
            
        except Exception as e:
            db.rollback()
            print(f"Failed to bulk update devices: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update devices: {str(e)}"
            )
        
        return {
            "message": f"Successfully updated {updated_count} devices",
            "updated_devices": [device.id for device in devices],
            "updated_fields": list(update_data.keys())
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error bulk updating devices: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to bulk update devices: {str(e)}")

@router.delete("/database/devices/bulk-delete")
async def bulk_delete_devices(
    device_ids: List[int],
    delete_config_files: bool = Query(False, description="Also delete config files from Azure Storage"),
    tenant_name: Optional[str] = Query(None, description="Tenant name for config file deletion"),
    db: Session = Depends(get_db),
    storage: AzureStorageRecordSaver = Depends(get_storage_saver),
    auth: Dict[str, Any] = Depends(verify_combined_auth)
):
    """
    Delete multiple devices at once
    
    Args:
        device_ids: List of device IDs to delete
        delete_config_files: Whether to also delete config files from Azure Storage
        tenant_name: Tenant name override for config file deletion
    """
    try:
        # Override tenant if provided
        if tenant_name:
            storage = AzureStorageRecordSaver(tenant_name=tenant_name)
        
        # Get all devices
        devices = db.query(ProvisioningDevice).filter(
            ProvisioningDevice.id.in_(device_ids)
        ).all()
        
        if not devices:
            raise HTTPException(status_code=404, detail="No devices found with provided IDs")
        
        deleted_devices = []
        config_files_deleted = []
        config_file_errors = []
        
        # Delete config files if requested
        if delete_config_files:
            for device in devices:
                try:
                    filename = f"{device.mac_address}.cfg"
                    file_deleted = await storage.delete_record(filename)
                    if file_deleted:
                        config_files_deleted.append(filename)
                    else:
                        config_file_errors.append(f"{filename}: not found")
                except Exception as e:
                    config_file_errors.append(f"{device.mac_address}.cfg: {str(e)}")
        
        # Delete devices from database
        for device in devices:
            deleted_devices.append({
                'id': device.id,
                'endpoint': device.endpoint,
                'mac_address': device.mac_address,
                'make': device.make,
                'model': device.model
            })
            db.delete(device)
        
        # Commit all deletions
        try:
            db.commit()
            print(f"Bulk deleted {len(deleted_devices)} devices")
            
        except Exception as e:
            db.rollback()
            print(f"Failed to bulk delete devices: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete devices: {str(e)}"
            )
        
        response = {
            "message": f"Successfully deleted {len(deleted_devices)} devices",
            "deleted_devices": deleted_devices,
            "config_files_deleted": len(config_files_deleted),
            "config_file_names": config_files_deleted
        }
        
        if config_file_errors:
            response["config_file_errors"] = config_file_errors
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error bulk deleting devices: {e}")
        try:
            db.rollback()
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to bulk delete devices: {str(e)}")

@router.get("/database/devices/not-approved", response_model=PaginatedDevicesResponse)
async def list_not_approved_devices(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(verify_combined_auth)
):
    """List devices that are not approved (false or NULL)"""
    try:
        # Start with base query
        query = db.query(ProvisioningDevice)
        
        # Filter for not approved devices (false OR NULL)
        query = query.filter(
            (ProvisioningDevice.approved == False) | 
            (ProvisioningDevice.approved.is_(None))
        )
        
        # Get total count
        total_count = query.count()
        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
        offset = (page - 1) * per_page
        
        # Apply pagination and ordering
        devices = query.order_by(ProvisioningDevice.created_at.desc()).offset(offset).limit(per_page).all()
        
        # Convert to response items
        device_items = []
        for device in devices:
            item = DeviceItem(
                id=device.id,
                endpoint=device.endpoint,
                make=device.make,
                model=device.model,
                mac_address=device.mac_address,
                device=device.device,
                status=device.status,
                provisioning_status=device.provisioning_status,
                approved=device.approved,
                ip_address=device.ip_address,
                username=device.username,
                password=device.password,
                created_at=device.created_at,
                updated_at=device.updated_at,
                request_date=device.request_date,
                last_provisioning_attempt=device.last_provisioning_attempt,
                config_file_url=None
            )
            device_items.append(item)
        
        response = PaginatedDevicesResponse(
            items=device_items,
            total=total_count,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error listing not approved devices: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list not approved devices: {str(e)}")