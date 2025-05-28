import os
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from .schemas import (
    AdvancedEndpoint, SimpleEndpoint, EndpointCreate, EndpointUpdate,
    BulkEndpointCreate
)
from .config_parser import AdvancedPJSIPConfigParser
from shared.utils import execute_asterisk_command
from config import ASTERISK_PJSIP_CONFIG

logger = logging.getLogger(__name__)

class AdvancedEndpointService:
    """Advanced service for managing PJSIP endpoints with full configuration support"""
    
    @staticmethod
    def get_parser() -> AdvancedPJSIPConfigParser:
        """Get a configured parser instance"""
        parser = AdvancedPJSIPConfigParser(ASTERISK_PJSIP_CONFIG)
        parser.parse()
        return parser
    
    @staticmethod
    def list_endpoints() -> List[Dict[str, Any]]:
        """List all endpoints from current configuration"""
        parser = AdvancedEndpointService.get_parser()
        return parser.list_endpoints()
    
    @staticmethod
    def get_endpoint(endpoint_id: str) -> Optional[Dict[str, Any]]:
        """Get specific endpoint details"""
        parser = AdvancedEndpointService.get_parser()
        endpoints = parser.list_endpoints()
        
        for endpoint in endpoints:
            if endpoint['id'] == endpoint_id:
                return endpoint
        
        return None
    
    @staticmethod
    def add_endpoint_from_json(endpoint_json: Dict[str, Any]) -> bool:
        """Add endpoint from your JSON format"""
        parser = AdvancedEndpointService.get_parser()
        
        try:
            # Convert your JSON format to our internal format
            endpoint_data = {
                'id': endpoint_json['id'],
                'type': endpoint_json.get('type', 'endpoint'),
                'entity_type': endpoint_json.get('entity_type', 'endpoint'),
                'name': endpoint_json.get('name', f"Extension {endpoint_json['id']}"),
                'accountcode': endpoint_json.get('accountcode'),
                'max_audio_streams': endpoint_json.get('max_audio_streams', '2'),
                'device_state_busy_at': endpoint_json.get('device_state_busy_at', '2'),
                'allow_transfer': endpoint_json.get('allow_transfer', 'yes'),
                'outbound_auth': endpoint_json.get('outbound_auth', ''),
                'context': endpoint_json.get('context', 'internal'),
                'callerid': endpoint_json.get('callerid', ''),
                'callerid_privacy': endpoint_json.get('callerid_privacy', ''),
                'connected_line_method': endpoint_