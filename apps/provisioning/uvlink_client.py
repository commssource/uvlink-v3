"""
UVLink API client for fetching endpoint configurations
"""

import httpx
import logging
from typing import Optional, Dict, Any
from config import BASE_URL, API_KEY

logger = logging.getLogger(__name__)

class UVLinkAPIClient:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or API_KEY
        self.base_url = base_url or BASE_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def get_endpoint_config(self, endpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch endpoint configuration from UVLink API
        
        Args:
            endpoint_id: The endpoint ID to fetch
            
        Returns:
            Dict containing endpoint configuration or None if failed
        """
        try:
            # Fixed URL construction - base_url already includes /api/v1
            url = f"{self.base_url}/api/v1/endpoints/{endpoint_id}"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers, timeout=30.0)
                
                if response.status_code == 200:
                    config = response.json()
                    logger.info(f"Successfully fetched config for endpoint {endpoint_id}")
                    return config
                elif response.status_code == 404:
                    logger.warning(f"Endpoint {endpoint_id} not found")
                    return None
                else:
                    logger.error(f"API request failed with status {response.status_code}: {response.text}")
                    return None
                    
        except httpx.TimeoutException:
            logger.error(f"Timeout while fetching endpoint {endpoint_id}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Request error while fetching endpoint {endpoint_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error while fetching endpoint {endpoint_id}: {e}")
            return None

def map_endpoint_to_config(endpoint_data: Dict[str, Any], sip_host: str, sip_port: int) -> str:
    """
    Map endpoint API response to correct Yealink T43U provisioning config file format
    
    Args:
        endpoint_data: Response from UVLink API
        sip_host: SIP server host
        sip_port: SIP server port
        
    Returns:
        Formatted config file content with correct Yealink T43U parameters
    """
    try:
        # Transport mapping for Yealink phones
        TRANSPORT_MAPPING = {
            "udp": 0,
            "tcp": 1,
            "tls": 2,
            "auto": 3
        }
        
        # Extract values from the nested JSON structure
        endpoint_id = endpoint_data.get("id", "")
        
        # Extract auth information
        auth_data = endpoint_data.get("auth", {})
        username = auth_data.get("username", "")
        password = auth_data.get("password", "")
        
        # Extract transport from transport_network and map to numeric value
        transport_network = endpoint_data.get("transport_network", {})
        transport_string = transport_network.get("transport", "udp").lower()
        transport_numeric = TRANSPORT_MAPPING.get(transport_string, 0)  # Default to UDP (0)
        
        # Force logging to print (using print instead of logger to ensure we see it)
        print(f"=== CONFIG MAPPING DEBUG ===")
        print(f"Endpoint ID: {endpoint_id}")
        print(f"Transport Network Data: {transport_network}")
        print(f"Extracted Transport String: {transport_string}")
        print(f"Mapped Transport Numeric: {transport_numeric}")
        print(f"Auth Data: {auth_data}")
        print(f"================================")
        
        # Generate config file with CORRECT Yealink T43U parameter format
        config_content = f"""#!version:1.0.0.1

##################################################################################
## Account 1 Configuration - Using Correct T43U Parameter Format
##################################################################################
account.1.enable = 1
account.1.label = {endpoint_id}
account.1.display_name = {endpoint_id}
account.1.auth_name = {username}
account.1.user_name = {username}
account.1.password = {password}
account.1.sip_server.1.address = {sip_host}
account.1.sip_server.1.port = {sip_port}
account.1.sip_server.1.transport_type = {transport_numeric}
account.1.sip_server.1.expires = 3600
account.1.sip_server.1.retry_counts = 3
account.1.sip_server.1.register_on_enable = 1

##################################################################################
## Time & Date Settings - UK London Configuration
##################################################################################
local_time.time_zone = 0
local_time.time_zone_name = United Kingdom(London)
local_time.ntp_server1 = pool.ntp.org
local_time.ntp_server2 = time.windows.com
local_time.interval = 1000
local_time.date_format = 3
local_time.time_format = 1

##################################################################################
## Security Settings
##################################################################################
security.user_password = admin:Cs411828
security.user_password = user:Cs411828
##################################################################################
## Audio Settings
##################################################################################
voice.handfree.ag_enable = 1
voice.echo_cancellation = 1
voice.vad = 1

##################################################################################
## Network Settings  
##################################################################################
network.vlan.internet_port_enable = 0
network.lldp.enable = 1

##################################################################################
## Phone Settings
##################################################################################
phone_setting.backgrounds = Config:bg.jpg
phone_setting.ring_type = Config:Ring1.wav

##################################################################################
## Features
##################################################################################
features.pickup_mode = 1
features.call_pickup.enable = 1
features.call_waiting.enable = 1
features.caller_id_source = 1

##################################################################################
## Static Settings (Override Protection)
##################################################################################
static.account.1.enable = 1
static.account.1.sip_server.1.address = {sip_host}
static.account.1.sip_server.1.port = {sip_port}
static.account.1.auth_name = {username}
static.account.1.user_name = {username}
static.account.1.password = {password}

##################################################################################
## Line Key Programming Configuration
##################################################################################
# Line Key 1 - Account 1
linekey.1.line = 1
linekey.1.type = 15
linekey.1.value = {username}
linekey.1.label = {endpoint_id}

# Line Key 2 - Speed Dial
linekey.2.line = 1
linekey.2.type = 13
linekey.2.value = 
linekey.2.label = Speed Dial

# Line Key 3 - BLF (Busy Lamp Field)
linekey.3.line = 1
linekey.3.type = 16
linekey.3.value = 
linekey.3.label = BLF

# Line Key 4 - Call Pickup
linekey.4.line = 1
linekey.4.type = 10
linekey.4.value = *8
linekey.4.label = Pickup

# Line Key 5 - Do Not Disturb
linekey.5.line = 1
linekey.5.type = 6
linekey.5.value = 
linekey.5.label = DND

# Line Key 6 - Call Forward
linekey.6.line = 1
linekey.6.type = 7
linekey.6.value = 
linekey.6.label = Forward

# Line Key 7 - Transfer
linekey.7.line = 1
linekey.7.type = 4
linekey.7.value = 
linekey.7.label = Transfer

# Line Key 8 - Hold
linekey.8.line = 1
linekey.8.type = 3
linekey.8.value = 
linekey.8.label = Hold

##################################################################################
## Programmable Keys Configuration (Memory Keys)
##################################################################################
# Memory Key 1
memorykey.1.line = 1
memorykey.1.type = 13
memorykey.1.value = 
memorykey.1.label = Memory 1

# Memory Key 2
memorykey.2.line = 1
memorykey.2.type = 13
memorykey.2.value = 
memorykey.2.label = Memory 2

# Memory Key 3
memorykey.3.line = 1
memorykey.3.type = 13
memorykey.3.value = 
memorykey.3.label = Memory 3

##################################################################################
## Remote URL Settings - Push XML Configuration
##################################################################################
push_xml.server = 
push_xml.username = 
push_xml.password = 
push_xml.sip_notify = 1
push_xml.block_in_calling = 0

##################################################################################
## Feature Settings - Action URI and CSTA Control
##################################################################################
features.action_uri_limit_ip = any
features.csta_control.enable = 0

##################################################################################
## Action URL Settings - Webhook Notifications
##################################################################################
action_url.setup_completed = https://resolved-chimp-jointly.ngrok-free.app/prov
action_url.registered = 
action_url.unregistered = 
action_url.register_failed = 

"""
        
        print(f"Generated config with correct T43U format")
        print(f"SIP Server: {sip_host}:{sip_port}")
        print(f"Transport: {transport_numeric} ({transport_string})")
        print(f"Username: {username}")
        print(f"Time Zone: UK London with auto DST")
        print(f"Admin Password: Cs411828")
        return config_content
        
    except Exception as e:
        print(f"ERROR in map_endpoint_to_config: {e}")
        print(f"Endpoint data received: {endpoint_data}")
        logger.error(f"Error mapping endpoint data to config: {e}")
        logger.error(f"Endpoint data received: {endpoint_data}")
        raise ValueError(f"Failed to map endpoint data: {e}")

# Factory function for dependency injection
def get_uvlink_client() -> UVLinkAPIClient:
    """Factory function to create UVLinkAPIClient instance"""
    return UVLinkAPIClient()