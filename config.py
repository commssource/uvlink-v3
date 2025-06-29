# ============================================================================
# config.py - Updated to properly use environment variables
# ============================================================================

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, List
from pathlib import Path
import os


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Application Metadata
    app_name: str = Field(default="Asterisk Configuration Manager", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")
    environment: str = Field(default="development", description="Environment")
    
    # Server Settings
    host: str = Field(default="0.0.0.0", description="Host to bind to")
    port: int = Field(default=8000, description="Port to bind to")
    workers: int = Field(default=1, description="Number of workers")
    
    # PJSIP Configuration Paths - Updated to use environment variables properly
    pjsip_conf_path: str = Field(
        default="local_test/pjsip.conf",
        description="Path to main pjsip.conf file"
    )
    pjsip_includes_dir: str = Field(
        default="local_test/includes/pjsip.d",
        description="Directory for endpoint include files"
    )
    pjsip_backup_dir: str = Field(
        default="local_test/backups/pjsip",
        description="Directory for configuration backups"
    )

   # Queue-specific paths
    queue_conf_path: str = os.getenv("QUEUE_CONF_PATH", "local_test/queues.conf")   
    queue_includes_dir: str = os.getenv("QUEUE_INCLUDES_DIR", "local_test/includes/queues.d")
    queue_backup_dir: str = os.getenv("QUEUE_BACKUP_DIR", "local_test/backups/queues")
    queue_metadata_dir: str = os.getenv("QUEUE_METADATA_DIR", "local_test/queue_metadata")
    
    # Queue configuration options
    auto_backup: bool = True
    validate_configs: bool = True
    max_queue_backups: int = 10

    # Template directories
    template_root: str = Field(default="templates", description="Base template directory")
    template_dir: str = Field(default="templates", description="Base template directory")  # Keep for compatibility
    pjsip_template_dir: str = Field(default="templates/pjsip", description="PJSIP template directory")
    queue_template_dir: str = Field(default="templates/queues", description="Queue template directory")
    
    # Feature Flags
    auto_backup: bool = Field(default=True, description="Automatically create backups")
    validate_configs: bool = Field(default=True, description="Validate generated configurations")
    auto_reload_asterisk: bool = Field(default=False, description="Auto-reload Asterisk after changes")
    
    # Security Settings
    allowed_hosts: List[str] = Field(default=["*"], description="Allowed hosts for CORS")
    api_key: Optional[str] = Field(default=None, description="API key for authentication")
    
    # Logging Settings
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: Optional[str] = Field(default=None, description="Log file path")
    
    # Asterisk Integration
    asterisk_reload_command: str = Field(
        default="asterisk -rx 'pjsip reload'",
        description="Command to reload PJSIP configuration"
    )
    
    # AMI Settings (for queue monitoring)
    ami_enabled: bool = Field(default=False, description="Enable AMI for queue monitoring")
    ami_host: str = Field(default="localhost", description="AMI host")
    ami_port: int = Field(default=5038, description="AMI port")
    ami_username: str = Field(default="admin", description="AMI username")
    ami_password: str = Field(default="", description="AMI password")
    
    # Performance Settings
    max_concurrent_operations: int = Field(default=10, description="Max concurrent operations")
    operation_timeout: int = Field(default=60, description="Operation timeout in seconds")
    
    class Config:
        env_file = ".env"
        env_prefix = "ASTERISK_"
        case_sensitive = False
    
    def get_template_directories(self) -> List[Path]:
        """Get ordered list of template directories for UnifiedTemplateManager"""
        return [
            Path(self.template_root),
            Path(self.pjsip_template_dir),
            Path(self.queue_template_dir),
            Path(self.template_root) / "shared",
        ]
    
    def ensure_directories(self):
        """Ensure all required directories exist"""
        directories = [
            self.pjsip_includes_dir,
            self.pjsip_backup_dir,
            self.queue_includes_dir,
            self.queue_backup_dir,
            self.template_dir,
            self.pjsip_template_dir,
            self.queue_template_dir,
            Path(self.pjsip_conf_path).parent,
            Path(self.queue_conf_path).parent,
        ]
        
        if self.log_file:
            directories.append(Path(self.log_file).parent)
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    def setup_logging(self):
        """Setup application logging"""
        import logging
        
        # Configure logging
        log_level = getattr(logging, self.log_level.upper(), logging.INFO)
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                *([logging.FileHandler(self.log_file)] if self.log_file else [])
            ]
        )
    
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.debug or self.environment.lower() in ['development', 'dev']
    
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.environment.lower() in ['production', 'prod']
    
    def get_uvicorn_config(self) -> dict:
        """Get Uvicorn server configuration"""
        return {
            "host": self.host,
            "port": self.port,
            "workers": self.workers if self.is_production() else 1,
            "reload": self.debug and not self.is_production(),
            "log_level": self.log_level.lower(),
        }


