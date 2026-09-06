#!/bin/bash
BACKUP_DIR="/home/tserver/blocktree_project/backups"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
sqlite3 /home/tserver/blocktree_project/grid_data.db ".backup '$BACKUP_DIR/grid_data_$TIMESTAMP.db'"
echo "Backup created at $BACKUP_DIR/grid_data_$TIMESTAMP.db"
find "$BACKUP_DIR" -name "grid_data_*.db" -type f -mtime +14 -delete
