# ============================================================================
# shared/utils.py - Common utilities
# ============================================================================

import subprocess
import os
import shutil
from datetime import datetime
from pathlib import Path
import logging
from typing import Tuple
from fastapi import HTTPException

from config import ASTERISK_USER, ASTERISK_BACKUP_PATH

logger = logging.getLogger(__name__)

def execute_asterisk_command(command: str) -> Tuple[bool, str]:
    """Execute Asterisk CLI command"""
    try:
        full_command = ["sudo", "-u", ASTERISK_USER, "asterisk", "-rx", command]
        result = subprocess.run(
            full_command,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        success = result.returncode == 0
        output = result.stdout if success else result.stderr
        
        logger.info(f"Asterisk command '{command}' - Success: {success}")
        return success, output
        
    except subprocess.TimeoutExpired:
        logger.error(f"Asterisk command '{command}' timed out")
        return False, "Command timed out"
    except Exception as e:
        logger.error(f"Failed to execute command '{command}': {e}")
        return False, str(e)

def create_backup(config_path: str, backup_prefix: str = "config") -> str:
    """Create backup of configuration file"""
    Path(ASTERISK_BACKUP_PATH).mkdir(parents=True, exist_ok=True)
    
    if not os.path.exists(config_path):
        logger.warning(f"Config file {config_path} does not exist")
        return ""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    config_name = Path(config_path).stem
    backup_path = os.path.join(ASTERISK_BACKUP_PATH, f"{backup_prefix}_{config_name}_{timestamp}.conf")
    
    try:
        shutil.copy2(config_path, backup_path)
        logger.info(f"Backup created: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        raise HTTPException(status_code=500, detail=f"Backup failed: {str(e)}")

def ensure_directories(*dirs: str) -> None:
    """Ensure directories exist"""
    for directory in dirs:
        Path(directory).mkdir(parents=True, exist_ok=True)
