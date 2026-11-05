import sys
import json
import argparse
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
REGIONS = [
    ("Riverlands", "Fertile river delta with abundant forage and fresh water."),
    ("Crag", "Rugged rocky bluffs rich in stone and timber."),
    ("Highland", "Windswept plateau suitable for grazing and herbal collection."),
    ("Lowwood", "Dense ancient canopy providing rich game and foraging.")
]

def initialize_world(force: bool = False):
    settings.ensure_directories()
    
    if settings.DB_PATH.exists() and not force:
        conn = get_connection()
        try:
            count = conn.execute("SELECT COUNT(*) FROM world_state").fetchone()[0]
        except Exception:
            count = 0
        conn.close()
        if count > 0:
            print(f"[!] Existing world detected at {settings.DB_PATH}. Pass --force to wipe and re-initialize.")
            return

    init_db()

    seed_val = getattr(settings, "SIMULATION_SEED", 42)
    rng = Random(seed_val)

    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM agents")
        conn.execute("DELETE FROM world_state")
        conn.execute("DELETE FROM chronicles")
        try:
            conn.execute("DELETE FROM regions")
        except Exception:
            pass

        # Seed Regions
        for r_name, r_desc in REGIONS:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO regions (name, description, resources)
                    VALUES (?, ?, ?)
                """, (r_name, r_desc, json.dumps({"forage_abundance": 1.0})))
            except Exception:
                pass

        conn.execute("""
            INSERT INTO world_state (day, hour, weather, active_events)
            VALUES (1, 0, 'Clear', '[]')
        """)

        # Seed starting citizens
        region_names = [r[0] for r in REGIONS]
        num_founders = getattr(settings, "STARTING_FOUNDERS", 30)
        for i in range(num_founders):
            aid = f"ag_{rng.getrandbits(32):08x}"
            name = rng.choice(FIRST_NAMES)
            age = round(rng.uniform(18.0, 38.0), 2)
            region = rng.choice(region_names)
            prof = rng.choice(PROFESSIONS)
            inv = {"rations": rng.randint(4, 8)}

            conn.execute("""
                INSERT INTO agents (
                    id, name, generation, age, current_region, profession,
                    health, hunger, energy, inventory, lineage, traits, is_alive
                ) VALUES (?, ?, 1, ?, ?, ?, 100.0, 10.0, 100.0, ?, '{}', '[]', 1)
            """, (aid, name, age, region, prof, json.dumps(inv)))

    conn.close()
    print(f"✓ World seeded deterministically with {num_founders} founding citizens and {len(REGIONS)} regions.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize Morgul Engine simulation world.")
    parser.add_argument("--force", action="store_true", help="Force wipe existing database and reinitialize.")
    args = parser.parse_args()
    initialize_world(force=args.force)
