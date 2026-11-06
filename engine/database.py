# database.py
import sqlite3
import json
from typing import Dict, List, Set, Any, Optional
from models import Agent

import os

DB_DIR = os.getenv("DATA_DIR", "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.getenv("DB_PATH", os.path.join(DB_DIR, "civilization.db"))

FEMALE_CITIZENS = {
    "Matriarch_Yvane", "Forager_Nia", "Heresiarch_Sybil",
    "Weaver_Mira", "Serf_Cora", "Scribe_Lyric",
    "Drover_Sari", "Herdgirl_Zaya",
    "Mason_Garrick", "Forager_Elspeth",
    "Smith_Hilda", "Trapper_Freya"
}

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. World Metadata (Includes Annexation / Dominance Data)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS world_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                day INTEGER NOT NULL,
                hour INTEGER NOT NULL,
                blocked_borders TEXT NOT NULL,
                territory_control TEXT NOT NULL DEFAULT '{}'
            );
        """)

        # Auto-migration for territory_control in world_state
        cursor.execute("PRAGMA table_info(world_state);")
        world_cols = [row["name"] for row in cursor.fetchall()]
        if "territory_control" not in world_cols:
            cursor.execute("ALTER TABLE world_state ADD COLUMN territory_control TEXT NOT NULL DEFAULT '{}';")
            print("🔧 Auto-migrated schema: Added 'territory_control' to world_state.")
        if "shrines" not in world_cols:
            cursor.execute("ALTER TABLE world_state ADD COLUMN shrines TEXT NOT NULL DEFAULT '{}';")
            print("🔧 Auto-migrated schema: Added 'shrines' column to world_state.")

        # 2. Agents Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                name TEXT PRIMARY KEY,
                gender TEXT NOT NULL DEFAULT 'M',
                birth_region TEXT NOT NULL,
                current_region TEXT NOT NULL,
                social_class TEXT NOT NULL,
                role TEXT NOT NULL,
                personality TEXT NOT NULL,
                heat_tolerance INTEGER NOT NULL,
                cold_tolerance INTEGER NOT NULL,
                attractiveness INTEGER NOT NULL,
                hunger INTEGER NOT NULL,
                energy INTEGER NOT NULL,
                health INTEGER NOT NULL,
                mating_cooldown INTEGER NOT NULL,
                children_count INTEGER NOT NULL,
                is_rogue BOOLEAN NOT NULL,
                inventory TEXT NOT NULL,
                relationships TEXT NOT NULL DEFAULT '{}',
                parents TEXT NOT NULL DEFAULT '[]',
                generation INTEGER NOT NULL DEFAULT 1,
                piety INTEGER NOT NULL DEFAULT 50,
                ambition INTEGER NOT NULL DEFAULT 50,
                dread INTEGER NOT NULL DEFAULT 10
            );
        """)

        cursor.execute("PRAGMA table_info(agents);")
        columns = [row["name"] for row in cursor.fetchall()]
        
        if "piety" not in columns:
            cursor.execute("ALTER TABLE agents ADD COLUMN piety INTEGER NOT NULL DEFAULT 50;")
        if "ambition" not in columns:
            cursor.execute("ALTER TABLE agents ADD COLUMN ambition INTEGER NOT NULL DEFAULT 50;")
        if "dread" not in columns:
            cursor.execute("ALTER TABLE agents ADD COLUMN dread INTEGER NOT NULL DEFAULT 10;")
        if "parents" not in columns:
            cursor.execute("ALTER TABLE agents ADD COLUMN parents TEXT NOT NULL DEFAULT '[]';")
        if "generation" not in columns:
            cursor.execute("ALTER TABLE agents ADD COLUMN generation INTEGER NOT NULL DEFAULT 1;")
        if "gender" not in columns:
            cursor.execute("ALTER TABLE agents ADD COLUMN gender TEXT NOT NULL DEFAULT 'M';")
        if "age" not in columns:
            cursor.execute("ALTER TABLE agents ADD COLUMN age REAL NOT NULL DEFAULT 24.0;")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                day INTEGER NOT NULL,
                hour INTEGER NOT NULL,
                memory_text TEXT NOT NULL,
                FOREIGN KEY (agent_name) REFERENCES agents(name)
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS divine_chronicle (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day INTEGER NOT NULL,
                hour INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                target TEXT NOT NULL,
                details TEXT NOT NULL
            );
        """)
        conn.commit()

def save_world(day: int, hour: int, blocked_borders: Set[str], agents: Dict[str, Agent], territory_control: Optional[Dict[str, Any]] = None, shrines: Optional[Dict[str, Any]] = None):
    with get_connection() as conn:
        cursor = conn.cursor()
        
        borders_json = json.dumps(list(blocked_borders))
        territory_json = json.dumps(territory_control or {})
        shrines_json = json.dumps(shrines or {})
        
        cursor.execute("""
            INSERT INTO world_state (id, day, hour, blocked_borders, territory_control, shrines)
            VALUES (1, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                day=excluded.day,
                hour=excluded.hour,
                blocked_borders=excluded.blocked_borders,
                territory_control=excluded.territory_control,
                shrines=excluded.shrines;
        """, (day, hour, borders_json, territory_json, shrines_json))

        for agent in agents.values():
            cursor.execute("""
                INSERT INTO agents (
                    name, gender, birth_region, current_region, social_class, role,
                    personality, heat_tolerance, cold_tolerance, attractiveness,
                    hunger, energy, health, mating_cooldown, children_count,
                    is_rogue, inventory, relationships, parents, generation,
                    piety, ambition, dread, age
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    age=excluded.age,
                    gender=excluded.gender,
                    current_region=excluded.current_region,
                    social_class=excluded.social_class,
                    role=excluded.role,
                    hunger=excluded.hunger,
                    energy=excluded.energy,
                    health=excluded.health,
                    attractiveness=excluded.attractiveness,
                    mating_cooldown=excluded.mating_cooldown,
                    children_count=excluded.children_count,
                    inventory=excluded.inventory,
                    relationships=excluded.relationships,
                    parents=excluded.parents,
                    generation=excluded.generation,
                    piety=excluded.piety,
                    ambition=excluded.ambition,
                    dread=excluded.dread;
            """, (
                agent.name, getattr(agent, "gender", "M"),
                agent.birth_region, agent.current_region,
                agent.social_class, agent.role, agent.personality,
                agent.heat_tolerance, agent.cold_tolerance, agent.attractiveness,
                agent.hunger, agent.energy, agent.health,
                agent.mating_cooldown, agent.children_count,
                1 if agent.is_rogue else 0,
                json.dumps(agent.inventory),
                json.dumps(getattr(agent, "relationships", {})),
                json.dumps(getattr(agent, "parents", [])),
                getattr(agent, "generation", 1),
                getattr(agent, "piety", 50),
                getattr(agent, "ambition", 50),
                getattr(agent, "dread", 10),
                getattr(agent, "age", 24.0)
            ))
            
        conn.commit()

def record_memory(agent_name: str, day: int, hour: int, text: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO agent_memories (agent_name, day, hour, memory_text)
            VALUES (?, ?, ?, ?);
        """, (agent_name, day, hour, text))
        conn.commit()

def record_divine_action(day: int, hour: int, action_type: str, target: str, details: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO divine_chronicle (day, hour, action_type, target, details)
            VALUES (?, ?, ?, ?, ?);
        """, (day, hour, action_type, target, details))
        conn.commit()

def load_world() -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT day, hour, blocked_borders, territory_control FROM world_state WHERE id = 1;")
        world_row = cursor.fetchone()
        if not world_row:
            return None

        day = world_row["day"]
        hour = world_row["hour"]
        blocked_borders = set(json.loads(world_row["blocked_borders"]))
        
        territory_control = {}
        if "territory_control" in world_row.keys() and world_row["territory_control"]:
            try:
                territory_control = json.loads(world_row["territory_control"])
            except Exception:
                territory_control = {}

        shrines = {}
        if "shrines" in world_row.keys() and world_row["shrines"]:
            try:
                shrines = json.loads(world_row["shrines"])
            except Exception:
                shrines = {}

        cursor.execute("SELECT * FROM agents;")
        agent_rows = cursor.fetchall()
        agents: Dict[str, Agent] = {}

        for row in agent_rows:
            if row["name"] in FEMALE_CITIZENS:
                gender_val = "F"
            elif "gender" in row.keys() and row["gender"]:
                gender_val = row["gender"]
            else:
                gender_val = "M"

            parents_val = json.loads(row["parents"]) if "parents" in row.keys() and row["parents"] else []
            gen_val = row["generation"] if "generation" in row.keys() and row["generation"] else 1
            piety_val = row["piety"] if "piety" in row.keys() and row["piety"] is not None else 50
            ambition_val = row["ambition"] if "ambition" in row.keys() and row["ambition"] is not None else 50
            dread_val = row["dread"] if "dread" in row.keys() and row["dread"] is not None else 10

            age_val = row["age"] if "age" in row.keys() and row["age"] is not None else 24.0

            agent = Agent(
                name=row["name"],
                gender=gender_val,
                birth_region=row["birth_region"],
                current_region=row["current_region"],
                social_class=row["social_class"],
                role=row["role"],
                personality=row["personality"],
                heat_tolerance=row["heat_tolerance"],
                cold_tolerance=row["cold_tolerance"],
                attractiveness=row["attractiveness"],
                initial_inventory=json.loads(row["inventory"]),
                is_rogue=bool(row["is_rogue"]),
                parents=parents_val,
                generation=gen_val,
                piety=piety_val,
                ambition=ambition_val,
                dread=dread_val,
                age=age_val
            )
            agent.hunger = row["hunger"]
            agent.energy = row["energy"]
            agent.health = row["health"]
            agent.mating_cooldown = row["mating_cooldown"]
            agent.children_count = row["children_count"]
            
            if "relationships" in row.keys() and row["relationships"]:
                agent.relationships = json.loads(row["relationships"])
            else:
                agent.relationships = {}

            cur2 = conn.cursor()
            cur2.execute("""
                SELECT memory_text FROM agent_memories
                WHERE agent_name = ?
                ORDER BY id DESC
                LIMIT 12;
            """, (agent.name,))
            mem_rows = cur2.fetchall()
            agent.memories = [m["memory_text"] for m in reversed(mem_rows)]

            agents[agent.name] = agent

        import seeds
        initial_pop = seeds.get_initial_population()
        for seed_agent in initial_pop:
            if seed_agent.name not in agents:
                agents[seed_agent.name] = seed_agent
                print(f"✨ New Lore Inhabitant arrived: {seed_agent.name} in {seed_agent.current_region}")

        save_world(day, hour, blocked_borders, agents, territory_control, shrines)

        return {
            "day": day,
            "hour": hour,
            "blocked_borders": blocked_borders,
            "agents": agents,
            "territory_control": territory_control,
            "shrines": shrines
        }
def delete_agent(agent_name: str, day: Optional[int] = None, hour: Optional[int] = None, cause: Optional[str] = None):
    with get_connection() as conn:
        cursor = conn.cursor()
        if day is not None and hour is not None and cause is not None:
            cursor.execute("SELECT role, current_region, generation, age FROM agents WHERE name = ?;", (agent_name,))
            row = cursor.fetchone()
            if row:
                role, region, gen, age = row[0], row[1], row[2], row[3]
                details = f"{agent_name} ({role or 'Inhabitant'}, Gen {gen}, Age {age:.1f}) perished in {region}: {cause}"
            else:
                details = f"{agent_name} perished: {cause}"
            cursor.execute('''
                INSERT INTO divine_chronicle (day, hour, action_type, target, details)
                VALUES (?, ?, 'mortality', ?, ?);
            ''', (day, hour, agent_name, details))
        cursor.execute("DELETE FROM agents WHERE name = ?;", (agent_name,))
        conn.commit()
