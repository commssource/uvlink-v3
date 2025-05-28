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
                'connected_line_method': endpoint_json.get('connected_line_method', 'invite'),
                'transport': endpoint_json.get('transport', 'transport-udp'),
                'identify_by': endpoint_json.get('identify_by', 'username'),
                'deny': endpoint_json.get('deny', ''),
                'permit': endpoint_json.get('permit', ''),
                'allow': endpoint_json.get('allow', 'ulaw,alaw'),
                'disallow': endpoint_json.get('disallow', 'all'),
                'force_rport': endpoint_json.get('force_rport', 'yes'),
                'webrtc': endpoint_json.get('webrtc', 'no'),
                'moh_suggest': endpoint_json.get('moh_suggest', 'default'),
                'call_group': endpoint_json.get('call_group', '1'),
                'rtp_symmetric': endpoint_json.get('rtp_symmetric', 'yes'),
                'rtp_timeout': endpoint_json.get('rtp_timeout', '30'),
                'rtp_timeout_hold': endpoint_json.get('rtp_timeout_hold', '60'),
                'rewrite_contact': endpoint_json.get('rewrite_contact', 'yes'),
                'from_user': endpoint_json.get('from_user', endpoint_json['id']),
                'from_domain': endpoint_json.get('from_domain', ''),
                'mailboxes': endpoint_json.get('mailboxes', ''),
                'voicemail_extension': endpoint_json.get('voicemail_extension', ''),
                'pickup_group': endpoint_json.get('pickup_group', '1'),
                'one_touch_recording': endpoint_json.get('one_touch_recording', 'yes'),
                'record_on_feature': endpoint_json.get('record_on_feature', '*1'),
                'record_off_feature': endpoint_json.get('record_off_feature', '*2'),
                'record_calls': endpoint_json.get('record_calls', 'yes'),
                'allow_subscribe': endpoint_json.get('allow_subscribe', 'yes'),
                'dtmf_mode': endpoint_json.get('dtmf_mode', 'rfc4733'),
                '100rel': endpoint_json.get('100rel', 'no'),
                'direct_media': endpoint_json.get('direct_media', 'no'),
                'ice_support': endpoint_json.get('ice_support', 'no'),
                'sdp_session': endpoint_json.get('sdp_session', 'Asterisk'),
                'set_var': endpoint_json.get('set_var', ''),
                'tone_zone': endpoint_json.get('tone_zone', 'us'),
                'send_pai': endpoint_json.get('send_pai', 'yes'),
                'send_rpid': endpoint_json.get('send_rpid', 'yes'),
                'mac_address': endpoint_json.get('mac_address'),
                'auto_provisioning_enabled': endpoint_json.get('auto_provisioning_enabled', True),
                'auth': endpoint_json.get('auth', {}),
                'aor': endpoint_json.get('aor', {})
            }
            
            # Add endpoint
            if parser.add_advanced_endpoint(endpoint_data):
                return parser.save(backup_suffix="add_advanced_endpoint")
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to add endpoint from JSON: {e}")
            return False
    
    @staticmethod
    def add_simple_endpoint(endpoint_data: SimpleEndpoint) -> bool:
        """Add a simple endpoint"""
        parser = AdvancedEndpointService.get_parser()
        
        # Convert simple endpoint to advanced format
        advanced_data = {
            'id': endpoint_data.id,
            'name': endpoint_data.name or f"Extension {endpoint_data.id}",
            'context': endpoint_data.context,
            'allow': ','.join(endpoint_data.codecs),
            'callerid': endpoint_data.callerid or "",
            'auth': {
                'username': endpoint_data.username,
                'password': endpoint_data.password,
                'realm': 'UVLink'
            },
            'aor': {
                'max_contacts': endpoint_data.max_contacts
            }
        }
        
        if parser.add_advanced_endpoint(advanced_data):
            return parser.save(backup_suffix="add_simple_endpoint")
        
        return False
    
    @staticmethod
    def add_bulk_endpoints(bulk_data: BulkEndpointCreate) -> Dict[str, Any]:
        """Add multiple endpoints at once"""
        parser = AdvancedEndpointService.get_parser()
        
        results = {
            'success': [],
            'failed': [],
            'skipped': []
        }
        
        for endpoint in bulk_data.endpoints:
            endpoint_id = endpoint.id
            
            # Check if exists and handle accordingly
            if endpoint_id in parser.sections:
                if bulk_data.overwrite_existing:
                    # Delete existing first
                    parser.delete_endpoint(endpoint_id)
                else:
                    results['skipped'].append({
                        'id': endpoint_id,
                        'reason': 'Already exists'
                    })
                    continue
            
            # Convert to advanced format
            if isinstance(endpoint, SimpleEndpoint):
                advanced_data = {
                    'id': endpoint.id,
                    'name': endpoint.name or f"Extension {endpoint.id}",
                    'context': endpoint.context,
                    'allow': ','.join(endpoint.codecs),
                    'callerid': endpoint.callerid or "",
                    'auth': {
                        'username': endpoint.username,
                        'password': endpoint.password,
                        'realm': 'UVLink'
                    },
                    'aor': {
                        'max_contacts': endpoint.max_contacts
                    }
                }
            else:  # AdvancedEndpoint
                advanced_data = endpoint.model_dump()
            
            # Try to add
            if parser.add_advanced_endpoint(advanced_data):
                results['success'].append(endpoint_id)
            else:
                results['failed'].append({
                    'id': endpoint_id,
                    'reason': 'Failed to add'
                })
        
        # Save if any were successful
        if results['success']:
            parser.save(backup_suffix="bulk_add_endpoints")
        
        return results
    
    @staticmethod
    def update_endpoint(endpoint_id: str, endpoint_data: EndpointUpdate) -> bool:
        """Update an existing endpoint"""
        parser = AdvancedEndpointService.get_parser()
        
        # Build update data
        update_data = {'id': endpoint_id}
        
        # Add provided fields
        if endpoint_data.name is not None:
            update_data['name'] = endpoint_data.name
        if endpoint_data.context is not None:
            update_data['context'] = endpoint_data.context
        if endpoint_data.callerid is not None:
            update_data['callerid'] = endpoint_data.callerid
        if endpoint_data.allow is not None:
            update_data['allow'] = endpoint_data.allow
        if endpoint_data.transport is not None:
            update_data['transport'] = endpoint_data.transport
        if endpoint_data.webrtc is not None:
            update_data['webrtc'] = endpoint_data.webrtc
        
        # Handle auth updates
        if endpoint_data.username or endpoint_data.password or endpoint_data.realm:
            auth_data = {}
            if endpoint_data.username:
                auth_data['username'] = endpoint_data.username
            if endpoint_data.password:
                auth_data['password'] = endpoint_data.password
            if endpoint_data.realm:
                auth_data['realm'] = endpoint_data.realm
            update_data['auth'] = auth_data
        
        # Handle AOR updates
        if endpoint_data.max_contacts or endpoint_data.qualify_frequency:
            aor_data = {}
            if endpoint_data.max_contacts:
                aor_data['max_contacts'] = endpoint_data.max_contacts
            if endpoint_data.qualify_frequency:
                aor_data['qualify_frequency'] = endpoint_data.qualify_frequency
            update_data['aor'] = aor_data
        
        if parser.update_endpoint(update_data):
            return parser.save(backup_suffix="update_endpoint")
        
        return False
    
    @staticmethod
    def delete_endpoint(endpoint_id: str) -> bool:
        """Delete an endpoint safely"""
        parser = AdvancedEndpointService.get_parser()
        
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
    
    @staticmethod
    def validate_endpoint_data(endpoint_json: Dict[str, Any]) -> Dict[str, Any]:
        """Validate endpoint data before adding"""
        errors = []
        warnings = []
        
        # Required fields
        required_fields = ['id']
        for field in required_fields:
            if field not in endpoint_json or not endpoint_json[field]:
                errors.append(f"Missing required field: {field}")
        
        # Validate auth section
        if 'auth' in endpoint_json:
            auth = endpoint_json['auth']
            if not auth.get('username'):
                errors.append("Auth username is required")
            if not auth.get('password'):
                errors.append("Auth password is required")
        else:
            errors.append("Auth configuration is required")
        
        # Validate codecs
        if 'allow' in endpoint_json:
            allowed_codecs = ['ulaw', 'alaw', 'g722', 'g729', 'gsm', 'opus', 'h264', 'vp8', 'vp9']
            codecs = [c.strip() for c in endpoint_json['allow'].split(',')]
            for codec in codecs:
                if codec not in allowed_codecs and codec != 'all':
                    warnings.append(f"Unknown codec: {codec}")
        
        # Check if endpoint exists
        existing = AdvancedEndpointService.get_endpoint(endpoint_json['id'])
        if existing:
            warnings.append(f"Endpoint {endpoint_json['id']} already exists")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    @staticmethod
    def export_endpoints_to_json() -> List[Dict[str, Any]]:
        """Export all endpoints to JSON format"""
        return AdvancedEndpointService.list_endpoints()
    
    @staticmethod
    def import_endpoints_from_json(endpoints_json: List[Dict[str, Any]], overwrite: bool = False) -> Dict[str, Any]:
        """Import endpoints from JSON format"""
        parser = AdvancedEndpointService.get_parser()
        
        results = {
            'success': [],
            'failed': [],
            'skipped': []
        }
        
        for endpoint_json in endpoints_json:
            endpoint_id = endpoint_json.get('id')
            if not endpoint_id:
                results['failed'].append({
                    'data': endpoint_json,
                    'reason': 'No ID provided'
                })
                continue
            
            # Validate first
            validation = AdvancedEndpointService.validate_endpoint_data(endpoint_json)
            if not validation['valid']:
                results['failed'].append({
                    'id': endpoint_id,
                    'reason': ', '.join(validation['errors'])
                })
                continue
            
            # Check if exists
            if endpoint_id in parser.sections:
                if overwrite:
                    parser.delete_endpoint(endpoint_id)
                else:
                    results['skipped'].append({
                        'id': endpoint_id,
                        'reason': 'Already exists'
                    })
                    continue
            
            # Try to add
            if AdvancedEndpointService.add_endpoint_from_json(endpoint_json):
                results['success'].append(endpoint_id)
            else:
                results['failed'].append({
                    'id': endpoint_id,
                    'reason': 'Failed to add'
                })
        
        return results