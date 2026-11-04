import sys
import json
from pathlib import Path
from random import Random
from typing import Dict, Any, List

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import settings
from engine.database import get_connection

FIRST_NAMES = [
    "Aelric", "Bram", "Caelen", "Dorothea", "Elysia", "Farrin", "Garrow", "Helena",
    "Ivor", "Jareth", "Kaelen", "Lysandra", "Merrick", "Nesta", "Orin", "Perrin",
    "Quinn", "Rowan", "Sariel", "Thorne", "Ulric", "Vesper", "Wren", "Yvaine", "Zephyr"
]

PROFESSIONS = ["Forager", "Woodcutter", "Stonecutter", "Herbalist", "Hunter", "Weaver"]

class SimulationEngine:
    def __init__(self):
        settings.ensure_directories()

    def tick_hour(self) -> Dict[str, Any]:
        """Advances world by 1 hour with deterministic hourly RNG, parental infant feeding, and carrying capacity."""
        conn = get_connection()
        cycle_completed = False
        events_logged: List[str] = []

        with conn:
            state_row = conn.execute("SELECT id, day, hour, weather FROM world_state ORDER BY id DESC LIMIT 1").fetchone()
            if not state_row:
                return {"error": "World state missing. Run init_sim.py first."}

            state_id = state_row["id"]
            current_day = state_row["day"]
            current_hour = state_row["hour"] + 1

            if current_hour >= settings.HOURS_PER_DAY:
                current_hour = 0
                current_day += 1
                cycle_completed = True

            # Deterministic RNG tied strictly to seed, cycle day, and hour
            seed_base = getattr(settings, "SIMULATION_SEED", 42)
            rng = Random(f"{seed_base}:{current_day}:{current_hour}")

            is_night = (current_hour >= 22 or current_hour < 6)
            agents = conn.execute("SELECT * FROM agents WHERE is_alive = 1").fetchall()
            living_count = len(agents)

            carrying_cap = getattr(settings, "CARRYING_CAPACITY", 65)
            resource_stress = max(0.15, 1.0 - (living_count / (carrying_cap * 1.5)))

            # Pre-load state into memory for parent-infant food sharing
            agent_dict = {}
            for ag in agents:
                agent_dict[ag["id"]] = {
                    "data": ag,
                    "inv": json.loads(ag["inventory"] or "{}"),
                    "hunger": ag["hunger"],
                    "energy": ag["energy"],
                    "health": ag["health"],
                    "age": ag["age"] + (1.0 / (365.0 * 24.0)),
                    "is_alive": 1
                }

            # 1. Update Energy, Circadian Rest & Adult Foraging
            for aid, state in agent_dict.items():
                ag = state["data"]
                profession = ag["profession"] or "Forager"
                age = state["age"]

                if is_night:
                    state["energy"] = min(100.0, state["energy"] + 12.5)
                    state["hunger"] = min(100.0, state["hunger"] + 0.4)
                else:
                    state["energy"] = max(0.0, state["energy"] - 2.8)
                    state["hunger"] = min(100.0, state["hunger"] + 1.8)

                    # Only capable agents (age > infant cutoff) forage
                    infant_cutoff = getattr(settings, "INFANT_MAX_AGE", 3.0)
                    if age > infant_cutoff and state["energy"] > 20.0:
                        harvest_rate = 0.35 * resource_stress if profession in ["Forager", "Hunter", "Herbalist"] else 0.15 * resource_stress
                        if rng.random() < harvest_rate:
                            state["inv"]["rations"] = state["inv"].get("rations", 0) + 1

                # Spoilage decay above 20 rations
                if state["inv"].get("rations", 0) > 20 and rng.random() < 0.20:
                    state["inv"]["rations"] -= 1

            # 2. Nutrition Consumption & Parental Dependent Feeding
            for aid, state in agent_dict.items():
                ag = state["data"]
                age = state["age"]
                infant_cutoff = getattr(settings, "INFANT_MAX_AGE", 3.0)

                # Feed self if rations exist
                if state["hunger"] > 40.0 and state["inv"].get("rations", 0) > 0:
                    state["inv"]["rations"] -= 1
                    state["hunger"] = max(0.0, state["hunger"] - 45.0)

                # Infant parental feeding: draw from living parent if still hungry
                if state["hunger"] > 40.0 and age <= infant_cutoff:
                    lineage = json.loads(ag["lineage"] or "{}")
                    for parent_id in lineage.get("parents", []):
                        if parent_id in agent_dict and agent_dict[parent_id]["inv"].get("rations", 0) > 1:
                            agent_dict[parent_id]["inv"]["rations"] -= 1
                            state["hunger"] = max(0.0, state["hunger"] - 45.0)
                            break

                # Starvation damage or recovery
                if state["hunger"] >= settings.HUNGER_DAMAGE_THRESHOLD:
                    state["health"] -= 3.5
                elif state["hunger"] < 30.0 and state["health"] < 100.0:
                    state["health"] = min(100.0, state["health"] + 0.5)

                # Mortality check
                if state["health"] <= 0.0:
                    state["is_alive"] = 0
                    events_logged.append(f"{ag['name']} succumbed to starvation at age {int(age)}.")
                elif age >= settings.BASE_MORTALITY_AGE:
                    risk = (age - settings.BASE_MORTALITY_AGE) * 0.002
                    if rng.random() < risk:
                        state["is_alive"] = 0
                        events_logged.append(f"{ag['name']} passed away of old age at {int(age)}.")

            # Write updated agent states back to DB
            for aid, state in agent_dict.items():
                conn.execute("""
                    UPDATE agents
                    SET age = ?, hunger = ?, energy = ?, health = ?, inventory = ?, is_alive = ?
                    WHERE id = ?
                """, (
                    round(state["age"], 4),
                    round(state["hunger"], 2),
                    round(state["energy"], 2),
                    max(0.0, round(state["health"], 2)),
                    json.dumps(state["inv"]),
                    state["is_alive"],
                    aid
                ))

            # 3. Reproduction Check (Daily at hour 6)
            if current_hour == 6 and living_count < 100:
                fertile_agents = conn.execute(
                    "SELECT * FROM agents WHERE is_alive = 1 AND age >= ? AND age <= 45.0",
                    (settings.MATURITY_AGE,)
                ).fetchall()

                fertility_rate = max(0.05, 0.22 * resource_stress)
                if len(fertile_agents) >= 2 and rng.random() < fertility_rate:
                    p1, p2 = rng.sample(fertile_agents, 2)
                    child_id = f"ag_{rng.getrandbits(32):08x}"
                    child_name = rng.choice(FIRST_NAMES)
                    child_gen = max(p1["generation"], p2["generation"]) + 1
                    child_region = p1["current_region"]
                    child_prof = rng.choice(PROFESSIONS)
                    lineage = {"parents": [p1["id"], p2["id"]]}

                    conn.execute("""
                        INSERT INTO agents (
                            id, name, generation, age, current_region, profession,
                            health, hunger, energy, inventory, lineage, traits, is_alive
                        ) VALUES (?, ?, ?, 0.1, ?, ?, 100.0, 5.0, 100.0, '{"rations": 2}', ?, '[]', 1)
                    """, (child_id, child_name, child_gen, child_region, child_prof, json.dumps(lineage)))
                    events_logged.append(f"A child named {child_name} was born to {p1['name']} and {p2['name']}.")

            # 4. Commit updated world state
            conn.execute("""
                UPDATE world_state
                SET day = ?, hour = ?, active_events = ?
                WHERE id = ?
            """, (current_day, current_hour, json.dumps(events_logged), state_id))

        conn.close()

        return {
            "day": current_day,
            "hour": current_hour,
            "cycle_completed": cycle_completed,
            "events": events_logged,
        }

engine = SimulationEngine()
