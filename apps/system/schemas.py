# ============================================================================
# apps/system/schemas.py - Fixed for Pydantic v2
# ============================================================================

from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

class StatusResponse(BaseModel):
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None

class ReloadResponse(BaseModel):
    success: bool
    message: str
    output: Optional[str] = None

class ConfigResponse(BaseModel):
    success: bool
    config: str
    timestamp: datetime

class BackupInfo(BaseModel):
    filename: str
    size: int
    created: str
    app: str

class SystemHealth(BaseModel):
    status: str
    asterisk_version: Optional[str] = None
    database_status: str
    disk_usage: Dict[str, Any]
    memory_usage: Dict[str, Any]
    active_apps: List[str]