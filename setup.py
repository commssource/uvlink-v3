# ============================================================================
# Quick setup script - setup.py
# ============================================================================

#!/usr/bin/env python3
"""
Quick setup script for the multi-app FastAPI project
"""

import os
import sys
from pathlib import Path

def create_directory_structure():
    """Create the required directory structure"""
    base_dir = Path("/opt/pjsip-manager")
    
    directories = [
        "shared",
        "apps/endpoints",
        "apps/dids", 
        "apps/queues",
        "apps/reports",
        "apps/ivr",
        "apps/system",
        "static",
        "logs"
    ]
    
    for directory in directories:
        dir_path = base_dir / directory
        dir_path.mkdir(parents=True, exist_ok=True)
        
        # Create __init__.py files
        if "apps" in directory or directory == "shared":
            (dir_path / "__init__.py").touch()
    
    print("✅ Directory structure created")

def create_minimal_files():
    """Create minimal files to get started"""
    base_dir = Path("/opt/pjsip-manager")
    
    # Create minimal __init__.py files for apps that don't have routes yet
    minimal_apps = ["dids", "queues", "reports", "ivr"]
    
    for app in minimal_apps:
        app_dir = base_dir / "apps" / app
        
        # Create minimal schemas.py
        (app_dir / "schemas.py").write_text(f'''
from pydantic import BaseModel

class {app.capitalize()}Base(BaseModel):
    pass
''')
        
        # Create minimal routes.py
        (app_dir / "routes.py").write_text(f'''
from fastapi import APIRouter

router = APIRouter(prefix="/{app}", tags=["{app}"])

@router.get("/")
async def get_{app}():
    return {{"message": "{app.capitalize()} module - Coming soon!"}}
''')
        
        # Create minimal services.py
        (app_dir / "services.py").write_text(f'''
class {app.capitalize()}Service:
    pass
''')
        
        # Create minimal models.py
        (app_dir / "models.py").write_text(f'''
from shared.database import Base

# {app.capitalize()} models will be defined here
''')
    
    print("✅ Minimal app files created")

def create_env_file():
    """Create environment file"""
    env_content = '''# Asterisk Management Platform Configuration

# Security
API_KEY=change-this-super-secure-key-here
SECRET_KEY=your-jwt-secret-key-here

# Asterisk Configuration
ASTERISK_CONFIG_PATH=/etc/asterisk/
ASTERISK_BACKUP_PATH=/etc/asterisk/backups/
ASTERISK_USER=asterisk

# Database (SQLite for development)
DATABASE_URL=sqlite:///./asterisk_manager.db
DATABASE_ECHO=false

# Server Settings
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=info

# CORS Settings
CORS_ORIGINS=*

# Enabled Apps (comma-separated)
ENABLED_APPS=endpoints,dids,queues,reports,ivr,system
'''
    
    with open("/opt/pjsip-manager/.env", "w") as f:
        f.write(env_content)
    
    print("✅ Environment file created")

def main():
    """Main setup function"""
    print("🚀 Setting up FastAPI Multi-App Project")
    print("=" * 50)
    
    try:
        create_directory_structure()
        create_minimal_files()
        create_env_file()
        
        print("\n✅ Setup complete!")
        print("\n📋 Next steps:")
        print("1. cd /opt/pjsip-manager")
        print("2. python3 -m venv venv")
        print("3. source venv/bin/activate")
        print("4. pip install -r requirements.txt")
        print("5. Copy the corrected files from the artifacts")
        print("6. python main.py")
        print("\n🌐 Your API will be available at: http://localhost:8000")
        print("📚 Documentation at: http://localhost:8000/docs")
        
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()