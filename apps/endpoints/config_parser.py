import re
import logging
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
import yaml
import os

logger = logging.getLogger(__name__)

class AdvancedPJSIPConfigParser:
    """Advanced parser for PJSIP configuration that handles complex endpoint configurations"""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.sections = {}
        self.comments = {}
        self.order = []
        # Load options from YAML
        options_path = os.path.join(os.path.dirname(__file__), "pjsip_options.yaml")
        with open(options_path, "r") as f:
            self.options = yaml.safe_load(f)
        self.endpoint_options = self.options.get("endpoint", {})
        self.auth_options = self.options.get("auth", {})
        self.aor_options = self.options.get("aor", {})
        
    def parse(self) -> Dict[Tuple[str, Optional[str]], Dict[str, str]]:
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
            
            # Handle comments
            if line.startswith(';') or line.startswith('#'):
                section_comments.append(line)
                continue
            
            # Ignore blank lines (do not store as comments)
            if not line.strip():
                continue
            
            # Handle section headers [section_name](template)
            section_match = re.match(r'^\[([^\]]+)\](?:\(([^)]+)\))?', line)
            if section_match:
                section_name = section_match.group(1)
                section_template = section_match.group(2)  # None if not present
                section_key = (section_name, section_template)
                
                # Handle duplicate section names (if needed)
                if section_name in self.sections:
                    if section_name not in section_counter:
                        section_counter[section_name] = 1
                    section_counter[section_name] += 1
                    section_name = f"{section_name}_{section_counter[section_name]}"
                
                # Store section in order
                if section_key not in self.order:
                    self.order.append(section_key)
                
                # Initialize section
                if section_key not in self.sections:
                    self.sections[section_key] = {}
                
                # Store comments for this section
                if section_comments:
                    self.comments[section_key] = section_comments
                    section_comments = []
                
                current_section = section_key
                continue
            
            # Handle key=value pairs
            if current_section and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                self.sections[current_section][key] = value
        
        # Store any remaining comments (not blank lines)
        if section_comments:
            self.comments['_end'] = section_comments
        
        return self.sections
    
    def get_endpoint_sections(self, endpoint_id: str) -> List[Tuple[str, Optional[str]]]:
        """Get all sections related to an endpoint using the new tuple key structure"""
        related_sections = []

        # Main endpoint section
        endpoint_key = (endpoint_id, 'endpoint-tpl')
        if endpoint_key in self.sections:
            related_sections.append(endpoint_key)

        # Auth section
        auth_key = (f"{endpoint_id}-auth", None)
        if auth_key in self.sections:
            related_sections.append(auth_key)

        # AOR section
        aor_key = (endpoint_id, 'aor-tpl')
        if aor_key in self.sections:
            related_sections.append(aor_key)

        return related_sections
        
    
    def add_advanced_endpoint(self, endpoint_data: Dict[str, Any]) -> bool:
        """Add an advanced endpoint with all configuration options"""
        endpoint_id = endpoint_data['id']
        
        # Check if endpoint already exists
        endpoint_key = (endpoint_id, 'endpoint-tpl')
        if endpoint_key in self.sections:
            logger.warning(f"Endpoint {endpoint_id} already exists")
            return False
        
        # Build endpoint section from YAML options
        endpoint_section = {}
        for key, default in self.endpoint_options.items():
            # Special handling for aors, auth, outbound_auth
            if key == "aors":
                value = endpoint_data.get("aors", endpoint_id)
            elif key == "auth" or key == "outbound_auth":
                value = f"{endpoint_id}-auth"
            else:
                value = endpoint_data.get(key, default)
            if value != "" and value is not None:
                endpoint_section[key] = str(value)
        self.sections[endpoint_key] = endpoint_section
        
        # Build auth section from YAML options
        auth_key = (f"{endpoint_id}-auth", None)
        auth_data = endpoint_data.get('auth', {})
        auth_section = {}
        for key, default in self.auth_options.items():
            value = auth_data.get(key, default)
            if value != "" and value is not None:
                auth_section[key] = str(value)
        self.sections[auth_key] = auth_section
        
        # Build aor section from YAML options
        aor_key = (endpoint_id, 'aor-tpl')
        aor_data = endpoint_data.get('aor', {})
        aor_section = {}
        for key, default in self.aor_options.items():
            value = aor_data.get(key, default)
            if value != "" and value is not None:
                aor_section[key] = str(value)
        self.sections[aor_key] = aor_section
        
        # Add to order
        self.order.extend([endpoint_key, auth_key, aor_key])
        
        logger.info(f"Added advanced endpoint {endpoint_id}")
        return True
    
    def update_endpoint(self, endpoint_data: Dict[str, Any]) -> bool:
        """Update an existing endpoint"""
        old_endpoint_id = endpoint_data.get('old_id')  # Get the old ID from the data
        new_endpoint_id = endpoint_data['id']  # Get the new ID from the data
        
        logger.info(f"Updating endpoint from {old_endpoint_id} to {new_endpoint_id}")
        
        # If IDs are different, we need to rename the sections
        if old_endpoint_id and old_endpoint_id != new_endpoint_id:
            old_endpoint_key = (old_endpoint_id, 'endpoint-tpl')
            old_auth_key = (f"{old_endpoint_id}-auth", None)
            old_aor_key = (old_endpoint_id, 'aor-tpl')
            
            # Check if old endpoint exists
            if old_endpoint_key not in self.sections:
                logger.warning(f"Endpoint {old_endpoint_id} does not exist")
                return False
            
            # Create new section keys
            new_endpoint_key = (new_endpoint_id, 'endpoint-tpl')
            new_auth_key = (f"{new_endpoint_id}-auth", None)
            new_aor_key = (new_endpoint_id, 'aor-tpl')
            
            # Move sections to new keys
            self.sections[new_endpoint_key] = self.sections.pop(old_endpoint_key)
            if old_auth_key in self.sections:
                self.sections[new_auth_key] = self.sections.pop(old_auth_key)
            if old_aor_key in self.sections:
                self.sections[new_aor_key] = self.sections.pop(old_aor_key)
            
            # Update order
            if old_endpoint_key in self.order:
                idx = self.order.index(old_endpoint_key)
                self.order[idx] = new_endpoint_key
            if old_auth_key in self.order:
                idx = self.order.index(old_auth_key)
                self.order[idx] = new_auth_key
            if old_aor_key in self.order:
                idx = self.order.index(old_aor_key)
                self.order[idx] = new_aor_key
            
            # Update references in the endpoint section
            endpoint_section = self.sections[new_endpoint_key]
            if 'auth' in endpoint_section:
                endpoint_section['auth'] = f"{new_endpoint_id}-auth"
            if 'outbound_auth' in endpoint_section:
                endpoint_section['outbound_auth'] = f"{new_endpoint_id}-auth"
            if 'aors' in endpoint_section:
                endpoint_section['aors'] = new_endpoint_id
            
            # Update references in auth section
            if new_auth_key in self.sections:
                auth_section = self.sections[new_auth_key]
                if 'username' in auth_section:
                    auth_section['username'] = new_endpoint_id
            
            logger.info(f"Renamed endpoint from {old_endpoint_id} to {new_endpoint_id}")
        
        # Now proceed with normal update using new ID
        endpoint_key = (new_endpoint_id, 'endpoint-tpl')
        auth_key = (f"{new_endpoint_id}-auth", None)
        aor_key = (new_endpoint_id, 'aor-tpl')

        if endpoint_key not in self.sections:
            logger.warning(f"Endpoint {new_endpoint_id} does not exist")
            return False

        logger.info(f"Before update: {self.sections[endpoint_key]}")
        
        # Update endpoint section
        for key, value in endpoint_data.items():
            if key in ['id', 'old_id']:  # Skip both old and new IDs
                continue
                
            if isinstance(value, dict):
                # Handle nested fields
                if key == 'auth':
                    # Update auth section
                    if auth_key not in self.sections:
                        self.sections[auth_key] = {'type': 'auth'}
                    for nested_key, nested_value in value.items():
                        if nested_value is not None:
                            # If this is a username field and we're changing IDs, update it
                            if nested_key == 'username' and old_endpoint_id != new_endpoint_id:
                                self.sections[auth_key][nested_key] = new_endpoint_id
                            else:
                                self.sections[auth_key][nested_key] = str(nested_value)
                elif key == 'aor':
                    # Update aor section
                    if aor_key not in self.sections:
                        self.sections[aor_key] = {'type': 'aor'}
                    for nested_key, nested_value in value.items():
                        if nested_value is not None:
                            self.sections[aor_key][nested_key] = str(nested_value)
                elif key == 'transport_network':
                    # Update transport network settings
                    for nested_key, nested_value in value.items():
                        if nested_value is not None:
                            if nested_key == 'transport':
                                self.sections[endpoint_key]['transport'] = str(nested_value)
                            else:
                                self.sections[endpoint_key][nested_key] = str(nested_value)
                elif key == 'audio_media':
                    # Update audio media settings
                    for nested_key, nested_value in value.items():
                        if nested_value is not None:
                            self.sections[endpoint_key][nested_key] = str(nested_value)
                elif key == 'rtp':
                    # Update RTP settings
                    for nested_key, nested_value in value.items():
                        if nested_value is not None:
                            self.sections[endpoint_key][nested_key] = str(nested_value)
                elif key == 'recording':
                    # Update recording settings
                    for nested_key, nested_value in value.items():
                        if nested_value is not None:
                            self.sections[endpoint_key][nested_key] = str(nested_value)
                elif key == 'call':
                    # Update call settings
                    for nested_key, nested_value in value.items():
                        if nested_value is not None:
                            self.sections[endpoint_key][nested_key] = str(nested_value)
                elif key == 'presence':
                    # Update presence settings
                    for nested_key, nested_value in value.items():
                        if nested_value is not None:
                            self.sections[endpoint_key][nested_key] = str(nested_value)
                elif key == 'voicemail':
                    # Update voicemail settings
                    for nested_key, nested_value in value.items():
                        if nested_value is not None:
                            self.sections[endpoint_key][nested_key] = str(nested_value)
            else:
                # Handle direct fields
                if value is not None:
                    # If we're changing IDs, update these fields automatically
                    if old_endpoint_id != new_endpoint_id:
                        if key in ['accountcode', 'from_user'] and str(value) == old_endpoint_id:
                            self.sections[endpoint_key][key] = new_endpoint_id
                        else:
                            self.sections[endpoint_key][key] = str(value)
                    else:
                        self.sections[endpoint_key][key] = str(value)

        logger.info(f"After update: {self.sections[endpoint_key]}")
        logger.info(f"Updated endpoint {new_endpoint_id}")

        # Save the changes
        try:
            return self.save(backup_suffix=f"update_{new_endpoint_id}")
        except Exception as e:
            logger.error(f"Failed to save changes: {e}")
            return False
    
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
            endpoint_info = {'id': section_name[0]}
            
            # Add endpoint options
            for key in self.endpoint_options:
                endpoint_info[key] = section_data.get(key, self.endpoint_options[key])
            
            # Add auth options
            auth_info = {}
            for key in self.auth_options:
                auth_info[key] = auth_data.get(key, self.auth_options[key])
            endpoint_info['auth'] = auth_info
            
            # Add aor options
            aor_info = {}
            for key in self.aor_options:
                aor_info[key] = aor_data.get(key, self.aor_options[key])
            endpoint_info['aor'] = aor_info
            
            # Add all other endpoint properties
            for key, value in section_data.items():
                if key not in ['type', 'auth', 'aors'] and key not in endpoint_info:
                    endpoint_info[key] = value
            
            endpoints.append(endpoint_info)
        
        return endpoints
    
    def save(self, backup_suffix: str = None) -> bool:
        """Save the configuration back to file"""
        logger.info(f"Saving config to {self.config_path}")
        try:
            # Create backup
            if backup_suffix:
                from shared.utils import create_backup
                create_backup(self.config_path, f"pjsip_{backup_suffix}")
            
            # Generate content
            content_lines = []
            
            # Add sections in order
            for section_key in self.order:
                if section_key not in self.sections:
                    continue
                
                # Add comments before section
                if section_key in self.comments:
                    content_lines.extend(self.comments[section_key])
                
                # Add section header with template if needed
                section_name, section_template = section_key
                if section_template:
                    content_lines.append(f"[{section_name}]({section_template})")
                else:
                    content_lines.append(f"[{section_name}]")
                
                # Add section content
                for key, value in self.sections[section_key].items():
                    content_lines.append(f"{key}={value}")
                
                # Add single newline between sections
                content_lines.append("")
            
            # Add any remaining sections not in order
            for section_name, section_data in self.sections.items():
                if section_name not in self.order:
                    # Add section header with template if needed
                    section_name, section_template = section_name
                    if section_template:
                        content_lines.append(f"[{section_name}]({section_template})")
                    else:
                        content_lines.append(f"[{section_name}]")
                    
                    for key, value in section_data.items():
                        content_lines.append(f"{key}={value}")
                    
                    # Add single newline between sections
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
            
            # Add endpoint section with options from YAML
            new_sections.append(f"[{endpoint_id}](endpoint-tpl)")
            for key, default in self.endpoint_options.items():
                # Special handling for aors, auth, outbound_auth
                if key == "aors":
                    value = endpoint_data.get("aors", endpoint_id)
                elif key == "auth" or key == "outbound_auth":
                    value = f"{endpoint_id}-auth"
                else:
                    value = endpoint_data.get(key, default)
                if value != "" and value is not None:
                    new_sections.append(f"{key}={value}")
            new_sections.append("")  # blank line after section
            
            # Add auth section with options from YAML
            new_sections.append(f"[{endpoint_id}-auth]")
            for key, default in self.auth_options.items():
                value = endpoint_data.get('auth', {}).get(key, default)
                if value != "" and value is not None:
                    new_sections.append(f"{key}={value}")
            new_sections.append("")
            
            # Add AOR section with options from YAML
            new_sections.append(f"[{endpoint_id}](aor-tpl)")
            for key, default in self.aor_options.items():
                value = endpoint_data.get('aor', {}).get(key, default)
                if value != "" and value is not None:
                    new_sections.append(f"{key}={value}")
            new_sections.append("")
            
            # Log final configuration
            logger.info("Final configuration:")
            for line in new_sections:
                logger.info(line)
            
            # Append new sections to file
            with open(self.config_path, 'a') as f:
                f.write('\n' + '\n'.join(new_sections))
            
            logger.info(f"Added endpoint {endpoint_id} efficiently")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add endpoint efficiently: {e}")
            return False