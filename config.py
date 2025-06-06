# ============================================================================
# Option 1: Fix with Sync MySQL Driver (Recommended for simplicity)
# ============================================================================

# config.py - Updated database URL to use sync driver
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import timedelta

# Load environment variables from .env file
load_dotenv()

# Application settings
APP_NAME = "UVLink Platform"
APP_VERSION = "1.2.0"
APP_DESCRIPTION = "Dashboard for managing UVLink"
BASE_URL = os.getenv("BASE_URL", "https://s1.uvlink.cloud")

# Azure Storage configuration
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER", "provisioning")
AZURE_STORAGE_ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
AZURE_STORAGE_ACCOUNT_KEY = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")

# Asterisk configuration
ASTERISK_CONFIG_PATH = os.getenv("ASTERISK_CONFIG_PATH")
ASTERISK_PJSIP_CONFIG = os.path.join(ASTERISK_CONFIG_PATH, "pjsip.conf")
ASTERISK_BACKUP_PATH = os.getenv("ASTERISK_BACKUP_PATH")
ASTERISK_USER = os.getenv("ASTERISK_USER", "asterisk")

# Database configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "csadmin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "asterisk")
# DB_PORT = os.getenv("DB_PORT", "3306")

# Construct DATABASE_URL with SYNC driver (pymysql)
if DB_PASSWORD:
    DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
else:
    DATABASE_URL = f"mysql+pymysql://{DB_USER}@{DB_HOST}/{DB_NAME}"

# Override with direct DATABASE_URL if provided
DATABASE_URL = os.getenv("DATABASE_URL", DATABASE_URL)

# Database settings
DATABASE_ECHO = os.getenv("DATABASE_ECHO", "false").lower() == "true"

# Security
API_KEY = os.getenv("API_KEY", "XFYMsQwBwnyzd-6GNVfoNbFP2EF-tPnA69JQdZQUWAM")
API_KEY_FILE = os.getenv("API_KEY_FILE")
JWT_SECRET =  os.getenv("JWT_SECRET")
JWT_ALGORITHM =  os.getenv("JWT_ALGORITHM")
JWT_EXPIRATION_DELTA = timedelta(hours=24)

# Load API key from file if specified
if API_KEY_FILE and Path(API_KEY_FILE).exists():
    with open(API_KEY_FILE, 'r') as f:
        API_KEY = f.read().strip()

# Server settings
SIP_SERVER_HOST = os.getenv("SIP_SERVER_HOST", "s1.uvlink.cloud")
HOST = os.getenv("HOST", "s1.uvlink.cloud")
PORT = int(os.getenv("PORT", 8000))
LOG_LEVEL = os.getenv("LOG_LEVEL", "info")

# CORS settings
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# Apps configuration