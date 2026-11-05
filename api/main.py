import sys
import json
from pathlib import Path
from typing import Optional, List

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, Query, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from engine.database import get_connection
from engine.core import engine
from engine.chronicler import record_daily_annal

app = FastAPI(
    title="Morgul Engine API",
    description="Autonomous multi-agent simulation backend",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

ws_manager = ConnectionManager()

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "environment": settings.ENV}

@app.get("/api/state")
def get_world_state():
    conn = get_connection()
    with conn:
        state_row = conn.execute("SELECT * FROM world_state ORDER BY id DESC LIMIT 1").fetchone()
        if not state_row:
            raise HTTPException(status_code=404, detail="World not seeded. Run init_sim.py first.")
        
        living_count = conn.execute("SELECT COUNT(*) FROM agents WHERE is_alive = 1").fetchone()[0]
        deceased_count = conn.execute("SELECT COUNT(*) FROM agents WHERE is_alive = 0").fetchone()[0]
        total_regions = conn.execute("SELECT COUNT(*) FROM regions").fetchone()[0]

    conn.close()

    return {
        "day": state_row["day"],
        "hour": state_row["hour"],
        "weather": state_row["weather"],
        "active_events": json.loads(state_row["active_events"] or "[]"),
        "demographics": {
            "living": living_count,
            "deceased": deceased_count,
            "regions": total_regions
        }
    }

@app.get("/api/agents")
def get_agents(alive_only: bool = Query(True), limit: int = Query(50, le=200)):
    conn = get_connection()
    with conn:
        query = "SELECT * FROM agents WHERE is_alive = 1 LIMIT ?" if alive_only else "SELECT * FROM agents LIMIT ?"
        rows = conn.execute(query, (limit,)).fetchall()
    conn.close()

    results = []
    for r in rows:
        item = dict(r)
        item["inventory"] = json.loads(item.get("inventory") or "{}")
        item["lineage"] = json.loads(item.get("lineage") or "{}")
        item["traits"] = json.loads(item.get("traits") or "[]")
        results.append(item)
    return results

@app.get("/api/annals")
def get_annals(limit: int = Query(20, le=100)):
    conn = get_connection()
    with conn:
        rows = conn.execute("SELECT * FROM chronicles ORDER BY day DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/tick")
async def trigger_manual_tick():
    result = engine.tick_hour()
    if result.get("cycle_completed"):
        record_daily_annal(result["day"])
    await ws_manager.broadcast({"type": "TICK", "data": result})
    return result

@app.websocket("/ws/simulation")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
