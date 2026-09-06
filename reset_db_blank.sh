#!/bin/bash
set -e
PROJECT_DIR="/home/tserver/blocktree_project"

echo "1. Creating snapshot backup before reset..."
bash "$PROJECT_DIR/backup_db.sh"

echo "2. Wiping content tables in SQLite..."
python3 - << 'PYEOF'
import sqlite3, os, glob

db_path = '/home/tserver/blocktree_project/grid_data.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute('DELETE FROM nodes')
c.execute('DELETE FROM authors')
c.execute('DELETE FROM admin_audit_logs')
c.execute('DELETE FROM admin_lockouts')
c.execute("DELETE FROM sqlite_sequence WHERE name IN ('nodes', 'authors', 'admin_audit_logs', 'admin_lockouts')")
c.execute("UPDATE admins SET failed_attempts=0, locked_until=NULL, totp_enabled=0, totp_secret=NULL, backup_codes=NULL WHERE username='admin'")

conn.commit()
c.execute('VACUUM')
conn.close()

# Clean uploaded images
for f in glob.glob('/home/tserver/blocktree_project/static/uploads/*'):
    if os.path.isfile(f):
        os.remove(f)

print("Database and uploads cleaned successfully.")
PYEOF

echo "3. Restarting service daemon..."
bash "$PROJECT_DIR/stop.sh"
bash "$PROJECT_DIR/start.sh"

echo "BlockTree is now 100% BLANK, clean, and ready for production!"
