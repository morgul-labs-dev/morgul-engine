from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class Inventory(BaseModel):
    rations: int = Field(default=0, ge=0)
    tools: int = Field(default=0, ge=0)
    materials: Dict[str, int] = Field(default_factory=dict)

class AgentSchema(BaseModel):
    id: str
    name: str
    generation: int = Field(default=1, ge=1)
    age: float = Field(ge=0.0)
    current_region: str
    profession: str
    health: float = Field(default=100.0, ge=0.0, le=100.0)
    hunger: float = Field(default=0.0, ge=0.0, le=100.0)
    energy: float = Field(default=100.0, ge=0.0, le=100.0)
    inventory: Dict[str, Any] = Field(default_factory=dict)
    lineage: Dict[str, Any] = Field(default_factory=dict)
    traits: List[str] = Field(default_factory=list)
    is_alive: bool = Field(default=True)

class RegionSchema(BaseModel):
    id: str
    name: str
    biome: str
    resources: Dict[str, int] = Field(default_factory=dict)
    danger_level: float = Field(ge=0.0, le=1.0)

class WorldStateSchema(BaseModel):
    day: int
    hour: int
    weather: str
    active_events: List[str] = Field(default_factory=list)

class CensusSummary(BaseModel):
    total_population: int
    living_agents: int
    average_age: float
    generations_present: List[int]
    professions: Dict[str, int]
    region_distribution: Dict[str, int]
