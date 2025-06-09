import asyncio
import logging
from typing import Optional, Dict, Any
import asterisk.manager
import sys
from pathlib import Path

# Add project root to Python path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

from config import AMI_HOST, AMI_PORT, AMI_USERNAME, AMI_SECRET

logger = logging.getLogger(__name__)

class AsteriskAMI:
    def __init__(self):
        self.host = AMI_HOST
        self.port = int(AMI_PORT)  # Convert to int since it's a string in config
        self.username = AMI_USERNAME
        self.secret = AMI_SECRET
        self.manager: Optional[asterisk.manager.Manager] = None

    async def connect(self) -> bool:
        """Connect to Asterisk AMI"""
        try:
            self.manager = asterisk.manager.Manager()
            await asyncio.to_thread(
                self.manager.connect,
                host=self.host,
                port=self.port
            )
            await asyncio.to_thread(
                self.manager.login,
                username=self.username,
                secret=self.secret
            )
            logger.info(f"Successfully connected to Asterisk AMI at {self.host}:{self.port}")
            return True
        except asterisk.manager.ManagerSocketException as e:
            logger.error(f"Failed to connect to Asterisk AMI: {str(e)}")
            return False
        except asterisk.manager.ManagerAuthException as e:
            logger.error(f"Authentication failed for Asterisk AMI: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to Asterisk AMI: {str(e)}")
            return False

    async def disconnect(self):
        """Disconnect from Asterisk AMI"""
        if self.manager:
            try:
                await asyncio.to_thread(self.manager.close)
                logger.info("Disconnected from Asterisk AMI")
            except Exception as e:
                logger.error(f"Error disconnecting from Asterisk AMI: {str(e)}")

    async def check_registration_status(self, mac_address: str) -> Dict[str, Any]:
        """
        Check registration status for a given MAC address
        Returns a dictionary with registration status information
        """
        if not self.manager:
            if not await self.connect():
                return {
                    "success": False,
                    "error": "Failed to connect to Asterisk AMI",
                    "status": "unknown"
                }

        try:
            # Convert MAC address to lowercase and remove colons for SIP username format
            sip_username = mac_address.lower().replace(':', '')
            
            # Initialize status info
            status_info = {
                "success": True,
                "mac_address": mac_address,
                "sip_username": sip_username,
                "raw_responses": {},
                "status": "unknown",
                "details": {}
            }

            # 1. Check SIP peer status
            try:
                sip_response = await asyncio.to_thread(
                    self.manager.command,
                    f"sip show peer {sip_username}"
                )
                status_info["raw_responses"]["sip_peer"] = sip_response.data
                
                # Parse SIP peer status
                if "Status: OK" in sip_response.data:
                    status_info["status"] = "registered"
                    # Extract additional details
                    for line in sip_response.data.split('\n'):
                        if "IP Address:" in line:
                            status_info["details"]["ip_address"] = line.split(":", 1)[1].strip()
                        elif "Port:" in line:
                            status_info["details"]["port"] = line.split(":", 1)[1].strip()
                        elif "User Agent:" in line:
                            status_info["details"]["user_agent"] = line.split(":", 1)[1].strip()
            except Exception as e:
                logger.warning(f"Error checking SIP peer: {str(e)}")

            # 2. Check PJSIP endpoints
            try:
                pjsip_response = await asyncio.to_thread(
                    self.manager.command,
                    f"pjsip show endpoints"
                )
                status_info["raw_responses"]["pjsip_endpoints"] = pjsip_response.data
                
                # Check if MAC address is in PJSIP endpoints
                if sip_username in pjsip_response.data:
                    status_info["details"]["pjsip_registered"] = True
            except Exception as e:
                logger.warning(f"Error checking PJSIP endpoints: {str(e)}")

            # 3. Check SIP registry
            try:
                registry_response = await asyncio.to_thread(
                    self.manager.command,
                    "sip show registry"
                )
                status_info["raw_responses"]["sip_registry"] = registry_response.data
            except Exception as e:
                logger.warning(f"Error checking SIP registry: {str(e)}")

            # 4. Check active channels
            try:
                channels_response = await asyncio.to_thread(
                    self.manager.command,
                    "core show channels"
                )
                status_info["raw_responses"]["active_channels"] = channels_response.data
                
                # Check if MAC address is in active channels
                if sip_username in channels_response.data:
                    status_info["details"]["has_active_channels"] = True
            except Exception as e:
                logger.warning(f"Error checking active channels: {str(e)}")

            # Print to console for now
            print(f"\n=== Registration Status for {mac_address} ===")
            print(f"SIP Username: {sip_username}")
            print(f"Status: {status_info['status']}")
            print("\nDetails:")
            for key, value in status_info["details"].items():
                print(f"  {key}: {value}")
            print("\nRaw Responses:")
            for key, value in status_info["raw_responses"].items():
                print(f"\n--- {key} ---")
                print(value)
            print("=" * 50)

            return status_info

        except Exception as e:
            logger.error(f"Error checking registration status: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "status": "error"
            }

# Example usage:
async def check_phone_registration(mac_address: str):
    """
    Example function to check phone registration status
    """
    ami = AsteriskAMI()

    try:
        status = await ami.check_registration_status(mac_address)
        return status
    finally:
        await ami.disconnect()

# For testing
if __name__ == "__main__":
    import asyncio
    
    async def test():
        mac = "24:9a:d8:18:cd:91"
        status = await check_phone_registration(mac)
        print(f"Final status: {status}")

    asyncio.run(test()) 