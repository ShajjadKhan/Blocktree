#!/bin/bash
cd /home/tserver/blocktree_project

# Persistent random session secret (generated once, never committed)
if [ ! -f .secret_key ]; then
    /home/tserver/blocktree_project/venv/bin/python -c "import secrets; print(secrets.token_hex(32))" > .secret_key
    chmod 600 .secret_key
fi
export SECRET_KEY="$(cat .secret_key)"

pkill -f '/home/tserver/blocktree_project/venv/bin/python app.py' || true
sleep 1
nohup /home/tserver/blocktree_project/venv/bin/python app.py >> /home/tserver/blocktree_project/server.log 2>&1 &
echo 'BlockTree matrix daemon launched on 0.0.0.0:9999'
