#!/bin/bash
cd "$(dirname "$0")/../backend"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi
mkdir -p ../data/frames ../data/thermal ../data/exports ../logs
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
