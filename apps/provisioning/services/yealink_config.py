from azure.storage.blob import BlobServiceClient
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

class YealinkConfig:
    def __init__(self, connection_string: str, container_name: str):
        """Initialize the YealinkConfig service with Azure Storage connection"""
        try:
            logger.info(f"Initializing Azure Storage client with container: {container_name}")
            self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
            self.container_client = self.blob_service_client.get_container_client(container_name)
            logger.info("Successfully initialized Azure Storage client")
        except Exception as e:
            logger.error(f"Failed to initialize Azure Storage client: {str(e)}")
            logger.error(f"Connection string length: {len(connection_string) if connection_string else 0}")
            logger.error(f"Container name: {container_name}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize storage connection: {str(e)}"
            )

    async def get_file_content(self, filename: str) -> str:
        """Get the content of a file from Azure Storage"""
        try:
            logger.info(f"Attempting to get file content for: {filename}")
            blob_client = self.container_client.get_blob_client(filename)
            
            logger.info(f"Checking if blob exists: {filename}")
            exists = blob_client.exists()
            logger.info(f"Blob exists: {exists}")
            
            if not exists:
                logger.warning(f"File {filename} not found in Azure Storage")
                return None
                
            # Download the blob content
            logger.info(f"Downloading blob content for: {filename}")
            download_stream = blob_client.download_blob()
            content = download_stream.readall()
            logger.info(f"Successfully downloaded content for: {filename}")
            return content.decode('utf-8')
        except Exception as e:
            logger.error(f"Error getting file content from Azure Storage: {str(e)}")
            logger.error(f"Filename: {filename}")
            logger.error(f"Container name: {self.container_client.container_name}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get file content: {str(e)}"
            ) 