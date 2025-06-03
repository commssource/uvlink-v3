import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))

from shared.database import init_database
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_provisioning_table():
    try:
        # Initialize database which will create all tables
        if init_database():
            logger.info("✅ Provisioning table created successfully")
            return True
        else:
            logger.error("❌ Failed to create provisioning table")
            return False

    except Exception as e:
        logger.error(f"❌ Failed to create provisioning table: {e}")
        return False

if __name__ == "__main__":
    create_provisioning_table() 