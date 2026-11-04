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
        self._conn = None

    def get_conn(self):
        if self._conn is None:
            self._conn = get_connection()
            self._conn.execute("PRAGMA journal_mode = WAL")
        return self._conn

    def tick_hour(self) -> Dict[str, Any]:
        """Advances world by 1 hour with deterministic hourly RNG, parental dependent feeding, and carrying capacity."""
        conn = self.get_conn()
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
            rng = Random(f"{settings.SIMULATION_SEED}:{current_day}:{current_hour}")

            is_night = (current_hour >= 22 or current_hour < 6)
            agents = conn.execute("SELECT * FROM agents WHERE is_alive = 1").fetchall()

            # Pre-load state into memory
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

            # 1. Carrying Capacity Pressure
            capable_adults = [aid for aid, s in agent_dict.items() if s["age"] > settings.INFANT_MAX_AGE]
            adult_count = len(capable_adults)
            
            # Density curve: harvest rate responds dynamically to crowding
            density = adult_count / max(1, settings.CARRYING_CAPACITY)
            yield_multiplier = max(0.18, 1.0 - (0.65 * max(0.0, density - 0.5)))

            # 2. Update Energy, Circadian Rest & Adult Foraging
            for aid, state in agent_dict.items():
                ag = state["data"]
                profession = ag["profession"] or "Forager"
                age = state["age"]

                if is_night:
                    state["energy"] = min(100.0, state["energy"] + 12.5)
                    state["hunger"] = min(100.0, state["hunger"] + 0.35)
                else:
                    state["energy"] = max(0.0, state["energy"] - 2.5)
                    state["hunger"] = min(100.0, state["hunger"] + 1.25)

                    # Only capable agents forage
                    if age > settings.INFANT_MAX_AGE and state["energy"] > 20.0:
                        base_harvest = 0.36 if profession in ["Forager", "Hunter", "Herbalist"] else 0.22
                        harvest_rate = base_harvest * yield_multiplier
                        if rng.random() < harvest_rate:
                            state["inv"]["rations"] = state["inv"].get("rations", 0) + 1

                # Daily Spoilage: executed at midnight (hour 0)
                # Removes 5% of excess over 20 rations, plus spoilage acceleration over 40
                if current_hour == 0 and state["inv"].get("rations", 0) > 20:
                    excess = state["inv"]["rations"] - 20
                    spoilage = max(1, int(excess * 0.05))
                    if state["inv"]["rations"] > 40:
                        spoilage += int((state["inv"]["rations"] - 40) * 0.10)
                    state["inv"]["rations"] = max(20, state["inv"]["rations"] - spoilage)

            # 3. Nutrition: Feed Dependents First, Then Adults
            for aid, state in agent_dict.items():
                if state["age"] <= settings.INFANT_MAX_AGE and state["hunger"] > 40.0:
                    if state["inv"].get("rations", 0) > 0:
                        state["inv"]["rations"] -= 1
                        state["hunger"] = max(0.0, state["hunger"] - 45.0)

                    # Feed from living parents first
                    if state["hunger"] > 40.0:
                        lineage = json.loads(state["data"]["lineage"] or "{}")
                        for parent_id in lineage.get("parents", []):
                            if parent_id in agent_dict and agent_dict[parent_id]["inv"].get("rations", 0) > 0:
                                agent_dict[parent_id]["inv"]["rations"] -= 1
                                state["hunger"] = max(0.0, state["hunger"] - 45.0)
                                if state["hunger"] <= 40.0:
                                    break

                    # Surplus community aid for vulnerable infants
                    if state["hunger"] > 40.0:
                        for donor_id, donor_state in agent_dict.items():
                            if donor_state["age"] > settings.INFANT_MAX_AGE and donor_state["inv"].get("rations", 0) >= 6:
                                donor_state["inv"]["rations"] -= 1
                                state["hunger"] = max(0.0, state["hunger"] - 45.0)
                                break

            # Adults eat their own rations
            for aid, state in agent_dict.items():
                if state["age"] > settings.INFANT_MAX_AGE and state["hunger"] > 40.0:
                    if state["inv"].get("rations", 0) > 0:
                        state["inv"]["rations"] -= 1
                        state["hunger"] = max(0.0, state["hunger"] - 45.0)

            # 4. Starvation & Mortality
            for aid, state in agent_dict.items():
                ag = state["data"]
                age = state["age"]

                if state["hunger"] >= settings.HUNGER_DAMAGE_THRESHOLD:
                    state["health"] -= 3.0
                elif state["hunger"] < 30.0 and state["health"] < 100.0:
                    state["health"] = min(100.0, state["health"] + 0.6)

                if state["health"] <= 0.0:
                    state["is_alive"] = 0
                    events_logged.append(f"{ag['name']} succumbed to starvation at age {int(age)}.")
                elif age >= settings.BASE_MORTALITY_AGE:
                    risk = (age - settings.BASE_MORTALITY_AGE) * 0.003
                    if rng.random() < risk:
                        state["is_alive"] = 0
                        events_logged.append(f"{ag['name']} passed away of old age at {int(age)}.")
                elif age >= 35.0:
                    # Natural adult illness/wear baseline (~1-2 deaths per year across community)
                    if rng.random() < 0.00008:
                        state["is_alive"] = 0
                        events_logged.append(f"{ag['name']} succumbed to illness at age {int(age)}.")

            # Batch update state
            update_rows = [
                (
                    round(s["age"], 4),
                    round(s["hunger"], 2),
                    round(s["energy"], 2),
                    max(0.0, round(s["health"], 2)),
                    json.dumps(s["inv"]),
                    s["is_alive"],
                    aid
                )
                for aid, s in agent_dict.items()
            ]
            conn.executemany("""
                UPDATE agents
                SET age = ?, hunger = ?, energy = ?, health = ?, inventory = ?, is_alive = ?
                WHERE id = ?
            """, update_rows)

                        # 5. Food-gated reproduction (Natural soft equilibrium around CARRYING_CAPACITY)
            living_total = len([s for s in agent_dict.values() if s["is_alive"] == 1])
            if current_hour == 6:
                fertile_agents = [
                    s for s in agent_dict.values()
                    if s["is_alive"] == 1 
                    and settings.MATURITY_AGE <= s["age"] <= 45.0 
                    and s["inv"].get("rations", 0) >= 8
                ]

                # Soft logistic pressure: fertility slows when overcrowded, accelerates when underpopulated
                density_factor = living_total / max(1, settings.CARRYING_CAPACITY)
                birth_prob = max(0.015, 0.16 * (1.25 - (0.75 * density_factor)))
                
                if len(fertile_agents) >= 2 and rng.random() < birth_prob:
                    p1, p2 = rng.sample(fertile_agents, 2)
                    child_id = f"ag_{rng.getrandbits(32):08x}"
                    child_name = rng.choice(FIRST_NAMES)
                    child_gen = max(p1["data"]["generation"], p2["data"]["generation"]) + 1
                    child_region = p1["data"]["current_region"]
                    child_prof = rng.choice(PROFESSIONS)
                    lineage = {"parents": [p1["data"]["id"], p2["data"]["id"]]}

                    p1["inv"]["rations"] -= 2
                    p2["inv"]["rations"] -= 2
                    conn.execute("UPDATE agents SET inventory = ? WHERE id = ?", (json.dumps(p1["inv"]), p1["data"]["id"]))
                    conn.execute("UPDATE agents SET inventory = ? WHERE id = ?", (json.dumps(p2["inv"]), p2["data"]["id"]))

                    conn.execute("""
                        INSERT INTO agents (
                            id, name, generation, age, current_region, profession,
                            health, hunger, energy, inventory, lineage, traits, is_alive
                        ) VALUES (?, ?, ?, 0.1, ?, ?, 100.0, 5.0, 100.0, '{"rations": 3}', ?, '[]', 1)
                    """, (child_id, child_name, child_gen, child_region, child_prof, json.dumps(lineage)))
                    events_logged.append(f"A child named {child_name} was born to {p1['data']['name']} and {p2['data']['name']}.")

            # 6. Commit world state
            conn.execute("""
                UPDATE world_state
                SET day = ?, hour = ?, active_events = ?
                WHERE id = ?
            """, (current_day, current_hour, json.dumps(events_logged), state_id))

        return {
            "day": current_day,
            "hour": current_hour,
            "cycle_completed": cycle_completed,
            "events": events_logged,
        }

engine = SimulationEngine()