# Environment-specific settings
class DevelopmentSettings(Settings):
    """Development environment settings"""
    debug: bool = True
    environment: str = "development"
    log_level: str = "DEBUG"
    auto_backup: bool = False
    validate_configs: bool = False


class ProductionSettings(Settings):
    """Production environment settings"""
    debug: bool = False
    environment: str = "production" 
    log_level: str = "INFO"
    workers: int = 4
    auto_backup: bool = True
    validate_configs: bool = True
    auto_reload_asterisk: bool = True
    
    # Production paths - override defaults
    pjsip_conf_path: str = "/etc/asterisk/pjsip.conf"
    pjsip_includes_dir: str = "/etc/asterisk/pjsip.d"
    pjsip_backup_dir: str = "/var/backups/asterisk/pjsip"
    queue_conf_path: str = "/etc/asterisk/queues.conf"
    queue_includes_dir: str = "/etc/asterisk/queues.d"
    queue_backup_dir: str = "/var/backups/asterisk/queues"
    template_root: str = "/etc/asterisk-templates"
    pjsip_template_dir: str = "/etc/asterisk-templates/pjsip"
    queue_template_dir: str = "/etc/asterisk-templates/queues"
    log_file: str = "/var/log/asterisk/config-manager.log"


# Settings factory
_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    """Get application settings (singleton pattern)"""
    global _settings_instance
    if _settings_instance is None:
        environment = os.getenv("ASTERISK_ENVIRONMENT", "development").lower()
        
        if environment in ["production", "prod"]:
            _settings_instance = ProductionSettings()
        elif environment in ["development", "dev"]:
            _settings_instance = DevelopmentSettings()
        else:
            _settings_instance = Settings()
        
        # Ensure directories exist and setup logging
        _settings_instance.ensure_directories()
        _settings_instance.setup_logging()
    
    return _settings_instance


def get_current_settings() -> Settings:
    """Get current settings - alias for get_settings()"""
    return get_settings()


def print_configuration_summary(settings: Settings):
    """Print a summary of the current configuration"""
    print(f"""
🚀 {settings.app_name} v{settings.app_version}

🌍 Environment: {settings.environment.upper()}
🐛 Debug Mode: {'✅ Enabled' if settings.debug else '❌ Disabled'}
📊 Log Level: {settings.log_level}

🌐 Server: {settings.host}:{settings.port}
👥 Workers: {settings.workers}

📁 Configuration Paths:
  • PJSIP Config: {settings.pjsip_conf_path}
  • PJSIP Includes: {settings.pjsip_includes_dir}
  • Queue Config: {settings.queue_conf_path}
  • Queue Includes: {settings.queue_includes_dir}
  • Templates: {settings.template_root}
  • Backups: PJSIP({settings.pjsip_backup_dir}), Queues({settings.queue_backup_dir})

🔧 Features:
  • Auto Backup: {'✅' if settings.auto_backup else '❌'}
  • Config Validation: {'✅' if settings.validate_configs else '❌'}
  • Auto Reload: {'✅' if settings.auto_reload_asterisk else '❌'}
  • AMI: {'✅' if settings.ami_enabled else '❌'}
""")


if __name__ == "__main__":
    # Test the configuration
    settings = get_current_settings()
    print_configuration_summary(settings)
    print("✅ Configuration loaded successfully!")