# ============================================================================
# apps/endpoints/pjsip_manager/config_manager.py - OPTIMIZED VERSION
# ============================================================================

from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import aiofiles
import logging
import json
import re
from datetime import datetime
from fastapi import HTTPException

from config import Settings
from shared.utils.backup import create_config_backup
from shared.models import ConfigValidationResult, ConfigGenerationResult
from ..schemas import (
    EndpointConfig, StructuredEndpoint, EndpointListResponse, AudioMediaConfig, 
    TransportNetworkConfig, RTPConfig, RecordingConfig, CallConfig, PresenceConfig, 
    VoicemailConfig, AuthConfig, AORConfig, EndpointFilters, SortOptions, 
    EndpointTypeFilter, AuthTypeFilter
)
from shared.template_manager import UnifiedTemplateManager


class FieldConfigManager:
    """Simplified field configuration manager with better error handling"""
    
    def __init__(self, config_file: str = "field_config.json"):
        self.config_file = Path(config_file)
        self.field_config = self._load_config()
        
        # Default field configurations
        self.default_fields = {
            "context": {"default": "internal", "required": True},
            "auth_id": {"default": "{endpoint_id}-auth", "required": False},
            "aor_id": {"default": "{endpoint_id}", "required": False},
            "transport_id": {"default": "transport-{endpoint_id}", "required": False},
        }
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration with fallback to defaults"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logging.warning(f"Failed to load field config: {e}")
        
        # Return default configuration
        return {"endpoint_fields": self.default_fields}
    
    def _save_config(self, config: Dict[str, Any]) -> None:
        """Save configuration with error handling"""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save field config: {e}")

    async def _generate_registration_section_with_inheritance(
        self, 
        endpoint_id: str, 
        registration_config: Dict[str, Any], 
        base_variables: Dict[str, Any]
    ) -> str:
        """Generate registration section"""
        registration_template = registration_config.get("template", "registration-basic")
        
        registration_variables = {
            "registration_id": registration_config.get("registration_id", f"{endpoint_id}-reg"),
            **base_variables,
            **registration_config
        }
        
        registration_variables.pop("template", None)
        registration_variables = {k: v for k, v in registration_variables.items() if v is not None}
        
        return await self.template_manager.render_template(registration_template, registration_variables)

    
    def process_variables(self, endpoint_config: EndpointConfig) -> Dict[str, Any]:
        """Process variables with template substitution"""
        variables = {
            "endpoint_id": endpoint_config.id,
            **endpoint_config.variables
        }
        
        # Apply field defaults and processing
        for field_name, field_def in self.field_config.get("endpoint_fields", {}).items():
            current_value = getattr(endpoint_config, field_name, None) or variables.get(field_name)
            default_value = field_def.get("default")
            
            if current_value:
                variables[field_name] = current_value
            elif default_value:
                variables[field_name] = self._substitute_placeholders(default_value, endpoint_config.id)
        
        return {k: v for k, v in variables.items() if v is not None}
    
    def _substitute_placeholders(self, value: str, endpoint_id: str) -> str:
        """Replace placeholders in default values"""
        if isinstance(value, str):
            return value.replace("{endpoint_id}", endpoint_id)
        return value


