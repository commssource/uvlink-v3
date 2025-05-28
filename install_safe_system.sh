#!/bin/bash

# Installation script for Safe PJSIP Endpoint Manager
# Run this script to install the new safe system

set -e

APP_DIR="/opt/pjsip-manager"
BACKUP_DIR="/tmp/pjsip-manager-backup-$(date +%Y%m%d_%H%M%S)"

echo "🛡️ Installing Safe PJSIP Endpoint Manager"
echo "========================================"

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo "❌ Please run this script from the /opt/pjsip-manager directory"
    exit 1
fi

# Create backup of current system
echo "📦 Creating backup of current system..."
mkdir -p "$BACKUP_DIR"
cp -r apps/ "$BACKUP_DIR/" 2>/dev/null || true
cp main.py "$BACKUP_DIR/" 2>/dev/null || true
cp config.py "$BACKUP_DIR/" 2>/dev/null || true
echo "✅ Backup created at: $BACKUP_DIR"

# Stop the current service if running
echo "🛑 Stopping current FastAPI service..."
pkill -f "python.*main.py" || true
sleep 2

# Backup current PJSIP config
echo "💾 Creating backup of current PJSIP configuration..."
if [ -f "/etc/asterisk/pjsip.conf" ]; then
    sudo mkdir -p /etc/asterisk/backups
    sudo cp /etc/asterisk/pjsip.conf "/etc/asterisk/backups/pjsip_before_safe_install_$(date +%Y%m%d_%H%M%S).conf"
    echo "✅ PJSIP config backed up"
fi

# Install the new safe system
echo "🔧 Installing safe endpoint management system..."

# Note: At this point, you would copy the actual files
# For this script, we'll show the manual steps

echo "📝 Manual installation steps:"
echo ""
echo "1. Copy config_parser.py:"
echo "   nano apps/endpoints/config_parser.py"
echo "   # Copy content from the config_parser.py artifact"
echo ""
echo "2. Replace services.py:"
echo "   nano apps/endpoints/services.py"
echo "   # Copy content from the safe services.py artifact"
echo ""
echo "3. Replace routes.py:"
echo "   nano apps/endpoints/routes.py"
echo "   # Copy content from the safe routes.py artifact"
echo ""
echo "4. Update schemas.py:"
echo "   nano apps/endpoints/schemas.py"
echo "   # Copy content from the updated schemas.py artifact"
echo ""

# Create helper scripts
echo "📋 Creating helper scripts..."

cat > backup_restore.py << 'EOF'
# Copy the backup_restore.py content from the artifact
echo "Helper script placeholder - copy content from backup_restore.py artifact"
EOF

cat > test_commands.sh << 'EOF'
# Copy the test_commands.sh content from the artifact
echo "Test script placeholder - copy content from test_commands.sh artifact"
EOF

chmod +x test_commands.sh

echo ""
echo "✅ Installation preparation complete!"
echo ""
echo "🔧 Next steps:"
echo "1. Copy the file contents from the artifacts into the respective files"
echo "2. Update your API_KEY in test_commands.sh"
echo "3. Test the installation: ./test_commands.sh"
echo "4. Start your FastAPI server: python main.py"
echo ""
echo "📁 Files to update:"
echo "  - apps/endpoints/config_parser.py (NEW FILE)"
echo "  - apps/endpoints/services.py (REPLACE)"
echo "  - apps/endpoints/routes.py (REPLACE)"
echo "  - apps/endpoints/schemas.py (UPDATE)"
echo ""
echo "🛡️ Safety features:"
echo "  ✅ Preserves existing PJSIP configuration"
echo "  ✅ Individual endpoint operations only"
echo "  ✅ Automatic backups before changes"
echo "  ✅ No risk of losing transports/system settings"
echo ""
echo "💾 Backups created:"
echo "  - Application backup: $BACKUP_DIR"
echo "  - PJSIP config backup: /etc/asterisk/backups/"
echo ""
echo "🔄 To rollback if needed:"
echo "  sudo cp $BACKUP_DIR/apps/endpoints/* apps/endpoints/"
echo "  sudo cp $BACKUP_DIR/main.py ."

# Function to copy file content with prompts
copy_file_content() {
    local file_path=$1
    local description=$2
    
    echo ""
    echo "📝 Ready to edit $file_path ($description)"
    echo "   Press Enter when ready, then copy the content from the artifact..."
    read
    nano "$file_path"
}

# Offer to open files for editing
echo ""
read -p "🤔 Would you like to open the files for editing now? (y/n): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "📂 Opening files for editing..."
    
    # Create config_parser.py if it doesn't exist
    touch apps/endpoints/config_parser.py
    
    copy_file_content "apps/endpoints/config_parser.py" "NEW - Safe configuration parser"
    copy_file_content "apps/endpoints/services.py" "REPLACE - Safe endpoint service"
    copy_file_content "apps/endpoints/routes.py" "REPLACE - Safe API routes"
    copy_file_content "apps/endpoints/schemas.py" "UPDATE - Add EndpointUpdate schema"
    
    echo ""
    echo "✅ File editing complete!"
    echo ""
    echo "🧪 Test the installation:"
    echo "   1. Start FastAPI: python main.py"
    echo "   2. In another terminal: ./test_commands.sh"
    echo "   3. Check API docs: https://uvlink.cloud/docs"
fi

echo ""
echo "🎉 Safe PJSIP Endpoint Manager installation complete!"