#!/bin/bash
sleep 3
pkill -9 -f agent.py
pkill -9 -f main.py
cd /root/aiagent
nohup python3.11 -u main.py > main.log 2>&1 &
