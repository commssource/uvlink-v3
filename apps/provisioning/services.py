import os
from azure.storage.blob import BlobServiceClient
from fastapi import HTTPException
import aiohttp
from typing import Dict, Any
import logging
import traceback
import time
from config import API_KEY

logger = logging.getLogger(__name__)

class YealinkConfig:
    def __init__(self, connection_string: str, container_name: str):
        try:
            logger.info("Initializing YealinkConfig service")
            self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
            self.container_name = container_name
            self.container_client = self.blob_service_client.get_container_client(container_name)
            logger.info(f"Successfully initialized YealinkConfig with container: {container_name}")
        except Exception as e:
            logger.error(f"Failed to initialize YealinkConfig: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize Azure Storage client: {str(e)}"
            )

    def get_file_content(self, filename: str) -> str:
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
            logger.error(f"Container name: {self.container_name}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get file content: {str(e)}"
            )

    async def _get_endpoint_data(self, endpoint_id: str, base_url: str) -> Dict[str, Any]:
        """Fetch endpoint data from the API"""
        start_time = time.time()
        try:
            logger.info(f"Fetching endpoint data for ID: {endpoint_id}")
            # Remove trailing slash from base_url if present
            base_url = base_url.rstrip('/')
            # Construct the full URL
            url = f"{base_url}/endpoints/{endpoint_id}"
            logger.info(f"Requesting URL: {url}")
            
            # Add timeout and headers with API key
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {API_KEY}'
            }
            
            # Log the full request details for debugging
            logger.info(f"Making request to: {url}")
            logger.info(f"With headers: {headers}")
            
            request_start = time.time()
            timeout = aiohttp.ClientTimeout(total=30)  # 30 seconds total timeout
            async with aiohttp.ClientSession(timeout=timeout) as session:
                try:
                    async with session.get(url, headers=headers, ssl=False) as response:
                        request_time = time.time() - request_start
                        logger.info(f"Request completed in {request_time:.2f} seconds")
                        
                        # Log the response details
                        logger.info(f"Response status: {response.status}")
                        logger.info(f"Response headers: {response.headers}")
                        
                        # Get response text first for logging
                        response_text = await response.text()
                        logger.info(f"Raw response text: {response_text}")
                        
                        if response.status == 404:
                            logger.error(f"Endpoint {endpoint_id} not found at URL: {url}")
                            raise HTTPException(
                                status_code=404,
                                detail=f"Endpoint {endpoint_id} not found. Please verify the endpoint ID exists and the URL is correct: {url}"
                            )
                        elif response.status == 401:
                            logger.error("Unauthorized: Invalid or missing API key")
                            raise HTTPException(
                                status_code=401,
                                detail="Unauthorized: Invalid or missing API key"
                            )
                        elif response.status != 200:
                            logger.error(f"Failed to fetch endpoint data. Status: {response.status}, Response: {response_text}")
                            raise HTTPException(
                                status_code=response.status,
                                detail=f"Failed to fetch endpoint data: {response_text}"
                            )
                        
                        try:
                            # Try to parse JSON
                            data = await response.json()
                            logger.info(f"Parsed JSON data: {data}")
                            
                            # Check if data is a dictionary
                            if not isinstance(data, dict):
                                logger.error(f"Expected dictionary response, got {type(data)}")
                                raise HTTPException(
                                    status_code=500,
                                    detail=f"Invalid response format: expected dictionary, got {type(data)}"
                                )
                            
                            # Log all available fields
                            logger.info(f"Available fields in response: {list(data.keys())}")
                            
                            # Check for auth field
                            if 'auth' not in data:
                                logger.error("Missing 'auth' field in response")
                                raise HTTPException(
                                    status_code=500,
                                    detail="Endpoint data missing required 'auth' field"
                                )
                            
                            # Extract auth data
                            auth_data = data['auth']
                            if not isinstance(auth_data, dict):
                                logger.error(f"Expected auth field to be a dictionary, got {type(auth_data)}")
                                raise HTTPException(
                                    status_code=500,
                                    detail="Invalid auth data format"
                                )
                            
                            # Validate required auth fields
                            required_fields = ['username', 'password']
                            missing_fields = [field for field in required_fields if field not in auth_data]
                            if missing_fields:
                                logger.error(f"Missing required auth fields: {missing_fields}")
                                logger.error(f"Available auth fields: {list(auth_data.keys())}")
                                raise HTTPException(
                                    status_code=500,
                                    detail=f"Endpoint auth data missing required fields: {', '.join(missing_fields)}. Available fields: {', '.join(list(auth_data.keys()))}"
                                )
                            
                            # Create the expected data structure
                            endpoint_data = {
                                'endpoint_id': endpoint_id,  # Add endpoint ID to the data
                                'auth_name': auth_data.get('username', ''),  # Use username as auth_name
                                'username': auth_data.get('username', ''),
                                'password': auth_data.get('password', '')
                            }
                            
                            total_time = time.time() - start_time
                            logger.info(f"Successfully fetched endpoint data in {total_time:.2f} seconds")
                            return endpoint_data
                            
                        except ValueError as json_error:
                            logger.error(f"Invalid JSON response: {response_text}")
                            logger.error(f"JSON parse error: {str(json_error)}")
                            raise HTTPException(
                                status_code=500,
                                detail=f"Invalid JSON response from endpoint API: {str(json_error)}"
                            )
                        except Exception as parse_error:
                            logger.error(f"Error parsing response: {str(parse_error)}")
                            logger.error(f"Response text: {response_text}")
                            raise HTTPException(
                                status_code=500,
                                detail=f"Error parsing endpoint API response: {str(parse_error)}"
                            )
                            
                except aiohttp.ClientError as e:
                    logger.error(f"Connection error while connecting to: {url}")
                    logger.error(f"Connection error details: {str(e)}")
                    raise HTTPException(
                        status_code=503,
                        detail=f"Could not connect to Endpoint API: {str(e)}"
                    )
                except Exception as request_error:
                    logger.error(f"Unexpected error during request: {str(request_error)}")
                    logger.error(traceback.format_exc())
                    raise HTTPException(
                        status_code=500,
                        detail=f"Unexpected error during request: {str(request_error)}"
                    )
                
        except HTTPException:
            # Re-raise HTTP exceptions without wrapping
            raise
        except Exception as e:
            logger.error(f"Unexpected error while fetching endpoint data: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Unexpected error while fetching endpoint data: {str(e)}"
            )

    async def generate_config_files(self, mac_address: str, endpoint_id: str, base_url: str) -> Dict[str, str]:
        start_time = time.time()
        try:
            logger.info(f"Generating config files for MAC: {mac_address}")
            
            # Fetch endpoint data
            try:
                endpoint_data = await self._get_endpoint_data(endpoint_id, base_url)
            except HTTPException as http_err:
                # Log and re-raise HTTP exceptions
                logger.error(f"HTTP error while fetching endpoint data: {http_err.detail}")
                raise
            
            # Generate configuration content
            try:
                config_start = time.time()
                config_content = self._generate_config_content(endpoint_data)
                boot_content = self._generate_boot_content(mac_address, base_url)
                y000_content = self._generate_y000_content(mac_address, base_url)
                config_time = time.time() - config_start
                logger.info(f"Generated configuration content in {config_time:.2f} seconds")
            except Exception as e:
                logger.error(f"Failed to generate configuration content: {str(e)}")
                logger.error(traceback.format_exc())
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to generate configuration content: {str(e)}"
                )
            
            # Upload files to Azure Blob Storage
            files = {
                f"{mac_address}.cfg": config_content,
                f"{mac_address}.boot": boot_content,
                "y000000000000.cfg": y000_content
            }
            
            uploaded_urls = {}
            for filename, content in files.items():
                try:
                    upload_start = time.time()
                    logger.info(f"Uploading file: {filename}")
                    blob_client = self.container_client.get_blob_client(filename)
                    blob_client.upload_blob(content, overwrite=True)
                    uploaded_urls[filename] = blob_client.url
                    upload_time = time.time() - upload_start
                    logger.info(f"Successfully uploaded {filename} in {upload_time:.2f} seconds")
                except Exception as upload_error:
                    logger.error(f"Failed to upload {filename}: {str(upload_error)}")
                    logger.error(traceback.format_exc())
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to upload {filename}: {str(upload_error)}"
                    )
                
            total_time = time.time() - start_time
            logger.info(f"Successfully generated and uploaded all configuration files in {total_time:.2f} seconds")
            return uploaded_urls
            
        except HTTPException:
            # Re-raise HTTP exceptions without wrapping
            raise
        except Exception as e:
            logger.error(f"Unexpected error in generate_config_files: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate configuration files: {str(e)}"
            )

    def _generate_config_content(self, endpoint_data: Dict[str, Any]) -> str:
        try:
            logger.info("Generating config content")
            # Generate Yealink configuration content based on endpoint data
            config = f"""#!version:1.0.0.1
account.1.enable = 1
account.1.label = {endpoint_data.get('endpoint_id', '')}
account.1.display_name = {endpoint_data.get('endpoint_id', '')}
account.1.auth_name = {endpoint_data.get('auth_name', '')}
account.1.user_name = {endpoint_data.get('username', '')}
account.1.password = {endpoint_data.get('password', '')}
account.1.transport = 0
account.1.expires = 3600
"""
            logger.info("Successfully generated config content")
            return config
        except Exception as e:
            logger.error(f"Failed to generate config content: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate config content: {str(e)}"
            )

    def _generate_boot_content(self, mac_address: str, base_url: str) -> str:
        try:
            logger.info("Generating boot content")
            content = f"""#!version:1.0.0.1
include:config "{base_url}/provisioning/{mac_address}.cfg"
"""
            logger.info("Successfully generated boot content")
            return content
        except Exception as e:
            logger.error(f"Failed to generate boot content: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate boot content: {str(e)}"
            )

    def _generate_y000_content(self, mac_address: str, base_url: str) -> str:
        try:
            logger.info("Generating y000 content")
            content = f"""#!version:1.0.0.1
include:config "{base_url}/provisioning/{mac_address}.cfg"
"""
            logger.info("Successfully generated y000 content")
            return content
        except Exception as e:
            logger.error(f"Failed to generate y000 content: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate y000 content: {str(e)}"
            ) 