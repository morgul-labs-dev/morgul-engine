import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field

BASE_DIR = Path(__file__).resolve().parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "Morgul Engine"
    ENV: str = Field(default="production", env="ENV")
    API_V1_STR: str = "/api"
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8000, env="PORT")
    
    # Paths
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "data"
    DB_PATH: Path = DATA_DIR / "world.db"
    ANNALS_DIR: Path = DATA_DIR / "annals"

    # Simulation Parameters
    TICK_INTERVAL_SEC: float = Field(default=3.0, description="Runtime sleep interval between ticks in run_sim.py")
    SIMULATION_SEED: int = Field(default=42, description="RNG seed for reproducible runs")
    CARRYING_CAPACITY: int = Field(default=65, description="World population the land supports")
    INFANT_MAX_AGE: float = Field(default=3.0, description="Age below which agents are fed by parents")
    STARTING_FOUNDERS: int = Field(default=30, description="Initial citizens seeded at world initialization")
    HOURS_PER_DAY: int = 24
    BASE_MORTALITY_AGE: float = 60.0
    MATURITY_AGE: float = 16.0
    HUNGER_DAMAGE_THRESHOLD: float = 80.0

    # Security & CORS
    CORS_ORIGINS: List[str] = [
        "https://pangaea.morgul-labs.com",
        "https://morgul-labs.com",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:8000"
    ]

    # LLM Settings
    OPENAI_API_KEY: str = Field(default="mock_key", env="OPENAI_API_KEY")
    OPENAI_BASE_URL: str = Field(default="http://localhost:11434/v1", env="OPENAI_BASE_URL")
    LLM_MODEL: str = Field(default="llama3", env="LLM_MODEL")
    LLM_TEMPERATURE: float = 0.7

    class Config:
        env_file = BASE_DIR / ".env"
        extra = "ignore"

    def ensure_directories(self):
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.ANNALS_DIR.mkdir(parents=True, exist_ok=True)

settings = Settings()
