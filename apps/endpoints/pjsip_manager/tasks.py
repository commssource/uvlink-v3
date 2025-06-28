# ============================================================================
# apps/endpoints/pjsip_manager/tasks.py - Background tasks
# ============================================================================

import asyncio
import logging
from shared.utils.asterisk import reload_asterisk_module
from shared.utils.backup import cleanup_old_backups

logger = logging.getLogger(__name__)

async def reload_asterisk_config() -> bool:
    """Background task to reload Asterisk PJSIP configuration"""
    return await reload_asterisk_module("res_pjsip.so")

async def cleanup_old_backups_task(backup_dir: str, days_to_keep: int = 30):
    """Background task to cleanup old backup files"""
    try:
        cleanup_old_backups(backup_dir, days_to_keep)
        logger.info(f"Cleaned up backups older than {days_to_keep} days")
    except Exception as e:
        logger.error(f"Failed to cleanup old backups: {e}")
