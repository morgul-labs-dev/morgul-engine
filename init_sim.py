import argparse
import json
import random
import uuid
from engine.database import get_connection, init_db
from config import settings

DEFAULT_REGIONS = [
    {"id": "reg_haven", "name": "The Sylvan Vale", "biome": "Forest", "resources": {"timber": 850, "game": 600, "forage": 700}, "danger_level": 0.05},
    {"id": "reg_cairn", "name": "Cairn Plateau", "biome": "Highlands", "resources": {"stone": 950, "ore": 500, "forage": 250}, "danger_level": 0.15},
    {"id": "reg_fen", "name": "Mirefang Delta", "biome": "Swamp", "resources": {"herbs": 750, "fish": 800, "peat": 450}, "danger_level": 0.25},
    {"id": "reg_strand", "name": "The Sunken Strand", "biome": "Coast", "resources": {"salt": 600, "fish": 900, "driftwood": 400}, "danger_level": 0.10}
]

FIRST_NAMES = [
    "Aelric", "Bram", "Caelen", "Dorothea", "Elysia", "Farrin", "Garrow", "Helena",
    "Ivor", "Jareth", "Kaelen", "Lysandra", "Merrick", "Nesta", "Orin", "Perrin",
    "Quinn", "Rowan", "Sariel", "Thorne", "Ulric", "Vesper", "Wren", "Yvaine", "Zephyr"
]

PROFESSIONS = ["Forager", "Woodcutter", "Stonecutter", "Herbalist", "Hunter", "Weaver"]

def seed_simulation(founders_count: int, reset: bool = False):
    if reset and settings.DB_PATH.exists():
        settings.DB_PATH.unlink(missing_ok=True)
        print("Existing database wiped.")

    init_db()
    conn = get_connection()

    with conn:
        # Check if already seeded
        existing_agents = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
        if existing_agents > 0 and not reset:
            print(f"Simulation already contains {existing_agents} agents. Pass --reset to re-seed.")
            return

        # 1. Initialize World State
        conn.execute("""
            INSERT INTO world_state (day, hour, weather, active_events)
            VALUES (1, 6, 'Dawn Mist', '[]')
        """)

        # 2. Seed Regions
        for r in DEFAULT_REGIONS:
            conn.execute("""
                INSERT OR REPLACE INTO regions (id, name, biome, resources, danger_level)
                VALUES (?, ?, ?, ?, ?)
            """, (r["id"], r["name"], r["biome"], json.dumps(r["resources"]), r["danger_level"]))

        # 3. Seed Founder Agents with Staggered Demographics
        names_pool = FIRST_NAMES.copy()
        random.shuffle(names_pool)

        for i in range(founders_count):
            agent_id = f"ag_{uuid.uuid4().hex[:8]}"
            name = names_pool[i % len(names_pool)] if i < len(names_pool) else f"Founder {i+1}"
            
            # Stagger founder ages (18 to 36) to prevent simultaneous demographic collapse
            age = round(random.uniform(18.0, 36.0), 1)
            region = random.choice(DEFAULT_REGIONS)["id"]
            profession = random.choice(PROFESSIONS)
            
            inventory = {
                "rations": random.randint(4, 8),
                "tools": 1
            }

            conn.execute("""
                INSERT INTO agents (
                    id, name, generation, age, current_region, profession,
                    health, hunger, energy, inventory, lineage, traits, is_alive
                ) VALUES (?, ?, 1, ?, ?, ?, 100.0, 10.0, 100.0, ?, '{}', '[]', 1)
            """, (agent_id, name, age, region, profession, json.dumps(inventory)))

    conn.close()
    print(f"Simulation seeded successfully with {len(DEFAULT_REGIONS)} regions and {founders_count} founder agents.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Autonomous AI World Engine")
    parser.add_argument("--founders", type=int, default=settings.STARTING_FOUNDERS, help="Number of starting agents")
    parser.add_argument("--reset", action="store_true", help="Wipe database before seeding")
    args = parser.parse_args()

    seed_simulation(founders_count=args.founders, reset=args.reset)
