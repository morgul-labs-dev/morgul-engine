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

NAMES = [
    "Aelric", "Bram", "Caelen", "Dorothea", "Elysia", "Farrin", "Garrow", "Helena",
    "Ivor", "Jareth", "Kaelen", "Lysandra", "Merrick", "Nesta", "Orin", "Perrin",
    "Quinn", "Rowan", "Sariel", "Thorne", "Ulric", "Vesper", "Wren", "Yvaine", "Zephyr"
]
PROFS = ["Forager", "Woodcutter", "Stonecutter", "Herbalist", "Hunter", "Weaver"]
REGIONS = [
    ("reg_river", "Riverlands", "River Valley", json.dumps({"forage_abundance": 1.0}), 0.1),
    ("reg_crag", "Crag", "Rocky Bluff", json.dumps({"stone1abundance": 1.0}), 0.2),
    ("reg_highland", "Highland", "Plateau", json.dumps({"herbal_abundance": 1.0}), 0.15),
    ("reg_lowwood", "Lowwood", "Dense Canopy", json.dumps({"game_abundance": 1.0}), 0.25)
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
    rng = Random(settings.SIMULATION_SEED)
    conn = get_connection()
    with conn:
        for tbl in ["agents", "world_state", "chronicles", "regions"]:
            conn.execute(f"DELETE FROM {tbl}")

        for rid, rname, rbiome, rres, rdanger in REGIONS:
            conn.execute(
                "INSERT INTO regions (id, name, biome, resources, danger_level) VALUES (?, ?, ?, ?, ?)",
                (rid, rname, rbiome, rres, rdanger)
            )

        conn.execute(
            "INSERT INTO world_state (day, hour, weather, active_events) VALUES (1, 0, 'Clear', '[]')"
        )

        rnames = [r[1] for r in REGIONS]
        num_founders = getattr(settings, "STARTING_FOUNDERS", 30)
        for _ in range(num_founders):
            aid = f"ag_{rng.getrandbits(32):08x}"
            name = rng.choice(NAMES)
            age = round(rng.uniform(18.0, 38.0), 2)
            region = rng.choice(rnames)
            prof = rng.choice(PROFS)
            inv = json.dumps({"rations": rng.randint(6, 10)})
            conn.execute(
                "INSERT INTO agents (id, name, generation, age, current_region, profession, health, hunger, energy, inventory, lineage, traits, is_alive) VALUES (?, ?, 1, ?, ?, ?, 100.0, 10.0, 100.0, ?, '{}', '[]', 1)",
                (aid, name, age, region, prof, inv)
            )

    conn.close()
    print(f"✄ Seeded {num_founders} founders and {len(REGIONS)} regions.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize Morgul Engine simulation world.")
    parser.add_argument("--force", action="store_true", help="Force wipe existing database and reinitialize.")
    args = parser.parse_args()
    initialize_world(force=args.force)
