
CONTINENT_LORE = {
    "Boreas": "Frozen northern crags rich in iron and coal, home to hardened miners and austere cliff clans.",
    "Oakhaven Basin": "Temperate fertile river basin abundant in timber and grain, revered as the ancestral agrarian heartland.",
    "Verdant Mire": "Dense southern subtropical wetlands teeming with exotic herbs, rogue syndicates, and mystic rites.",
    "Sunreach Steppe": "Vast sun-baked eastern savannah and trade plains known for livestock herds and sun shrines."
}

# engine.py
import random
from typing import Dict, List, Set, Optional, Any
from models import Agent
from config import REGIONS
import llm_client
import database

REGIONAL_YIELDS = {
    "Verdant Mire": {"medicinal_herbs": 2, "food": 2},
    "Oakhaven Basin": {"grain": 4, "food": 1, "flax_fiber": 1},
    "Sunreach Steppe": {"livestock": 1, "food": 1, "salt": 2},
    "Eldervale": {"hardwood_timber": 2, "food": 1, "stone": 1},
    "Boreas": {"iron_ore": 2, "coal": 2, "food": 1}
}

FACTION_ORIGINS = {
    "Verdant Mire": "The Canopy Circle",
    "Oakhaven Basin": "The Granary Guild",
    "Sunreach Steppe": "The Steppe Clan",
    "Eldervale": "The Timber Wardens",
    "Boreas": "The Iron Compact"
}

