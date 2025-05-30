import re
import logging
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class AdvancedPJSIPConfigParser:
    """Advanced parser for PJSIP configuration that handles complex endpoint configurations"""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.sections = {}
        self.comments = {}
        self.order = []
        
    def parse(self) -> Dict[str, Dict[str, str]]:
        """Parse PJSIP configuration file while preserving structure"""
        if not Path(self.config_path).exists():
            logger.warning(f"Config file {self.config_path} does not exist")
            return {}
        
        with open(self.config_path, 'r') as f:
            content = f.read()
        
        current_section = None
        section_comments = []
        section_counter = {}  # Track number of sections with same name
        
        for line_num, line in enumerate(content.split('\n'), 1):
            line = line.rstrip()
            
            # Handle comments and empty lines
            if line.startswith(';') or line.startswith('#') or not line.strip():
                section_comments.append(line)
                continue
            
            # Handle section headers [section_name]
            section_match = re.match(r'^\[([^\]]+)\]', line)
            if section_match:
                current_section = section_match.group(1)
                
                # Handle duplicate section names
                if current_section in self.sections:
                    if current_section not in section_counter:
                        section_counter[current_section] = 1
                    section_counter[current_section] += 1
                    current_section = f"{current_section}_{section_counter[current_section]}"
                
                # Store section in order
                if current_section not in self.order:
                    self.order.append(current_section)
                
                # Initialize section
                if current_section not in self.sections:
                    self.sections[current_section] = {}
                
                # Store comments for this section
                if section_comments:
                    self.comments[current_section] = section_comments
                    section_comments = []
                
                continue
            
            # Handle key=value pairs
            if current_section and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                self.sections[current_section][key] = value
        
        # Store any remaining comments
        if section_comments:
            self.comments['_end'] = section_comments
        
        return self.sections
    
    def get_endpoint_sections(self, endpoint_id: str) -> List[str]:
        """Get all sections related to an endpoint"""
        related_sections = []
        
        # Main endpoint section
        if endpoint_id in self.sections:
            related_sections.append(endpoint_id)
        
        # Auth section
        auth_section = f"{endpoint_id}"
        if auth_section in self.sections:
            related_sections.append(auth_section)
        
        # AOR section
        aor_section = f"{endpoint_id}"
        if aor_section in self.sections:
            related_sections.append(aor_section)
            print(f"AOR-AUTH Section: {related_sections}")
        return related_sections
        
    
    def add_advanced_endpoint(self, endpoint_data: Dict[str, Any]) -> bool:
        """Add an advanced endpoint with all configuration options"""
        endpoint_id = endpoint_data['id']
        
        # Check if endpoint already exists
        if endpoint_id in self.sections:
            logger.warning(f"Endpoint {endpoint_id} already exists")
            return False
        
        # Add endpoint section with all advanced options
        endpoint_section = {
            'type': endpoint_data.get('type', 'endpoint'),
            'context': endpoint_data.get('context', 'internal'),
            'disallow': endpoint_data.get('disallow', 'all'),
            'allow': endpoint_data.get('allow', 'ulaw,alaw'),
            'auth': f"{endpoint_id}_auth",
            'aors': f"{endpoint_id}_aor"
        }
        
        # Add all the advanced PJSIP options
        advanced_options = {
            'accountcode': endpoint_data.get('accountcode'),
            'max_audio_streams': endpoint_data.get('max_audio_streams', '2'),
            'device_state_busy_at': endpoint_data.get('device_state_busy_at', '2'),
            'allow_transfer': endpoint_data.get('allow_transfer', 'yes'),
            'outbound_auth': endpoint_data.get('outbound_auth', ''),
            'callerid': endpoint_data.get('callerid', ''),
            'callerid_privacy': endpoint_data.get('callerid_privacy', ''),
            'connected_line_method': endpoint_data.get('connected_line_method', 'invite'),
            'transport': endpoint_data.get('transport', 'transport-udp'),
            'identify_by': endpoint_data.get('identify_by', 'username'),
            'deny': endpoint_data.get('deny', ''),
            'permit': endpoint_data.get('permit', ''),
            'force_rport': endpoint_data.get('force_rport', 'yes'),
            'webrtc': endpoint_data.get('webrtc', 'no'),
            'moh_suggest': endpoint_data.get('moh_suggest', 'default'),
            'call_group': endpoint_data.get('call_group', '1'),
            'rtp_symmetric': endpoint_data.get('rtp_symmetric', 'yes'),
            'rtp_timeout': endpoint_data.get('rtp_timeout', '30'),
            'rtp_timeout_hold': endpoint_data.get('rtp_timeout_hold', '60'),
            'rewrite_contact': endpoint_data.get('rewrite_contact', 'yes'),
            'from_user': endpoint_data.get('from_user', endpoint_id),
            'from_domain': endpoint_data.get('from_domain', ''),
            'mailboxes': endpoint_data.get('mailboxes', ''),
            'voicemail_extension': endpoint_data.get('voicemail_extension', ''),
            'pickup_group': endpoint_data.get('pickup_group', '1'),
            'one_touch_recording': endpoint_data.get('one_touch_recording', 'yes'),
            'record_on_feature': endpoint_data.get('record_on_feature', '*1'),
            'record_off_feature': endpoint_data.get('record_off_feature', '*2'),
            'record_calls': endpoint_data.get('record_calls', 'yes'),
            'allow_subscribe': endpoint_data.get('allow_subscribe', 'yes'),
            'dtmf_mode': endpoint_data.get('dtmf_mode', 'rfc4733'),
            '100rel': endpoint_data.get('100rel', 'no'),
            'direct_media': endpoint_data.get('direct_media', 'no'),
            'ice_support': endpoint_data.get('ice_support', 'no'),
            'sdp_session': endpoint_data.get('sdp_session', 'Asterisk'),
            'set_var': endpoint_data.get('set_var', ''),
            'tone_zone': endpoint_data.get('tone_zone', 'us'),
            'send_pai': endpoint_data.get('send_pai', 'yes'),
            'send_rpid': endpoint_data.get('send_rpid', 'yes')
        }
        
        # Only add non-empty values
        for key, value in advanced_options.items():
            if value is not None and str(value).strip():
                endpoint_section[key] = str(value)
        
        self.sections[endpoint_id] = endpoint_section
        
        # Add auth section
        auth_section = f"{endpoint_id}_auth"
        auth_data = endpoint_data.get('auth', {})
        self.sections[auth_section] = {
            'type': auth_data.get('type', 'auth'),
            'auth_type': auth_data.get('auth_type', 'userpass'),
            'username': auth_data.get('username', endpoint_id),
            'password': auth_data.get('password', ''),
            'realm': auth_data.get('realm', 'UVLink')
        }
        
        # Add AOR section
        aor_section = f"{endpoint_id}_aor"
        aor_data = endpoint_data.get('aor', {})
        aor_config = {
            'type': aor_data.get('type', 'aor'),
            'max_contacts': str(aor_data.get('max_contacts', 2))
        }
        
        # Add optional AOR settings
        if aor_data.get('qualify_frequency'):
            aor_config['qualify_frequency'] = str(aor_data['qualify_frequency'])
        if aor_data.get('authenticate_qualify'):
            aor_config['authenticate_qualify'] = str(aor_data['authenticate_qualify'])
        if aor_data.get('default_expiration'):
            aor_config['default_expiration'] = str(aor_data['default_expiration'])
        if aor_data.get('minimum_expiration'):
            aor_config['minimum_expiration'] = str(aor_data['minimum_expiration'])
        if aor_data.get('maximum_expiration'):
            aor_config['maximum_expiration'] = str(aor_data['maximum_expiration'])
        
        self.sections[aor_section] = aor_config
        
        # Add to order
        self.order.extend([endpoint_id, auth_section, aor_section])
        
        logger.info(f"Added advanced endpoint {endpoint_id}")
        return True
    
    def update_endpoint(self, endpoint_data: Dict[str, Any]) -> bool:
        """Update an existing endpoint"""
        endpoint_id = endpoint_data['id']
        
        if endpoint_id not in self.sections:
            logger.warning(f"Endpoint {endpoint_id} does not exist")
            return False
        
        # Update endpoint section with provided values
        for key, value in endpoint_data.items():
            if key not in ['id', 'auth', 'aor'] and value is not None:
                # Always include transport even if it's the default
                if key == 'transport' or str(value).strip():
                    self.sections[endpoint_id][key] = str(value)
        
        # Update auth section if provided
        if 'auth' in endpoint_data and endpoint_data['auth']:
            auth_section = f"{endpoint_id}_auth"
            if auth_section in self.sections:
                auth_data = endpoint_data['auth']
                for key, value in auth_data.items():
                    if value is not None:
                        self.sections[auth_section][key] = str(value)
        
        # Update AOR section if provided
        if 'aor' in endpoint_data and endpoint_data['aor']:
            aor_section = f"{endpoint_id}_aor"
            if aor_section in self.sections:
                aor_data = endpoint_data['aor']
                for key, value in aor_data.items():
                    if value is not None:
                        self.sections[aor_section][key] = str(value)
        
        logger.info(f"Updated endpoint {endpoint_id}")
        return True
    
    def delete_endpoint(self, endpoint_id: str) -> bool:
        """Delete an endpoint and all related sections"""
        related_sections = self.get_endpoint_sections(endpoint_id)
        
        if not related_sections:
            logger.warning(f"Endpoint {endpoint_id} not found")
            return False
        
        # Remove sections
        for section in related_sections:
            if section in self.sections:
                del self.sections[section]
            if section in self.comments:
                del self.comments[section]
            if section in self.order:
                self.order.remove(section)
        
        logger.info(f"Deleted endpoint {endpoint_id} and related sections")
        return True
    
    def list_endpoints(self) -> List[Dict[str, Any]]:
        """List all endpoints with their full configuration"""
        endpoints = []
        
        # First pass: collect all sections by type
        endpoint_sections = {}
        auth_sections = {}
        aor_sections = {}
        
        for section_name, section_data in self.sections.items():
            section_type = section_data.get('type')
            if section_type == 'endpoint':
                endpoint_sections[section_name] = section_data
            elif section_type == 'auth':
                auth_sections[section_name] = section_data
            elif section_type == 'aor':
                aor_sections[section_name] = section_data
        
        # Second pass: build complete endpoint info
        for section_name, section_data in endpoint_sections.items():
            # Get related auth and aor sections
            auth_data = auth_sections.get(section_name, {})
            aor_data = aor_sections.get(section_name, {})
            
            # Build complete endpoint info
            endpoint_info = {
                'id': section_name,
                'type': section_data.get('type', 'endpoint'),
                'entity_type': 'endpoint',
                'name': section_data.get('name', f'Extension {section_name}'),
                'context': section_data.get('context', 'internal'),
                'allow': section_data.get('allow', 'ulaw,alaw'),
                'disallow': section_data.get('disallow', 'all'),
                'transport': section_data.get('transport', 'transport-udp'),
                'callerid': section_data.get('callerid', ''),
                'webrtc': section_data.get('webrtc', 'no'),
                'auth': {
                    'type': auth_data.get('type', 'auth'),
                    'auth_type': auth_data.get('auth_type', 'userpass'),
                    'username': auth_data.get('username', section_name),
                    'password': auth_data.get('password', ''),
                    'realm': auth_data.get('realm', 'UVLink')
                },
                'aor': {
                    'type': aor_data.get('type', 'aor'),
                    'max_contacts': int(aor_data.get('max_contacts', 2)),
                    'qualify_frequency': int(aor_data.get('qualify_frequency', 60)) if aor_data.get('qualify_frequency') else 60,
                    'remove_unavailable': aor_data.get('remove_unavailable', 'no')
                }
            }
            
            # Add all other endpoint properties
            for key, value in section_data.items():
                if key not in ['type', 'auth', 'aors'] and key not in endpoint_info:
                    endpoint_info[key] = value
            
            endpoints.append(endpoint_info)
        
        return endpoints
    
    def save(self, backup_suffix: str = None) -> bool:
        """Save the configuration back to file"""
        try:
            # Create backup
            if backup_suffix:
                from shared.utils import create_backup
                create_backup(self.config_path, f"pjsip_{backup_suffix}")
            
            # Generate content
            content_lines = []
            
            # Add sections in order
            for section_name in self.order:
                if section_name not in self.sections:
                    continue
                
                # Add comments before section
                if section_name in self.comments:
                    content_lines.extend(self.comments[section_name])
                
                # Add section header
                content_lines.append(f"[{section_name}]")
                
                # Add section content
                for key, value in self.sections[section_name].items():
                    content_lines.append(f"{key}={value}")
                
                content_lines.append("")  # Empty line after section
            
            # Add any remaining sections not in order
            for section_name, section_data in self.sections.items():
                if section_name not in self.order:
                    content_lines.append(f"[{section_name}]")
                    for key, value in section_data.items():
                        content_lines.append(f"{key}={value}")
                    content_lines.append("")
            
            # Add end comments
            if '_end' in self.comments:
                content_lines.extend(self.comments['_end'])
            
            # Write to file
            with open(self.config_path, 'w') as f:
                f.write('\n'.join(content_lines))
            
            logger.info(f"Configuration saved to {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False
    
    def add_endpoint_efficient(self, endpoint_data: Dict[str, Any]) -> bool:
        """Add endpoint efficiently without full parsing"""
        try:
            endpoint_id = endpoint_data['id']
            logger.info(f"Adding endpoint {endpoint_id} with data: {endpoint_data}")
            
            # First check if endpoint exists by scanning file
            with open(self.config_path, 'r') as f:
                content = f.read()
                if f'[{endpoint_id}]' in content:
                    logger.warning(f"Endpoint {endpoint_id} already exists")
                    return False
            
            # Create backup
            from shared.utils import create_backup
            create_backup(self.config_path, f"pjsip_add_{endpoint_id}")
            
            # Prepare new sections
            new_sections = []
            
            # Add endpoint section with exact configuration
            new_sections.append(f"[{endpoint_id}]")
            new_sections.append("type=endpoint")
            new_sections.append(f"aors={endpoint_id}")
            new_sections.append(f"accountcode={endpoint_id}")
            new_sections.append(f"subscribe_context=t-{endpoint_id}")
            new_sections.append("moh_suggest=default")
            new_sections.append("notify_early_inuse_ringing=yes")
            new_sections.append("refer_blind_progress=yes")
            new_sections.append(f"auth={endpoint_id}")
            new_sections.append(f"outbound_auth={endpoint_id}")
            new_sections.append("direct_media=no")
            new_sections.append("force_rport=yes")
            new_sections.append("rtp_symmetric=yes")
            new_sections.append("rewrite_contact=yes")
            new_sections.append("dtmf_mode=rfc4733")
            new_sections.append("context=t-internal")
            new_sections.append("allow=alaw")
            new_sections.append("use_ptime=no")
            
            # Add callerid if provided in custom_data
            if 'custom_data' in endpoint_data and endpoint_data['custom_data']:
                name = endpoint_data['custom_data'].get('name')
                if name:
                    new_sections.append(f"callerid={name} <{endpoint_id}>")
                else:
                    new_sections.append(f"callerid=Extension {endpoint_id} <{endpoint_id}>")
            
            # Add auth section
            new_sections.append(f"\n[{endpoint_id}]")
            new_sections.append("type=auth")
            new_sections.append("auth_type=userpass")
            
            # Get auth data from either auth section or endpoint_settings
            auth_data = endpoint_data.get('auth', {})
            if not auth_data and 'endpoint_settings' in endpoint_data:
                auth_data = endpoint_data['endpoint_settings']
            
            # Always add username and password
            username = auth_data.get('username', endpoint_id)
            password = auth_data.get('password', '')
            
            new_sections.append(f"username={username}")
            new_sections.append(f"password={password}")  # Always add password, even if empty
            
            # Add AOR section with all required fields
            new_sections.append(f"\n[{endpoint_id}]")
            new_sections.append("type=aor")
            new_sections.append("max_contacts=1")
            new_sections.append("qualify_frequency=60")
            new_sections.append("qualify_timeout=8")
            new_sections.append("remove_unavailable=yes")
            new_sections.append("remove_existing=yes")
            new_sections.append("default_expiration=3600")
            new_sections.append("minimum_expiration=60")
            new_sections.append("maximum_expiration=7200")
            
            # Log final configuration
            logger.info("Final configuration:")
            for line in new_sections:
                logger.info(line)
            
            # Append new sections to file
            with open(self.config_path, 'a') as f:
                f.write('\n' + '\n'.join(new_sections) + '\n')
            
            logger.info(f"Added endpoint {endpoint_id} efficiently")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add endpoint efficiently: {e}")
            return False