class SectionGenerator:
    """Handles generation of different configuration sections"""
    
    def __init__(self, template_manager: UnifiedTemplateManager, logger: logging.Logger):
        self.template_manager = template_manager
        self.logger = logger
    
    async def generate_section(
        self, 
        section_type: str, 
        template_name: str, 
        variables: Dict[str, Any]
    ) -> str:
        """Generic section generator"""
        try:
            # Add section-specific defaults
            section_variables = self._add_section_defaults(section_type, variables)
            
            content = await self.template_manager.render_template(template_name, section_variables)
            self.logger.debug(f"Generated {section_type} section using template '{template_name}'")
            return content
            
        except Exception as e:
            self.logger.error(f"Failed to generate {section_type} section: {e}")
            raise ValueError(f"{section_type.title()} section generation failed: {e}")
    
    def _add_section_defaults(self, section_type: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Add section-specific default variables"""
        section_vars = variables.copy()
        endpoint_id = variables.get("endpoint_id", "")
        
        defaults = {
            "auth": {
                "auth_id": f"{endpoint_id}-auth",
                "auth_template": f"auth-basic-tpl"
            },
            "aor": {
                "aor_id": endpoint_id,
                "aor_template": f"aor-basic-tpl"
            },
            "transport": {
                "transport_id": f"transport-{endpoint_id}",
                "transport_template": f"transport-udp-tpl"
            }
        }
        
        if section_type in defaults:
            for key, default_value in defaults[section_type].items():
                if key not in section_vars:
                    section_vars[key] = default_value
        
        return section_vars


class ConfigValidator:
    """Handles configuration validation"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.section_pattern = re.compile(r'^\[(.*?)\](?:\((.*?)\))?$')
        self.option_pattern = re.compile(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.*)$')
    
    async def validate_config(self, config_file: Path) -> ConfigValidationResult:
        """Validate configuration file syntax"""
        errors = []
        warnings = []
        sections_validated = 0
        
        try:
            async with aiofiles.open(config_file, 'r') as f:
                content = await f.read()
            
            lines = content.split('\n')
            current_section = None
            
            for line_number, line in enumerate(lines, 1):
                line = line.strip()
                
                if not line or line.startswith(';') or line.startswith('#'):
                    continue
                
                if self.section_pattern.match(line):
                    current_section = line
                    sections_validated += 1
                elif self.option_pattern.match(line):
                    if not current_section:
                        errors.append(f"Line {line_number}: Option outside of section")
                elif line:  # Non-empty line that doesn't match patterns
                    errors.append(f"Line {line_number}: Invalid syntax: {line}")
            
            return ConfigValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                sections_validated=sections_validated
            )
            
        except Exception as e:
            return ConfigValidationResult(
                is_valid=False,
                errors=[f"Validation failed: {e}"],
                warnings=[],
                sections_validated=0
            )


class ConfigFileManager:
    """Handles file operations for configuration management"""
    
    def __init__(self, settings: Settings, logger: logging.Logger):
        self.settings = settings
        self.logger = logger
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        """Ensure required directories exist"""
        Path(self.settings.pjsip_backup_dir).mkdir(parents=True, exist_ok=True)
        Path(self.settings.pjsip_includes_dir).mkdir(parents=True, exist_ok=True)
    
    async def write_config_file(self, endpoint_id: str, content: str) -> Path:
        """Write configuration to include file"""
        include_file = Path(self.settings.pjsip_includes_dir) / f"{endpoint_id}.conf"
        
        try:
            async with aiofiles.open(include_file, 'w') as f:
                await f.write(content)
            self.logger.debug(f"Configuration written to {include_file}")
            return include_file
        except Exception as e:
            self.logger.error(f"Failed to write config file: {e}")
            raise
    
    async def update_main_config_includes(self, endpoint_id: str) -> None:
        """Update main pjsip.conf with include directive"""
        main_conf_path = Path(self.settings.pjsip_conf_path)
        include_line = f'#include "{self.settings.pjsip_includes_dir}/{endpoint_id}.conf"'
        
        try:
            # Read current content
            current_content = ""
            if main_conf_path.exists():
                async with aiofiles.open(main_conf_path, 'r') as f:
                    current_content = await f.read()
            
            # Add include if not present
            if include_line not in current_content:
                if current_content and not current_content.endswith('\n'):
                    current_content += '\n'
                current_content += f"{include_line}\n"
                
                async with aiofiles.open(main_conf_path, 'w') as f:
                    await f.write(current_content)
                
                self.logger.info(f"Added include directive for {endpoint_id}")
        
        except Exception as e:
            self.logger.error(f"Failed to update main config includes: {e}")
            raise
    
    async def remove_main_config_include(self, endpoint_id: str) -> None:
        """Remove include directive from main pjsip.conf"""
        main_conf_path = Path(self.settings.pjsip_conf_path)
        include_line = f'#include "{self.settings.pjsip_includes_dir}/{endpoint_id}.conf"'
        
        try:
            if not main_conf_path.exists():
                return
            
            async with aiofiles.open(main_conf_path, 'r') as f:
                lines = await f.readlines()
            
            filtered_lines = [line for line in lines if include_line not in line]
            
            if len(filtered_lines) != len(lines):
                async with aiofiles.open(main_conf_path, 'w') as f:
                    await f.writelines(filtered_lines)
                self.logger.info(f"Removed include directive for {endpoint_id}")
        
        except Exception as e:
            self.logger.error(f"Failed to remove include directive: {e}")
            raise


