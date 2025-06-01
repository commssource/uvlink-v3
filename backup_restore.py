#!/usr/bin/env python3
"""
Backup and Restore Helper for PJSIP Configuration
"""

import os
import sys
import shutil
from datetime import datetime
from pathlib import Path

# ASTERISK_CONFIG_PATH = "/etc/asterisk/pjsip.conf"
# ASTERISK_BACKUP_PATH = "/etc/asterisk/backups/"

def list_backups():
    """List available backups"""
    if not os.path.exists(ASTERISK_BACKUP_PATH):
        print("No backup directory found")
        return []
    
    backups = []
    for file in os.listdir(ASTERISK_BACKUP_PATH):
        if file.startswith("pjsip_") and file.endswith(".conf"):
            file_path = os.path.join(ASTERISK_BACKUP_PATH, file)
            stat = os.stat(file_path)
            backups.append({
                'filename': file,
                'path': file_path,
                'size': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_ctime)
            })
    
    # Sort by creation time (newest first)
    backups.sort(key=lambda x: x['created'], reverse=True)
    return backups

def show_backups():
    """Display available backups"""
    backups = list_backups()
    
    if not backups:
        print("No backups found")
        return
    
    print("\nAvailable Backups:")
    print("=" * 60)
    for i, backup in enumerate(backups, 1):
        print(f"{i:2d}. {backup['filename']}")
        print(f"    Created: {backup['created'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"    Size: {backup['size']} bytes")
        print()

def restore_backup(backup_file):
    """Restore a backup file"""
    backup_path = os.path.join(ASTERISK_BACKUP_PATH, backup_file)
    
    if not os.path.exists(backup_path):
        print(f"Backup file not found: {backup_file}")
        return False
    
    try:
        # Create a backup of current config before restoring
        if os.path.exists(ASTERISK_CONFIG_PATH):
            current_backup = os.path.join(
                ASTERISK_BACKUP_PATH, 
                f"pjsip_before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.conf"
            )
            shutil.copy2(ASTERISK_CONFIG_PATH, current_backup)
            print(f"Current config backed up to: {current_backup}")
        
        # Restore the backup
        shutil.copy2(backup_path, ASTERISK_CONFIG_PATH)
        print(f"Restored: {backup_file} -> {ASTERISK_CONFIG_PATH}")
        
        # Reload Asterisk
        print("Reloading Asterisk PJSIP configuration...")
        os.system("sudo asterisk -rx 'pjsip reload'")
        
        return True
        
    except Exception as e:
        print(f"Failed to restore backup: {e}")
        return False

def create_manual_backup():
    """Create a manual backup"""
    if not os.path.exists(ASTERISK_CONFIG_PATH):
        print("No PJSIP configuration file found")
        return False
    
    try:
        Path(ASTERISK_BACKUP_PATH).mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"pjsip_manual_{timestamp}.conf"
        backup_path = os.path.join(ASTERISK_BACKUP_PATH, backup_file)
        
        shutil.copy2(ASTERISK_CONFIG_PATH, backup_path)
        print(f"Manual backup created: {backup_file}")
        return True
        
    except Exception as e:
        print(f"Failed to create backup: {e}")
        return False

def show_current_config():
    """Show current configuration"""
    if not os.path.exists(ASTERISK_CONFIG_PATH):
        print("No PJSIP configuration file found")
        return
    
    try:
        with open(ASTERISK_CONFIG_PATH, 'r') as f:
            content = f.read()
        
        print(f"\nCurrent PJSIP Configuration ({ASTERISK_CONFIG_PATH}):")
        print("=" * 60)
        print(content[:1000] + "..." if len(content) > 1000 else content)
        
    except Exception as e:
        print(f"Failed to read config: {e}")

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("PJSIP Configuration Backup/Restore Tool")
        print("=" * 40)
        print("Usage:")
        print("  python backup_restore.py list                - List available backups")
        print("  python backup_restore.py show                - Show current config")
        print("  python backup_restore.py backup              - Create manual backup")
        print("  python backup_restore.py restore <filename>  - Restore specific backup")
        print("  python backup_restore.py latest              - Restore latest backup")
        print()
        print("Examples:")
        print("  python backup_restore.py list")
        print("  python backup_restore.py restore pjsip_20250528_195030.conf")
        return
    
    command = sys.argv[1].lower()
    
    if command == "list":
        show_backups()
        
    elif command == "show":
        show_current_config()
        
    elif command == "backup":
        create_manual_backup()
        
    elif command == "restore":
        if len(sys.argv) < 3:
            print("Please specify backup filename")
            print("Use 'python backup_restore.py list' to see available backups")
            return
        
        backup_file = sys.argv[2]
        restore_backup(backup_file)
        
    elif command == "latest":
        backups = list_backups()
        if not backups:
            print("No backups found")
            return
        
        latest_backup = backups[0]['filename']
        print(f"Restoring latest backup: {latest_backup}")
        restore_backup(latest_backup)
        
    else:
        print(f"Unknown command: {command}")
        print("Use 'python backup_restore.py' to see usage")

if __name__ == "__main__":
    main()