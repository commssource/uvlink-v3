import os
import json
import logging
import re
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import HTTPException


from .schemas import (
    AdvancedEndpoint, EndpointUpdate
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
    def _build_organized_endpoint(endpoint: Dict[str, Any], parser: AdvancedPJSIPConfigParser) -> Dict[str, Any]:
        """Helper method to build organized endpoint data"""
        # Get auth and aor section data by checking section type
        auth_data = {}
        aor_data = {}
        for section_name, section_data in parser.sections.items():
            # section_name is a tuple (name, type)
            if section_data.get('type') == 'auth' and section_name[0] == endpoint['id']:
                auth_data = section_data
            elif section_data.get('type') == 'aor' and section_name[0] == endpoint['id']:
                aor_data = section_data
        
        # Get the auth section directly from the parser
        auth_section = parser.sections.get((f"{endpoint['id']}-auth", 'auth'))
        if auth_section:
            auth_data = auth_section
        
        def safe_int(value, default=0):
            """Safely convert a value to integer"""
            if value is None:
                return default
            try:
                # Try to convert to int, if it fails return default
                return int(str(value).split()[0])  # Take first word if multiple words
            except (ValueError, TypeError):
                return default
        
        return {
            'id': endpoint['id'],
            'type': endpoint['type'],
            'accountcode': endpoint.get('accountcode'),
            'set_var': endpoint.get('set_var', ''),
            
            'audio_media': {
                'max_audio_streams': safe_int(endpoint.get('max_audio_streams'), 2),
                'allow': endpoint.get('allow', 'ulaw,alaw'),
                'disallow': endpoint.get('disallow', 'all'),
                'moh_suggest': endpoint.get('moh_suggest', 'default'),
                'tone_zone': endpoint.get('tone_zone', 'us'),
                'dtmf_mode': endpoint.get('dtmf_mode', 'rfc4733'),
                'allow_transfer': endpoint.get('allow_transfer', 'yes')
            },
            
            'transport_network': {
                'transport': endpoint.get('transport', 'transport-udp'),
                'identify_by': endpoint.get('identify_by', 'username'),
                'deny': endpoint.get('deny', ''),
                'permit': endpoint.get('permit', ''),
                'force_rport': endpoint.get('force_rport', 'yes'),
                'rewrite_contact': endpoint.get('rewrite_contact', 'yes'),
                'from_user': endpoint.get('from_user'),
                'from_domain': endpoint.get('from_domain', ''),
                'direct_media': endpoint.get('direct_media', 'no'),
                'ice_support': endpoint.get('ice_support', 'no'),
                'webrtc': endpoint.get('webrtc', 'no')
            },
            
            'rtp': {
                'rtp_symmetric': endpoint.get('rtp_symmetric', 'yes'),
                'rtp_timeout': safe_int(endpoint.get('rtp_timeout'), 30),
                'rtp_timeout_hold': safe_int(endpoint.get('rtp_timeout_hold'), 60),
                'sdp_session': endpoint.get('sdp_session', 'Asterisk')
            },
            
            'recording': {
                'record_calls': endpoint.get('record_calls', 'yes'),
                'one_touch_recording': endpoint.get('one_touch_recording', 'yes'),
                'record_on_feature': endpoint.get('record_on_feature', '*1'),
                'record_off_feature': endpoint.get('record_off_feature', '*2')
            },
            
            'call': {
                'context': endpoint.get('context', 'internal'),
                'callerid': endpoint.get('callerid', ''),
                'callerid_privacy': endpoint.get('callerid_privacy', ''),
                'connected_line_method': endpoint.get('connected_line_method', 'invite'),
                'call_group': endpoint.get('call_group', '1'),
                'pickup_group': endpoint.get('pickup_group', '1'),
                'device_state_busy_at': safe_int(endpoint.get('device_state_busy_at'), 2)
            },
            
            'presence': {
                'allow_subscribe': endpoint.get('allow_subscribe', 'yes'),
                'send_pai': endpoint.get('send_pai', 'yes'),
                'send_rpid': endpoint.get('send_rpid', 'yes'),
                '100rel': endpoint.get('100rel', 'no')
            },
            
            'voicemail': {
                'mailboxes': endpoint.get('mailboxes', ''),
                'voicemail_extension': endpoint.get('voicemail_extension', '')
            },
            
            'auth': {
                'type': 'auth',
                'auth_type': auth_data.get('auth_type', 'userpass'),
                'username': auth_data.get('username', endpoint['id']),
                'password': auth_data.get('password', 'Cs3244EG*01'),
                'realm': auth_data.get('realm', 'UVLink')
            },
            
            'aor': {
                'type': 'aor',
                'max_contacts': safe_int(aor_data.get('max_contacts'), 1),
                'qualify_timeout': safe_int(aor_data.get('qualify_timeout'), 8),
                'qualify_frequency': safe_int(aor_data.get('qualify_frequency'), 60),
                'authenticate_qualify': aor_data.get('authenticate_qualify', 'no'),
                'default_expiration': safe_int(aor_data.get('default_expiration'), 360),
                'minimum_expiration': safe_int(aor_data.get('minimum_expiration'), 120),
                'maximum_expiration': safe_int(aor_data.get('maximum_expiration'), 300)
            }
        }
    
    @staticmethod
    def list_endpoints() -> List[Dict[str, Any]]:
        """List all endpoints from current configuration with organized sections"""
        parser = AdvancedEndpointService.get_parser()
        endpoints = parser.list_endpoints()
        
        # Organize endpoints into sections
        organized_endpoints = []
        for endpoint in endpoints:
            organized_endpoints.append(AdvancedEndpointService._build_organized_endpoint(endpoint, parser))
        
        return organized_endpoints
    
    @staticmethod
    def get_endpoint(endpoint_id: str) -> Optional[Dict[str, Any]]:
        """Get specific endpoint details"""
        parser = AdvancedEndpointService.get_parser()
        endpoints = parser.list_endpoints()
        
        for endpoint in endpoints:
            if endpoint['id'] == endpoint_id:
                return AdvancedEndpointService._build_organized_endpoint(endpoint, parser)
        
        return None
    
    @staticmethod
    def add_endpoint_from_json(endpoint_data: Dict[str, Any]) -> bool:
        """Add endpoint from JSON data"""
        try:
            parser = AdvancedEndpointService.get_parser()
            endpoint_id = endpoint_data['id']
            logger.info(f"Processing endpoint {endpoint_id} with data: {endpoint_data}")
            
            flat_data = {
                'id': endpoint_id,
                'type': 'endpoint',
                'context': endpoint_data.get('context', 'internal'),
                'allow': endpoint_data.get('allow', 'ulaw,alaw'),
                'callerid': endpoint_data.get('callerid', ''),
                'set_var': endpoint_data.get('set_var', ''),
            }
            
            # Handle transport_network fields
            if 'transport_network' in endpoint_data:
                transport_data = endpoint_data['transport_network']
                for key, value in transport_data.items():
                    if value is not None:
                        flat_data[key] = value
                logger.info(f"Added transport_network data: {transport_data}")
            
            # Handle audio_media fields
            if 'audio_media' in endpoint_data:
                audio_data = endpoint_data['audio_media']
                for key, value in audio_data.items():
                    if value is not None:
                        flat_data[key] = value
                logger.info(f"Added audio_media data: {audio_data}")
            
            # Add custom data if present
            if 'custom_data' in endpoint_data and endpoint_data['custom_data']:
                flat_data['custom_data'] = {
                    k: v for k, v in endpoint_data['custom_data'].items() 
                    if v is not None
                }
                logger.info(f"Added custom data: {flat_data['custom_data']}")
            
            # Add auth section
            if 'auth' in endpoint_data:
                auth_data = endpoint_data['auth'].copy()
                # Ensure required auth fields are present
                if 'username' not in auth_data:
                    auth_data['username'] = endpoint_id
                if 'password' not in auth_data:
                    raise ValueError("Password is required in auth section")
                if 'realm' not in auth_data:
                    auth_data['realm'] = 'UVLink'
                flat_data['auth'] = auth_data
                logger.info(f"Added auth data: {auth_data}")
            
            # Add AOR section
            if 'aor' in endpoint_data:
                aor_data = endpoint_data['aor'].copy()
                # Ensure required AOR fields are present
                if 'max_contacts' not in aor_data:
                    aor_data['max_contacts'] = 1
                flat_data['aor'] = aor_data
                logger.info(f"Added AOR data: {aor_data}")
            
            # Add any additional fields
            for key, value in endpoint_data.items():
                if key not in ['id', 'type', 'auth', 'aor', 'custom_data', 'transport_network', 'audio_media'] and value is not None:
                    flat_data[key] = value
            
            logger.info(f"Final flat data: {flat_data}")
            
            # Add endpoint using efficient method
            return parser.add_endpoint_efficient(flat_data)
            
        except Exception as e:
            logger.error(f"Failed to add endpoint from JSON: {e}")
            return False
    
    @staticmethod
    def update_endpoint(endpoint_id: str, endpoint_data: EndpointUpdate) -> tuple[bool, str]:
        """Update an existing endpoint"""
        try:
            parser = AdvancedEndpointService.get_parser()
            # Convert the update data to a dictionary
            update_dict = endpoint_data.model_dump(exclude_unset=True)
            
            # Always set old_id to the current endpoint_id from the URL
            update_dict['old_id'] = endpoint_id
            
            # If no new ID is provided in the update data, use the URL endpoint_id
            if 'id' not in update_dict:
                update_dict['id'] = endpoint_id
            else:
                logger.info(f"Changing endpoint ID from {endpoint_id} to {update_dict['id']}")
                
            logger.info(f"Updating endpoint with data: {update_dict}")
            
            # Check if the endpoint exists before trying to update
            if not parser.sections.get((endpoint_id, 'endpoint-tpl')):
                return False, f"Endpoint {endpoint_id} does not exist"
                
            return parser.update_endpoint(update_dict), "Endpoint updated successfully"
        except Exception as e:
            logger.error(f"Failed to update endpoint: {e}")
            return False, str(e)
    
    @staticmethod
    def delete_endpoint(endpoint_id: str) -> bool:
        """Delete an endpoint"""
        try:
            parser = AdvancedEndpointService.get_parser()
            return parser.delete_endpoint(endpoint_id)
        except Exception as e:
            logger.error(f"Failed to delete endpoint: {e}")
            return False
    
    @staticmethod
    def get_current_config() -> str:
        """Get current PJSIP configuration"""
        try:
            with open(ASTERISK_PJSIP_CONFIG, 'r') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read config file: {e}")
            return ""
    
    @staticmethod
    def reload_pjsip() -> tuple[bool, str]:
        """Reload PJSIP configuration in Asterisk"""
        return execute_asterisk_command("pjsip reload")
    
    @staticmethod
    def validate_endpoint_data(endpoint_json: Dict[str, Any]) -> Dict[str, Any]:
        """Validate endpoint data before adding"""
        try:
            # Validate required fields
            if 'id' not in endpoint_json:
                return {
                    'valid': False,
                    'errors': ['Missing required field: id']
                }
            
            # Validate auth section
            if 'auth' not in endpoint_json:
                return {
                    'valid': False,
                    'errors': ['Missing required section: auth']
                }
            
            auth = endpoint_json['auth']
            if 'password' not in auth:
                return {
                    'valid': False,
                    'errors': ['Missing required field: auth.password']
                }
            
            # Validate AOR section
            if 'aor' not in endpoint_json:
                return {
                    'valid': False,
                    'errors': ['Missing required section: aor']
                }
            
            # Check for duplicate endpoint ID
            parser = AdvancedEndpointService.get_parser()
            if endpoint_json['id'] in parser.sections:
                return {
                    'valid': False,
                    'errors': [f"Endpoint ID '{endpoint_json['id']}' already exists"]
                }
            
            return {
                'valid': True,
                'warnings': []
            }
            
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return {
                'valid': False,
                'errors': [str(e)]
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

    @staticmethod
    def add_endpoint(endpoint_data: Dict[str, Any]) -> bool:
        """Add an endpoint with proper data handling"""
        try:
            endpoint_id = endpoint_data['id']
            logger.info(f"Adding endpoint {endpoint_id} with data: {endpoint_data}")
            
            # Create the complete endpoint data structure
            complete_data = {
                'id': endpoint_id,
                'type': 'endpoint',
                'context': endpoint_data.get('context', 'internal'),
                'allow': endpoint_data.get('allow', 'ulaw,alaw'),
                'callerid': endpoint_data.get('callerid', ''),
                'set_var': endpoint_data.get('set_var', ''),
            }
            
            # Handle custom data
            custom_data = {}
            if 'name' in endpoint_data:
                custom_data['name'] = endpoint_data['name']
            elif 'custom_data' in endpoint_data and 'name' in endpoint_data['custom_data']:
                custom_data['name'] = endpoint_data['custom_data']['name']
            else:
                custom_data['name'] = f'Extension {endpoint_id}'
            
            # Add any other custom data
            if 'custom_data' in endpoint_data:
                for k, v in endpoint_data['custom_data'].items():
                    if k != 'name' and v is not None:
                        custom_data[k] = v
            
            # Only add custom_data if it has values
            if custom_data:
                complete_data['custom_data'] = custom_data
            
            # Handle auth section - ensure required fields
            auth_data = {
                'type': 'auth',
                'auth_type': 'userpass',
                'username': endpoint_id,  # Default to endpoint ID
                'password': '',  # Default empty password
                'realm': 'UVLink'  # Default realm
            }
            
            # Update with provided auth data
            if 'auth' in endpoint_data:
                if 'username' in endpoint_data['auth'] and endpoint_data['auth']['username'] is not None:
                    auth_data['username'] = endpoint_data['auth']['username']
                if 'password' in endpoint_data['auth'] and endpoint_data['auth']['password'] is not None:
                    auth_data['password'] = endpoint_data['auth']['password']
                if 'realm' in endpoint_data['auth'] and endpoint_data['auth']['realm'] is not None:
                    auth_data['realm'] = endpoint_data['auth']['realm']
            
            complete_data['auth'] = auth_data
            
            # Handle AOR section
            aor_data = {
                'type': 'aor',
                'max_contacts': 1  # Default value
            }
            
            # Update with provided AOR data
            if 'aor' in endpoint_data:
                if 'max_contacts' in endpoint_data['aor'] and endpoint_data['aor']['max_contacts'] is not None:
                    aor_data['max_contacts'] = endpoint_data['aor']['max_contacts']
            
            complete_data['aor'] = aor_data
            
            logger.info(f"Complete endpoint data: {complete_data}")
            
            # Use the efficient method to add the endpoint
            parser = AdvancedPJSIPConfigParser(ASTERISK_PJSIP_CONFIG)
            return parser.add_endpoint_efficient(complete_data)
            
        except Exception as e:
            logger.error(f"Failed to add endpoint: {e}")
            return False