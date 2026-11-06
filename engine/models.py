import random
from typing import List, Dict, Any, Optional

class Agent:
    def __init__(
        self,
        name: str,
        gender: str,  # "M" or "F"
        birth_region: str,
        current_region: str,
        social_class: str = "Commoner",
        role: str = "Apprentice",
        personality: str = "Pragmatic and focused on survival.",
        heat_tolerance: int = 50,
        cold_tolerance: int = 50,
        attractiveness: int = 50,
        initial_inventory: Optional[Dict[str, int]] = None,
        is_rogue: bool = False,
        parents: Optional[List[str]] = None,
        generation: int = 1,
        piety: int = 50,
        ambition: int = 50,
        dread: int = 10,
        age: float = 16.0
    ):
        self.name = name
        self.gender = gender
        self.birth_region = birth_region
        self.current_region = current_region
        self.social_class = social_class
        self.role = role
        self.personality = personality
        self.is_rogue = is_rogue
        self.parents = parents or []
        self.generation = generation
        self.age = age
        self.deity_memory: List[Dict[str, str]] = []

        # Physical Attributes (0-100)
        self.heat_tolerance = heat_tolerance
        self.cold_tolerance = cold_tolerance
        self.attractiveness = attractiveness
        self.hunger = 10
        self.energy = 100
        self.health = 100

        # Psychological Drives (0-100)
        self.piety = piety
        self.ambition = ambition
        self.dread = dread

        # Reproduction trackers
        self.mating_cooldown = 0
        self.children_count = 0

        # Social Graph: { "Other_Agent_Name": score (-100 to 100) }
        self.relationships: Dict[str, int] = {}

        self.inventory = initial_inventory or {"food": 2}
        self.memories: List[str] = [
            f"Born in {birth_region} as a {social_class} class {role}."
        ]

    @property
    def region_id(self) -> str:
        return self.current_region

    @property
    def region(self) -> str:
        return self.current_region

    def modify_relationship(self, other_name: str, delta: int):
        current = self.relationships.get(other_name, 0)
        self.relationships[other_name] = max(-100, min(100, current + delta))

    def get_relationship(self, other_name: str) -> int:
        return self.relationships.get(other_name, 0)

    def add_memory(self, event: str, day: int = 1, hour: int = 6):
        self.memories.append(event)
        if len(self.memories) > 12:
            self.memories.pop(0)
        try:
            import database
            database.record_memory(self.name, day, hour, event)
        except Exception:
            pass

    @classmethod
    def spawn_child(cls, parent_a: 'Agent', parent_b: 'Agent', global_id: int) -> 'Agent':
        is_rogue = random.random() < 0.025
        child_gender = "M" if random.random() < 0.512 else "F"
        next_gen = max(parent_a.generation, parent_b.generation) + 1

        def blend(stat_a: int, stat_b: int) -> int:
            val = int((stat_a + stat_b) / 2 + random.randint(-5, 5))
            return max(0, min(100, val))

        child_piety = blend(parent_a.piety, parent_b.piety)
        child_ambition = blend(parent_a.ambition, parent_b.ambition)
        child_dread = max(5, int((parent_a.dread + parent_b.dread) / 2))

        if is_rogue:
            child = cls(
                name=f"Rogue_{parent_a.name[:3]}{parent_b.name[:3]}_{global_id}",
                gender=child_gender,
                birth_region=parent_a.current_region,
                current_region=parent_a.current_region,
                social_class="Low",
                role="Wild Outcast",
                personality="Defiant, detached from ancestral customs, driven by independent ambition.",
                heat_tolerance=random.randint(5, 95),
                cold_tolerance=random.randint(5, 95),
                attractiveness=random.randint(5, 95),
                initial_inventory={"food": 2},
                is_rogue=True,
                parents=[parent_a.name, parent_b.name],
                generation=next_gen,
                piety=random.randint(5, 30),
                ambition=random.randint(70, 95),
                dread=random.randint(5, 35),
                age=0.0
            )
            child.memories = [f"Born a rogue outlier in {parent_a.current_region}. Disavowed familial bonds."]
            return child

        child = cls(
            name=f"{parent_a.name.split('_')[0]}_{parent_b.name.split('_')[0]}_{global_id}",
            gender=child_gender,
            birth_region=parent_a.current_region,
            current_region=parent_a.current_region,
            social_class=getattr(parent_a, "social_class", "Commoner"),
            role="Apprentice",
            personality=f"Offspring of {parent_a.name} and {parent_b.name}. Strives for survival and status.",
            heat_tolerance=blend(parent_a.heat_tolerance, parent_b.heat_tolerance),
            cold_tolerance=blend(parent_a.cold_tolerance, parent_b.cold_tolerance),
            attractiveness=blend(parent_a.attractiveness, parent_b.attractiveness),
            initial_inventory={"food": 2},
            is_rogue=False,
            parents=[parent_a.name, parent_b.name],
            generation=next_gen,
            piety=child_piety,
            ambition=child_ambition,
            dread=child_dread,
            age=0.0
        )
        child.memories = [f"Born in {parent_a.current_region} to {parent_a.name} and {parent_b.name}."]

        child.modify_relationship(parent_a.name, +60)
        child.modify_relationship(parent_b.name, +60)
        parent_a.modify_relationship(child.name, +60)
        parent_b.modify_relationship(child.name, +60)

        return child

    def decay_daily(self):
        """Daily natural regression toward equilibrium baselines."""
        # 1. Piety regression toward neutral (50)
        if self.piety > 50:
            self.piety = max(50, self.piety - 1)
        elif self.piety < 50:
            self.piety = min(50, self.piety + 1)

        # 2. Ambition regression toward neutral (50)
        if self.ambition > 50:
            self.ambition = max(50, self.ambition - 1)
        elif self.ambition < 50:
            self.ambition = min(50, self.ambition + 1)

        # 3. Relationship decay toward neutral (0)
        to_delete = []
        for other, score in list(self.relationships.items()):
            if score > 0:
                new_score = max(0, score - 2)
            elif score < 0:
                new_score = min(0, score + 2)
            else:
                new_score = 0
            
            if new_score == 0 and other not in self.parents:
                to_delete.append(other)
            else:
                self.relationships[other] = new_score

        for other in to_delete:
            del self.relationships[other]
