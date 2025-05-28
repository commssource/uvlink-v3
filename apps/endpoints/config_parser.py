import re
import logging
from typing import Dict, List, Tuple, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class PJSIPConfigParser:
    """Safe parser for PJSIP configuration that preserves existing settings"""
    
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
    
    def is_endpoint_section(self, section_name: str) -> bool:
        """Check if section is an endpoint-related section"""
        if not section_name:
            return False
        
        section = self.sections.get(section_name, {})
        
        # Direct endpoint section
        if section.get('type') == 'endpoint':
            return True
        
        # Auth section for endpoint
        if section.get('type') == 'auth' and section_name.endswith('_auth'):
            return True
        
        # AOR section for endpoint  
        if section.get('type') == 'aor' and section_name.endswith('_aor'):
            return True
        
        return False
    
    def get_endpoint_sections(self, endpoint_id: str) -> List[str]:
        """Get all sections related to an endpoint"""
        related_sections = []
        
        # Main endpoint section
        if endpoint_id in self.sections:
            related_sections.append(endpoint_id)
        
        # Auth section
        auth_section = f"{endpoint_id}_auth"
        if auth_section in self.sections:
            related_sections.append(auth_section)
        
        # AOR section
        aor_section = f"{endpoint_id}_aor"
        if aor_section in self.sections:
            related_sections.append(aor_section)
        
        return related_sections
    
    def add_endpoint(self, endpoint_data: dict) -> bool:
        """Add a new endpoint to the configuration"""
        endpoint_id = endpoint_data['id']
        
        # Check if endpoint already exists
        if endpoint_id in self.sections:
            logger.warning(f"Endpoint {endpoint_id} already exists")
            return False
        
        # Add endpoint section
        self.sections[endpoint_id] = {
            'type': 'endpoint',
            'context': endpoint_data.get('context', 'internal'),
            'disallow': 'all',
            'allow': ','.join(endpoint_data.get('codecs', ['ulaw', 'alaw'])),
            'auth': f"{endpoint_id}_auth",
            'aors': f"{endpoint_id}_aor"
        }
        
        if endpoint_data.get('callerid'):
            self.sections[endpoint_id]['callerid'] = endpoint_data['callerid']
        
        # Add auth section
        auth_section = f"{endpoint_id}_auth"
        self.sections[auth_section] = {
            'type': 'auth',
            'auth_type': 'userpass',
            'username': endpoint_data['username'],
            'password': endpoint_data['password']
        }
        
        # Add AOR section
        aor_section = f"{endpoint_id}_aor"
        self.sections[aor_section] = {
            'type': 'aor',
            'max_contacts': str(endpoint_data.get('max_contacts', 1))
        }
        
        # Add to order
        self.order.extend([endpoint_id, auth_section, aor_section])
        
        logger.info(f"Added endpoint {endpoint_id}")
        return True
    
    def update_endpoint(self, endpoint_data: dict) -> bool:
        """Update an existing endpoint"""
        endpoint_id = endpoint_data['id']
        
        if endpoint_id not in self.sections:
            logger.warning(f"Endpoint {endpoint_id} does not exist")
            return False
        
        # Update endpoint section
        self.sections[endpoint_id].update({
            'context': endpoint_data.get('context', 'internal'),
            'allow': ','.join(endpoint_data.get('codecs', ['ulaw', 'alaw'])),
        })
        
        if endpoint_data.get('callerid'):
            self.sections[endpoint_id]['callerid'] = endpoint_data['callerid']
        elif 'callerid' in self.sections[endpoint_id]:
            del self.sections[endpoint_id]['callerid']
        
        # Update auth section
        auth_section = f"{endpoint_id}_auth"
        if auth_section in self.sections:
            self.sections[auth_section].update({
                'username': endpoint_data['username'],
                'password': endpoint_data['password']
            })
        
        # Update AOR section
        aor_section = f"{endpoint_id}_aor"
        if aor_section in self.sections:
            self.sections[aor_section].update({
                'max_contacts': str(endpoint_data.get('max_contacts', 1))
            })
        
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
    
    def list_endpoints(self) -> List[Dict[str, str]]:
        """List all endpoints in the configuration"""
        endpoints = []
        
        for section_name, section_data in self.sections.items():
            if section_data.get('type') == 'endpoint':
                # Get related auth section
                auth_section = f"{section_name}_auth"
                auth_data = self.sections.get(auth_section, {})
                
                # Get related AOR section
                aor_section = f"{section_name}_aor"
                aor_data = self.sections.get(aor_section, {})
                
                endpoint_info = {
                    'id': section_name,
                    'context': section_data.get('context', ''),
                    'codecs': section_data.get('allow', '').split(','),
                    'username': auth_data.get('username', ''),
                    'max_contacts': aor_data.get('max_contacts', '1'),
                    'callerid': section_data.get('callerid', '')
                }
                
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