# ============================================================================
# apps/endpoints/dependencies.py - Endpoints app dependencies
# ============================================================================

from functools import lru_cache
from typing import Optional
from fastapi import HTTPException, Depends
from config import get_settings
from .pjsip_manager.template_manager import TemplateManager
from .pjsip_manager.config_manager import ConfigManager

# App-specific manager instances
_template_manager: Optional[TemplateManager] = None
_config_manager: Optional[ConfigManager] = None

def initialize_pjsip_managers():
    """Initialize PJSIP managers - called from main.py startup"""
    global _template_manager, _config_manager
    
    settings = get_settings()
    if not settings.pjsip_enabled:
        return
    
    _template_manager = TemplateManager(settings)
    _config_manager = ConfigManager(settings, _template_manager)

async def load_initial_templates():
    """Load initial templates - called from main.py startup"""
    if _template_manager:
        await _template_manager.load_templates()

async def get_template_manager() -> TemplateManager:
    """Get the template manager instance"""
    if _template_manager is None:
        raise HTTPException(
            status_code=503, 
            detail="PJSIP template manager not initialized or disabled"
        )
    return _template_manager

async def get_config_manager() -> ConfigManager:
    """Get the config manager instance"""
    if _config_manager is None:
        raise HTTPException(
            status_code=503, 
            detail="PJSIP config manager not initialized or disabled"
        )
    return _config_manager

def get_pjsip_settings():
    """Get PJSIP-specific settings"""
    return get_settings()