import sys
import json
import uuid
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
        seed_val = getattr(settings, "SIMULATION_SEED", 42)
        self.rng = Random(seed_val)

    def tick_hour(self) -> Dict[str, Any]:
        """Advances world by 1 hour with deterministic state transitions, circadian loops, and carrying capacity."""
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

            is_night = (current_hour >= 22 or current_hour < 6)
            agents = conn.execute("SELECT * FROM agents WHERE is_alive = 1").fetchall()
            living_count = len(agents)

            # Regional Carrying Capacity: yield drops as population rises
            carrying_capacity = 65
            resource_stress = max(0.2, 1.0 - (living_count / (carrying_capacity * 1.5)))

            for agent in agents:
                aid = agent["id"]
                name = agent["name"]
                profession = agent["profession"] or "Forager"
                age = agent["age"] + (1.0 / (365.0 * 24.0))
                health = agent["health"]
                hunger = agent["hunger"]
                energy = agent["energy"]
                inv = json.loads(agent["inventory"] or "{}")

                if is_night:
                    # Circadian rest: recover energy, low metabolic draw
                    energy = min(100.0, energy + 12.5)
                    hunger = min(100.0, hunger + 0.4)
                else:
                    # Daytime labor
                    energy = max(0.0, energy - 2.8)
                    hunger = min(100.0, hunger + 1.8)

                    # Foraging with regional resource limits
                    if energy > 20.0:
                        harvest_chance = 0.35 * resource_stress if profession in ["Forager", "Hunter", "Herbalist"] else 0.15 * resource_stress
                        if self.rng.random() < harvest_chance:
                            inv["rations"] = inv.get("rations", 0) + 1

                # Ration spoilage above carrying threshold (prevents hoarding thousands of rations)
                if inv.get("rations", 0) > 20:
                    if self.rng.random() < 0.20:
                        inv["rations"] -= 1

                # Nutrition consumption
                if hunger > 40.0 and inv.get("rations", 0) > 0:
                    inv["rations"] -= 1
                    hunger = max(0.0, hunger - 45.0)

                # Starvation damage
                if hunger >= settings.HUNGER_DAMAGE_THRESHOLD:
                    health -= 3.5
                elif hunger < 30.0 and health < 100.0:
                    health = min(100.0, health + 0.5)

                # Mortality
                is_alive = 1
                if health <= 0.0:
                    is_alive = 0
                    events_logged.append(f"{name} succumbed to starvation at age {int(age)}.")
                elif age >= settings.BASE_MORTALITY_AGE:
                    risk = (age - settings.BASE_MORTALITY_AGE) * 0.002
                    if self.rng.random() < risk:
                        is_alive = 0
                        events_logged.append(f"{name} passed away of old age at {int(age)}.")

                conn.execute("""
                    UPDATE agents
                    SET age = ?, hunger = ?, energy = ?, health = ?, inventory = ?, is_alive = ?
                    WHERE id = ?
                """, (round(age, 4), round(hunger, 2), round(energy, 2), max(0.0, round(health, 2)), json.dumps(inv), is_alive, aid))

            # Reproduction: Balanced birth rate tied to regional population
            if current_hour == 6 and living_count < 100:
                fertile_agents = conn.execute(
                    "SELECT * FROM agents WHERE is_alive = 1 AND age >= ? AND age <= 45.0",
                    (settings.MATURITY_AGE,)
                ).fetchall()

                # Fertility throttles down as population nears carrying capacity
                fertility_rate = max(0.05, 0.25 * resource_stress)
                if len(fertile_agents) >= 2 and self.rng.random() < fertility_rate:
                    p1, p2 = self.rng.sample(fertile_agents, 2)
                    child_id = f"ag_{uuid.uuid4().hex[:8]}"
                    child_name = self.rng.choice(FIRST_NAMES)
                    child_gen = max(p1["generation"], p2["generation"]) + 1
                    child_region = p1["current_region"]
                    child_prof = self.rng.choice(PROFESSIONS)
                    lineage = {"parents": [p1["id"], p2["id"]]}

                    conn.execute("""
                        INSERT INTO agents (
                            id, name, generation, age, current_region, profession,
                            health, hunger, energy, inventory, lineage, traits, is_alive
                        ) VALUES (?, ?, ?, 0.1, ?, ?, 100.0, 5.0, 100.0, '{"rations": 3}', ?, '[]', 1)
                    """, (child_id, child_name, child_gen, child_region, child_prof, json.dumps(lineage)))
                    events_logged.append(f"A child named {child_name} was born to {p1['name']} and {p2['name']}.")

            # Commit updated state
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
