# ============================================================================
# apps/queues/queue_manager.py - Enhanced Queue Configuration Manager
# ============================================================================

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import aiofiles
import asyncio
import re
import shutil

from config import Settings
from shared.template_manager import UnifiedTemplateManager


# ============================================================================
# Enhanced Data Models
# ============================================================================

class QueueStrategy(str, Enum):
    """Available queue strategies"""
    RINGALL = "ringall"
    LEASTRECENT = "leastrecent"
    FEWESTCALLS = "fewestcalls"
    RANDOM = "random"
    RRMEMORY = "rrmemory"
    LINEAR = "linear"
    WRANDOM = "wrandom"

@dataclass
class QueueMember:
    """Queue member configuration"""
    interface: str
    penalty: int = 0
    member_name: Optional[str] = None
    state_interface: Optional[str] = None
    paused: bool = False
    
    @property
    def extension(self) -> str:
        """Get extension (alias for member_name or interface)"""
        return self.member_name or self.interface
    
    @property
    def hint(self) -> str:
        """Get hint for the member"""
        return f"{self.interface}@default"

@dataclass
class QueueConfig:
    """Complete queue configuration"""
    name: str
    template: str = "queue-basic"
    
    # Core queue settings
    strategy: str = "ringall"
    musiconhold: str = "default"
    timeout: int = 15
    retry: int = 5
    maxlen: int = 0
    
    # Announcement settings
    announce_frequency: int = 0
    announce_holdtime: bool = False
    announce_position: bool = True
    periodic_announce_frequency: int = 0
    announce_round_seconds: int = 0
    
    # Behavior settings
    joinempty: bool = True
    leavewhenempty: bool = False
    ringinuse: bool = False
    wrapuptime: int = 0
    autopause: bool = False
    autopausedelay: int = 0
    autofill: bool = True
    
    # Service level and weight
    servicelevel: int = 60
    weight: int = 0
    
    # Context settings
    context: Optional[str] = None
    cbcontext: Optional[str] = None
    setinterfacevar: bool = False
    
    # Members and custom variables
    members: List[QueueMember] = None
    variables: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.members is None:
            self.members = []
        if self.variables is None:
            self.variables = {}

