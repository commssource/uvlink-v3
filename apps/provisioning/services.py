from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .models import Provisioning
from .schemas import ProvisioningCreate, ProvisioningUpdate, ProvisioningResponse
from .storage import MACAddressStorage, StorageError
from config import AZURE_STORAGE_CONNECTION_STRING, AZURE_STORAGE_CONTAINER
import logging
import traceback
import pymysql

logger = logging.getLogger(__name__)

class ProvisioningService:
    def __init__(self, db: Session):
        self.db = db
        self.storage = MACAddressStorage(
            connection_string=AZURE_STORAGE_CONNECTION_STRING,
            container_name=AZURE_STORAGE_CONTAINER
        )
#===============================================Create Provisioning===============================================
    async def create_provisioning(self, provisioning: ProvisioningCreate) -> ProvisioningResponse:
        """Create a new provisioning record"""
        try:
            # Check if MAC address already exists
            existing_record = self.db.query(Provisioning).filter(
                Provisioning.mac_address == provisioning.mac_address
            ).first()
            
            if existing_record:
                raise HTTPException(
                    status_code=400,
                    detail=f"A provisioning record with MAC address {provisioning.mac_address} already exists"
                )
            
            # First, try to store in Azure Storage
            try:
                await self.storage.store_mac_record(provisioning.mac_address, provisioning)
            except StorageError as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to store MAC address record: {str(e)}"
                )
            
            # Only create database record if storage operation succeeds
            try:
                # Create a copy of the provisioning data and set approved to True
                provisioning_data = provisioning.model_dump()
                provisioning_data['approved'] = True  # Set approved to True after successful storage
                
                db_provisioning = Provisioning(**provisioning_data)
                self.db.add(db_provisioning)
                self.db.commit()
                self.db.refresh(db_provisioning)
                
                # Convert SQLAlchemy model to dict before creating Pydantic model
                db_dict = {
                    "id": db_provisioning.id,
                    "endpoint": db_provisioning.endpoint,
                    "make": db_provisioning.make,
                    "model": db_provisioning.model,
                    "mac_address": db_provisioning.mac_address,
                    "username": db_provisioning.username,
                    "password": db_provisioning.password,
                    "status": db_provisioning.status,
                    "provisioning_request": db_provisioning.provisioning_request,
                    "ip_address": db_provisioning.ip_address,
                    "provisioning_status": db_provisioning.provisioning_status,
                    "request_date": db_provisioning.request_date,
                    "approved": db_provisioning.approved  # This will now be True
                }
                
                return ProvisioningResponse(**db_dict)
                
            except IntegrityError as e:
                self.db.rollback()
                raise HTTPException(
                    status_code=500,
                    detail=f"Database error: {str(e)}"
                )
                
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating provisioning record: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create provisioning record: {str(e)}"
            )
#===============================================Get Provisioning===============================================
    async def get_provisioning(self, mac_address: str) -> ProvisioningResponse:
        """Get a provisioning record by MAC address"""
        try:
            # Get from database
            db_provisioning = self.db.query(Provisioning).filter(Provisioning.mac_address == mac_address).first()
            if not db_provisioning:
                raise HTTPException(
                    status_code=404,
                    detail=f"Provisioning record not found for MAC address: {mac_address}"
                )
            
            # Get from Azure Storage
            storage_record = await self.storage.get_mac_record(mac_address)
            if not storage_record:
                logger.warning(f"Storage record not found for MAC address: {mac_address}")
            
            return ProvisioningResponse.model_validate(db_provisioning)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting provisioning record: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get provisioning record: {str(e)}"
            )
#===============================================Update Provisioning===============================================
    async def update_provisioning(self, mac_address: str, provisioning: ProvisioningUpdate) -> ProvisioningResponse:
        """Update a provisioning record"""
        try:
            # Get existing record
            db_provisioning = self.db.query(Provisioning).filter(Provisioning.mac_address == mac_address).first()
            if not db_provisioning:
                raise HTTPException(
                    status_code=404,
                    detail=f"Provisioning record not found for MAC address: {mac_address}"
                )
            
            # Update database record with new values
            update_data = provisioning.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_provisioning, key, value)
            
            # Store updated record in Azure Storage
            try:
                await self.storage.store_mac_record(mac_address, db_provisioning)
            except StorageError as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to update MAC address record in storage: {str(e)}"
                )
            
            # If storage update succeeds, commit database changes
            self.db.commit()
            self.db.refresh(db_provisioning)
            
            # Convert SQLAlchemy model to dict before creating Pydantic model
            db_dict = {
                "id": db_provisioning.id,
                "endpoint": db_provisioning.endpoint,
                "make": db_provisioning.make,
                "model": db_provisioning.model,
                "mac_address": db_provisioning.mac_address,
                "username": db_provisioning.username,
                "password": db_provisioning.password,
                "status": db_provisioning.status,
                "provisioning_request": db_provisioning.provisioning_request,
                "ip_address": db_provisioning.ip_address,
                "provisioning_status": db_provisioning.provisioning_status,
                "request_date": db_provisioning.request_date,
                "approved": db_provisioning.approved
            }
            
            return ProvisioningResponse(**db_dict)
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating provisioning record: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update provisioning record: {str(e)}"
            )

    async def delete_provisioning(self, mac_address: str) -> None:
        """Delete a provisioning record"""
        try:
            # Delete from database
            db_provisioning = self.db.query(Provisioning).filter(Provisioning.mac_address == mac_address).first()
            if not db_provisioning:
                raise HTTPException(
                    status_code=404,
                    detail=f"Provisioning record not found for MAC address: {mac_address}"
                )
            
            self.db.delete(db_provisioning)
            self.db.commit()
            
            # Delete from Azure Storage
            await self.storage.delete_mac_record(mac_address)
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting provisioning record: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete provisioning record: {str(e)}"
            )