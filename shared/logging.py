"""
Logging configuration module for FastAPI application
Provides centralized logging setup with different handlers and formatters
"""

import logging
import logging.handlers
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import json

# Global logging configuration
LOGGING_CONFIGURED = False

# ============================================================================
# SETTINGS DETECTION (NO IMPORT DEPENDENCY)
# ============================================================================

def get_logging_settings():
    """Get logging settings from environment variables"""
    return {
        'debug': os.getenv('DEBUG', 'false').lower() == 'true',
        'log_level': os.getenv('LOG_LEVEL', 'INFO').upper(),
        'log_directory': os.getenv('LOG_DIRECTORY', 'logs'),
        'app_name': os.getenv('APP_NAME', 'FastAPI App'),
    }

# ============================================================================
# CUSTOM FORMATTERS
# ============================================================================

class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output"""
    
    # Color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record):
        # Add color to levelname
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.COLORS['RESET']}"
        
        return super().format(record)

class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add extra fields if present
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        if hasattr(record, 'endpoint'):
            log_entry['endpoint'] = record.endpoint
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)

# ============================================================================
# LOGGING SETUP FUNCTIONS
# ============================================================================

def setup_logging(debug: Optional[bool] = None, log_level: Optional[str] = None, log_dir: Optional[str] = None):
    """
    Setup comprehensive logging configuration
    
    Args:
        debug: Override debug mode detection
        log_level: Override log level
        log_dir: Override log directory
    """
    global LOGGING_CONFIGURED
    
    if LOGGING_CONFIGURED:
        return
    
    # Get settings from environment or parameters
    settings = get_logging_settings()
    
    debug_mode = debug if debug is not None else settings['debug']
    log_level = log_level or settings['log_level']
    log_directory = log_dir or settings['log_directory']
    
    # Create logs directory
    log_dir_path = Path(log_directory)
    log_dir_path.mkdir(exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Setup console handler
    setup_console_handler(root_logger, debug_mode)
    
    # Setup file handlers
    setup_file_handlers(root_logger, log_dir_path, debug_mode)
    
    # Setup application-specific loggers
    setup_application_loggers(debug_mode)
    
    # Setup third-party library loggers
    setup_third_party_loggers(debug_mode)
    
    LOGGING_CONFIGURED = True
    
    # Log initial message
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized - Level: {log_level}, Debug: {debug_mode}")

def setup_console_handler(root_logger: logging.Logger, debug_mode: bool):
    """Setup console handler with appropriate formatter"""
    console_handler = logging.StreamHandler(sys.stdout)
    
    if debug_mode:
        # Colored formatter for development
        console_format = '%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s'
        console_formatter = ColoredFormatter(console_format)
    else:
        # Simple formatter for production
        console_format = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        console_formatter = logging.Formatter(console_format)
    
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO if not debug_mode else logging.DEBUG)
    
    root_logger.addHandler(console_handler)

def setup_file_handlers(root_logger: logging.Logger, log_dir: Path, debug_mode: bool):
    """Setup file handlers for different log levels"""
    
    # General application log (rotating)
    app_log_file = log_dir / 'app.log'
    app_handler = logging.handlers.RotatingFileHandler(
        app_log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    
    app_format = '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s'
    app_handler.setFormatter(logging.Formatter(app_format))
    app_handler.setLevel(logging.INFO)
    root_logger.addHandler(app_handler)
    
    # Error log (separate file for errors only)
    error_log_file = log_dir / 'error.log'
    error_handler = logging.handlers.RotatingFileHandler(
        error_log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,
        encoding='utf-8'
    )
    
    error_format = '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s\n%(pathname)s:%(funcName)s'
    error_handler.setFormatter(logging.Formatter(error_format))
    error_handler.setLevel(logging.ERROR)
    root_logger.addHandler(error_handler)
    
    # JSON log for structured logging (production)
    if not debug_mode:
        json_log_file = log_dir / 'app.json'
        json_handler = logging.handlers.RotatingFileHandler(
            json_log_file,
            maxBytes=50 * 1024 * 1024,  # 50MB
            backupCount=3,
            encoding='utf-8'
        )
        json_handler.setFormatter(JSONFormatter())
        json_handler.setLevel(logging.INFO)
        root_logger.addHandler(json_handler)
    
    # Debug log (only in debug mode)
    if debug_mode:
        debug_log_file = log_dir / 'debug.log'
        debug_handler = logging.handlers.RotatingFileHandler(
            debug_log_file,
            maxBytes=20 * 1024 * 1024,  # 20MB
            backupCount=3,
            encoding='utf-8'
        )
        
        debug_format = '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d in %(funcName)s() - %(message)s'
        debug_handler.setFormatter(logging.Formatter(debug_format))
        debug_handler.setLevel(logging.DEBUG)
        root_logger.addHandler(debug_handler)

def setup_application_loggers(debug_mode: bool):
    """Setup loggers for different application modules"""
    
    log_level = logging.DEBUG if debug_mode else logging.INFO
    
    # Main application logger
    app_logger = logging.getLogger('app')
    app_logger.setLevel(log_level)
    
    # Database logger
    db_logger = logging.getLogger('shared.database')
    db_logger.setLevel(log_level)
    
    # PJSIP logger
    pjsip_logger = logging.getLogger('apps.endpoints.pjsip_manager')
    pjsip_logger.setLevel(log_level)
    
    # API loggers for each app
    for app_name in ['call_centre', 'endpoints', 'provisioning', 'system', 'inbound_call_routing']:
        app_logger = logging.getLogger(f'apps.{app_name}')
        app_logger.setLevel(log_level)

def setup_third_party_loggers(debug_mode: bool):
    """Configure third-party library loggers"""
    
    # SQLAlchemy
    sqlalchemy_logger = logging.getLogger('sqlalchemy')
    if debug_mode:
        # Show SQL queries in debug mode
        sqlalchemy_logger.setLevel(logging.INFO)
        # Echo pool checkouts/checkins
        logging.getLogger('sqlalchemy.pool').setLevel(logging.DEBUG)
    else:
        sqlalchemy_logger.setLevel(logging.WARNING)
    
    # FastAPI/Uvicorn
    uvicorn_logger = logging.getLogger('uvicorn')
    uvicorn_logger.setLevel(logging.INFO)
    
    uvicorn_access_logger = logging.getLogger('uvicorn.access')
    if debug_mode:
        uvicorn_access_logger.setLevel(logging.INFO)
    else:
        uvicorn_access_logger.setLevel(logging.WARNING)
    
    # HTTP libraries
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    
    # Disable some noisy loggers
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('concurrent.futures').setLevel(logging.WARNING)

# ============================================================================
# CUSTOM LOGGING UTILITIES
# ============================================================================

class RequestLogger:
    """Logger with request context"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.request_id = None
        self.user_id = None
        self.endpoint = None
    
    def set_context(self, request_id: str = None, user_id: str = None, endpoint: str = None):
        """Set request context for logging"""
        self.request_id = request_id
        self.user_id = user_id
        self.endpoint = endpoint
    
    def _log_with_context(self, level: int, message: str, *args, **kwargs):
        """Log message with request context"""
        extra = kwargs.get('extra', {})
        if self.request_id:
            extra['request_id'] = self.request_id
        if self.user_id:
            extra['user_id'] = self.user_id
        if self.endpoint:
            extra['endpoint'] = self.endpoint
        
        kwargs['extra'] = extra
        self.logger.log(level, message, *args, **kwargs)
    
    def debug(self, message: str, *args, **kwargs):
        self._log_with_context(logging.DEBUG, message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        self._log_with_context(logging.INFO, message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        self._log_with_context(logging.WARNING, message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        self._log_with_context(logging.ERROR, message, *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs):
        self._log_with_context(logging.CRITICAL, message, *args, **kwargs)

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with proper configuration"""
    if not LOGGING_CONFIGURED:
        setup_logging()
    return logging.getLogger(name)

def get_request_logger(name: str) -> RequestLogger:
    """Get a request logger with context support"""
    if not LOGGING_CONFIGURED:
        setup_logging()
    return RequestLogger(name)

# ============================================================================
# PERFORMANCE LOGGING
# ============================================================================

import time
from functools import wraps
from typing import Callable
import asyncio
import inspect

def log_performance(logger_name: str = None):
    """Decorator to log function performance"""
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(logger_name or func.__module__)
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                logger.info(f"{func.__name__} completed in {execution_time:.3f}s")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"{func.__name__} failed after {execution_time:.3f}s: {e}")
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger(logger_name or func.__module__)
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                logger.info(f"{func.__name__} completed in {execution_time:.3f}s")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"{func.__name__} failed after {execution_time:.3f}s: {e}")
                raise
        
        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper
    return decorator

# ============================================================================
# REQUEST LOGGING MIDDLEWARE
# ============================================================================

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request, Response
    from starlette.middleware.base import BaseHTTPMiddleware

class RequestLoggingMiddleware:
    """Middleware to log all HTTP requests"""
    
    def __init__(self, app):
        self.app = app
        self.logger = get_logger('request')
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Generate request ID
        request_id = str(uuid.uuid4())
        
        # Extract request info from scope
        method = scope["method"]
        path = scope["path"]
        client_ip = scope.get("client", [None])[0] if scope.get("client") else None
        
        # Log request
        start_time = time.time()
        self.logger.info(
            f"Request started: {method} {path}",
            extra={
                'request_id': request_id,
                'method': method,
                'path': path,
                'client_ip': client_ip
            }
        )
        
        # Add request ID to scope
        scope['request_id'] = request_id
        
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                process_time = time.time() - start_time
                status_code = message["status"]
                
                # Log response
                self.logger.info(
                    f"Request completed: {status_code} in {process_time:.3f}s",
                    extra={
                        'request_id': request_id,
                        'status_code': status_code,
                        'process_time': process_time
                    }
                )
            
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            process_time = time.time() - start_time
            self.logger.error(
                f"Request failed: {str(e)} after {process_time:.3f}s",
                extra={
                    'request_id': request_id,
                    'error': str(e),
                    'process_time': process_time
                },
                exc_info=True
            )
            raise

# ============================================================================
# INITIALIZATION WITH ERROR HANDLING
# ============================================================================

def safe_setup_logging():
    """Setup logging with error handling and fallback"""
    try:
        setup_logging()
    except Exception as e:
        # Fallback to basic logging if setup fails
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('app.log') if os.access('.', os.W_OK) else logging.NullHandler()
            ]
        )
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to setup advanced logging, using basic config: {e}")

# Auto-setup logging when module is imported if needed
if not LOGGING_CONFIGURED and os.getenv('AUTO_SETUP_LOGGING', 'true').lower() == 'true':
    safe_setup_logging()