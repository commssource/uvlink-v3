# ============================================================================
# shared/utils/asterisk.py - Asterisk integration utilities
# ============================================================================

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

async def reload_asterisk_module(module: str = "res_pjsip.so") -> bool:
    """Reload an Asterisk module"""
    try:
        process = await asyncio.create_subprocess_exec(
            "asterisk", "-rx", f"module reload {module}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            logger.info(f"Successfully reloaded Asterisk module: {module}")
            return True
        else:
            logger.error(f"Failed to reload Asterisk module {module}: {stderr.decode()}")
            return False
            
    except Exception as e:
        logger.error(f"Exception during Asterisk module reload: {e}")
        return False

async def check_asterisk_running() -> bool:
    """Check if Asterisk is running"""
    try:
        process = await asyncio.create_subprocess_exec(
            "asterisk", "-rx", "core show version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        await process.communicate()
        return process.returncode == 0
        
    except Exception:
        return False