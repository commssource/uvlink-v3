from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceNotFoundError
from fastapi import HTTPException
from typing import List, Optional, Union, Dict, Any
import logging
import traceback
import aiohttp
from config import TENANT_NAME, BASE_URL, SIP_SERVER_HOST, SIP_SERVER_PORT, API_KEY
from .schemas import ProvisioningCreate, ProvisioningUpdate, ProvisioningResponse

logger = logging.getLogger(__name__)

class StorageError(Exception):
    """Custom exception for storage-related errors"""
    pass

class MACAddressStorage:
    def __init__(self, connection_string: str, container_name: str):
        self.connection_string = connection_string
        self.container_name = container_name
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        self.container_client = self.blob_service_client.get_container_client(container_name)

    async def _get_endpoint_config(self, endpoint: str) -> dict:
        """Get configuration from endpoints API"""
        try:
            async with aiohttp.ClientSession() as session:
                # Call the endpoints API with Bearer token authentication
                url = f"{BASE_URL}/api/v1/endpoints/{endpoint}"
                headers = {
                    "Authorization": f"Bearer {API_KEY}"
                }
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        endpoint_data = await response.json()
                        logger.info(f"Received endpoint data: {endpoint_data}")
                        
                        # Map transport types to Yealink values
                        transport_map = {
                            'udp': '0',
                            'tcp': '1',
                            'tls': '2'
                        }
                        
                        # Get transport value from endpoint data
                        transport = endpoint_data.get('transport_network', {}).get('transport', 'udp')
                        transport_value = transport_map.get(transport, '0')  # Default to UDP if unknown
                        
                        logger.info(f"Transport mapping for endpoint {endpoint}: {transport} -> {transport_value}")
                        
                        config = {
                            "label": endpoint_data.get('id', ''),
                            "display_name": endpoint_data.get('id', ''),
                            "auth_name": endpoint_data.get('auth', {}).get('username', ''),
                            "user_name": endpoint_data.get('auth', {}).get('username', ''),
                            "password": endpoint_data.get('auth', {}).get('password', ''),
                            "sip_server_host": SIP_SERVER_HOST,
                            "sip_server_port": SIP_SERVER_PORT,
                            "transport": transport_value,
                            "expires": endpoint_data.get('aor', {}).get('default_expiration', '3600')
                        }
                        
                        logger.info(f"Generated config for endpoint {endpoint}: {config}")
                        return config
                    elif response.status == 404:
                        # Return default configuration when endpoint doesn't exist
                        logger.warning(f"Endpoint {endpoint} not found. Using default configuration.")
                        return {
                            "label": endpoint,
                            "display_name": endpoint,
                            "auth_name": endpoint,
                            "user_name": endpoint,
                            "password": "",  # Empty password as default
                            "sip_server_host": SIP_SERVER_HOST,
                            "sip_server_port": SIP_SERVER_PORT,
                            "transport": "0",  # Default to UDP
                            "expires": "3600"  # Default expiration
                        }
                    elif response.status == 403:
                        raise StorageError("Authentication failed. Please check your API key.")
                    else:
                        error_text = await response.text()
                        raise StorageError(f"Failed to get endpoint configuration: HTTP {response.status} - {error_text}")
        except aiohttp.ClientError as e:
            # Return default configuration on connection errors
            logger.warning(f"Failed to connect to endpoints API: {str(e)}. Using default configuration.")
            return {
                "label": endpoint,
                "display_name": endpoint,
                "auth_name": endpoint,
                "user_name": endpoint,
                "password": "",  # Empty password as default
                "sip_server_host": SIP_SERVER_HOST,
                "sip_server_port": SIP_SERVER_PORT,
                "transport": "0",  # Default to UDP
                "expires": "3600"  # Default expiration
            }
        except Exception as e:
            raise StorageError(f"Error getting endpoint configuration: {str(e)}")

    async def store_mac_record(self, mac_address: str, data: Union[ProvisioningCreate, ProvisioningUpdate, ProvisioningResponse]) -> None:
        """Store a MAC address record in Azure Storage"""
        try:
            # Convert data to dict based on its type
            if hasattr(data, 'model_dump'):  # For Pydantic models
                record_data = data.model_dump()
            else:  # For SQLAlchemy models
                record_data = {
                    'endpoint': data.endpoint,
                    'make': data.make,
                    'model': data.model,
                    'mac_address': data.mac_address,
                    'username': data.username,
                    'password': data.password,
                    'status': data.status,
                    #'provisioning_request': data.provisioning_request,
                    'ip_address': data.ip_address,
                    'provisioning_status': data.provisioning_status,
                    'request_date': data.request_date,
                    'approved': data.approved
                }
            
            # Get configuration from API
            endpoint_config = await self._get_endpoint_config(record_data.get('endpoint', ''))
            
            # Log the endpoint config for debugging
            logger.info(f"Endpoint config for {mac_address}: {endpoint_config}")
            
            # Format as Yealink config
            content = f"""#!version:1.0.0.1

account.1.enable = 1
account.1.label = {endpoint_config['label']}
account.1.display_name = {endpoint_config['display_name']}
account.1.auth_name = {endpoint_config['auth_name']}
account.1.user_name = {endpoint_config['user_name']}
account.1.password = {endpoint_config['password']}
account.1.sip_server_host = {endpoint_config['sip_server_host']}
account.1.sip_server_port = {endpoint_config['sip_server_port']}
account.1.transport = {endpoint_config['transport']}  # udp = 0, tcp = 1, tls = 2
account.1.expires = {endpoint_config['expires']}
"""
            
            # Log the exact content being written
            logger.info(f"Writing config content for {mac_address}:")
            logger.info("---BEGIN CONFIG---")
            logger.info(content)
            logger.info("---END CONFIG---")
            
            # Upload config file
            blob_path = f"{TENANT_NAME}/{mac_address}.cfg"
            self.container_client.upload_blob(
                name=blob_path,
                data=content,
                overwrite=True
            )
            
            # Create boot file
            boot_content = f"""# MAC: {mac_address}
config_server_url = {BASE_URL}/prov/{mac_address}
"""
            
            # Upload boot file
            boot_path = f"{TENANT_NAME}/{mac_address}.boot"
            self.container_client.upload_blob(
                name=boot_path,
                data=boot_content,
                overwrite=True
            )
            
            logger.info(f"Successfully stored MAC address record for {mac_address}")
            
        except Exception as e:
            logger.error(f"Error storing MAC address record: {str(e)}")
            logger.error(traceback.format_exc())
            raise StorageError(f"Failed to store MAC address record: {str(e)}")

    async def get_mac_record(self, mac_address: str) -> Optional[Dict[str, Any]]:
        """Retrieve a MAC address record from Azure Storage"""
        try:
            logger.info(f"Retrieving MAC address record for: {mac_address}")
            
            # Create blob name with tenant folder
            blob_name = f"{TENANT_NAME}/{mac_address}.cfg"
            
            # Get blob client
            blob_client = self.container_client.get_blob_client(blob_name)
            
            # Check if blob exists
            if not blob_client.exists():
                logger.info(f"No record found for MAC address: {mac_address}")
                return None
            
            # Download the record
            download_stream = blob_client.download_blob()
            content = download_stream.readall().decode('utf-8')
            
            # Parse the Yealink config content
            record = {}
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    try:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        record[key] = value
                    except ValueError:
                        continue
            
            logger.info(f"Successfully retrieved MAC address record for: {mac_address}")
            return record
            
        except Exception as e:
            logger.error(f"Failed to retrieve MAC address record: {str(e)}")
            raise StorageError(f"Failed to retrieve MAC address record: {str(e)}")

    async def delete_mac_record(self, mac_address: str) -> None:
        """Delete MAC address record from Azure Storage"""
        try:
            logger.info(f"Deleting MAC address record for: {mac_address}")
            
            # Create blob names with tenant folder
            config_blob_name = f"{TENANT_NAME}/{mac_address}.cfg"
            boot_blob_name = f"{TENANT_NAME}/{mac_address}.boot"
            
            # Get blob clients
            config_blob_client = self.container_client.get_blob_client(config_blob_name)
            boot_blob_client = self.container_client.get_blob_client(boot_blob_name)
            
            # Delete both files if they exist
            if config_blob_client.exists():
                config_blob_client.delete_blob()
            if boot_blob_client.exists():
                boot_blob_client.delete_blob()
            
            logger.info(f"Successfully deleted MAC address record for: {mac_address}")
            
        except Exception as e:
            logger.error(f"Failed to delete MAC address record: {str(e)}")
            raise StorageError(f"Failed to delete MAC address record: {str(e)}")

    async def list_mac_records(self) -> list[str]:
        """List all MAC address records in Azure Storage"""
        try:
            logger.info("Listing all MAC address records")
            
            # List all blobs in the tenant folder
            blobs = self.container_client.list_blobs(name_starts_with=f"{TENANT_NAME}/")
            
            # Extract MAC addresses from blob names
            mac_addresses = []
            for blob in blobs:
                if blob.name.endswith('.cfg'):
                    # Extract MAC address from blob name (remove .cfg extension and tenant folder)
                    mac_address = blob.name.replace(f"{TENANT_NAME}/", "").replace(".cfg", "")
                    mac_addresses.append(mac_address)
            
            logger.info(f"Found {len(mac_addresses)} MAC address records")
            return mac_addresses
            
        except Exception as e:
            logger.error(f"Failed to list MAC address records: {str(e)}")
            raise StorageError(f"Failed to list MAC address records: {str(e)}")
