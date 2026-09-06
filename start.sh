#!/bin/bash
cd /home/tserver/blocktree_project
pkill -f 'app.py' || true
sleep 1
nohup /home/tserver/blocktree_project/venv/bin/python app.py >> /home/tserver/blocktree_project/server.log 2>&1 &
echo 'BlockTree matrix daemon launched on 0.0.0.0:9999'
