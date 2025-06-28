# ============================================================================
# shared/models.py - Add base PJSIP models to existing shared models
# ============================================================================

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

# Add these to your existing shared/models.py

class TemplateType(str, Enum):
    ENDPOINT = "endpoint"
    AUTH = "auth"
    AOR = "aor"
    TRANSPORT = "transport"
    IDENTIFY = "identify"

class BaseConfigModel(BaseModel):
    """Base model for all PJSIP configurations"""
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = Field(default_factory=datetime.now)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ConfigValidationResult(BaseModel):
    """Configuration validation result"""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    sections_validated: int = 0

class ConfigGenerationResult(BaseModel):
    """Configuration generation result"""
    success: bool
    file_path: str
    sections_generated: int
    backup_created: Optional[str] = None
    validation_result: Optional[ConfigValidationResult] = None