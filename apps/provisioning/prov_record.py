import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import AzureError
import logging

# FastAPI project imports
from config import (
    AZURE_STORAGE_CONNECTION_STRING,
    AZURE_STORAGE_CONTAINER,
    TENANT_NAME
)

# Setup logging
logger = logging.getLogger(__name__)

class AzureStorageRecordSaver:
    def __init__(self, tenant_name: Optional[str] = None):
        """
        Initialize Azure Storage client
        
        Args:
            tenant_name: Optional tenant name override
        """
        try:
            self.blob_service_client = BlobServiceClient.from_connection_string(
                AZURE_STORAGE_CONNECTION_STRING
            )
            self.container_name = AZURE_STORAGE_CONTAINER
            self.tenant_name = tenant_name or TENANT_NAME
            
            # Ensure container exists
            self._ensure_container_exists()
            
        except Exception as e:
            logger.error(f"Error initializing Azure Storage client: {e}")
            raise

    def _ensure_container_exists(self) -> None:
        """Create container if it doesn't exist"""
        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            if not container_client.exists():
                container_client.create_container()
                logger.info(f"Created container: {self.container_name}")
        except AzureError as e:
            logger.error(f"Error creating container: {e}")
            raise

    async def save_record(self, record_content: str, filename: Optional[str] = None) -> Dict[str, str]:
        """
        Save record to Azure Storage
        
        Args:
            record_content: Content to save
            filename: Custom filename. If None, generates timestamp-based name
        
        Returns:
            Dict with file info including URL and path
        """
        try:
            # Generate filename if not provided
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"record_{timestamp}.cfg"
            
            # Create blob path with tenant folder
            blob_path = f"{self.tenant_name}/{filename}"
            
            # Get blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_path
            )
            
            # Upload content
            blob_client.upload_blob(
                record_content,
                overwrite=True,
                content_type='text/plain'
            )
            
            logger.info(f"Successfully saved record to: {blob_path}")
            
            return {
                "filename": filename,
                "blob_path": blob_path,
                "url": blob_client.url,
                "container": self.container_name,
                "tenant": self.tenant_name
            }
            
        except AzureError as e:
            logger.error(f"Error saving record to Azure Storage: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    async def list_records(self) -> List[Dict[str, Any]]:
        """List all records for the current tenant"""
        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            blob_list = container_client.list_blobs(name_starts_with=f"{self.tenant_name}/")
            
            records = []
            for blob in blob_list:
                try:
                    # Extract filename from blob path
                    filename = blob.name.split('/')[-1] if '/' in blob.name else blob.name
                    
                    record = {
                        'filename': filename,
                        'blob_path': blob.name,
                        'size': blob.size or 0,
                        'last_modified': blob.last_modified,
                        'url': f"{container_client.url}/{blob.name}",
                        'tenant': self.tenant_name
                    }
                    records.append(record)
                    
                except Exception as blob_error:
                    logger.warning(f"Error processing blob {blob.name}: {blob_error}")
                    continue
            
            return records
            
        except AzureError as e:
            logger.error(f"Error listing records: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing records: {e}")
            return []

    async def get_record(self, filename: str) -> Optional[str]:
        """Get record content by filename"""
        try:
            blob_path = f"{self.tenant_name}/{filename}"
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_path
            )
            
            download_stream = blob_client.download_blob()
            content = download_stream.readall().decode('utf-8')
            
            return content
            
        except AzureError as e:
            logger.error(f"Error getting record: {e}")
            return None

    async def delete_record(self, filename: str) -> bool:
        """Delete a specific record"""
        try:
            blob_path = f"{self.tenant_name}/{filename}"
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_path
            )
            
            blob_client.delete_blob()
            logger.info(f"Successfully deleted record: {blob_path}")
            return True
            
        except AzureError as e:
            logger.error(f"Error deleting record: {e}")
            return False

    async def record_exists(self, filename: str) -> bool:
        """Check if a record exists"""
        try:
            blob_path = f"{self.tenant_name}/{filename}"
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_path
            )
            
            return blob_client.exists()
            
        except AzureError as e:
            logger.error(f"Error checking record existence: {e}")
            return False

def create_sample_record() -> str:
    """Create the sample provisioning record content"""
    return """#!version:1.0.0.1
account.1.enable = 1
account.1.label = "201"
account.1.display_name = "201"
account.1.auth_name = "201"
account.1.user_name = "201"
account.1.password = "1234"
account.1.sip_server_host = "s1.uvlink.cloud"
account.1.sip_server_port = 5060
account.1.transport = "udp"
account.1.expires = 3600"""

# Factory function for dependency injection
def get_storage_saver(tenant_name: Optional[str] = None) -> AzureStorageRecordSaver:
    """Factory function to create AzureStorageRecordSaver instance"""
    return AzureStorageRecordSaver(tenant_name=tenant_name)