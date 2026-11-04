import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    PROJECT_NAME: str = "Morgul Engine"
    API_V1_STR: str = "/api"
    CORS_ORIGINS: list[str] = ["*"]
    
    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent
    DATA_DIR: Path = BASE_DIR / "data"
    DB_PATH: Path = DATA_DIR / "world.db"
    ANNALS_DIR: Path = DATA_DIR / "annals"

    # Simulation Parameters
    SIMULATION_SEED: int = Field(default=42, description="RNG seed for reproducible runs")
    CARRYING_CAPACITY: int = Field(default=65, description="World population the land supports")
    INFANT_MAX_AGE: float = Field(default=3.0, description="Age below which agents are fed by parents")
    HOURS_PER_DAY: int = 24
    BASE_MORTALITY_AGE: float = 60.0
    MATURITY_AGE: float = 16.0
    HUNGER_DAMAGE_THRESHOLD: float = 80.0

    # LLM Settings
    OPENAI_API_KEY: str = Field(default="mock_key", env="OPENAI_API_KEY")
    OPENAI_BASE_URL: str = Field(default="http://localhost:11434/v1", env="OPENAI_BASE_URL")
    LLM_MODEL: str = Field(default="llama3", env="LLM_MODEL")
    LLM_TEMPERATURE: float = 0.7

    class Config:
        env_file = ".env"
        extra = "ignore"

    def ensure_directories(self):
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.ANNALS_DIR.mkdir(parents=True, exist_ok=True)

settings = Settings()
