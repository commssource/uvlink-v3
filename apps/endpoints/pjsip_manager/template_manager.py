# ============================================================================
# apps/endpoints/pjsip_manager/template_manager.py - OPTIMIZED VERSION
# ============================================================================

import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateNotFound, TemplateSyntaxError
from jinja2.exceptions import UndefinedError
import aiofiles
import asyncio


class TemplateManager:
    """
    Optimized template manager using Jinja2 for PJSIP configuration generation.
    Supports template inheritance, custom filters, and async rendering.
    """
    
    def __init__(self, template_dir: Union[str, Path] = "templates/pjsip"):
        self.template_dir = Path(template_dir)
        self.logger = logging.getLogger(f"{__name__}.TemplateManager")
        
        # Ensure template directory exists
        self.template_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Jinja2 environment
        self.env = self._setup_jinja_environment()
        
        # Template cache for performance
        self._template_cache = {}
        
        # Create default templates if they don't exist
        asyncio.create_task(self._create_default_templates())
    
    def _setup_jinja_environment(self) -> Environment:
        """Setup Jinja2 environment with custom configurations"""
        env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
            newline_sequence='\n'  # Ensure proper line endings
        )
        
        # Add custom filters
        env.filters.update({
            'bool_to_yesno': self._bool_to_yesno,
            'default_if_none': self._default_if_none,
            'sanitize_identifier': self._sanitize_identifier,
            'format_contact': self._format_contact,
            'format_codec_list': self._format_codec_list,
        })
        
        # Add custom tests
        env.tests.update({
            'endpoint_type': self._is_endpoint_type,
            'webrtc_capable': self._is_webrtc_capable,
        })
        
        # Add global functions
        env.globals.update({
            'generate_auth_id': self._generate_auth_id,
            'generate_aor_id': self._generate_aor_id,
            'get_default_transport': self._get_default_transport,
        })
        
        return env
    
    async def render_template(self, template_name: str, variables: Dict[str, Any]) -> str:
        """
        Render a template with the given variables.
        
        Args:
            template_name: Name of the template file (without .j2 extension)
            variables: Dictionary of variables to pass to the template
            
        Returns:
            Rendered template content
            
        Raises:
            ValueError: If template rendering fails
        """
        try:
            # Ensure template has .j2 extension
            if not template_name.endswith('.j2'):
                template_name += '.j2'
            
            # Get template (with caching)
            template = self._get_template(template_name)
            
            # Prepare variables with defaults
            render_vars = self._prepare_variables(variables)
            
            # Render template
            content = await self._render_async(template, render_vars)
            
            self.logger.debug(f"Successfully rendered template '{template_name}'")
            return content.strip()
            
        except TemplateNotFound as e:
            error_msg = f"Template not found: {template_name}"
            self.logger.error(error_msg)
            raise ValueError(error_msg) from e
            
        except TemplateSyntaxError as e:
            error_msg = f"Template syntax error in '{template_name}': {e.message} at line {e.lineno}"
            self.logger.error(error_msg)
            raise ValueError(error_msg) from e
            
        except UndefinedError as e:
            error_msg = f"Undefined variable in template '{template_name}': {e}"
            self.logger.error(error_msg)
            raise ValueError(error_msg) from e
            
        except Exception as e:
            error_msg = f"Template rendering error for '{template_name}': {e}"
            self.logger.error(error_msg)
            raise ValueError(error_msg) from e
    
    def _get_template(self, template_name: str):
        """Get template with caching"""
        if template_name not in self._template_cache:
            self._template_cache[template_name] = self.env.get_template(template_name)
        return self._template_cache[template_name]
    
    async def _render_async(self, template, variables: Dict[str, Any]) -> str:
        """Render template asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, template.render, variables)
    
    def _prepare_variables(self, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare variables with defaults and transformations"""
        # Set common defaults
        defaults = {
            'allow': 'ulaw,alaw',
            'disallow': 'all',
            'dtmf_mode': 'rfc4733',
            'context': 'internal',
            'direct_media': 'no',
            'rtp_symmetric': 'yes',
            'force_rport': 'yes',
            'rewrite_contact': 'yes',
            'ice_support': 'no',
            'device_state_busy_at': '1',
            'send_pai': 'yes',
            'send_rpid': 'yes',
            'allow_subscribe': 'yes',
            'rtp_timeout': '30',
            'rtp_timeout_hold': '60',
            'max_contacts': '1',
            'qualify_timeout': '3',
            'qualify_frequency': '60',
            'authenticate_qualify': 'no',
            'default_expiration': '3600',
            'minimum_expiration': '60',
            'maximum_expiration': '7200',
            'remove_existing': 'yes',
            'auth_type': 'userpass',
        }
        
        # Merge with provided variables (variables take precedence)
        result = {**defaults, **variables}
        
        # Auto-generate IDs if not provided
        endpoint_id = result.get('endpoint_id', '')
        if endpoint_id:
            result.setdefault('auth_id', f"{endpoint_id}-auth")
            result.setdefault('aor_id', endpoint_id)
            result.setdefault('transport_id', f"transport-{endpoint_id}")
            result.setdefault('username', endpoint_id)
        
        return result
    
    # Custom Jinja2 filters
    def _bool_to_yesno(self, value: Any) -> str:
        """Convert boolean to yes/no string"""
        if isinstance(value, bool):
            return 'yes' if value else 'no'
        if isinstance(value, str):
            return 'yes' if value.lower() in ('true', '1', 'yes', 'on') else 'no'
        return 'no'
    
    def _default_if_none(self, value: Any, default: Any) -> Any:
        """Return default if value is None or empty string"""
        return default if value in (None, '') else value
    
    def _sanitize_identifier(self, value: str) -> str:
        """Sanitize string to be a valid PJSIP identifier"""
        import re
        if not value:
            return ''
        # Replace invalid characters with underscores
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', str(value))
        # Ensure it starts with a letter or underscore
        if sanitized and not sanitized[0].isalpha() and sanitized[0] != '_':
            sanitized = '_' + sanitized
        return sanitized
    
    def _format_contact(self, endpoint_id: str, domain: str = '', port: int = 5060) -> str:
        """Format SIP contact string"""
        if not domain:
            return f"sip:{endpoint_id}@localhost:{port}"
        return f"sip:{endpoint_id}@{domain}:{port}"
    
    def _format_codec_list(self, codecs: Union[str, List[str]]) -> str:
        """Format codec list"""
        if isinstance(codecs, list):
            return ','.join(codecs)
        return str(codecs) if codecs else 'ulaw,alaw'
    
    # Custom Jinja2 tests
    def _is_endpoint_type(self, endpoint_type: str, expected_type: str) -> bool:
        """Test if endpoint is of a specific type"""
        return str(endpoint_type).lower() == str(expected_type).lower()
    
    def _is_webrtc_capable(self, variables: Dict[str, Any]) -> bool:
        """Test if endpoint is WebRTC capable"""
        return (
            variables.get('webrtc') == 'yes' or
            variables.get('transport', '').startswith('transport-wss') or
            'webrtc' in variables.get('template', '').lower()
        )
    
    # Global functions
    def _generate_auth_id(self, endpoint_id: str) -> str:
        """Generate auth ID for endpoint"""
        return f"{endpoint_id}-auth"
    
    def _generate_aor_id(self, endpoint_id: str) -> str:
        """Generate AOR ID for endpoint"""
        return endpoint_id
    
    def _get_default_transport(self, endpoint_type: str = 'endpoint') -> str:
        """Get default transport for endpoint type"""
        transport_map = {
            'webrtc': 'transport-wss',
            'trunk': 'transport-udp',
            'endpoint': 'transport-udp',
        }
        return transport_map.get(endpoint_type.lower(), 'transport-udp')
    
    async def list_templates(self) -> List[str]:
        """List available templates"""
        templates = []
        try:
            for template_file in self.template_dir.glob('*.j2'):
                templates.append(template_file.stem)  # Remove .j2 extension
        except Exception as e:
            self.logger.error(f"Failed to list templates: {e}")
        
        return sorted(templates)
    
    async def get_template_content(self, template_name: str) -> Optional[str]:
        """Get raw template content"""
        try:
            if not template_name.endswith('.j2'):
                template_name += '.j2'
            
            template_path = self.template_dir / template_name
            if template_path.exists():
                async with aiofiles.open(template_path, 'r') as f:
                    return await f.read()
        except Exception as e:
            self.logger.error(f"Failed to read template '{template_name}': {e}")
        
        return None
    
    async def create_template(self, template_name: str, content: str) -> bool:
        """Create or update a template"""
        try:
            if not template_name.endswith('.j2'):
                template_name += '.j2'
            
            template_path = self.template_dir / template_name
            async with aiofiles.open(template_path, 'w') as f:
                await f.write(content)
            
            # Clear cache for this template
            if template_name in self._template_cache:
                del self._template_cache[template_name]
            
            self.logger.info(f"Created/updated template: {template_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create template '{template_name}': {e}")
            return False
    
    async def delete_template(self, template_name: str) -> bool:
        """Delete a template"""
        try:
            if not template_name.endswith('.j2'):
                template_name += '.j2'
            
            template_path = self.template_dir / template_name
            if template_path.exists():
                template_path.unlink()
                
                # Clear cache for this template
                if template_name in self._template_cache:
                    del self._template_cache[template_name]
                
                self.logger.info(f"Deleted template: {template_name}")
                return True
        except Exception as e:
            self.logger.error(f"Failed to delete template '{template_name}': {e}")
        
        return False
    
    async def validate_template(self, template_name: str, test_variables: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate a template by attempting to render it"""
        if test_variables is None:
            test_variables = {
                'endpoint_id': 'test_endpoint',
                'context': 'internal',
                'auth_id': 'test_endpoint-auth',
                'aor_id': 'test_endpoint',
                'transport': 'transport-udp'
            }
        
        try:
            content = await self.render_template(template_name, test_variables)
            return {
                'valid': True,
                'content': content,
                'error': None
            }
        except Exception as e:
            return {
                'valid': False,
                'content': None,
                'error': str(e)
            }
    
    # Add these templates to your _create_default_templates method in template_manager.py

    async def _create_default_templates(self):
        """Create default templates if they don't exist"""
        default_templates = {
            'endpoint-basic.j2': '''[{{ endpoint_id }}]({{ template_name | default('endpoint-basic-tpl') }})
    type=endpoint
    {% if context -%}
    context={{ context }}
    {% endif -%}
    {% if auth_id -%}
    auth={{ auth_id }}
    {% endif -%}
    {% if aor_id -%}
    aors={{ aor_id }}
    {% endif -%}
    {% if transport -%}
    transport={{ transport }}
    {% endif -%}
    {% if callerid -%}
    callerid={{ callerid }}
    {% endif -%}
    allow={{ allow }}
    disallow={{ disallow }}
    dtmf_mode={{ dtmf_mode }}
    direct_media={{ direct_media }}
    rtp_symmetric={{ rtp_symmetric }}
    force_rport={{ force_rport }}
    rewrite_contact={{ rewrite_contact }}
    ice_support={{ ice_support }}
    device_state_busy_at={{ device_state_busy_at }}
    send_pai={{ send_pai }}
    send_rpid={{ send_rpid }}
    allow_subscribe={{ allow_subscribe }}
    rtp_timeout={{ rtp_timeout }}
    rtp_timeout_hold={{ rtp_timeout_hold }}''',
            
            'auth-basic.j2': '''[{{ auth_id }}]({{ auth_template | default('auth-basic-tpl') }})
    type=auth
    auth_type={{ auth_type }}
    username={{ username }}
    {% if password -%}
    password={{ password }}
    {% endif -%}
    {% if realm -%}
    realm={{ realm }}
    {% endif -%}''',
            
            'aor-basic.j2': '''[{{ aor_id }}]({{ aor_template | default('aor-basic-tpl') }})
    type=aor
    {% if contact -%}
    contact={{ contact }}
    {% endif -%}
    max_contacts={{ max_contacts }}
    qualify_timeout={{ qualify_timeout }}
    qualify_frequency={{ qualify_frequency }}
    authenticate_qualify={{ authenticate_qualify }}
    default_expiration={{ default_expiration }}
    minimum_expiration={{ minimum_expiration }}
    maximum_expiration={{ maximum_expiration }}
    remove_existing={{ remove_existing }}''',

            'identify-basic.j2': '''[{{ identify_id }}]({{ identify_template | default('identify-basic-tpl') }})
    type=identify
    endpoint={{ endpoint }}
    {% if match -%}
    match={{ match }}
    {% endif -%}
    {% if srv_lookups -%}
    srv_lookups={{ srv_lookups }}
    {% endif -%}''',

            'registration-basic.j2': '''[{{ registration_id }}]({{ registration_template | default('registration-basic-tpl') }})
    type=registration
    {% if transport -%}
    transport={{ transport }}
    {% endif -%}
    {% if outbound_auth -%}
    outbound_auth={{ outbound_auth }}
    {% endif -%}
    {% if server_uri -%}
    server_uri={{ server_uri }}
    {% endif -%}
    {% if client_uri -%}
    client_uri={{ client_uri }}
    {% endif -%}
    {% if contact_user -%}
    contact_user={{ contact_user }}
    {% endif -%}
    {% if retry_interval -%}
    retry_interval={{ retry_interval }}
    {% endif -%}
    {% if max_retries -%}
    max_retries={{ max_retries }}
    {% endif -%}
    {% if forbidden_retry_interval -%}
    forbidden_retry_interval={{ forbidden_retry_interval }}
    {% endif -%}
    {% if expiration -%}
    expiration={{ expiration }}
    {% endif -%}'''
        }
        
        for template_name, content in default_templates.items():
            template_path = self.template_dir / template_name
            if not template_path.exists():
                await self.create_template(template_name, content)