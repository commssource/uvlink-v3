import os
import json
import logging
from typing import List, Optional, Dict
from datetime import datetime

from .schemas import Endpoint, EndpointCreate, EndpointUpdate
from .config_parser import PJSIPConfigParser
from shared.utils import execute_asterisk_command
from config import ASTERISK_PJSIP_CONFIG

logger = logging.getLogger(__name__)

class SafeEndpointService:
    """Safe service for managing PJSIP endpoints without breaking existing config"""
    
    @staticmethod
    def get_parser() -> PJSIPConfigParser:
        """Get a configured parser instance"""
        parser = PJSIPConfigParser(ASTERISK_PJSIP_CONFIG)
        parser.parse()
        return parser
    
    @staticmethod
    def list_endpoints() -> List[Dict[str, any]]:
        """List all endpoints from current configuration"""
        parser = SafeEndpointService.get_parser()
        return parser.list_endpoints()
    
    @staticmethod
    def get_endpoint(endpoint_id: str) -> Optional[Dict[str, any]]:
        """Get specific endpoint details"""
        parser = SafeEndpointService.get_parser()
        endpoints = parser.list_endpoints()
        
        for endpoint in endpoints:
            if endpoint['id'] == endpoint_id:
                return endpoint
        
        return None
    
    @staticmethod
    def add_endpoint(endpoint_data: EndpointCreate) -> bool:
        """Add a new endpoint safely"""
        parser = SafeEndpointService.get_parser()
        
        # Convert Pydantic model to dict
        endpoint_dict = {
            'id': endpoint_data.id,
            'username': endpoint_data.username,
            'password': endpoint_data.password,
            'context': endpoint_data.context,
            'codecs': endpoint_data.codecs,
            'max_contacts': endpoint_data.max_contacts,
            'callerid': endpoint_data.callerid
        }
        
        # Add endpoint
        if parser.add_endpoint(endpoint_dict):
            return parser.save(backup_suffix="add_endpoint")
        
        return False
    
    @staticmethod
    def update_endpoint(endpoint_id: str, endpoint_data: EndpointUpdate) -> bool:
        """Update an existing endpoint safely"""
        parser = SafeEndpointService.get_parser()
        
        # Convert Pydantic model to dict (excluding None values)
        endpoint_dict = {
            'id': endpoint_id,
            'username': endpoint_data.username,
            'context': endpoint_data.context,
            'codecs': endpoint_data.codecs,
            'max_contacts': endpoint_data.max_contacts,
            'callerid': endpoint_data.callerid
        }
        
        # Add password if provided
        if endpoint_data.password:
            endpoint_dict['password'] = endpoint_data.password
        else:
            # Keep existing password
            existing = SafeEndpointService.get_endpoint(endpoint_id)
            if existing:
                # We need to get password from config
                parser_sections = parser.sections
                auth_section = f"{endpoint_id}_auth"
                if auth_section in parser_sections:
                    endpoint_dict['password'] = parser_sections[auth_section].get('password', '')
        
        # Update endpoint
        if parser.update_endpoint(endpoint_dict):
            return parser.save(backup_suffix="update_endpoint")
        
        return False
    
    @staticmethod
    def delete_endpoint(endpoint_id: str) -> bool:
        """Delete an endpoint safely"""
        parser = SafeEndpointService.get_parser()
        
        if parser.delete_endpoint(endpoint_id):
            return parser.save(backup_suffix="delete_endpoint")
        
        return False
    
    @staticmethod
    def get_current_config() -> str:
        """Get current PJSIP configuration"""
        try:
            if os.path.exists(ASTERISK_PJSIP_CONFIG):
                with open(ASTERISK_PJSIP_CONFIG, 'r') as f:
                    return f.read()
            else:
                return "; No configuration file found"
        except Exception as e:
            logger.error(f"Failed to read config: {e}")
            return f"; Error reading config: {e}"
    
    @staticmethod
    def reload_pjsip() -> tuple[bool, str]:
        """Reload PJSIP configuration in Asterisk"""
        return execute_asterisk_command("pjsip reload")