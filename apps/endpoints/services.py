import os
import json
import logging
import re
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import HTTPException

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
    def _build_organized_endpoint(endpoint: Dict[str, Any], parser: AdvancedPJSIPConfigParser) -> Dict[str, Any]:
        """Helper method to build organized endpoint data"""
        # Get auth section data by checking section type
        auth_data = {}
        for section_name, section_data in parser.sections.items():
            if section_data.get('type') == 'auth':
                auth_data = section_data
                break
        
        return {
            'id': endpoint['id'],
            'type': endpoint['type'],
            'accountcode': endpoint.get('accountcode'),
            
            'audio_media': {
                'max_audio_streams': int(endpoint.get('max_audio_streams', 2)),
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
                'rtp_timeout': int(endpoint.get('rtp_timeout', 30)),
                'rtp_timeout_hold': int(endpoint.get('rtp_timeout_hold', 60)),
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
                'device_state_busy_at': int(endpoint.get('device_state_busy_at', 2))
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
                'auth_type': 'userpass',
                'username': auth_data.get('username', endpoint['id']),
                'password': auth_data.get('password', ''),
                'realm': auth_data.get('realm', 'UVLink')
            },
            
            'aor': endpoint.get('aor', {})
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
            }
            
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
                if key not in ['id', 'type', 'auth', 'aor', 'custom_data'] and value is not None:
                    flat_data[key] = value
            
            logger.info(f"Final flat data: {flat_data}")
            
            # Add endpoint using efficient method
            return parser.add_endpoint_efficient(flat_data)
            
        except Exception as e:
            logger.error(f"Failed to add endpoint from JSON: {e}")
            return False
    
    @staticmethod
    def add_simple_endpoint(endpoint_data: SimpleEndpoint) -> bool:
        """Add a simple endpoint"""
        try:
            # Convert simple endpoint to advanced format
            advanced_data = {
                "id": endpoint_data.id,
                "type": "endpoint",
                "context": "internal",
                "allow": "ulaw,alaw",
                "callerid": "",
                "auth": {
                    "type": "auth",
                    "auth_type": "userpass",
                    "username": endpoint_data.id,
                    "password": endpoint_data.password,  # Use the password from the request
                    "realm": "UVLink"
                },
                "aor": {
                    "type": "aor",
                    "max_contacts": 1
                },
                "custom_data": {
                    "name": f"Extension {endpoint_data.id}"
                }
            }
            
            logger.info(f"Converting simple endpoint to advanced format: {advanced_data}")
            
            # Add endpoint using parser
            parser = AdvancedPJSIPConfigParser("/etc/asterisk/pjsip.conf")
            success = parser.add_endpoint_efficient(advanced_data)
            
            if not success:
                raise HTTPException(status_code=400, detail="Failed to add endpoint")
            
            return {"message": "Endpoint added successfully", "endpoint": advanced_data}
            
        except Exception as e:
            logger.error(f"Error adding simple endpoint: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
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
                        'id': endpoint.id,  # Use same ID as endpoint
                        'username': endpoint.username,
                        'password': endpoint.password,
                        'realm': 'UVLink'
                    },
                    'aor': {
                        'id': endpoint.id,  # Use same ID as endpoint
                        'max_contacts': endpoint.max_contacts
                    }
                }
            else:  # AdvancedEndpoint
                advanced_data = endpoint.model_dump()
                # Ensure auth and aor use same ID
                if 'auth' in advanced_data:
                    advanced_data['auth']['id'] = endpoint_id
                if 'aor' in advanced_data:
                    advanced_data['aor']['id'] = endpoint_id
            
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
        """Update an existing endpoint - requires full parsing"""
        parser = AdvancedEndpointService.get_parser()  # This will parse the entire file
        
        # Build update data
        update_data = {'id': endpoint_id}
        
        # Add provided fields
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
        """Delete an endpoint safely - requires full parsing"""
        parser = AdvancedEndpointService.get_parser()  # This will parse the entire file
        
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
        
        # Validate ID format
        if 'id' in endpoint_json:
            if not re.match(r'^[a-zA-Z0-9_-]+$', endpoint_json['id']):
                errors.append("ID must contain only letters, numbers, underscores, and hyphens")
        
        # Validate sections
        sections = {
            'audio_media': {
                'max_audio_streams': (int, 1, 10),
                'allow': (str, None, None),
                'disallow': (str, None, None),
                'moh_suggest': (str, None, None),
                'tone_zone': (str, None, None),
                'dtmf_mode': (str, None, None),
                'allow_transfer': (str, ['yes', 'no'])
            },
            'transport_network': {
                'transport': (str, None, None),
                'identify_by': (str, None, None),
                'force_rport': (str, ['yes', 'no']),
                'rewrite_contact': (str, ['yes', 'no']),
                'direct_media': (str, ['yes', 'no']),
                'ice_support': (str, ['yes', 'no']),
                'webrtc': (str, ['yes', 'no'])
            },
            'rtp': {
                'rtp_symmetric': (str, ['yes', 'no']),
                'rtp_timeout': (int, 0, 300),
                'rtp_timeout_hold': (int, 0, 3600),
                'sdp_session': (str, None, None)
            },
            'recording': {
                'record_calls': (str, ['yes', 'no']),
                'one_touch_recording': (str, ['yes', 'no']),
                'record_on_feature': (str, None, None),
                'record_off_feature': (str, None, None)
            },
            'call': {
                'context': (str, None, None),
                'callerid': (str, None, None),
                'callerid_privacy': (str, None, None),
                'connected_line_method': (str, None, None),
                'call_group': (str, None, None),
                'pickup_group': (str, None, None),
                'device_state_busy_at': (int, 1, 10)
            },
            'presence': {
                'allow_subscribe': (str, ['yes', 'no']),
                'send_pai': (str, ['yes', 'no']),
                'send_rpid': (str, ['yes', 'no']),
                '100rel': (str, ['yes', 'no'])
            }
        }
        
        # Validate each section
        for section_name, section_fields in sections.items():
            if section_name in endpoint_json:
                section_data = endpoint_json[section_name]
                for field_name, (field_type, min_val, max_val) in section_fields.items():
                    if field_name in section_data:
                        value = section_data[field_name]
                        
                        # Type validation
                        if not isinstance(value, field_type):
                            errors.append(f"{section_name}.{field_name} must be of type {field_type.__name__}")
                            continue
                        
                        # Range validation for numbers
                        if field_type == int and min_val is not None and max_val is not None:
                            if not min_val <= value <= max_val:
                                errors.append(f"{section_name}.{field_name} must be between {min_val} and {max_val}")
                        
                        # Enum validation for strings
                        if field_type == str and isinstance(min_val, list):
                            if value not in min_val:
                                errors.append(f"{section_name}.{field_name} must be one of {min_val}")
        
        # Validate auth section
        if 'auth' in endpoint_json:
            auth = endpoint_json['auth']
            if not auth.get('username'):
                errors.append("Auth username is required")
            if not auth.get('password'):
                errors.append("Auth password is required")
            if auth.get('username') and len(auth['username']) > 50:
                errors.append("Auth username must be 50 characters or less")
            if auth.get('password') and len(auth['password']) > 128:
                errors.append("Auth password must be 128 characters or less")
        else:
            errors.append("Auth configuration is required")
        
        # Validate AOR section
        if 'aor' in endpoint_json:
            aor = endpoint_json['aor']
            if 'max_contacts' in aor:
                try:
                    max_contacts = int(aor['max_contacts'])
                    if not 1 <= max_contacts <= 10:
                        errors.append("AOR max_contacts must be between 1 and 10")
                except ValueError:
                    errors.append("AOR max_contacts must be a number")
            if 'qualify_frequency' in aor:
                try:
                    qualify_freq = int(aor['qualify_frequency'])
                    if not 0 <= qualify_freq <= 300:
                        errors.append("AOR qualify_frequency must be between 0 and 300")
                except ValueError:
                    errors.append("AOR qualify_frequency must be a number")
        else:
            errors.append("AOR configuration is required")
        
        # Validate codecs
        if 'audio_media' in endpoint_json and 'allow' in endpoint_json['audio_media']:
            allowed_codecs = ['ulaw', 'alaw', 'g722', 'g729', 'gsm', 'opus', 'h264', 'vp8', 'vp9']
            codecs = [c.strip() for c in endpoint_json['audio_media']['allow'].split(',')]
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