@dataclass
class QueueGenerationResult:
    """Enhanced result of queue configuration generation"""
    success: bool
    queue_name: str = ""
    file_path: str = ""
    config_path: str = ""
    backup_created: str = ""
    validation_result: Optional[Dict[str, Any]] = None
    template_variables_saved: bool = False
    errors: List[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []

@dataclass
class QueueValidationResult:
    """Queue configuration validation result"""
    valid: bool
    errors: List[str] = None
    warnings: List[str] = None
    suggestions: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
        if self.suggestions is None:
            self.suggestions = []


class QueueConfigManager:
    """Enhanced Asterisk queue configuration manager using templates"""
    
    def __init__(self, settings: Settings, template_manager: UnifiedTemplateManager = None):
        self.settings = settings
        self.template_manager = template_manager
        self.logger = logging.getLogger(f"{__name__}.QueueConfigManager")
        
        # Queue-specific paths from config.py
        self.queue_conf_path = Path(settings.queue_conf_path)
        self.queue_includes_dir = Path(settings.queue_includes_dir)
        self.queue_backup_dir = Path(settings.queue_backup_dir)
        self.queue_metadata_dir = Path(settings.queue_metadata_dir)
        
        # Configuration options from config.py
        self.auto_backup = settings.auto_backup
        self.validate_configs = settings.validate_configs
        self.max_backups = settings.max_queue_backups
        
        # Ensure directories exist
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure required directories exist"""
        for directory in [self.queue_includes_dir, self.queue_backup_dir, self.queue_metadata_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    # ============================================================================
    # Core Configuration Generation
    # ============================================================================
    
    async def generate_queue_config(self, queue_config: QueueConfig) -> QueueGenerationResult:
        """Generate queue configuration from template with enhanced error handling"""
        result = QueueGenerationResult(success=False, queue_name=queue_config.name)
        
        try:
            # Validate configuration
            validation = await self._validate_queue_config(queue_config)
            if not validation.valid:
                result.errors.extend(validation.errors)
                return result
            
            result.warnings.extend(validation.warnings)
            
            # Create backup if enabled
            if self.auto_backup:
                backup_path = await self._create_backup()
                result.backup_created = backup_path
            
            # Process variables with defaults
            variables = self._prepare_queue_variables(queue_config)
            
            # Render the template
            content = await self.template_manager.render_template(
                queue_config.template, 
                variables
            )
            
            # Add header comment
            full_content = self._add_header(queue_config, content)
            
            # Write configuration file
            config_file = await self._write_queue_file(queue_config.name, full_content)
            result.file_path = str(config_file)
            
            # Save template variables for future reference
            metadata_saved = await self._save_queue_metadata(queue_config, variables)
            result.template_variables_saved = metadata_saved
            
            # Update main queues.conf with include directive
            await self._update_main_config_includes(queue_config.name)
            
            # Validate final configuration if enabled
            if self.validate_configs:
                validation_result = await self._validate_generated_config(config_file)
                result.validation_result = validation_result
            
            result.success = True
            self.logger.info(f"Successfully generated configuration for queue '{queue_config.name}'")
            
        except Exception as e:
            error_msg = f"Failed to generate queue config for {queue_config.name}: {e}"
            self.logger.error(error_msg)
            result.errors.append(error_msg)
        
        return result
    
    async def _validate_queue_config(self, queue_config: QueueConfig) -> QueueValidationResult:
        """Enhanced queue configuration validation"""
        result = QueueValidationResult(valid=True)
        
        # Validate queue name
        if not queue_config.name:
            result.errors.append("Queue name is required")
            result.valid = False
        elif not re.match(r'^[a-zA-Z0-9_-]+$', queue_config.name):
            result.errors.append("Queue name must contain only alphanumeric characters, hyphens, and underscores")
            result.valid = False
        elif len(queue_config.name) > 80:
            result.errors.append("Queue name must be 80 characters or less")
            result.valid = False
        
        # Validate template
        if not queue_config.template:
            result.errors.append("Template is required")
            result.valid = False
        elif self.template_manager:
            available_templates = await self.template_manager.list_templates()
            if queue_config.template not in available_templates:
                result.errors.append(f"Template '{queue_config.template}' not found")
                result.valid = False
        
        # Validate strategy
        if queue_config.strategy not in [s.value for s in QueueStrategy]:
            result.warnings.append(f"Unknown strategy '{queue_config.strategy}', will use as-is")
        
        # Validate numeric values
        if queue_config.timeout < 1 or queue_config.timeout > 3600:
            result.warnings.append("Timeout should be between 1 and 3600 seconds")
        
        if queue_config.retry < 1 or queue_config.retry > 300:
            result.warnings.append("Retry should be between 1 and 300 seconds")
        
        if queue_config.maxlen < 0:
            result.errors.append("Maximum length cannot be negative")
            result.valid = False
        
        # Validate members
        for i, member in enumerate(queue_config.members):
            if not member.interface:
                result.errors.append(f"Member {i+1}: Interface is required")
                result.valid = False
            elif not re.match(r'^[a-zA-Z0-9/_-]+$', member.interface):
                result.warnings.append(f"Member {i+1}: Interface '{member.interface}' contains unusual characters")
            
            if member.penalty < 0 or member.penalty > 999:
                result.warnings.append(f"Member {i+1}: Penalty should be between 0 and 999")
        
        # Check for duplicate member interfaces
        interfaces = [m.interface for m in queue_config.members]
        duplicates = set([x for x in interfaces if interfaces.count(x) > 1])
        if duplicates:
            result.warnings.append(f"Duplicate member interfaces found: {', '.join(duplicates)}")
        
        # Suggestions
        if queue_config.maxlen == 0:
            result.suggestions.append("Consider setting a maximum queue length to prevent unlimited queuing")
        
        if queue_config.wrapuptime == 0 and queue_config.strategy in ["ringall", "leastrecent"]:
            result.suggestions.append("Consider setting wrap-up time to prevent immediate re-queuing of calls")
        
        return result
    
    def _prepare_queue_variables(self, queue_config: QueueConfig) -> Dict[str, Any]:
        """Prepare variables with defaults for queue configuration"""
        # Convert QueueConfig to dict
        variables = asdict(queue_config)
        
        # Remove non-template fields
        variables.pop('template', None)
        variables.pop('members', None)
        variables.pop('variables', None)
        
        # Add member data in template-friendly format
        variables['members'] = []
        for member in queue_config.members:
            member_data = {
                'interface': f"PJSIP/{member.interface}" if not member.interface.startswith('PJSIP/') else member.interface,
                'penalty': member.penalty,
                'member_name': member.member_name or member.interface,
                'state_interface': member.state_interface,
                'paused': member.paused
            }
            variables['members'].append(member_data)
        
        # Convert boolean values to yes/no for Asterisk
        boolean_fields = ['announce_holdtime', 'announce_position', 'joinempty', 'leavewhenempty', 
                         'ringinuse', 'autopause', 'autofill', 'setinterfacevar']
        for field in boolean_fields:
            if field in variables and isinstance(variables[field], bool):
                variables[field] = 'yes' if variables[field] else 'no'
        
        # Add custom variables
        variables.update(queue_config.variables)
        
        return variables
    
    def _add_header(self, queue_config: QueueConfig, content: str) -> str:
        """Add enhanced header comment to configuration"""
        header = [
            f"; Queue configuration for '{queue_config.name}'",
            f"; Generated at: {datetime.now().isoformat()}",
            f"; Template: {queue_config.template}",
            f"; Strategy: {queue_config.strategy}",
            f"; Members: {len(queue_config.members)}",
            ";",
            "; This file was auto-generated. Manual changes may be overwritten.",
            "; Use the queue management API to make changes.",
            "",
            content
        ]
        return "\n".join(header)
    
    async def _write_queue_file(self, queue_name: str, content: str) -> Path:
        """Write queue configuration to include file with atomic operation"""
        queue_file = self.queue_includes_dir / f"{queue_name}.conf"
        temp_file = queue_file.with_suffix('.tmp')
        
        try:
            # Write to temporary file first
            async with aiofiles.open(temp_file, 'w') as f:
                await f.write(content)
            
            # Atomically move to final location
            temp_file.rename(queue_file)
            
            self.logger.debug(f"Queue configuration written to {queue_file}")
            return queue_file
            
        except Exception as e:
            # Clean up temp file if it exists
            if temp_file.exists():
                temp_file.unlink()
            self.logger.error(f"Failed to write queue config file: {e}")
            raise
    
    async def _save_queue_metadata(self, queue_config: QueueConfig, variables: Dict[str, Any]) -> bool:
        """Save queue metadata and template variables for future reference"""
        try:
            metadata_file = self.queue_metadata_dir / f"{queue_config.name}.json"
            
            metadata = {
                'queue_name': queue_config.name,
                'template': queue_config.template,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'original_config': asdict(queue_config),
                'template_variables': variables,
                'version': '1.0'
            }
            
            async with aiofiles.open(metadata_file, 'w') as f:
                await f.write(json.dumps(metadata, indent=2, default=str))
            
            self.logger.debug(f"Queue metadata saved to {metadata_file}")
            return True
            
        except Exception as e:
            self.logger.warning(f"Failed to save queue metadata: {e}")
            return False
    
    # ============================================================================
    # Configuration Retrieval and Parsing
    # ============================================================================
    
    async def get_queue_metadata(self, queue_name: str) -> Optional[Dict[str, Any]]:
        """Get stored queue metadata and template variables"""
        metadata_file = self.queue_metadata_dir / f"{queue_name}.json"
        
        if not metadata_file.exists():
            return None
        
        try:
            async with aiofiles.open(metadata_file, 'r') as f:
                content = await f.read()
                return json.loads(content)
        except Exception as e:
            self.logger.error(f"Failed to read queue metadata for {queue_name}: {e}")
            return None
    
    async def get_queue_config_object(self, queue_name: str) -> Optional[QueueConfig]:
        """Get queue configuration as QueueConfig object"""
        metadata = await self.get_queue_metadata(queue_name)
        if not metadata or 'original_config' not in metadata:
            return None
        
        try:
            config_data = metadata['original_config']
            
            # Convert members list back to QueueMember objects
            if 'members' in config_data:
                members = []
                for member_data in config_data['members']:
                    if isinstance(member_data, dict):
                        members.append(QueueMember(**member_data))
                    else:
                        # Handle legacy format
                        members.append(QueueMember(interface=str(member_data)))
                config_data['members'] = members
            
            return QueueConfig(**config_data)
            
        except Exception as e:
            self.logger.error(f"Failed to reconstruct QueueConfig for {queue_name}: {e}")
            return None
    
    async def parse_queue_config_from_content(self, queue_name: str, content: str) -> Optional[Dict[str, Any]]:
        """Parse queue configuration from rendered content"""
        try:
            config_data = {
                "name": queue_name,
                "context": None,
                "cbcontext": None,
                "setinterfacevar": False,
                "maxlen": 0,
                "timeout": 15,
                "joinempty": True,
                "leavewhenempty": False,
                "announce_holdtime": False,
                "announce_position": False,
                "announce_frequency": 0,
                "announce_round_seconds": 0,
                "members": [],
                "strategy": "ringall",
                "autofill": True,
                "ringinuse": False,
                "retry": 5,
                "wrapuptime": 0,
                "announce": None,
                "musiconhold": "default",
                "servicelevel": 60,
                "weight": 0,
                "autopause": False
            }
            
            lines = content.split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                
                # Skip comments and empty lines
                if not line or line.startswith(';') or line.startswith('#'):
                    continue
                
                # Handle section headers
                if line.startswith('[') and line.endswith(']'):
                    current_section = line[1:-1]
                    if current_section != queue_name:
                        config_data["name"] = current_section
                    continue
                
                # Handle member lines
                if line.startswith('member ') and '=>' in line:
                    member_spec = line.split('=>', 1)[1].strip()
                    member = self._parse_member_line(member_spec)
                    if member:
                        config_data["members"].append(member)
                    continue
                
                # Handle key=value pairs
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Map configuration keys
                    self._map_config_key_value(config_data, key, value)
            
            return config_data
            
        except Exception as e:
            self.logger.warning(f"Failed to parse queue config content for {queue_name}: {e}")
            return None
    
    def _parse_member_line(self, member_spec: str) -> Optional[Dict[str, Any]]:
        """Parse a member line from queue configuration"""
        try:
            parts = member_spec.split(',')
            if not parts:
                return None
            
            # Extract interface
            full_interface = parts[0].strip()
            interface = full_interface.replace('PJSIP/', '') if full_interface.startswith('PJSIP/') else full_interface
            
            # Parse additional fields
            penalty = 0
            extension = interface
            hint = f"{interface}@default"
            
            if len(parts) >= 2 and parts[1].strip().isdigit():
                penalty = int(parts[1].strip())
            if len(parts) >= 3 and parts[2].strip():
                extension = parts[2].strip()
            if len(parts) >= 4 and parts[3].strip():
                hint = parts[3].strip()
            
            return {
                "extension": extension,
                "interface": interface,
                "hint": hint,
                "penalty": penalty
            }
            
        except Exception as e:
            self.logger.warning(f"Failed to parse member line '{member_spec}': {e}")
            return None
    
    def _map_config_key_value(self, config_data: Dict[str, Any], key: str, value: str):
        """Map configuration key-value pairs to config_data"""
        # Boolean mappings
        boolean_keys = {
            'setinterfacevar': 'setinterfacevar',
            'joinempty': 'joinempty',
            'leavewhenempty': 'leavewhenempty',
            'announce-holdtime': 'announce_holdtime',
            'announce-position': 'announce_position',
            'autofill': 'autofill',
            'ringinuse': 'ringinuse',
            'autopause': 'autopause'
        }
        
        # Integer mappings
        integer_keys = {
            'maxlen': 'maxlen',
            'timeout': 'timeout',
            'announce-frequency': 'announce_frequency',
            'announce-round-seconds': 'announce_round_seconds',
            'periodic-announce-frequency': 'announce_frequency',  # Fallback
            'retry': 'retry',
            'wrapuptime': 'wrapuptime',
            'servicelevel': 'servicelevel',
            'weight': 'weight'
        }
        
        # String mappings
        string_keys = {
            'context': 'context',
            'cbcontext': 'cbcontext',
            'strategy': 'strategy',
            'announce': 'announce',
            'musiconhold': 'musiconhold'
        }
        
        # Apply mappings
        if key in boolean_keys:
            config_data[boolean_keys[key]] = value.lower() in ['yes', 'true', '1']
        elif key in integer_keys:
            try:
                config_data[integer_keys[key]] = int(value) if value.isdigit() else config_data.get(integer_keys[key], 0)
            except ValueError:
                pass
        elif key in string_keys:
            config_data[string_keys[key]] = value
    
    # ============================================================================
    # Enhanced Backup and Validation
    # ============================================================================
    
    async def create_backup(self) -> str:
        """Create comprehensive queue configuration backup"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.queue_backup_dir / f"backup_{timestamp}"
        backup_dir.mkdir(exist_ok=True)
        
        try:
            files_backed_up = []
            
            # Backup main queues.conf
            if self.queue_conf_path.exists():
                main_backup = backup_dir / "queues.conf"
                shutil.copy2(self.queue_conf_path, main_backup)
                files_backed_up.append("queues.conf")
            
            # Backup all queue include files
            if self.queue_includes_dir.exists():
                includes_backup = backup_dir / "queues.d"
                shutil.copytree(self.queue_includes_dir, includes_backup, dirs_exist_ok=True)
                files_backed_up.extend([f.name for f in self.queue_includes_dir.glob("*.conf")])
            
            # Backup metadata
            if self.queue_metadata_dir.exists():
                metadata_backup = backup_dir / "metadata"
                shutil.copytree(self.queue_metadata_dir, metadata_backup, dirs_exist_ok=True)
                files_backed_up.extend([f.name for f in self.queue_metadata_dir.glob("*.json")])
            
            # Create backup manifest
            manifest = {
                'timestamp': timestamp,
                'created_at': datetime.now().isoformat(),
                'files_backed_up': files_backed_up,
                'backup_path': str(backup_dir)
            }
            
            manifest_file = backup_dir / "backup_manifest.json"
            async with aiofiles.open(manifest_file, 'w') as f:
                await f.write(json.dumps(manifest, indent=2))
            
            # Clean up old backups
            await self._cleanup_old_backups()
            
            self.logger.info(f"Created comprehensive backup: {backup_dir}")
            return str(backup_dir)
            
        except Exception as e:
            self.logger.error(f"Failed to create backup: {e}")
            # Clean up partial backup
            if backup_dir.exists():
                shutil.rmtree(backup_dir, ignore_errors=True)
            return ""
    
    async def _cleanup_old_backups(self):
        """Clean up old backup directories"""
        try:
            if not self.queue_backup_dir.exists():
                return
            
            # Get all backup directories
            backup_dirs = [d for d in self.queue_backup_dir.iterdir() 
                          if d.is_dir() and d.name.startswith('backup_')]
            
            # Sort by creation time (newest first)
            backup_dirs.sort(key=lambda x: x.stat().st_ctime, reverse=True)
            
            # Remove old backups beyond max_backups
            for old_backup in backup_dirs[self.max_backups:]:
                shutil.rmtree(old_backup, ignore_errors=True)
                self.logger.info(f"Removed old backup: {old_backup}")
                
        except Exception as e:
            self.logger.warning(f"Failed to cleanup old backups: {e}")
    
    async def _validate_generated_config(self, config_file: Path) -> Dict[str, Any]:
        """Validate generated configuration file"""
        try:
            async with aiofiles.open(config_file, 'r') as f:
                content = await f.read()
            
            validation_result = {
                'valid': True,
                'errors': [],
                'warnings': [],
                'file_size': len(content),
                'line_count': len(content.splitlines())
            }
            
            # Basic structure validation
            if not content.strip():
                validation_result['valid'] = False
                validation_result['errors'].append("Configuration file is empty")
                return validation_result
            
            # Check for section headers
            if not re.search(r'\[.+\]', content):
                validation_result['valid'] = False
                validation_result['errors'].append("No queue sections found in configuration")
            
            # Check for basic queue parameters
            required_params = ['strategy']
            for param in required_params:
                if param not in content:
                    validation_result['warnings'].append(f"Parameter '{param}' not found in configuration")
            
            # Validate member syntax
            member_lines = re.findall(r'member\s*=>\s*(.+)', content)
            for i, member_line in enumerate(member_lines):
                if not re.match(r'^[A-Za-z0-9/_-]+', member_line.strip()):
                    validation_result['warnings'].append(f"Member {i+1} has unusual interface format: {member_line}")
            
            return validation_result
            
        except Exception as e:
            return {
                'valid': False,
                'errors': [f"Validation failed: {e}"],
                'warnings': [],
                'file_size': 0,
                'line_count': 0
            }
    
    # ============================================================================
    # Enhanced Queue Management Operations
    # ============================================================================
    
    async def update_queue_config(self, queue_name: str, updates: Dict[str, Any]) -> QueueGenerationResult:
        """Update existing queue configuration"""
        try:
            # Get existing configuration
            existing_config = await self.get_queue_config_object(queue_name)
            if not existing_config:
                raise ValueError(f"Queue '{queue_name}' not found")
            
            # Check if name is being changed
            new_name = updates.get('name', queue_name)
            name_changed = new_name != queue_name
            
            # If name is changing, check if new name already exists
            if name_changed:
                existing_queues = await self.list_queue_configs()
                if new_name in existing_queues:
                    raise ValueError(f"Queue '{new_name}' already exists")
            
            # Apply updates
            for key, value in updates.items():
                if hasattr(existing_config, key):
                    setattr(existing_config, key, value)
                else:
                    # Add to custom variables
                    existing_config.variables[key] = value
            
            # Update timestamp in metadata
            existing_config.variables['updated_at'] = datetime.now().isoformat()
            
            # Generate configuration with new name
            result = await self.generate_queue_config(existing_config)
            
            # If name changed and new config was created successfully, delete old queue
            if name_changed and result.success:
                old_deletion_success = await self.delete_queue_config(queue_name)
                if old_deletion_success:
                    self.logger.info(f"Successfully deleted old queue '{queue_name}' after renaming to '{new_name}'")
                    if result.warnings is None:
                        result.warnings = []
                    result.warnings.append(f"Old queue '{queue_name}' was automatically deleted")
                else:
                    self.logger.warning(f"Failed to delete old queue '{queue_name}' after renaming to '{new_name}'")
                    if result.warnings is None:
                        result.warnings = []
                    result.warnings.append(f"Warning: Old queue '{queue_name}' may still exist")
            
            return result
            
        except Exception as e:
            result = QueueGenerationResult(success=False, queue_name=queue_name)
            result.errors.append(f"Failed to update queue: {e}")
            return result
    
    async def add_queue_member(self, queue_name: str, member: QueueMember) -> bool:
        """Add member to existing queue"""
        try:
            existing_config = await self.get_queue_config_object(queue_name)
            if not existing_config:
                return False
            
            # Check if member already exists
            for existing_member in existing_config.members:
                if existing_member.interface == member.interface:
                    self.logger.warning(f"Member {member.interface} already exists in queue {queue_name}")
                    return False
            
            # Add new member
            existing_config.members.append(member)
            
            # Regenerate configuration
            result = await self.generate_queue_config(existing_config)
            return result.success
            
        except Exception as e:
            self.logger.error(f"Failed to add member to queue {queue_name}: {e}")
            return False
    
    async def remove_queue_member(self, queue_name: str, interface: str) -> bool:
        """Remove member from existing queue"""
        try:
            existing_config = await self.get_queue_config_object(queue_name)
            if not existing_config:
                return False
            
            # Find and remove member
            original_count = len(existing_config.members)
            existing_config.members = [m for m in existing_config.members if m.interface != interface]
            
            if len(existing_config.members) == original_count:
                self.logger.warning(f"Member {interface} not found in queue {queue_name}")
                return False
            
            # Regenerate configuration
            result = await self.generate_queue_config(existing_config)
            return result.success
            
        except Exception as e:
            self.logger.error(f"Failed to remove member from queue {queue_name}: {e}")
            return False
    
    # ============================================================================
    # Existing Methods (Enhanced)
    # ============================================================================
    
    async def delete_queue_config(self, queue_name: str) -> bool:
        """Delete queue configuration with cleanup"""
        try:
            success = True
            
            # Remove include file
            queue_file = self.queue_includes_dir / f"{queue_name}.conf"
            if queue_file.exists():
                queue_file.unlink()
            else:
                success = False
            
            # Remove metadata file
            metadata_file = self.queue_metadata_dir / f"{queue_name}.json"
            if metadata_file.exists():
                metadata_file.unlink()
            
            # Remove include directive
            await self._remove_main_config_include(queue_name)
            
            if success:
                self.logger.info(f"Deleted configuration for queue {queue_name}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to delete config for queue {queue_name}: {e}")
            return False
    
    async def _update_main_config_includes(self, queue_name: str):
        """Update main queues.conf with include directive"""
        include_line = f'#include "{self.queue_includes_dir}/{queue_name}.conf"'
        
        try:
            current_content = ""
            if self.queue_conf_path.exists():
                async with aiofiles.open(self.queue_conf_path, 'r') as f:
                    current_content = await f.read()
            
            if include_line not in current_content:
                if current_content and not current_content.endswith('\n'):
                    current_content += '\n'
                current_content += f"{include_line}\n"
                
                # Write atomically
                temp_file = self.queue_conf_path.with_suffix('.tmp')
                async with aiofiles.open(temp_file, 'w') as f:
                    await f.write(current_content)
                temp_file.rename(self.queue_conf_path)
                
                self.logger.info(f"Added include directive for queue {queue_name}")
        
        except Exception as e:
            self.logger.error(f"Failed to update main queue config includes: {e}")
            raise
    
    async def _remove_main_config_include(self, queue_name: str):
        """Remove include directive from main queues.conf"""
        include_line = f'#include "{self.queue_includes_dir}/{queue_name}.conf"'
        
        try:
            if not self.queue_conf_path.exists():
                return
            
            async with aiofiles.open(self.queue_conf_path, 'r') as f:
                lines = await f.readlines()
            
            filtered_lines = [line for line in lines if include_line not in line]
            
            if len(filtered_lines) != len(lines):
                # Write atomically
                temp_file = self.queue_conf_path.with_suffix('.tmp')
                async with aiofiles.open(temp_file, 'w') as f:
                    await f.writelines(filtered_lines)
                temp_file.rename(self.queue_conf_path)
                
                self.logger.info(f"Removed include directive for queue {queue_name}")
        
        except Exception as e:
            self.logger.error(f"Failed to remove include directive: {e}")
            raise
    
    async def list_queue_configs(self) -> List[str]:
        """List all configured queues"""
        if not self.queue_includes_dir.exists():
            return []
        
        return sorted([f.stem for f in self.queue_includes_dir.glob("*.conf")])
    
    async def get_queue_config_content(self, queue_name: str) -> Optional[str]:
        """Get queue configuration content"""
        queue_file = self.queue_includes_dir / f"{queue_name}.conf"
        
        if not queue_file.exists():
            return None
        
        try:
            async with aiofiles.open(queue_file, 'r') as f:
                return await f.read()
        except Exception as e:
            self.logger.error(f"Failed to read config for queue {queue_name}: {e}")
            return None
    
    # ============================================================================
    # Statistics and Health Checks
    # ============================================================================
    
    async def get_queue_statistics(self) -> Dict[str, Any]:
        """Get comprehensive queue statistics"""
        try:
            queue_names = await self.list_queue_configs()
            
            stats = {
                'total_queues': len(queue_names),
                'queues_with_metadata': 0,
                'total_members': 0,
                'queues_by_strategy': {},
                'average_members_per_queue': 0,
                'health_status': 'healthy'
            }
            
            for queue_name in queue_names:
                # Check metadata
                metadata = await self.get_queue_metadata(queue_name)
                if metadata:
                    stats['queues_with_metadata'] += 1
                    
                    # Count members and strategy
                    original_config = metadata.get('original_config', {})
                    members = original_config.get('members', [])
                    stats['total_members'] += len(members)
                    
                    strategy = original_config.get('strategy', 'unknown')
                    stats['queues_by_strategy'][strategy] = stats['queues_by_strategy'].get(strategy, 0) + 1
            
            # Calculate averages
            if stats['total_queues'] > 0:
                stats['average_members_per_queue'] = round(stats['total_members'] / stats['total_queues'], 2)
            
            # Health check
            if stats['queues_with_metadata'] < stats['total_queues']:
                stats['health_status'] = 'warning'
                stats['health_message'] = f"{stats['total_queues'] - stats['queues_with_metadata']} queues missing metadata"
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get queue statistics: {e}")
            return {'error': str(e), 'health_status': 'error'}
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on queue configuration system"""
        health = {
            'status': 'healthy',
            'checks': {},
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            # Check directories
            health['checks']['directories'] = {
                'queue_includes_dir': self.queue_includes_dir.exists(),
                'queue_backup_dir': self.queue_backup_dir.exists(),
                'queue_metadata_dir': self.queue_metadata_dir.exists()
            }
            
            # Check template manager
            health['checks']['template_manager'] = self.template_manager is not None
            
            # Check file permissions
            health['checks']['permissions'] = {
                'can_write_includes': os.access(self.queue_includes_dir, os.W_OK),
                'can_write_backups': os.access(self.queue_backup_dir, os.W_OK),
                'can_write_metadata': os.access(self.queue_metadata_dir, os.W_OK)
            }
            
            # Count configurations
            queue_count = len(await self.list_queue_configs())
            health['checks']['queue_count'] = queue_count
            
            # Overall status
            if not all(health['checks']['directories'].values()):
                health['status'] = 'error'
                health['message'] = 'Required directories missing'
            elif not all(health['checks']['permissions'].values()):
                health['status'] = 'warning'
                health['message'] = 'Permission issues detected'
            elif not health['checks']['template_manager']:
                health['status'] = 'warning'
                health['message'] = 'Template manager not available'
            
        except Exception as e:
            health['status'] = 'error'
            health['message'] = f'Health check failed: {e}'
        
        return health