class SimulationEngine:
    def __init__(self):
        self.hour = 6
        self.day = 1
        self.agents: Dict[str, Agent] = {}
        self.logs: List[str] = []
        self.blocked_borders: Set[str] = set()
        self.regions = REGIONS
        self.active_caravans: List[Dict[str, Any]] = []
        self.active_raids: List[Dict[str, Any]] = []
        self.active_plots: List[Dict[str, Any]] = []
        
        # Territory Dominance: { "RegionName": { "controlling_guild": "...", "influence": 100 } }
        self.territory_control: Dict[str, Dict[str, Any]] = {
            r: {"controlling_guild": FACTION_ORIGINS[r], "influence": 100}
            for r in REGIONS.keys()
        }

        # Shrines: { "RegionName": { "name": "...", "type": "celestial|heretic", "progress": 100, "builder": "..." } }
        self.shrines: Dict[str, Dict[str, Any]] = {}

    def register_agent(self, agent: Agent):
        self.agents[agent.name] = agent

    def log(self, message: str):
        entry = f"[Day {self.day:02d} | {self.hour:02d}:00] {message}"
        self.logs.append(entry)
        print(entry)

    def _resolve_production(self, agent: Agent):
        if agent.energy < 10:
            agent.add_memory("Too exhausted to work effectively.", self.day, self.hour)
            return

        agent.energy = max(0, agent.energy - 10)
        yields = REGIONAL_YIELDS.get(agent.current_region, {"food": 1})
        
        # If region is occupied/annexed by another guild, occupant receives 50% tribute
        territory = self.territory_control.get(agent.current_region, {})
        occupier = territory.get("controlling_guild")
        native_guild = FACTION_ORIGINS.get(agent.current_region)
        is_occupied = occupier and occupier != native_guild

        gains = []
        for item, qty in yields.items():
            if is_occupied and qty > 1:
                # 1 unit deducted as conqueror tribute
                actual_qty = qty - 1
            else:
                actual_qty = qty
            agent.inventory[item] = agent.inventory.get(item, 0) + actual_qty
            gains.append(f"{actual_qty} {item}")
            
        summary = ", ".join(gains)
        tribute_note = f" (1 tribute taxed by {occupier})" if is_occupied else ""
        agent.add_memory(f"Worked and produced {summary}{tribute_note}.", self.day, self.hour)
        self.log(f"⚒️  {agent.name} produced {summary}{tribute_note} in {agent.current_region}.")

    def _feed_dependent_child(self, child: Agent):
        if getattr(child, "age", 24.0) >= 4.0 or child.hunger < 25:
            return

        # 1. Biological parent care
        for p_name in getattr(child, "parents", []):
            parent = self.agents.get(p_name)
            if parent and parent.current_region == child.current_region:
                if parent.inventory.get("food", 0) >= 1:
                    parent.inventory["food"] -= 1
                    child.hunger = max(0, child.hunger - 45)
                    child.health = min(100, child.health + 5)
                    child.add_memory(f"Nourished with meals provided by parent {parent.name}.", self.day, self.hour)
                    parent.add_memory(f"Provided rations to care for child {child.name}.", self.day, self.hour)
                    return

        # 2. Communal Foster Care (village elders foster orphans)
        if child.hunger >= 45:
            elders = [a for a in self.agents.values() if a.current_region == child.current_region and getattr(a, "age", 24.0) >= 16.0 and a.inventory.get("food", 0) >= 2]
            if elders:
                guardian = elders[0]
                guardian.inventory["food"] -= 1
                child.hunger = max(0, child.hunger - 40)
                child.health = min(100, child.health + 5)
                child.add_memory(f"Fostered and fed by community elder {guardian.name}.", self.day, self.hour)
                guardian.add_memory(f"Shared communal rations to foster orphan {child.name}.", self.day, self.hour)
                return

    def _resolve_consumption(self, agent: Agent):
        starving_kin = [
            a for a in self.agents.values()
            if a.current_region == agent.current_region 
            and a.name != agent.name
            and (a.name in agent.parents or agent.name in getattr(a, "parents", []))
            and a.hunger >= 75
        ]

        if starving_kin and agent.inventory.get("food", 0) >= 2:
            kin = starving_kin[0]
            agent.inventory["food"] -= 1
            kin.inventory["food"] = kin.inventory.get("food", 0) + 1
            agent.modify_relationship(kin.name, +20)
            kin.modify_relationship(agent.name, +25)
            agent.add_memory(f"Shared a food ration with my starving kin {kin.name}.", self.day, self.hour)
            kin.add_memory(f"My kin {agent.name} brought me food in my hour of starvation.", self.day, self.hour)
            self.log(f"🍞 KINSHIP: {agent.name} shared food with kin {kin.name} in {agent.current_region}!")

        if agent.inventory.get("food", 0) > 0:
            agent.inventory["food"] -= 1
            agent.hunger = max(0, agent.hunger - 35)
            agent.health = min(100, agent.health + 5)
            agent.add_memory("Ate a prepared food ration.", self.day, self.hour)
            return

        if agent.inventory.get("grain", 0) >= 2:
            agent.inventory["grain"] -= 2
            agent.inventory["food"] = agent.inventory.get("food", 0) + 2
            agent.hunger = max(0, agent.hunger - 35)
            agent.add_memory("Milled grain into bread and ate.", self.day, self.hour)
            self.log(f"🍞 {agent.name} milled 2 grain into food rations.")
            return

        if agent.inventory.get("livestock", 0) >= 1:
            agent.inventory["livestock"] -= 1
            agent.inventory["food"] = agent.inventory.get("food", 0) + 3
            agent.hunger = max(0, agent.hunger - 35)
            agent.add_memory("Slaughtered livestock for meat and ate.", self.day, self.hour)
            self.log(f"🥩 {agent.name} prepared livestock into meat rations.")
            return

        agent.add_memory("Attempted to eat, but possessed no rations or raw staples.", self.day, self.hour)

    def _resolve_prayer(self, agent: Agent):
        agent.energy = max(0, agent.energy - 5)
        agent.piety = min(100, agent.piety + 5)
        agent.dread = max(0, agent.dread - 8)
        agent.add_memory("Knelt in prayer, petitioning the divine sky for mercy and bounty.", self.day, self.hour)
        self.log(f"🙏 PRAYER: {agent.name} knelt in deep devotion to the heavens in {agent.current_region}.")

    def _resolve_preaching(self, agent: Agent):
        agent.energy = max(0, agent.energy - 10)
        locals_nearby = [
            a for a in self.agents.values() 
            if a.current_region == agent.current_region and a.name != agent.name and getattr(a, 'age', 24.0) >= 6.0
        ]
        
        if agent.piety >= 60:
            for l in locals_nearby:
                l.piety = min(100, l.piety + 4)
                l.dread = min(100, l.dread + 2)
                distant_realms = [r for r in CONTINENT_LORE if r != agent.current_region]
                rumor_realm = distant_realms[abs(hash(l.name + str(self.day))) % len(distant_realms)]
                l.add_memory(f"Listened to {agent.name} preach of divine majesty and incoming omens across {rumor_realm}.", self.day, self.hour)
            agent.add_memory(f"Preached divine glory to {len(locals_nearby)} citizens in the settlement.", self.day, self.hour)
            self.log(f"📿 PREACH: Zealot {agent.name} stirred {agent.current_region} with sermons of divine providence!")
        else:
            for l in locals_nearby:
                l.piety = max(0, l.piety - 5)
                l.ambition = min(100, l.ambition + 4)
                l.add_memory(f"Listened to {agent.name} denounce reliance on unseen gods.", self.day, self.hour)
            agent.add_memory(f"Urged the citizens of {agent.current_region} to take control of their own fates.", self.day, self.hour)
            self.log(f"🗣️ APOSTASY: {agent.name} preached defiance against divine intervention in {agent.current_region}!")

    def _resolve_conspiracy(self, agent: Agent):
        agent.energy = max(0, agent.energy - 8)
        agent.ambition = min(100, agent.ambition + 6)

        co_conspirators = [
            a for a in self.agents.values()
            if a.current_region == agent.current_region
            and a.name != agent.name
            and getattr(a, 'age', 24.0) >= 16.0
            and (a.ambition >= 65 or a.is_rogue)
        ]

        if not co_conspirators:
            agent.add_memory("Scouted settlement armaments for future raid opportunities.", self.day, self.hour)
            return

        partner = co_conspirators[0]

        # Check for betrayal if partner develops excessive dread or hostility
        if partner.dread >= 60 or partner.get_relationship(agent.name) < 0:
            partner.dread = max(0, partner.dread - 15)
            partner.modify_relationship(agent.name, -25)
            agent.modify_relationship(partner.name, -35)
            agent.dread = min(100, agent.dread + 20)
            
            # Purge any existing schemes between them
            self.active_plots = [
                p for p in self.active_plots 
                if not (p["leader"] in (agent.name, partner.name) and p["partner"] in (agent.name, partner.name))
            ]
            
            agent.add_memory(f"Betrayed by {partner.name}, who disclosed covert schemes to settlement elders!", self.day, self.hour)
            partner.add_memory(f"Confessed secret plots organized by {agent.name} to preserve settlement order.", self.day, self.hour)
            self.log(f"⚠️ PLOT FOILED: {partner.name} betrayed conspirator {agent.name} in {agent.current_region}!")
            return

        agent.modify_relationship(partner.name, +15)
        partner.modify_relationship(agent.name, +15)

        # Match existing ongoing plot or spawn a fresh scheme
        existing_plot = next(
            (p for p in self.active_plots if p["region"] == agent.current_region and (p["leader"] in (agent.name, partner.name) or p["partner"] in (agent.name, partner.name))),
            None
        )

        adjacent_regions = self.regions.get(agent.current_region, {}).get("adjacent", [])
        target_reg = adjacent_regions[0] if adjacent_regions else agent.current_region

        if existing_plot:
            existing_plot["readiness"] += 35
            readiness = existing_plot["readiness"]
            target_reg = existing_plot["target_region"]
            agent.add_memory(f"Advanced secret mobilization pact with {partner.name} (Readiness: {readiness}%).", self.day, self.hour)
            partner.add_memory(f"Secured stockpiles for covert campaign with {agent.name} (Readiness: {readiness}%).", self.day, self.hour)
            self.log(f"🗡️ CONSPIRACY ESCALATES: {agent.name} and {partner.name} accelerated their plot in {agent.current_region} to {readiness}% readiness.")

            if readiness >= 100:
                self.log(f"🔥 CONSPIRACY TRIGGERED: {agent.name} and {partner.name} launched their planned coup/raid from {agent.current_region} toward {target_reg}!")
                agent.ambition = min(100, agent.ambition + 15)
                partner.ambition = min(100, partner.ambition + 15)
                agent.dread = min(100, agent.dread + 10)
                partner.dread = min(100, partner.dread + 10)
                
                self.active_plots.remove(existing_plot)
                self._attempt_launch_raid(agent, target_reg)
        else:
            new_plot = {
                "id": f"plot_{len(self.active_plots)}_{random.randint(100, 999)}",
                "leader": agent.name,
                "partner": partner.name,
                "region": agent.current_region,
                "target_region": target_reg,
                "readiness": 40,
                "day_started": self.day
            }
            self.active_plots.append(new_plot)
            agent.add_memory(f"Initiated secret war council with {partner.name} targeting {target_reg}.", self.day, self.hour)
            partner.add_memory(f"Pledged covert loyalty to {agent.name} to strike {target_reg}.", self.day, self.hour)
            self.log(f"🗡️ CONSPIRACY HATCHED: {agent.name} and {partner.name} formed an armed conspiracy targeting {target_reg} (Readiness: 40%).")

    # -------------------------------------------------------------
    # RAID & TERRITORY ANNEXATION ENGINE
    # -------------------------------------------------------------
    def _attempt_launch_raid(self, leader: Agent, target_region: str):
        """Launches an armed expedition to plunder an adjacent region."""
        if any(r["leader_name"] == leader.name for r in self.active_raids):
            return

        border_key = ":".join(sorted([leader.current_region, target_region]))
        if border_key in self.blocked_borders and not leader.is_rogue:
            leader.add_memory(f"Ordered an assault on {target_region}, but the border gate was sealed by divine decree.", self.day, self.hour)
            self.log(f"🚫 RAID REPUDIATED: {leader.name}'s war party could not cross sealed border into {target_region}.")
            return

        # Gather raiders from local faction
        allies = [
            a for a in self.agents.values()
            if a.current_region == leader.current_region and getattr(a, 'age', 24.0) >= 16.0 
            and a.health >= 50 
            and (a.ambition >= 40 or a.hunger >= 50 or a.get_relationship(leader.name) >= 20)
        ]
        raiders = allies[:3]  # Leader + up to 2 raiders
        if not raiders:
            raiders = [leader]

        origin_guild = self.territory_control.get(leader.current_region, {}).get("controlling_guild", "Wild Raiders")

        self.active_raids.append({
            "id": f"raid_{len(self.active_raids)}_{random.randint(100,999)}",
            "leader_name": leader.name,
            "raiders": [r.name for r in raiders],
            "origin_region": leader.current_region,
            "target_region": target_region,
            "guild_name": origin_guild,
            "progress": 0.0
        })

        for r in raiders:
            r.energy = max(0, r.energy - 15)
            r.add_memory(f"Joined an armed raid under {leader.name} marching toward {target_region}!", self.day, self.hour)

        self.log(f"⚔️ WAR DECREED: {leader.name} lead a raiding war party of {len(raiders)} warriors from {leader.current_region} toward {target_region}!")

    def _resolve_raid_movement(self):
        finished_raids = []

        for raid in self.active_raids:
            raid["progress"] += 0.5

            if raid["progress"] >= 1.0:
                self._resolve_raid_clash(raid)
                finished_raids.append(raid)

        for fr in finished_raids:
            self.active_raids.remove(fr)

    def _resolve_raid_clash(self, raid: Dict[str, Any]):
        target_reg = raid["target_region"]
        origin_reg = raid["origin_region"]
        raider_agents = [self.agents.get(r_name) for r_name in raid["raiders"] if self.agents.get(r_name)]
        if not raider_agents:
            return

        defenders = [
            a for a in self.agents.values() 
            if a.current_region == target_reg and getattr(a, 'age', 24.0) >= 16.0 and not a.is_rogue and a.health >= 40
        ]

        # Calculate combat power
        raider_power = sum(r.health + r.energy for r in raider_agents) + random.randint(10, 60)
        defender_power = sum(d.health + d.energy for d in defenders) + random.randint(10, 60)

        border_key = ":".join(sorted([origin_reg, target_reg]))
        is_sealed = border_key in self.blocked_borders

        if is_sealed:
            # Wall ambush penalty for attackers
            raider_power -= 40

        target_territory = self.territory_control[target_reg]
        conquering_guild = raid["guild_name"]
        defending_guild = target_territory["controlling_guild"]

        if raider_power >= defender_power:
            # RAID VICTORY: Plunder food & commodities
            plundered_goods = []
            for d in list(defenders):
                d.health = max(0, d.health - 25)
                d.dread = min(100, d.dread + 30)
                if d.health <= 0:
                    self.log(f"⚔️ FALLEN IN BATTLE: Defender {d.name} was slain defending {target_reg}!")
                    database.delete_agent(d.name, day=self.day, hour=self.hour, cause=f"Slain defending {target_reg}")
                    if d.name in self.agents:
                        del self.agents[d.name]
                    continue
                # Mutual feud
                for r in raider_agents:
                    d.modify_relationship(r.name, -40)
                    r.modify_relationship(d.name, -30)

                # Plunder rations
                if d.inventory.get("food", 0) > 0:
                    stolen = min(2, d.inventory["food"])
                    d.inventory["food"] -= stolen
                    raider_agents[0].inventory["food"] = raider_agents[0].inventory.get("food", 0) + stolen
                    plundered_goods.append(f"{stolen} food from {d.name}")

            # Plunder regional raw supplies
            for r in raider_agents:
                r.energy = max(0, r.energy - 10)
                r.ambition = min(100, r.ambition + 10)
                r.current_region = origin_reg  # Return home with booty
                r.add_memory(f"Victorious raid upon {target_reg}! Sacked their stores and crushed defenses.", self.day, self.hour)

            # Territory Hegemony Shift
            target_territory["influence"] -= 35
            self.log(f"🔥 SACK OF {target_reg.upper()}: {raid['leader_name']}'s war party stormed {target_reg}! Defenses routed.")
            
            # Check for Complete Annexation
            if target_territory["influence"] <= 0:
                target_territory["controlling_guild"] = conquering_guild
                target_territory["influence"] = 100
                self.log(f"👑 TERRITORY ANNEXED! {conquering_guild} has completely conquered and annexed {target_reg}!")
                for a in self.agents.values():
                    if a.current_region == target_reg:
                        a.add_memory(f"Our homeland was conquered! We are now vassals to {conquering_guild}.", self.day, self.hour)
            else:
                self.log(f"   📉 {defending_guild}'s grip on {target_reg} weakened to {target_territory['influence']}% influence.")

        else:
            # RAID REPUDIATED: Defenders repel invaders
            for r in list(raider_agents):
                r.health = max(0, r.health - 30)
                r.dread = min(100, r.dread + 25)
                if r.health <= 0:
                    self.log(f"⚔️ FALLEN IN BATTLE: Raider {r.name} was slain in the assault on {target_reg}!")
                    database.delete_agent(r.name, day=self.day, hour=self.hour, cause=f"Slain in assault on {target_reg}")
                    if r.name in self.agents:
                        del self.agents[r.name]
                    continue
                r.current_region = origin_reg
                r.add_memory(f"Raid on {target_reg} failed! Repelled by fierce resistance.", self.day, self.hour)

            for d in defenders:
                d.energy = max(0, d.energy - 15)
                d.ambition = min(100, d.ambition + 5)
                d.add_memory(f"Fought bravely and repelled {raid['leader_name']}'s raiders from {origin_reg}!", self.day, self.hour)

            self.log(f"🛡️ DEFENDERS STAND: Citizens of {target_reg} beat back the invasion from {origin_reg}! Raiders fled.")

    def _resolve_caravan_movement(self):
        finished_caravans = []
        for c in self.active_caravans:
            c["progress"] += 0.5
            if c["progress"] >= 1.0:
                agent = self.agents.get(c["agent_name"])
                if not agent:
                    finished_caravans.append(c)
                    continue
                
                target_region = c["destination"]
                border_key = ":".join(sorted([c["origin"], target_region]))
                is_sealed = border_key in self.blocked_borders

                if is_sealed:
                    if c["is_smuggling"]:
                        stealth_roll = random.randint(1, 100) + (agent.attractiveness // 4)
                        if stealth_roll > 45:
                            cargo_item = c["cargo_item"]
                            cargo_qty = c["cargo_qty"]
                            reward_food = cargo_qty * 3
                            agent.inventory["food"] = agent.inventory.get("food", 0) + reward_food
                            agent.current_region = target_region
                            agent.ambition = min(100, agent.ambition + 5)
                            agent.add_memory(f"Smuggled {cargo_qty} {cargo_item} past sealed border into {target_region} for {reward_food} rations!", self.day, self.hour)
                            self.log(f"🗡️ SMUGGLE SUCCESS: {agent.name} bypassed the sealed pass into {target_region} selling {cargo_item} for {reward_food} food rations!")
                        else:
                            agent.health = max(10, agent.health - 25)
                            agent.dread = min(100, agent.dread + 20)
                            agent.add_memory(f"Ambushed while smuggling {c['cargo_item']} into {target_region}! Cargo confiscated.", self.day, self.hour)
                            self.log(f"🚨 SMUGGLER APPREHENDED: {agent.name} caught at the border of {target_region}! Cargo lost.")
                    else:
                        agent.inventory[c["cargo_item"]] = agent.inventory.get(c["cargo_item"], 0) + c["cargo_qty"]
                        agent.dread = min(100, agent.dread + 10)
                        agent.add_memory(f"Arrived at border of {target_region}, but it was sealed by divine power. Forced to turn back.", self.day, self.hour)
                        self.log(f"🛑 CARAVAN BLOCKED: {agent.name}'s caravan could not enter sealed {target_region}.")
                else:
                    cargo_item = c["cargo_item"]
                    cargo_qty = c["cargo_qty"]
                    reward_food = cargo_qty * 2
                    agent.inventory["food"] = agent.inventory.get("food", 0) + reward_food
                    agent.current_region = target_region
                    agent.ambition = min(100, agent.ambition + 3)
                    agent.add_memory(f"Completed trade run to {target_region}. Sold {cargo_qty} {cargo_item} for {reward_food} food rations.", self.day, self.hour)
                    self.log(f"📦 CARAVAN ARRIVED: {agent.name} delivered {cargo_qty} {cargo_item} to {target_region} for {reward_food} food rations.")

                finished_caravans.append(c)

        for fc in finished_caravans:
            self.active_caravans.remove(fc)

    def _attempt_launch_caravan(self, agent: Agent, target_region: str):
        if any(c["agent_name"] == agent.name for c in self.active_caravans):
            return

        trade_item = None
        for item, qty in agent.inventory.items():
            if item not in ["food"] and qty >= 2:
                trade_item = item
                break

        if not trade_item:
            agent.add_memory(f"Considered launching a caravan to {target_region}, but had no surplus commodities.", self.day, self.hour)
            return

        border_key = ":".join(sorted([agent.current_region, target_region]))
        is_sealed = border_key in self.blocked_borders

        if is_sealed and not agent.is_rogue:
            agent.add_memory(f"Wanted to trade with {target_region}, but the border is sealed by divine decree.", self.day, self.hour)
            self.log(f"🚫 BLOCKED ATTEMPT: {agent.name} aborted trade to {target_region} due to divine barrier.")
            return

        cargo_qty = min(3, agent.inventory[trade_item])
        agent.inventory[trade_item] -= cargo_qty
        is_smuggling = is_sealed and agent.is_rogue

        self.active_caravans.append({
            "id": f"caravan_{len(self.active_caravans)}_{random.randint(100,999)}",
            "agent_name": agent.name,
            "origin": agent.current_region,
            "destination": target_region,
            "cargo_item": trade_item,
            "cargo_qty": cargo_qty,
            "progress": 0.0,
            "is_smuggling": is_smuggling
        })

        if is_smuggling:
            self.log(f"🏴‍☠️ SMUGGLING RUN: Rogue {agent.name} slipped into the shadows carrying {cargo_qty} {trade_item} toward sealed {target_region}!")
            agent.add_memory(f"Began illicit smuggling run toward {target_region} carrying {cargo_qty} {trade_item}.", self.day, self.hour)
        else:
            self.log(f"🐪 CARAVAN DEPARTED: {agent.name} set out toward {target_region} carrying {cargo_qty} {trade_item}.")
            agent.add_memory(f"Departed on trade expedition toward {target_region} with {cargo_qty} {trade_item}.", self.day, self.hour)

    def _resolve_barter(self, buyer: Agent):
        region_agents = [
            a for a in self.agents.values() 
            if a.current_region == buyer.current_region and a.name != buyer.name and getattr(a, 'age', 24.0) >= 12.0
        ]

        wants_food = buyer.hunger > 35 or buyer.inventory.get("food", 0) == 0

        region_agents.sort(
            key=lambda x: 1 if (x.name in buyer.parents or buyer.name in getattr(x, "parents", [])) else 0,
            reverse=True
        )

        for seller in region_agents:
            is_kin = (seller.name in buyer.parents or buyer.name in getattr(seller, "parents", []))
            if not is_kin and (buyer.get_relationship(seller.name) < -30 or seller.get_relationship(buyer.name) < -30):
                buyer.add_memory(f"Refused to approach {seller.name} due to an ongoing bitter feud.", self.day, self.hour)
                continue

            seller_food = seller.inventory.get("food", 0)
            seller_grain = seller.inventory.get("grain", 0)
            can_sell_food = seller_food >= 2 or seller_grain >= 3
            
            if wants_food and can_sell_food:
                for offer_item, qty in list(buyer.inventory.items()):
                    if offer_item not in ["food", "grain", "livestock"] and qty > 0:
                        buyer.inventory[offer_item] -= 1
                        seller.inventory[offer_item] = seller.inventory.get(offer_item, 0) + 1

                        # Spread trade rumors to bystanders about distant markets
                        distant_trade_realms = [r for r in CONTINENT_LORE if r != buyer.current_region]
                        gossip_realm = distant_trade_realms[abs(hash(buyer.name + str(self.day))) % len(distant_trade_realms)]
                        buyer.add_memory(f"Heard merchant trade rumors regarding commodity shortages and yields in {gossip_realm}.", self.day, self.hour)
                        seller.add_memory(f"Exchanged marketplace news and caravan gossip from {gossip_realm}.", self.day, self.hour)

                        if seller_food >= 2:
                            seller.inventory["food"] -= 1
                            buyer.inventory["food"] = buyer.inventory.get("food", 0) + 1
                            traded_commodity = "food"
                        else:
                            seller.inventory["grain"] -= 2
                            buyer.inventory["grain"] = buyer.inventory.get("grain", 0) + 2
                            traded_commodity = "2 grain"

                        context = f"{buyer.name} is hungry and offers 1 {offer_item} for {traded_commodity} from {seller.name}."
                        line_a, line_b = llm_client.generate_agent_exchange(
                            buyer.name, f"{buyer.social_class} {buyer.role}, {buyer.personality}",
                            seller.name, f"{seller.social_class} {seller.role}, {seller.personality}",
                            context
                        )

                        buyer.modify_relationship(seller.name, +15)
                        seller.modify_relationship(buyer.name, +15)

                        buyer.add_memory(f"Bartered 1 {offer_item} to {seller.name}. Spoke: '{line_a}' (Heard: '{line_b}')", self.day, self.hour)
                        seller.add_memory(f"Sold {traded_commodity} to {buyer.name}. Spoke: '{line_b}'", self.day, self.hour)
                        
                        self.log(f"🤝 TRADE: {buyer.name} bartered 1 {offer_item} to {seller.name} for {traded_commodity}.")
                        self.log(f"   💬 {buyer.name}: \"{line_a}\" | {seller.name}: \"{line_b}\"")
                        return

        buyer.add_memory("Found no willing barter partners in the local settlement.", self.day, self.hour)

    def _resolve_mating(self, suitor: Agent):
        if getattr(suitor, "age", 24.0) < 16.0:
            return
        if suitor.mating_cooldown > 0:
            suitor.add_memory(f"Still recovering from last child ({suitor.mating_cooldown}h remaining).", self.day, self.hour)
            return
        if suitor.energy < 30 or suitor.hunger > 70:
            suitor.add_memory("Too exhausted or starved to pursue a mate.", self.day, self.hour)
            return

        candidates = [
            a for a in self.agents.values()
            if a.current_region == suitor.current_region 
            and a.name != suitor.name 
            and a.gender != suitor.gender
            and a.name not in suitor.parents
            and suitor.name not in getattr(a, "parents", [])
            and not (suitor.parents and a.parents and set(suitor.parents) == set(a.parents))
            and a.mating_cooldown == 0
            and a.hunger < 75
            and getattr(a, "age", 24.0) >= 16.0
        ]

        if not candidates:
            suitor.add_memory("Looked for an eligible partner nearby, but found none.", self.day, self.hour)
            return

        target = candidates[0]
        mating_approved = False
        dowry_item = None
        dowry_qty = 0

        if suitor.attractiveness >= 70:
            mating_approved = True
            suitor.add_memory(f"Charmed {target.name} effortlessly into a union.", self.day, self.hour)
            target.add_memory(f"Was wooed by the radiant charm of {suitor.name}.", self.day, self.hour)
            suitor.modify_relationship(target.name, +25)
            target.modify_relationship(suitor.name, +25)
            self.log(f"💘 CHARM: {suitor.name} wooed {target.name} freely.")
        else:
            valuable_goods = ["grain", "livestock", "food", "iron_ore", "medicinal_herbs", "hardwood_timber"]
            for item in valuable_goods:
                if suitor.inventory.get(item, 0) >= 2:
                    dowry_item = item
                    dowry_qty = 2
                    break

            if dowry_item:
                if target.hunger > 35 or target.attractiveness <= 60 or dowry_item in ["food", "grain", "livestock"]:
                    mating_approved = True
                    suitor.inventory[dowry_item] -= dowry_qty
                    target.inventory[dowry_item] = target.inventory.get(dowry_item, 0) + dowry_qty
                    suitor.add_memory(f"Secured a union with {target.name} by providing {dowry_qty} {dowry_item}.", self.day, self.hour)
                    target.add_memory(f"Accepted a union contract from {suitor.name} for {dowry_qty} {dowry_item}.", self.day, self.hour)
                    suitor.modify_relationship(target.name, +20)
                    target.modify_relationship(suitor.name, +20)
                    self.log(f"💍 DOWRY UNION: {suitor.name} gave {dowry_qty} {dowry_item} to {target.name}.")
                else:
                    suitor.add_memory(f"{target.name} rejected my dowry of {dowry_item}.", self.day, self.hour)
                    suitor.modify_relationship(target.name, -15)
                    return
            else:
                suitor.add_memory(f"Lacked the charm and the dowry goods to court {target.name}.", self.day, self.hour)
                return

        if mating_approved:
            suitor.energy = max(0, suitor.energy - 25)
            target.energy = max(0, target.energy - 25)
            suitor.mating_cooldown = 120
            target.mating_cooldown = 120
            suitor.children_count += 1
            target.children_count += 1

            global_id = len(self.agents) + 1
            child = Agent.spawn_child(suitor, target, global_id)
            self.register_agent(child)

            # --- HEIRLOOM LORE / DYNASTIC ORAL HISTORY ---
            suitor_origin = getattr(suitor, "region_id", suitor.current_region)
            target_origin = getattr(target, "region_id", target.current_region)
            child.add_memory(f"Dynastic Lore: Born to {suitor.name} and {target.name}, learning tales of their ancestral heritage in {suitor_origin}.", self.day, self.hour)
            if suitor_origin != child.current_region or target_origin != child.current_region:
                foreign_origin = suitor_origin if suitor_origin != child.current_region else target_origin
                child.add_memory(f"Heirloom Tale: Your lineage carries blood and memories from distant {foreign_origin}.", self.day, self.hour)

            if child.is_rogue:
                self.log(f"⚠️⚡ ROGUE BORN: {child.name} was born in {child.current_region}!")
            else:
                self.log(f"👶 BIRTH: {child.name} was born to {suitor.name} & {target.name} in {child.current_region}.")

    # Divine Interventions
    def divine_grant(self, agent_name: str, item: str, qty: int) -> bool:
        agent = self.agents.get(agent_name)
        if not agent:
            return False
        agent.inventory[item] = agent.inventory.get(item, 0) + qty
        agent.piety = min(100, agent.piety + 15)
        agent.dread = max(0, agent.dread - 10)
        agent.add_memory(f"A miracle occurred! The divine presence granted {qty} {item}.", self.day, self.hour)
        self.log(f"✨ DIVINE MIRACLE: {agent_name} was granted {qty} {item} from the heavens!")
        database.record_divine_action(self.day, self.hour, "GRANT", agent_name, f"Granted {qty} {item}")
        return True

    def divine_smite(self, agent_name: str) -> bool:
        agent = self.agents.get(agent_name)
        if not agent:
            return False
        agent.health = max(0, agent.health - 60)
        agent.energy = 0
        agent.dread = 100
        agent.piety = min(100, agent.piety + 20)
        agent.add_memory("Struck by divine thunder! Experienced terrifying celestial wrath.", self.day, self.hour)
        self.log(f"⚡ DIVINE SMITE: Lightning tore from the sky striking {agent_name}! (Health: {agent.health}%)")
        database.record_divine_action(self.day, self.hour, "SMITE", agent_name, f"Smote with lightning (HP: {agent.health})")
        reg = agent.current_region
        if reg in self.shrines:
            shrine = self.shrines[reg]
            if shrine["type"] == "heretic":
                self.log(f"⚡ ALTAR SHATTERED: Divine wrath destroyed {shrine['name']} in {reg}!")
                del self.shrines[reg]
        
        for other in self.agents.values():
            if other.current_region == agent.current_region and other.name != agent.name:
                other.dread = min(100, other.dread + 25)
                other.add_memory(f"Witnessed the deity smite {agent_name} with lightning.", self.day, self.hour)
        return True

    def divine_bless(self, agent_name: str) -> bool:
        agent = self.agents.get(agent_name)
        if not agent:
            return False
        agent.health = 100
        agent.hunger = 0
        agent.energy = 100
        agent.piety = 100
        agent.dread = 0
        agent.attractiveness = min(100, agent.attractiveness + 10)
        agent.add_memory("Bathed in golden celestial light. Vitals and spirit fully restored.", self.day, self.hour)
        self.log(f"🌟 DIVINE BLESSING: {agent_name} was rejuvenated by celestial radiance!")
        database.record_divine_action(self.day, self.hour, "BLESS", agent_name, "Restored stats and boosted charm +10")
        return True

    def toggle_border(self, reg_a: str, reg_b: str, block: bool) -> bool:
        key = ":".join(sorted([reg_a, reg_b]))
        if block:
            self.blocked_borders.add(key)
            self.log(f"🔒 DIVINE DECREE: The passage between {reg_a} and {reg_b} has been sealed!")
            database.record_divine_action(self.day, self.hour, "BLOCK_BORDER", key, "Border sealed")
            for a in self.agents.values():
                if a.current_region in [reg_a, reg_b]:
                    a.dread = min(100, a.dread + 10)
        else:
            self.blocked_borders.discard(key)
            self.log(f"🔓 DIVINE DECREE: The passage between {reg_a} and {reg_b} has been opened.")
            database.record_divine_action(self.day, self.hour, "UNBLOCK_BORDER", key, "Border opened")
        return True

    def trigger_calamity(self, region_name: str, calamity_type: str) -> bool:
        if region_name not in REGIONS:
            return False
            
        self.log(f"🌪️ CALAMITY: A {calamity_type.upper()} has struck {region_name}!")
        database.record_divine_action(self.day, self.hour, "CALAMITY", region_name, f"Triggered {calamity_type}")
        
        for agent in self.agents.values():
            if agent.current_region == region_name:
                agent.dread = min(100, agent.dread + 30)
                if calamity_type == "drought":
                    agent.hunger = min(100, agent.hunger + 30)
                    agent.inventory["food"] = max(0, agent.inventory.get("food", 0) - 2)
                    agent.add_memory("A parching drought withered the crops and emptied stores.", self.day, self.hour)
                elif calamity_type == "blizzard":
                    agent.health = max(0, agent.health - 25)
                    agent.energy = max(0, agent.energy - 30)
                    agent.add_memory("A supernatural blizzard froze the settlement to the bone.", self.day, self.hour)
                elif calamity_type == "blight":
                    agent.inventory["grain"] = 0
                    agent.inventory["medicinal_herbs"] = 0
                    agent.health = max(0, agent.health - 15)
                    agent.add_memory("A foul black blight rotted our reserves.", self.day, self.hour)
        return True

    def _resolve_shrine_building(self, agent: Agent):
        """Builds or contributes to a celestial shrine or heretical monument."""
        reg = agent.current_region
        build_mat = None
        for mat in ["stone", "hardwood_timber"]:
            if agent.inventory.get(mat, 0) >= 2:
                build_mat = mat
                break

        if not build_mat:
            agent.add_memory("Desired to raise a monument, but lacked stone or timber.", self.day, self.hour)
            return

        agent.inventory[build_mat] -= 2
        agent.energy = max(0, agent.energy - 20)

        existing_shrine = self.shrines.get(reg)

        if existing_shrine:
            existing_shrine["progress"] = min(100, existing_shrine["progress"] + 25)
            agent.add_memory(f"Contributed 2 {build_mat} to fortify {existing_shrine['name']}.", self.day, self.hour)
            self.log(f"🏛️ MONUMENT: {agent.name} contributed {build_mat} to {existing_shrine['name']} in {reg} ({existing_shrine['progress']}% complete).")
        else:
            is_heretic = agent.piety < 35 or agent.is_rogue
            shrine_type = "heretic" if is_heretic else "celestial"
            shrine_name = f"Blood Altar of {agent.name.split('_')[0]}" if is_heretic else f"Celestial Obelisk of {reg.split(' ')[0]}"
            
            self.shrines[reg] = {
                "name": shrine_name,
                "type": shrine_type,
                "progress": 30,
                "builder": agent.name
            }
            agent.add_memory(f"Laid the cornerstone of {shrine_name} with 2 {build_mat}.", self.day, self.hour)
            if is_heretic:
                self.log(f"🩸 HERESY RISES: {agent.name} laid the dark foundation of {shrine_name} in {reg}!")
            else:
                self.log(f"✨ HOLY GROUND: {agent.name} began raising {shrine_name} in devotion to the heavens in {reg}!")

    def _apply_shrine_auras(self):
        """Completed shrines radiate passive regional effects each hour."""
        for reg, shrine in list(self.shrines.items()):
            if shrine.get("progress", 0) >= 100:
                regional_agents = [a for a in self.agents.values() if a.current_region == reg]
                if shrine["type"] == "celestial":
                    for a in regional_agents:
                        a.piety = min(100, a.piety + 1)
                        a.dread = max(0, a.dread - 1)
                else: # heretic blood altar
                    for a in regional_agents:
                        a.piety = max(0, a.piety - 1)
                        a.ambition = min(100, a.ambition + 1)

    def tick_hour(self):
        """Advances the world simulation by 1 in-game hour."""
        self.hour += 1
        if self.hour >= 24:
            completed_day = self.day
            self.hour = 0
            self.day += 1
            for a in self.agents.values():
                if hasattr(a, "decay_daily"):
                    a.decay_daily()

            # Asynchronously chronicle the completed solar cycle
            import subprocess, threading
            def _compile_lore(d):
                try:
                    import sys, os
                    here = os.path.dirname(os.path.abspath(__file__))
                    subprocess.run([sys.executable, os.path.join(here, "chronicler.py"), "--day", str(d)], cwd=here, check=True)
                except Exception as err:
                    print(f"[Chronicler Hook] Error generating lore for day {d}: {err}")

            threading.Thread(target=_compile_lore, args=(completed_day,), daemon=True).start()

        self.log(f"--- Cycle Begins ---")

        self._resolve_caravan_movement()
        self._resolve_raid_movement()

        for name, agent in list(self.agents.items()):
            # Advance age: 1 year = 12 in-game days = 288 hours
            agent.age = getattr(agent, "age", 24.0) + (1.0 / 288.0)
            
            # Developmental role progression
            if agent.age < 12.0:
                agent.role = "Child"
            elif agent.age < 16.0:
                agent.role = "Youth"
            elif agent.role in ["Child", "Youth"]:
                agent.role = "Apprentice"

            agent.hunger = min(100, agent.hunger + 2)
            agent.energy = min(100, max(0, agent.energy - 1))
            agent.mating_cooldown = max(0, agent.mating_cooldown - 1)
            if self.hour % 4 == 0:
                agent.dread = max(0, agent.dread - 1)

            if agent.hunger >= 70:
                has_edible = (
                    agent.inventory.get("food", 0) > 0 or 
                    agent.inventory.get("grain", 0) >= 2 or 
                    agent.inventory.get("livestock", 0) >= 1
                )
                if has_edible:
                    self._resolve_consumption(agent)

            # Old Age / Senescence Mortality (Age 60+)
            if getattr(agent, "age", 24.0) >= 60.0:
                death_chance = (agent.age - 60.0) * 0.0006
                if random.random() < death_chance:
                    self.log(f"🪦 MORTALITY: {agent.name} passed away peacefully of old age at {int(agent.age)}.")
                    database.delete_agent(name, day=self.day, hour=self.hour, cause="Succumbed to severe starvation")
                    del self.agents[name]
                    continue

            # Juveniles (< 16) seek nourishment from living parents
            if getattr(agent, "age", 24.0) < 16.0:
                self._feed_dependent_child(agent)

            if agent.hunger >= 85:
                agent.health = max(0, agent.health - 3)
                agent.dread = min(100, agent.dread + 15)
                agent.add_memory("Suffering from severe starvation pains!", self.day, self.hour)
                if agent.health <= 0:
                    self.log(f"💀 MORTALITY: {agent.name} has succumbed to starvation.")
                    database.delete_agent(name, day=self.day, hour=self.hour, cause="Succumbed to severe starvation")
                    del self.agents[name]
                    continue

            # --- INFANT DEPENDENCY GATE (< 4.0y) ---
            if getattr(agent, "age", 24.0) < 4.0:
                agent.energy = min(100, agent.energy + 10)
                if agent.hunger >= 25:
                    self._feed_dependent_child(agent)
                agent.add_memory("Sheltered by family and learning settlement customs.", self.day, self.hour)
                continue

            # Adolescents (4.0y to 16.0y) can work, rest, and eat to survive
            if getattr(agent, "age", 24.0) < 16.0:
                if agent.hunger >= 60 and agent.inventory.get("food", 0) >= 1:
                    agent.inventory["food"] -= 1
                    agent.hunger = max(0, agent.hunger - 40)
                    agent.add_memory("Ate personal rations as a developing apprentice.", self.day, self.hour)
                    continue
                elif agent.energy <= 25:
                    agent.energy = min(100, agent.energy + 35)
                    agent.add_memory("Rested to recover energy.", self.day, self.hour)
                    continue
                else:
                    self._resolve_production(agent)
                    continue

            current_biome = REGIONS[agent.current_region]

            system_prompt = (
                f"You are {agent.name}, a {agent.social_class} {agent.role} ({agent.gender}, Gen {agent.generation}) in {agent.current_region}.\n"
                f"Personality: {agent.personality}\n"
                f"Psychological Drives: Piety {agent.piety}/100, Ambition {agent.ambition}/100, Dread {agent.dread}/100.\n"
                f"Adjacent regions: {current_biome['adjacent']}.\n"
                f"Continental Realms & Distant Lore: {CONTINENT_LORE}.\n"
                "Respond strictly with valid JSON:\n"
                '{"thought": "...", "action": "work|eat|rest|trade|caravan|mate|migrate|pray|preach|conspire|raid|build_shrine", "target": "region_or_item", "speech": "..."}'
            )

            user_prompt = (
                f"Status: Hunger {agent.hunger}/100, Energy {agent.energy}/100, Health {agent.health}/100.\n"
                f"Inventory: {agent.inventory}\n"
                f"Recent Memories:\n" + "\n".join([f"- {m}" for m in agent.memories[-4:]]) + "\n"
                "What is your next move?"
            )

            region_name = agent.region_id
            current_region = self.regions.get(region_name, {})
            active_edict = getattr(self, "active_edicts", {}).get(region_name, "open_commerce")

            # --- TOKEN CONSERVATION: Urgency & Drama Filter ---
            # Only trigger costly LLM completions when an agent faces pivotal decisions:
            # - Critical hunger (>= 55) or low health (<= 50)
            # - High ambition or rogue status (>= 70 ambition or is_rogue)
            # - Extreme piety or dread (>= 75 piety or >= 65 dread)
            # - Ready to reproduce (mating_cooldown == 0 and energy >= 60 and hunger < 40)
            # - High energy surplus with ambition ready to raid or build shrines
            # Only true life-or-death survival or active rogue revolt prompts LLM directly
            critical_need = (agent.hunger >= 80 or agent.health <= 30 or agent.is_rogue)
            # Stagger normal personality decisions across hours by agent index
            is_scheduled_speaker = (abs(hash(agent.name)) % 8 == getattr(self, "current_hour", getattr(self, "hour", 0)) % 8)

            is_urgent = critical_need or (is_scheduled_speaker and agent.energy >= 40)

            if is_urgent:
                decision = llm_client.generate_decision(
                    user_prompt=user_prompt,
                    system_prompt=system_prompt,
                    region_name=region_name,
                    active_edict=active_edict
                )
            else:
                decision = llm_client._heuristic_fallback(user_prompt)

            thought = decision.get("thought", "")
            action = decision.get("action", "rest")
            target = decision.get("target", "")

            if action == "work":
                self._resolve_production(agent)
            elif action == "eat":
                self._resolve_consumption(agent)
            elif action == "rest":
                agent.energy = min(100, agent.energy + 25)
                agent.add_memory("Rested to recover physical vigor.", self.day, self.hour)
            elif action == "trade":
                self._resolve_barter(agent)
            elif action == "pray":
                self._resolve_prayer(agent)
            elif action == "preach":
                self._resolve_preaching(agent)
            elif action == "conspire":
                self._resolve_conspiracy(agent)
            elif action == "raid" and target in current_biome["adjacent"]:
                self._attempt_launch_raid(agent, target)
            elif action == "caravan" and target in current_biome["adjacent"]:
                self._attempt_launch_caravan(agent, target)
            elif action == "mate":
                self._resolve_mating(agent)
            elif action == "migrate" and target in REGIONS:
                border_key = ":".join(sorted([agent.current_region, target]))
                if border_key in self.blocked_borders:
                    agent.dread = min(100, agent.dread + 10)
                    agent.add_memory(f"Attempted to cross into {target}, but the border was sealed by divine decree.", self.day, self.hour)
                    self.log(f"🚫 BLOCKED: {agent.name} was turned back at the sealed border of {target}!")
                elif target in current_biome["adjacent"]:
                    agent.current_region = target
                    agent.energy = max(0, agent.energy - 20)
                    agent.add_memory(f"Crossed {current_biome['border_name']} into {target}.", self.day, self.hour)
                    self.log(f"🚶 {agent.name} migrated across {current_biome['border_name']} into {target}!")
                else:
                    agent.add_memory(f"Attempted to migrate to {target}, but no direct route exists.", self.day, self.hour)
            elif action == "build_shrine":
                self._resolve_shrine_building(agent)
            else:
                # High piety or extreme dread triggers autonomous shrine construction if materials exist
                has_mat = agent.inventory.get("stone", 0) >= 2 or agent.inventory.get("hardwood_timber", 0) >= 2
                if (agent.piety >= 70 or agent.dread >= 60) and has_mat and agent.current_region not in self.shrines:
                    self._resolve_shrine_building(agent)
                elif agent.ambition >= 75 and agent.hunger >= 40 and current_biome["adjacent"]:
                    target_raid = current_biome["adjacent"][0]
                    self._attempt_launch_raid(agent, target_raid)
                else:
                    agent.add_memory("Spent the hour observing local settlement affairs.", self.day, self.hour)

            self.log(f"[{agent.name} ({agent.current_region})] Thought: \"{thought}\" -> Action: {action}")

        self._apply_shrine_auras()
        
        database.save_world(self.day, self.hour, self.blocked_borders, self.agents, self.territory_control, self.shrines)
