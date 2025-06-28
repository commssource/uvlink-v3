# ============================================================================
# config.py - Application Configuration Settings
# ============================================================================

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, List
from pathlib import Path
import os


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # API Settings
    api_title: str = Field(default="PJSIP Configuration API", description="API title")
    api_version: str = Field(default="1.0.0", description="API version")
    debug: bool = Field(default=False, description="Debug mode")
    
    # Server Settings
    host: str = Field(default="0.0.0.0", description="Host to bind to")
    port: int = Field(default=8000, description="Port to bind to")
    workers: int = Field(default=1, description="Number of workers")
    
    # PJSIP Configuration Paths
    pjsip_conf_path: str = Field(
        default=os.getenv("PJSIP_CONF_PATH", "local_test/pjsip.conf"),
        description="Path to main pjsip.conf file"
    )
    pjsip_includes_dir: str = Field(
        default=os.getenv("PJSIP_INCLUDES_DIR", "local_test/includes/pjsip.d"),
        description="Directory for endpoint include files"
    )
    pjsip_backup_dir: str = Field(
        default=os.getenv("PJSIP_BACKUP_DIR", "local_test/backups"),
        description="Directory for configuration backups"
    )
    
    # Template Settings
    template_dir: str = Field(
        default="templates/pjsip",
        description="Directory containing Jinja2 templates"
    )
    
    # Feature Flags
    auto_backup: bool = Field(default=True, description="Automatically create backups")
    validate_configs: bool = Field(default=True, description="Validate generated configurations")
    
    # Security Settings
    allowed_hosts: List[str] = Field(default=["*"], description="Allowed hosts for CORS")
    api_key: Optional[str] = Field(default=None, description="API key for authentication")
    
    # Database Settings (if you want to add database support later)
    database_url: Optional[str] = Field(default=None, description="Database connection URL")
    
    # Logging Settings
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: str = Field(default="pjsip_api.log", description="Log file path")
    
    # Asterisk Integration
    asterisk_reload_command: str = Field(
        default="asterisk -rx 'pjsip reload'",
        description="Command to reload PJSIP configuration"
    )
    auto_reload_asterisk: bool = Field(
        default=False,
        description="Automatically reload Asterisk after configuration changes"
    )
    
    # Rate Limiting
    rate_limit_enabled: bool = Field(default=False, description="Enable rate limiting")
    rate_limit_requests: int = Field(default=100, description="Requests per minute")
    
    # Field Configuration
    field_config_file: str = Field(
        default="field_config.json",
        description="Path to field configuration file"
    )
    
    class Config:
        env_file = ".env"
        env_prefix = "PJSIP_"
        case_sensitive = False


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get application settings (singleton pattern)"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# Environment-specific configurations
class DevelopmentSettings(Settings):
    """Development environment settings"""
    debug: bool = True
    auto_backup: bool = False
    validate_configs: bool = False
    log_level: str = "DEBUG"
    
    # Use local paths for development
    pjsip_conf_path: str = "./dev_config/pjsip.conf"
    pjsip_includes_dir: str = "./dev_config/pjsip.d"
    pjsip_backup_dir: str = "./dev_config/backups"


class ProductionSettings(Settings):
    """Production environment settings"""
    debug: bool = False
    auto_backup: bool = True
    validate_configs: bool = True
    log_level: str = "INFO"
    workers: int = 4
    
    # Production paths
    pjsip_conf_path: str = "/etc/asterisk/pjsip.conf"
    pjsip_includes_dir: str = "/etc/asterisk/pjsip.d"
    pjsip_backup_dir: str = "/var/backups/asterisk"


class TestingSettings(Settings):
    """Testing environment settings"""
    debug: bool = True
    auto_backup: bool = False
    validate_configs: bool = True
    
    # Test paths
    pjsip_conf_path: str = "./test_config/pjsip.conf"
    pjsip_includes_dir: str = "./test_config/pjsip.d"
    pjsip_backup_dir: str = "./test_config/backups"


def get_settings_for_environment(env: str = None) -> Settings:
    """Get settings for a specific environment"""
    if env is None:
        env = os.getenv("ENVIRONMENT", "development").lower()
    
    if env == "production":
        return ProductionSettings()
    elif env == "testing":
        return TestingSettings()
    else:
        return DevelopmentSettings()


# Create directories if they don't exist
def ensure_directories(settings: Settings):
    """Ensure required directories exist"""
    directories = [
        settings.pjsip_includes_dir,
        settings.pjsip_backup_dir,
        settings.template_dir,
        Path(settings.pjsip_conf_path).parent,
        Path(settings.log_file).parent if "/" in settings.log_file else Path(".")
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)