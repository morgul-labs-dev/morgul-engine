from engine import __version__
import secrets
import os
import asyncio
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Security, status, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

import database
import seeds
import llm_client
from engine import SimulationEngine, FACTION_ORIGINS, REGIONS
from edicts import VALID_EDICTS

is_prod = os.getenv("ENV", "").lower() == "production"
app = FastAPI(
    title="Pangaea Simulation Engine",
    version="1.2.0",
    docs_url=None if is_prod else "/docs",
    redoc_url=None if is_prod else "/redoc",
    openapi_url=None if is_prod else "/openapi.json"
)

# Strict CORS: No wildcard echoing, allow_credentials=False
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000")
ALLOWED_ORIGINS = [orig.strip() for orig in allowed_origins_env.split(",") if orig.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Admin Auth Header Dependency
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
api_key_header = APIKeyHeader(name="X-Admin-Token", auto_error=False)

def verify_admin_token(token: Optional[str] = Security(api_key_header)):
    if not ADMIN_TOKEN or ADMIN_TOKEN == "change-me":
        raise HTTPException(503, "Admin routes disabled: set ADMIN_TOKEN in the environment.")
    if not secrets.compare_digest(str(token or "").encode('utf-8'), str(ADMIN_TOKEN).encode('utf-8')):
        raise HTTPException(401, "Invalid or missing X-Admin-Token header")
    return token

class ConnectionNotifier:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

notifier = ConnectionNotifier()

class WorldManager:
    def __init__(self):
        self.engine: Optional[SimulationEngine] = None
        self.is_running = True
        self.tick_delay_seconds = 60.0
        self.recent_events: List[str] = []
        self.init_engine()

    def init_engine(self):
        database.init_db()
        self.engine = SimulationEngine()
        if not hasattr(self.engine, "active_edicts"):
            self.engine.active_edicts = {}

        saved = database.load_world()
        if saved and saved.get("agents"):
            self.engine.day = saved["day"]
            self.engine.hour = saved["hour"]
            self.engine.blocked_borders = saved["blocked_borders"]
            self.engine.agents = saved["agents"]
            if saved.get("territory_control"):
                self.engine.territory_control = saved["territory_control"]
            if saved.get("shrines"):
                self.engine.shrines = saved["shrines"]
            self.engine.log(f"World restored from SQLite (Day {self.engine.day:02d}, {len(self.engine.agents)} citizens).")
        else:
            for agent in seeds.get_initial_population():
                self.engine.register_agent(agent)
            database.save_world(
                self.engine.day,
                self.engine.hour,
                self.engine.blocked_borders,
                self.engine.agents,
                self.engine.territory_control,
                self.engine.shrines
            )
            self.engine.log(f"Seeded {len(self.engine.agents)} initial citizens across Pangaea.")

    def save_state(self):
        if not self.engine:
            return
        try:
            database.save_world(
                self.engine.day,
                self.engine.hour,
                self.engine.blocked_borders,
                self.engine.agents,
                self.engine.territory_control,
                self.engine.shrines
            )
        except Exception as e:
            print(f"⚠️ Failed to save world to SQLite: {e}")

    def calculate_factions(self) -> Dict[str, Any]:
        if not self.engine:
            return {}
        factions = {}
        for region_name, native_guild in FACTION_ORIGINS.items():
            tc = self.engine.territory_control.get(region_name, {})
            controlling_guild = tc.get("controlling_guild", native_guild)
            influence = tc.get("influence", 100)
            is_annexed = controlling_guild != native_guild

            # Members belong to a guild via their birth_region's native guild
            members = [
                a.name for a in self.engine.agents.values()
                if FACTION_ORIGINS.get(a.birth_region, native_guild) == controlling_guild
            ]
            factions[region_name] = {
                "name": controlling_guild,
                "native_guild": native_guild,
                "members": members,
                "population": len(members),
                "influence": influence,
                "is_annexed": is_annexed
            }
        return factions

    def get_serialized_state(self) -> Dict[str, Any]:
        if not self.engine:
            return {}

        agents_data = []
        for a in self.engine.agents.values():
            guild_name = FACTION_ORIGINS.get(a.birth_region, "Unaligned")
            agents_data.append({
                "id": a.name,
                "name": a.name,
                "gender": getattr(a, "gender", "M"),
                "generation": getattr(a, "generation", 1),
                "parents": getattr(a, "parents", []),
                "birth_region": a.birth_region,
                "region": a.current_region,
                "region_id": a.current_region,
                "location": a.current_region,
                "social_class": a.social_class,
                "role": a.role,
                "guild": guild_name,
                "faction": guild_name,
                "personality": a.personality,
                "age": round(getattr(a, "age", 24.0), 1),
                "is_sterile": getattr(a, "is_sterile", False),
            "is_rogue": getattr(a, "is_rogue", False),
                "health": a.health,
                "hunger": a.hunger,
                "energy": a.energy,
                "piety": getattr(a, "piety", 50),
                "ambition": getattr(a, "ambition", 50),
                "dread": getattr(a, "dread", 10),
                "heat_tolerance": getattr(a, "heat_tolerance", 50),
                "cold_tolerance": getattr(a, "cold_tolerance", 50),
                "attractiveness": getattr(a, "attractiveness", 50),
                "children_count": getattr(a, "children_count", 0),
                "inventory": a.inventory,
                "relationships": getattr(a, "relationships", {}),
                "social_ties": getattr(a, "relationships", {}),
                "memories": getattr(a, "memories", [])
            })

        clock_data = {
            "day": self.engine.day,
            "hour": self.engine.hour,
            "is_running": self.is_running,
            "tick_delay": self.tick_delay_seconds
        }
        return {
            "meta": clock_data,
            "clock": clock_data,
            "regions": list(REGIONS.keys()),
            "active_edicts": getattr(self.engine, "active_edicts", {}),
            "blocked_borders": list(self.engine.blocked_borders),
            "agents": agents_data,
            "factions": self.calculate_factions(),
            "territory_control": self.engine.territory_control,
            "shrines": getattr(self.engine, "shrines", {}),
            "active_caravans": getattr(self.engine, "active_caravans", []),
            "active_raids": getattr(self.engine, "active_raids", []),
            "active_plots": getattr(self.engine, "active_plots", []),
            "logs": self.engine.logs[-60:],
            "recent_events": self.engine.logs[-60:]
        }

world_mgr = WorldManager()

async def simulation_loop():
    print("🚀 Simulation loop started.")
    while True:
        try:
            if world_mgr.is_running and world_mgr.engine:
                prev_seq = getattr(world_mgr.engine, 'log_sequence', 0)
                await asyncio.to_thread(world_mgr.engine.tick_hour)
                curr_seq = getattr(world_mgr.engine, 'log_sequence', 0)
                generated_count = curr_seq - prev_seq
                new_logs = world_mgr.engine.logs[-generated_count:] if generated_count > 0 else []
                world_mgr.recent_events.extend(new_logs)
                world_mgr.save_state()

                state = world_mgr.get_serialized_state()
                await notifier.broadcast({"type": "STATE_UPDATE", "data": state})
        except Exception as e:
            print(f"❌ Error during tick_hour: {e}")

        await asyncio.sleep(world_mgr.tick_delay_seconds)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(simulation_loop())

@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    await notifier.connect(websocket)
    try:
        init_state = world_mgr.get_serialized_state()
        await websocket.send_json({"type": "INITIAL_STATE", "data": init_state})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        notifier.disconnect(websocket)
    except Exception:
        notifier.disconnect(websocket)

@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": __version__}

@app.get("/api/sim/state")
def get_state():
    return world_mgr.get_serialized_state()

class SimControlRequest(BaseModel):
    running: bool
    delay_seconds: float = 10.0

@app.post("/api/sim/control", dependencies=[Depends(verify_admin_token)])
async def control_sim(req: SimControlRequest):
    world_mgr.is_running = req.running
    world_mgr.tick_delay_seconds = max(0.5, float(req.delay_seconds))
    state = world_mgr.get_serialized_state()
    await notifier.broadcast({"type": "STATE_UPDATE", "data": state})
    return {"status": "success", "is_running": world_mgr.is_running, "tick_delay": world_mgr.tick_delay_seconds}

class BorderToggleRequest(BaseModel):
    region_a: str
    region_b: str
    block: Optional[bool] = None

@app.post("/api/divine/border", dependencies=[Depends(verify_admin_token)])
async def toggle_border(req: BorderToggleRequest):
    engine = world_mgr.engine
    key_forward = ":".join(sorted([req.region_a, req.region_b]))
    key_reverse = f"{req.region_b}<->{req.region_a}"
    currently_blocked = (key_forward in engine.blocked_borders) or (key_reverse in engine.blocked_borders)
    should_block = req.block if req.block is not None else (not currently_blocked)

    engine.toggle_border(req.region_a, req.region_b, should_block)
    world_mgr.save_state()
    state = world_mgr.get_serialized_state()
    await notifier.broadcast({"type": "STATE_UPDATE", "data": state})
    return {"status": "success", "blocked_borders": list(engine.blocked_borders)}

class GrantRequest(BaseModel):
    agent_name: Optional[str] = None
    agent_id: Optional[str] = None
    item: str
    qty: int = 1
    quantity: Optional[int] = None

@app.post("/api/divine/grant", dependencies=[Depends(verify_admin_token)])
async def divine_grant(req: GrantRequest):
    name = req.agent_name or req.agent_id
    amount = req.quantity if req.quantity is not None else req.qty
    if not name or not world_mgr.engine.divine_grant(name, req.item, amount):
        raise HTTPException(status_code=404, detail="Agent not found")
    world_mgr.save_state()
    state = world_mgr.get_serialized_state()
    await notifier.broadcast({"type": "STATE_UPDATE", "data": state})
    return {"status": "success"}

class AgentTargetRequest(BaseModel):
    agent_name: Optional[str] = None
    agent_id: Optional[str] = None

@app.post("/api/divine/smite", dependencies=[Depends(verify_admin_token)])
async def divine_smite(req: AgentTargetRequest):
    name = req.agent_name or req.agent_id
    if not name or not world_mgr.engine.divine_smite(name):
        raise HTTPException(status_code=404, detail="Agent not found")
    world_mgr.save_state()
    state = world_mgr.get_serialized_state()
    await notifier.broadcast({"type": "STATE_UPDATE", "data": state})
    return {"status": "success"}

@app.post("/api/divine/bless", dependencies=[Depends(verify_admin_token)])
async def divine_bless(req: AgentTargetRequest):
    name = req.agent_name or req.agent_id
    if not name or not world_mgr.engine.divine_bless(name):
        raise HTTPException(status_code=404, detail="Agent not found")
    world_mgr.save_state()
    state = world_mgr.get_serialized_state()
    await notifier.broadcast({"type": "STATE_UPDATE", "data": state})
    return {"status": "success"}

class CalamityRequest(BaseModel):
    region: str
    calamity_type: str

@app.post("/api/divine/calamity", dependencies=[Depends(verify_admin_token)])
async def divine_calamity(req: CalamityRequest):
    if not world_mgr.engine.trigger_calamity(req.region, req.calamity_type):
        raise HTTPException(status_code=400, detail="Failed to trigger calamity")
    world_mgr.save_state()
    state = world_mgr.get_serialized_state()
    await notifier.broadcast({"type": "STATE_UPDATE", "data": state})
    return {"status": "success"}

class RaidRequest(BaseModel):
    leader_name: str
    target_region: str

@app.post("/api/divine/raid", dependencies=[Depends(verify_admin_token)])
async def divine_raid(req: RaidRequest):
    if req.target_region not in REGIONS:
        raise HTTPException(status_code=400, detail=f"Invalid target region '{req.target_region}'. Must be one of: {list(REGIONS.keys())}")
    leader = world_mgr.engine.agents.get(req.leader_name)
    if not leader:
        raise HTTPException(status_code=404, detail="Leader not found")
    world_mgr.engine._attempt_launch_raid(leader, req.target_region)
    world_mgr.save_state()
    state = world_mgr.get_serialized_state()
    await notifier.broadcast({"type": "STATE_UPDATE", "data": state})
    return {"status": "success"}

class TalkRequest(BaseModel):
    agent_name: Optional[str] = None
    agent_id: Optional[str] = None
    message: str

@app.post("/api/talk", dependencies=[Depends(verify_admin_token)])
async def deity_whisper(req: TalkRequest):
    name = req.agent_name or req.agent_id
    target = world_mgr.engine.agents.get(name) if name else None
    if not target:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:
        reply = await asyncio.to_thread(
            llm_client.handle_deity_whisper,
            target,
            req.message,
            world_mgr.engine.day,
            world_mgr.engine.hour
        )
    except AttributeError:
        sys_prompt = f"You are {target.name}, a {target.role} in {target.current_region}. Personality: {target.personality}."
        reply = await asyncio.to_thread(llm_client.direct_dialogue, req.message, sys_prompt)

    world_mgr.engine.log(f"🕊️ DEITY WHISPER to {target.name}: \"{req.message}\" -> \"{reply}\"")
    world_mgr.save_state()
    state = world_mgr.get_serialized_state()
    await notifier.broadcast({"type": "STATE_UPDATE", "data": state})
    return {"status": "success", "response": reply, "reply": reply}

class DecreeLawRequest(BaseModel):
    region_id: str
    edict_id: str

@app.post("/api/sim/decree-law", dependencies=[Depends(verify_admin_token)])
async def decree_law(req: DecreeLawRequest):
    if req.edict_id not in VALID_EDICTS:
        raise HTTPException(status_code=400, detail="Invalid edict ID")

    engine = world_mgr.engine
    target_region_key = next((r for r in REGIONS.keys() if r.lower() == req.region_id.lower()), None)
    if not target_region_key:
        raise HTTPException(status_code=404, detail=f"Region {req.region_id} not found")

    if not hasattr(engine, "active_edicts"):
        engine.active_edicts = {}

    engine.active_edicts[target_region_key] = req.edict_id
    law_name = VALID_EDICTS[req.edict_id]["name"]
    engine.log(f"📜 GUILD EDICT ENACTED: {target_region_key} has declared '{law_name}' as the supreme law of the land!")
    world_mgr.save_state()
    state = world_mgr.get_serialized_state()
    await notifier.broadcast({"type": "STATE_UPDATE", "data": state})
    return {"status": "success", "region": target_region_key, "edict": req.edict_id}

@app.get("/api/census/export")
def export_census():
    return world_mgr.get_serialized_state()


class WastelandRaidRequest(BaseModel):
    target_region: Optional[str] = None

@app.post("/api/divine/wasteland_raid", dependencies=[Depends(verify_admin_token)])
async def trigger_wasteland_raid(req: Optional[WastelandRaidRequest] = None):
    target = req.target_region if req else None
    engine = world_mgr.engine
    result = engine.spawn_wasteland_raiders(target_region=target)

    world_mgr.save_state()
    state = world_mgr.get_serialized_state()
    await notifier.broadcast({"type": "STATE_UPDATE", "data": state})

    return {"status": "success", "raid": result}

