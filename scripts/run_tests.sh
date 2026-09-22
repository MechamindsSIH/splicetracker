#!/bin/bash
cd "$(dirname "$0")/../backend"
source venv/bin/activate
pip install pytest pytest-asyncio httpx 2>/dev/null
pytest tests/ -v
