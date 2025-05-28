# ============================================================================
# shared/logging.py - Logging configuration
# ============================================================================

import logging
import os
from pathlib import Path
from config import LOG_LEVEL

def setup_logging() -> None:
    """Configure application logging"""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper()),
        format=log_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_dir / "asterisk-manager.log")
        ]
    )
    
    # Set up app-specific loggers
    for app_name in ["endpoints", "dids", "queues", "reports", "ivr", "system"]:
        app_logger = logging.getLogger(f"apps.{app_name}")
        app_handler = logging.FileHandler(log_dir / f"{app_name}.log")
        app_handler.setFormatter(logging.Formatter(log_format))
        app_logger.addHandler(app_handler)
