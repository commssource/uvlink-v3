# ============================================================================
# setup_minimal.sh - Setup script
# ============================================================================

#!/bin/bash

echo "🚀 Setting up minimal working FastAPI structure..."

# Create directory structure
mkdir -p /opt/pjsip-manager/{shared,apps/endpoints,static,logs}

# Create __init__.py files
touch /opt/pjsip-manager/shared/__init__.py
touch /opt/pjsip-manager/apps/__init__.py
touch /opt/pjsip-manager/apps/endpoints/__init__.py

# Create .env file
# cat > /opt/pjsip-manager/.env << 'EOF'
# API_KEY=change-this-super-secure-key-here
# ASTERISK_CONFIG_PATH=/etc/asterisk/
# ASTERISK_BACKUP_PATH=/etc/asterisk/backups/
# ASTERISK_USER=asterisk
# HOST=0.0.0.0
# PORT=8000
# LOG_LEVEL=info
EOF

echo "✅ Minimal structure created"
echo ""
echo "📋 Next steps:"
echo "1. Copy the files from the artifact above"
echo "2. cd /opt/pjsip-manager"
echo "3. python3 -m venv venv"
echo "4. source venv/bin/activate"
echo "5. pip install -r requirements.txt"
echo "6. python main.py"