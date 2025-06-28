# ============================================================================
# shared/utils/backup.py - Backup utilities
# ============================================================================

import aiofiles
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

async def create_config_backup(source_file: str, backup_dir: str, prefix: str = "backup") -> str:
    """Create a timestamped backup of a configuration file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    source_path = Path(source_file)
    backup_path = Path(backup_dir) / f"{prefix}_{source_path.stem}_{timestamp}{source_path.suffix}"
    
    try:
        # Ensure backup directory exists
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        
        if source_path.exists():
            async with aiofiles.open(source_path, 'r') as src:
                content = await src.read()
            async with aiofiles.open(backup_path, 'w') as dst:
                await dst.write(content)
        
        logger.info(f"Created backup: {backup_path}")
        return str(backup_path)
        
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        return ""

def cleanup_old_backups(backup_dir: str, days_to_keep: int = 30):
    """Clean up old backup files"""
    try:
        backup_path = Path(backup_dir)
        if not backup_path.exists():
            return
        
        cutoff_time = datetime.now().timestamp() - (days_to_keep * 24 * 3600)
        
        for backup_file in backup_path.glob("backup_*"):
            if backup_file.stat().st_mtime < cutoff_time:
                backup_file.unlink()
                logger.info(f"Cleaned up old backup: {backup_file}")
                
    except Exception as e:
        logger.error(f"Failed to cleanup old backups: {e}")