class ConfigManager:
    """Updated PJSIP configuration manager using unified template manager"""
    
    def __init__(self, settings: Settings, template_manager: UnifiedTemplateManager = None):
        self.settings = settings
        
        # Use provided template manager or create new one with PJSIP focus
        if template_manager is None:
            template_dirs = [
                Path(settings.template_dir) / "pjsip",
                Path(settings.template_dir),
            ]
            self.template_manager = UnifiedTemplateManager(template_dirs)
        else:
            self.template_manager = template_manager
            
        self.logger = logging.getLogger(f"{__name__}.ConfigManager")
        
        # Initialize other components (same as before)
        self.field_manager = FieldConfigManager()
        self.section_generator = SectionGenerator(self.template_manager, self.logger)
        self.validator = ConfigValidator(self.logger)
        self.file_manager = ConfigFileManager(settings, self.logger)

    async def _generate_identify_section_with_inheritance(
        self, 
        endpoint_id: str, 
        identify_config: Dict[str, Any], 
        base_variables: Dict[str, Any]
    ) -> str:
        """Generate identify section"""
        identify_template = identify_config.get("template", "identify-basic")
        
        identify_variables = {
            "identify_id": identify_config.get("identify_id", f"{endpoint_id}-identify"),
            "endpoint": endpoint_id,
            **base_variables,
            **identify_config
        }
        
        identify_variables.pop("template", None)
        identify_variables = {k: v for k, v in identify_variables.items() if v is not None}
        
        return await self.template_manager.render_template(identify_template, identify_variables)

    async def _generate_registration_section_with_inheritance(
        self, 
        endpoint_id: str, 
        registration_config: Dict[str, Any], 
        base_variables: Dict[str, Any]
    ) -> str:
        """Generate registration section"""
        registration_template = registration_config.get("template", "registration-basic")
        
        registration_variables = {
            "registration_id": registration_config.get("registration_id", f"{endpoint_id}-reg"),
            **base_variables,
            **registration_config
        }
        
        registration_variables.pop("template", None)
        registration_variables = {k: v for k, v in registration_variables.items() if v is not None}
        
        return await self.template_manager.render_template(registration_template, registration_variables)

    async def generate_endpoint_config(self, endpoint_config: EndpointConfig) -> ConfigGenerationResult:
        """Generate endpoint configuration with improved error handling"""
        try:
            self._validate_input(endpoint_config)
            
            # Create backup if enabled
            backup_path = await self._create_backup_if_enabled()
            
            # Process variables
            variables = self.field_manager.process_variables(endpoint_config)
            
            # Generate configuration sections
            sections = await self._generate_all_sections(endpoint_config, variables)
            
            # Generate identify section if provided
            if hasattr(endpoint_config, 'identify_config') and endpoint_config.identify_config:
                try:
                    identify_content = await self._generate_identify_section_with_inheritance(
                        endpoint_config.id, 
                        endpoint_config.identify_config, 
                        variables
                    )
                    sections['identify'] = identify_content
                    self.logger.debug("Identify section generated successfully")
                except Exception as identify_error:
                    self.logger.error(f"Failed to generate identify section: {identify_error}")

            # Generate registration section if provided
            if hasattr(endpoint_config, 'registration_config') and endpoint_config.registration_config:
                try:
                    registration_content = await self._generate_registration_section_with_inheritance(
                        endpoint_config.id, 
                        endpoint_config.registration_config, 
                        variables
                    )
                    sections['registration'] = registration_content
                    self.logger.debug("Registration section generated successfully")
                except Exception as registration_error:
                    self.logger.error(f"Failed to generate registration section: {registration_error}")
            
            # Build and write configuration
            config_content = self._build_config_content(endpoint_config, sections)
            include_file = await self.file_manager.write_config_file(endpoint_config.id, config_content)
            
            # Update main configuration
            await self.file_manager.update_main_config_includes(endpoint_config.id)
            
            # Validate if enabled
            validation_result = await self._validate_if_enabled(include_file)
            
            return ConfigGenerationResult(
                success=True,
                file_path=str(include_file),
                sections_generated=len(sections),
                backup_created=backup_path,
                validation_result=validation_result
            )
            
        except Exception as e:
            error_msg = str(e) or f"Unknown error: {type(e).__name__}"
            self.logger.error(f"Failed to generate config for {endpoint_config.id}: {error_msg}")
            raise HTTPException(status_code=500, detail=f"Configuration generation failed: {error_msg}")
    
    def _validate_input(self, endpoint_config: EndpointConfig) -> None:
        """Validate input parameters"""
        if not endpoint_config.id:
            raise ValueError("Endpoint ID is required")
        if not endpoint_config.template:
            raise ValueError("Template is required")
    
    async def _create_backup_if_enabled(self) -> str:
        """Create backup if auto-backup is enabled"""
        if getattr(self.settings, 'auto_backup', True):
            try:
                return await self.create_backup()
            except Exception as e:
                self.logger.warning(f"Backup creation failed: {e}")
        return ""
    
    async def _generate_all_sections(
        self, 
        endpoint_config: EndpointConfig, 
        variables: Dict[str, Any]
    ) -> Dict[str, str]:
        """Generate all required configuration sections"""
        sections = {}
        
        # Main endpoint section
        sections['endpoint'] = await self.section_generator.generate_section(
            'endpoint', endpoint_config.template, variables
        )
        
        # Optional sections
        section_configs = [
            ('auth', endpoint_config.auth_config),
            ('aor', endpoint_config.aor_config),
            ('transport', endpoint_config.transport_config)
        ]
        
        for section_type, config in section_configs:
            if config:
                template_name = config.get('template', f'{section_type}-basic')
                section_variables = {**variables, **config}
                sections[section_type] = await self.section_generator.generate_section(
                    section_type, template_name, section_variables
                )
        
        return sections
    
    def _build_config_content(self, endpoint_config: EndpointConfig, sections: Dict[str, str]) -> str:
        """Build complete configuration content"""
        lines = [
            f"; Generated endpoint configuration for {endpoint_config.id}",
            f"; Generated at: {datetime.now().isoformat()}",
            f"; Template: {endpoint_config.template}",
            ""
        ]
        
        # Add sections in order
        section_order = ['endpoint', 'auth', 'aor', 'transport', 'identify', 'registration']  # Added identify and registration
        for section_type in section_order:
            if section_type in sections:
                lines.extend(["", sections[section_type]])
        
        return "\n".join(lines)
    
    async def _validate_if_enabled(self, config_file: Path) -> Optional[ConfigValidationResult]:
        """Validate configuration if validation is enabled"""
        if getattr(self.settings, 'validate_configs', False):
            try:
                return await self.validator.validate_config(config_file)
            except Exception as e:
                self.logger.warning(f"Config validation failed: {e}")
        return None
    
    async def delete_endpoint_config(self, endpoint_id: str) -> bool:
        """Delete endpoint configuration"""
        try:
            # Remove include file
            include_file = Path(self.settings.pjsip_includes_dir) / f"{endpoint_id}.conf"
            if include_file.exists():
                include_file.unlink()
            
            # Remove include directive
            await self.file_manager.remove_main_config_include(endpoint_id)
            
            self.logger.info(f"Deleted configuration for endpoint {endpoint_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete config for {endpoint_id}: {e}")
            return False
    
    async def list_endpoint_configs(self) -> List[str]:
        """List all configured endpoints"""
        includes_path = Path(self.settings.pjsip_includes_dir)
        if not includes_path.exists():
            return []
        
        return sorted([f.stem for f in includes_path.glob("*.conf")])
    
    async def get_endpoint_config_content(self, endpoint_id: str) -> Optional[str]:
        """Get endpoint configuration content"""
        include_file = Path(self.settings.pjsip_includes_dir) / f"{endpoint_id}.conf"
        
        if not include_file.exists():
            return None
        
        try:
            async with aiofiles.open(include_file, 'r') as f:
                return await f.read()
        except Exception as e:
            self.logger.error(f"Failed to read config for {endpoint_id}: {e}")
            return None
    
    async def create_backup(self) -> str:
        """Create configuration backup"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = Path(self.settings.pjsip_backup_dir) / f"pjsip_backup_{timestamp}.conf"
        
        try:
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            main_conf = Path(self.settings.pjsip_conf_path)
            if main_conf.exists():
                async with aiofiles.open(main_conf, 'r') as src, \
                           aiofiles.open(backup_path, 'w') as dst:
                    content = await src.read()
                    await dst.write(content)
            
            self.logger.info(f"Created backup: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            self.logger.error(f"Failed to create backup: {e}")
            return ""
    
    async def parse_endpoint_config(self, endpoint_id: str) -> Optional[StructuredEndpoint]:
        """Parse endpoint configuration into structured format"""
        include_file = Path(self.settings.pjsip_includes_dir) / f"{endpoint_id}.conf"
        
        if not include_file.exists():
            self.logger.warning(f"Config file not found: {include_file}")
            return None
        
        try:
            async with aiofiles.open(include_file, 'r') as f:
                content = await f.read()
            
            self.logger.debug(f"Raw config content for {endpoint_id}:\n{content}")
            
            # Parse the configuration content
            sections = self._parse_config_content(content)
            self.logger.debug(f"Parsed sections for {endpoint_id}: {sections}")
            
            # Extract sections by type and original section name
            endpoint_section = {}
            auth_section = {}
            aor_section = {}
            endpoint_template_used = None
            
            for unique_key, section_data in sections.items():
                section_type = section_data.get('_section_type', section_data.get('type'))
                template_used = section_data.get('_template_used')
                original_section_name = section_data.get('_section_name', unique_key.split('#')[0])
                
                self.logger.debug(f"Processing section '{unique_key}': original_name='{original_section_name}', type='{section_type}', template='{template_used}'")
                
                if section_type == 'endpoint' and original_section_name == endpoint_id:
                    endpoint_section = section_data
                    endpoint_template_used = template_used
                    self.logger.debug(f"Found endpoint section: {endpoint_section}")
                elif section_type == 'auth' and f"{endpoint_id}-auth" in original_section_name:
                    auth_section = section_data
                    self.logger.debug(f"Found auth section: {auth_section}")
                elif section_type == 'aor' and original_section_name == endpoint_id:
                    aor_section = section_data
                    self.logger.debug(f"Found AOR section: {aor_section}")
            
            self.logger.debug(f"Final sections - Endpoint: {endpoint_section}, Auth: {auth_section}, AOR: {aor_section}")
            self.logger.debug(f"Endpoint template used: {endpoint_template_used}")
            
            # Build structured endpoint
            structured_endpoint = self._build_structured_endpoint(
                endpoint_id, 
                endpoint_section, 
                auth_section, 
                aor_section,
                endpoint_template_used
            )
            
            return structured_endpoint
            
        except Exception as e:
            self.logger.error(f"Failed to parse endpoint {endpoint_id}: {e}", exc_info=True)
            return None
    
    def _parse_config_content(self, content: str) -> Dict[str, Dict[str, str]]:
        """Parse configuration file content into sections"""
        sections = {}
        current_section = None
        current_section_type = None
        current_template_used = None
        
        lines = content.split('\n')
        self.logger.debug(f"Parsing {len(lines)} lines of config content")
        
        for line_num, line in enumerate(lines, 1):
            original_line = line
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith(';') or line.startswith('#'):
                continue
            
            self.logger.debug(f"Line {line_num}: '{original_line.strip()}'")
            
            # Section header with template reference: [section_name](template-name)
            if line.startswith('[') and '(' in line and line.endswith(')'):
                # Parse: [section_name](template-name)
                try:
                    bracket_end = line.find('](')
                    if bracket_end > 0:
                        section_name = line[1:bracket_end]
                        template_name = line[bracket_end + 2:-1]  # Remove ]( and final )
                        
                        # Create unique key using section_name + template for uniqueness
                        unique_key = f"{section_name}#{template_name}"
                        current_section = unique_key
                        current_template_used = template_name
                        
                        sections[current_section] = {
                            '_template_used': template_name,
                            '_section_name': section_name  # Store original section name
                        }
                        self.logger.debug(f"Found section with template: [{section_name}]({template_name}) -> key: {unique_key}")
                        continue
                except Exception as e:
                    self.logger.warning(f"Failed to parse section header with template: {line} - {e}")
            
            # Section header without template reference: [section_name]
            elif line.startswith('[') and line.endswith(']'):
                section_name = line[1:-1]
                current_section = section_name
                current_template_used = None
                sections[current_section] = {'_section_name': section_name}
                self.logger.debug(f"Found section without template: [{section_name}]")
                continue
            
            # Key=value pairs
            if '=' in line and current_section:
                try:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    sections[current_section][key] = value
                    
                    # Track section type to help with parsing conflicts
                    if key == 'type':
                        current_section_type = value
                        sections[current_section]['_section_type'] = value
                        self.logger.debug(f"Section '{current_section}' identified as type '{value}'")
                        
                except Exception as e:
                    self.logger.warning(f"Failed to parse key=value: {line} - {e}")
        
        self.logger.debug(f"Final parsed sections: {sections}")
        return sections
    
    def _build_structured_endpoint(
        self, 
        endpoint_id: str, 
        endpoint_section: Dict[str, str], 
        auth_section: Dict[str, str], 
        aor_section: Dict[str, str],
        template_used: Optional[str] = None
    ) -> StructuredEndpoint:
        """Build structured endpoint using schema models"""
        
        # Use schema models instead of manual construction
        audio_media = AudioMediaConfig(
            allow=endpoint_section.get('allow', 'ulaw,alaw'),
            disallow=endpoint_section.get('disallow', 'all'),
            dtmf_mode=endpoint_section.get('dtmf_mode', 'rfc4733'),
            moh_suggest=endpoint_section.get('moh_suggest'),
            tone_zone=endpoint_section.get('tone_zone', 'us'),
            allow_transfer=endpoint_section.get('allow_transfer', 'yes')
        )
        
        transport_network = TransportNetworkConfig(
            transport=endpoint_section.get('transport'),
            identify_by=endpoint_section.get('identify_by', 'username'),
            deny=endpoint_section.get('deny', ''),
            permit=endpoint_section.get('permit', ''),
            force_rport=endpoint_section.get('force_rport', 'yes'),
            rewrite_contact=endpoint_section.get('rewrite_contact', 'yes'),
            from_user=endpoint_section.get('from_user'),
            from_domain=endpoint_section.get('from_domain', ''),
            direct_media=endpoint_section.get('direct_media', 'no').lower() == 'yes',
            ice_support=endpoint_section.get('ice_support', 'no'),
            webrtc=endpoint_section.get('webrtc', 'no')
        )
        
        rtp = RTPConfig(
            rtp_symmetric=endpoint_section.get('rtp_symmetric', 'yes'),
            rtp_timeout=int(endpoint_section.get('rtp_timeout', 30)),
            rtp_timeout_hold=int(endpoint_section.get('rtp_timeout_hold', 60)),
            sdp_session=endpoint_section.get('sdp_session', 'Asterisk')
        )
        
        recording = RecordingConfig(
            record_calls=endpoint_section.get('record_calls', 'no'),
            one_touch_recording=endpoint_section.get('one_touch_recording', 'no'),
            record_on_feature=endpoint_section.get('record_on_feature', '*1'),
            record_off_feature=endpoint_section.get('record_off_feature', '*2')
        )
        
        call = CallConfig(
            context=endpoint_section.get('context', 'internal'),
            callerid=endpoint_section.get('callerid'),
            callerid_privacy=endpoint_section.get('callerid_privacy', ''),
            connected_line_method=endpoint_section.get('connected_line_method', 'invite'),
            call_group=endpoint_section.get('call_group'),
            pickup_group=endpoint_section.get('pickup_group'),
            device_state_busy_at=int(endpoint_section.get('device_state_busy_at', 1))
        )
        
        presence = PresenceConfig(
            allow_subscribe=endpoint_section.get('allow_subscribe', 'yes'),
            send_pai=endpoint_section.get('send_pai', 'yes'),
            send_rpid=endpoint_section.get('send_rpid', 'yes'),
            rel100=endpoint_section.get('100rel', 'no')
        )
        
        voicemail = VoicemailConfig(
            mailboxes=endpoint_section.get('mailboxes', ''),
            voicemail_extension=endpoint_section.get('voicemail_extension', '')
        )
        
        auth = AuthConfig(
            username=auth_section.get('username', endpoint_id),
            password=auth_section.get('password', ''),
            auth_type=auth_section.get('auth_type', 'userpass'),
            realm=auth_section.get('realm', '')
        )
        
        aor = AORConfig(
            max_contacts=int(aor_section.get('max_contacts', 1)),
            qualify_timeout=int(aor_section.get('qualify_timeout', 3)),
            qualify_frequency=int(aor_section.get('qualify_frequency', 60)),
            authenticate_qualify=aor_section.get('authenticate_qualify', 'no'),
            default_expiration=int(aor_section.get('default_expiration', 3600)),
            minimum_expiration=int(aor_section.get('minimum_expiration', 60)),
            maximum_expiration=int(aor_section.get('maximum_expiration', 7200)),
            remove_existing=aor_section.get('remove_existing', 'yes')
        )
        
        return StructuredEndpoint(
            id=endpoint_id,
            accountcode=endpoint_section.get('accountcode'),
            set_var=endpoint_section.get('set_var', ''),
            audio_media=audio_media,
            transport_network=transport_network,
            rtp=rtp,
            recording=recording,
            call=call,
            presence=presence,
            voicemail=voicemail,
            auth=auth,
            aor=aor,
            template_used=template_used
        )
    
    async def list_structured_endpoints_with_filters(
        self,
        filters: EndpointFilters,
        sort_by: SortOptions = SortOptions.ID_ASC,
        page: int = 1,
        page_size: int = 50
    ) -> EndpointListResponse:
        """List endpoints with comprehensive filtering and sorting"""
        
        # Get all endpoint IDs
        all_endpoint_ids = await self.list_endpoint_configs()
        
        # Parse all endpoints into structured format
        all_endpoints = []
        for endpoint_id in all_endpoint_ids:
            structured_endpoint = await self.parse_endpoint_config(endpoint_id)
            if structured_endpoint:
                all_endpoints.append(structured_endpoint)
        
        # Apply filters
        filtered_endpoints = self._apply_filters(all_endpoints, filters)
        
        # Apply sorting
        sorted_endpoints = self._apply_sorting(filtered_endpoints, sort_by)
        
        # Apply pagination
        total_filtered = len(sorted_endpoints)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_endpoints = sorted_endpoints[start_idx:end_idx]
        
        # Calculate pagination metadata
        total_pages = (total_filtered + page_size - 1) // page_size
        
        return EndpointListResponse(
            endpoints=paginated_endpoints,
            total_count=len(all_endpoints),
            filtered_count=total_filtered,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            filters_applied=filters.dict(exclude_none=True),
            sort_by=sort_by.value
        )
    
    def _apply_filters(self, endpoints: List[StructuredEndpoint], filters: EndpointFilters) -> List[StructuredEndpoint]:
        """Apply filters to endpoint list"""
        filtered = endpoints
        
        # Filter by ID (partial match)
        if filters.id:
            filtered = [ep for ep in filtered if filters.id.lower() in ep.id.lower()]
        
        # Filter by specific IDs
        if filters.ids:
            filtered = [ep for ep in filtered if ep.id in filters.ids]
        
        # Filter by type (based on template used or configuration)
        if filters.type and filters.type != EndpointTypeFilter.ALL:
            filtered = [ep for ep in filtered if self._determine_endpoint_type(ep) == filters.type.value]
        
        # Filter by username (partial match)
        if filters.username:
            filtered = [ep for ep in filtered if filters.username.lower() in ep.auth.username.lower()]
        
        # Filter by auth type
        if filters.auth_type and filters.auth_type != AuthTypeFilter.ALL:
            filtered = [ep for ep in filtered if ep.auth.auth_type == filters.auth_type.value]
        
        # Filter by context
        if filters.context:
            filtered = [ep for ep in filtered if ep.call.context == filters.context]
        
        # Filter by account code
        if filters.accountcode:
            filtered = [ep for ep in filtered if ep.accountcode and filters.accountcode in ep.accountcode]
        
        # Filter by transport
        if filters.transport:
            filtered = [ep for ep in filtered if ep.transport_network.transport == filters.transport]
        
        # Filter by caller ID (partial match)
        if filters.callerid:
            filtered = [ep for ep in filtered 
                       if ep.call.callerid and filters.callerid.lower() in ep.call.callerid.lower()]
        
        # Filter by template used
        if filters.template_used:
            filtered = [ep for ep in filtered if ep.template_used == filters.template_used]
        
        # Filter by max contacts (greater than or equal)
        if filters.max_contacts_gte is not None:
            filtered = [ep for ep in filtered if ep.aor.max_contacts >= filters.max_contacts_gte]
        
        # Filter by max contacts (less than or equal)
        if filters.max_contacts_lte is not None:
            filtered = [ep for ep in filtered if ep.aor.max_contacts <= filters.max_contacts_lte]
        
        # Filter by direct media
        if filters.direct_media is not None:
            filtered = [ep for ep in filtered if ep.transport_network.direct_media == filters.direct_media]
        
        # Filter by WebRTC enabled
        if filters.webrtc_enabled is not None:
            webrtc_enabled = filters.webrtc_enabled
            filtered = [ep for ep in filtered 
                       if (ep.transport_network.webrtc == "yes") == webrtc_enabled]
        
        # Filter by recording enabled
        if filters.recording_enabled is not None:
            recording_enabled = filters.recording_enabled
            filtered = [ep for ep in filtered 
                       if (ep.recording.record_calls == "yes") == recording_enabled]
        
        # Filter by creation date (if available)
        if filters.created_after:
            try:
                from datetime import datetime
                after_date = datetime.fromisoformat(filters.created_after.replace('Z', '+00:00'))
                filtered = [ep for ep in filtered 
                           if ep.created_at and ep.created_at >= after_date]
            except ValueError:
                pass  # Invalid date format, skip filter
        
        if filters.created_before:
            try:
                from datetime import datetime
                before_date = datetime.fromisoformat(filters.created_before.replace('Z', '+00:00'))
                filtered = [ep for ep in filtered 
                           if ep.created_at and ep.created_at <= before_date]
            except ValueError:
                pass  # Invalid date format, skip filter
        
        return filtered
    
    def _determine_endpoint_type(self, endpoint) -> str:
        """Determine endpoint type based on configuration"""
        try:
            # Check template used first (most reliable)
            if hasattr(endpoint, 'template_used') and endpoint.template_used:
                template = endpoint.template_used.lower()
                if "trunk" in template:
                    return "trunk"
                elif "webrtc" in template:
                    return "webrtc"
                elif "basic" in template or "endpoint" in template:
                    return "endpoint"  # Explicitly return endpoint for basic templates
            
            # Only check context if template is unclear
            if endpoint.call.context in ["from-trunk", "trunk", "external"]:
                return "trunk"
            
            return "endpoint"
        except:
            return "endpoint"
    
    def _apply_sorting(self, endpoints: List[StructuredEndpoint], sort_by: SortOptions) -> List[StructuredEndpoint]:
        """Apply sorting to endpoint list"""
        if sort_by == SortOptions.ID_ASC:
            return sorted(endpoints, key=lambda ep: ep.id)
        elif sort_by == SortOptions.ID_DESC:
            return sorted(endpoints, key=lambda ep: ep.id, reverse=True)
        elif sort_by == SortOptions.USERNAME_ASC:
            return sorted(endpoints, key=lambda ep: ep.auth.username)
        elif sort_by == SortOptions.USERNAME_DESC:
            return sorted(endpoints, key=lambda ep: ep.auth.username, reverse=True)
        elif sort_by == SortOptions.CREATED_ASC:
            return sorted(endpoints, key=lambda ep: getattr(ep, 'created_at', datetime.min) or datetime.min)
        elif sort_by == SortOptions.CREATED_DESC:
            return sorted(endpoints, key=lambda ep: getattr(ep, 'created_at', datetime.min) or datetime.min, reverse=True)
        elif sort_by == SortOptions.CONTEXT_ASC:
            return sorted(endpoints, key=lambda ep: ep.call.context)
        elif sort_by == SortOptions.CONTEXT_DESC:
            return sorted(endpoints, key=lambda ep: ep.call.context, reverse=True)
        
        return endpoints