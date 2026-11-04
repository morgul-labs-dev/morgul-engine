import sys
import json
from pathlib import Path
from random import Random

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import settings
from engine.database import init_db, get_connection

FIRST_NAMES = [
    "Aelric", "Bram", "Caelen", "Dorothea", "Elysia", "Farrin", "Garrow", "Helena",
    "Ivor", "Jareth", "Kaelen", "Lysandra", "Merrick", "Nesta", "Orin", "Perrin",
    "Quinn", "Rowan", "Sariel", "Thorne", "Ulric", "Vesper", "Wren", "Yvaine", "Zephyr"
]

PROFESSIONS = ["Forager", "Woodcutter", "Stonecutter", "Herbalist", "Hunter", "Weaver"]
REGIONS = ["Riverlands", "Crag", "Highland", "Lowwood"]

def initialize_world():
    settings.ensure_directories()
    init_db()

    seed_val = getattr(settings, "SIMULATION_SEED", 42)
    rng = Random(seed_val)

    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM agents")
        conn.execute("DELETE FROM world_state")
        conn.execute("DELETE FROM chronicles")

        conn.execute("""
            INSERT INTO world_state (day, hour, weather, active_events)
            VALUES (1, 0, 'Clear', '[]')
        """)

        # Seed 30 founding citizens
        for i in range(30):
            aid = f"ag_{rng.getrandbits(32):08x}"
            name = rng.choice(FIRST_NAMES)
            age = round(rng.uniform(18.0, 38.0), 2)
            region = rng.choice(REGIONS)
            prof = rng.choice(PROFESSIONS)
            inv = {"rations": rng.randint(4, 8)}

            conn.execute("""
                INSERT INTO agents (
                    id, name, generation, age, current_region, profession,
                    health, hunger, energy, inventory, lineage, traits, is_alive
                ) VALUES (?, ?, 1, ?, ?, ?, 100.0, 10.0, 100.0, ?, '{}', '[]', 1)
            """, (aid, name, age, region, prof, json.dumps(inv)))

    conn.close()
    print("✓ World seeded deterministically with 30 founding citizens.")

if __name__ == "__main__":
    initialize_world()
