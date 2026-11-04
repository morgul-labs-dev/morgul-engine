#!/usr/bin/env bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

if [ ! -f .env ]; then
  echo "[-] .env not found. Creating from .env.example..."
  cp .env.example .env
fi

if [ ! -d "venv" ]; then
  echo "[+] Setting up Python virtual environment..."
  python3 -m venv venv
  ./venv/bin/pip install --upgrade pip
  ./venv/bin/pip install -r requirements.txt
fi

if [ ! -f "data/simulation.db" ]; then
  echo "[+] Initializing world database with 25 founders..."
  ./venv/bin/python3 init_sim.py --founders 25
fi

echo "=========================================================="
echo " Starting Morgul Engine Simulation Service"
echo " FastAPI API & WebSockets: http://localhost:8000"
echo " API Documentation:       http://localhost:8000/docs"
echo "=========================================================="

./venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
