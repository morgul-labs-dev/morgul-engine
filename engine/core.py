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

NAMES = [
    "Aelric", "Bram", "Caelen", "Dorothea", "Elysia", "Farrin", "Garrow", "Helena",
    "Ivor", "Jareth", "Kaelen", "Lysandra", "Merrick", "Nesta", "Orin", "Perrin",
    "Quinn", "Rowan", "Sariel", "Thorne", "Ulric", "Vesper", "Wren", "Yvaine", "Zephyr"
]
PROFS = ["Forager", "Woodcutter", "Stonecutter", "Herbalist", "Hunter", "Weaver"]

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
        conn = self.get_conn()
        cycle_completed = False
        events_logged: List[str] = []

        with conn:
            row = conn.execute("SELECT id, day, hour, weather FROM world_state ORDER BY id DESC LIMIT 1").fetchone()
            if not row:
                return {"error": "World state missing. Run init_sim.py first."}

            state_id, current_day, current_hour = row["id"], row["day"], row["hour"] + 1
            if current_hour >= settings.HOURS_PER_DAY:
                current_hour = 0
                current_day += 1
                cycle_completed = True

            rng = Random(f"{settings.SIMULATION_SEED}:{current_day}:{current_hour}")
            is_night = (current_hour >= 22 or current_hour < 6)
            agents = conn.execute("SELECT * FROM agents WHERE is_alive = 1").fetchall()

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

            adults = [aid for aid, s in agent_dict.items() if s["age"] > settings.INFANT_MAX_AGE]
            density = len(adults) / max(1, settings.CARRYING_CAPACITY)
            yield_mult = max(0.22, 1.0 - (0.55 * max(0.0, density - 0.5)))

            for aid, s in agent_dict.items():
                prof = s["data"]["profession"] or "Forager"
                if is_night:
                    s["energy"] = min(100.0, s["energy"] + 12.5)
                    s["hunger"] = min(100.0, s["hunger"] + 0.35)
                else:
                    s["energy"] = max(0.0, s["energy"] - 2.5)
                    s["hunger"] = min(100.0, s["hunger"] + 1.2)
                    if s["age"] > settings.INFANT_MAX_AGE and s["energy"] > 20.0:
                        base_h = 0.36 if prof in ["Forager", "Hunter", "Herbalist"] else 0.22
                        if rng.random() < (base_h * yield_mult):
                            s["inv"]["rations"] = s["inv"].get("rations", 0) + 1

                # Daily spoilage
                if current_hour == 0 and s["inv"].get("rations", 0) > 20:
                    ex = s["inv"]["rations"] - 20
                    spoil = max(1, int(ex * 0.06))
                    if s["inv"]["rations"] > 40:
                        spoil += int((s["inv"]["rations"] - 40) * 0.12)
                    s["inv"]["rations"] = max(20, s["inv"]["rations"] - spoil)

            # Dependent feeding priority: self -> parents -> community surplus
            for aid, s in agent_dict.items():
                if s["age"] <= settings.INFANT_MAX_AGE and s["hunger"] > 35.0:
                    if s["inv"].get("rations", 0) > 0:
                        s["inv"]["rations"] -= 1
                        s["hunger"] = max(0.0, s["hunger"] - 45.0)
                    if s["hunger"] > 35.0:
                        lin = json.loads(s["data"]["lineage"] or "{}")
                        for pid in lin.get("parents", []):
                            if pid in agent_dict and agent_dict[pid]["inv"].get("rations", 0) > 0:
                                agent_dict[pid]["inv"]["rations"] -= 1
                                s["hunger"] = max(0.0, s["hunger"] - 45.0)
                                if s["hunger"] <= 35.0:
                                    break
                    if s["hunger"] > 35.0:
                        for d_s in agent_dict.values():
                            if d_s["age"] > settings.INFANT_MAX_AGE and d_s["inv"].get("rations", 0) >= 4:
                                d_s["inv"]["rations"] -= 1
                                s["hunger"] = max(0.0, s["hunger"] - 45.0)
                                break

            # Adults eat
            for aid, s in agent_dict.items():
                if s["age"] > settings.INFANT_MAX_AGE and s["hunger"] > 40.0 and s["inv"].get("rations", 0) > 0:
                    s["inv"]["rations"] -= 1
                    s["hunger"] = max(0.0, s["hunger"] - 45.0)

            # Health & Daily Natural Mortality (checked once per day at hour 0)
            for aid, s in agent_dict.items():
                name, age = s["data"]["name"], s["age"]
                if s["hunger"] >= settings.HUNGER_DAMAGE_THRESHOLD:
                    s["health"] -= 3.0
                elif s["hunger"] < 30.0 and s["health"] < 100.0:
                    s["health"] = min(100.0, s["health"] + 0.6)

                if s["health"] <= 0.0:
                    s["is_alive"] = 0
                    events_logged.append(f"{name} succumbed to starvation at age {int(age)}.")
                elif current_hour == 0:
                    if age >= settings.BASE_MORTALITY_AGE:
                        if rng.random() < ((age - settings.BASE_MORTALITY_AGE) * 0.003):
                            s["is_alive"] = 0
                            events_logged.append(f"{name} passed away of old age at {int(age)}.")
                    elif age >= 22.0:
                        wear_prob = 0.00003 + ((age - 22.0) * 0.000004)
                        if rng.random() < wear_prob:
                            s["is_alive"] = 0
                            events_logged.append(f"{name} succumbed to illness at age {int(age)}.")

            conn.executemany(
                "UPDATE agents SET age=?, hunger=?, energy=?, health=?, inventory=?, is_alive=? WHERE id=?",
                [
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
            )

            # Reproduction (Daily at hour 6)
            living_total = sum(1 for s in agent_dict.values() if s["is_alive"] == 1)
            if current_hour == 6 and living_total < settings.CARRYING_CAPACITY * 1.2:
                fertile = [
                    s for s in agent_dict.values()
                    if s["is_alive"] == 1
                    and settings.MATURITY_AGE <= s["age"] <= 48.0
                    and s["inv"].get("rations", 0) >= 8
                ]
                headroom = (settings.CARRYING_CAPACITY - living_total) / settings.CARRYING_CAPACITY
                if headroom > 0:
                    b_prob = 0.015 + (0.16 * headroom)
                else:
                    b_prob = max(0.006, 0.015 + (0.05 * headroom))

                if len(fertile) >= 2 and rng.random() < b_prob:
                    p1, p2 = rng.sample(fertile, 2)
                    cid = f"ag_{rng.getrandbits(32):08x}"
                    cname = rng.choice(NAMES)
                    cgen = max(p1["data"]["generation"], p2["data"]["generation"]) + 1
                    p1["inv"]["rations"] -= 2
                    p2["inv"]["rations"] -= 2
                    conn.execute("UPDATE agents SET inventory=? WHERE id=?", (json.dumps(p1["inv"]), p1["data"]["id"]))
                    conn.execute("UPDATE agents SET inventory=? WHERE id=?", (json.dumps(p2["inv"]), p2["data"]["id"]))

                    child_inv = json.dumps({"rations": 4})
                    child_lineage = json.dumps({"parents": [p1["data"]["id"], p2["data"]["id"]]})
                    conn.execute(
                        "INSERT INTO agents (id, name, generation, age, current_region, profession, health, hunger, energy, inventory, lineage, traits, is_alive) VALUES (?, ?, ?, 0.1, ?, ?, 100.0, 5.0, 100.0, ?, ?, '[]', 1)",
                        (cid, cname, cgen, p1["data"]["current_region"], rng.choice(PROFS), child_inv, child_lineage)
                    )
                    events_logged.append(f"A child named {cname} was born to {p1['data']['name']} and {p2['data']['name']}.")

            conn.execute(
                "UPDATE world_state SET day=?, hour=?, active_events=? WHERE id=?",
                (current_day, current_hour, json.dumps(events_logged), state_id)
            )

        return {
            "day": current_day,
            "hour": current_hour,
            "cycle_completed": cycle_completed,
            "events": events_logged
        }

engine = SimulationEngine()
