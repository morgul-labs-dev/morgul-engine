#!/usr/bin/env bash
set -e

echo "=== Starting Morgul Engine ==="

# Check environment
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
fi

# Activate venv if present
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Initialize database if world.db does not exist
if [ ! -f "data/world.db" ]; then
    echo "Initializing new world state..."
    python3 init_sim.py --force
fi

echo "Starting API server on http://0.0.0.0:8000..."
exec uvicorn api.main:app --host 0.0.0.0 --port 8000
