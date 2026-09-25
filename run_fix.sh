#!/bin/bash
set -e

# Backup
BACKUP_NAME="outreach_queue.sqlite3.NEW-BACKUP-$(date +%Y%m%d%H%M%S)"
echo "Creating backup: $BACKUP_NAME"
cp outreach_queue.sqlite3 "$BACKUP_NAME"

# Run fix
echo "Running fix_db.py..."
python3 fix_db.py
