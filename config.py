from pathlib import Path
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path(__file__).resolve().parent

class SimulationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=APP_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 1. Base Paths (Relative-first)
    BASE_DIR: Path = Field(default=APP_DIR)
    DATA_DIR: Path = Field(default=APP_DIR / "data")
    DB_PATH: Path = Field(default=APP_DIR / "data" / "simulation.db")
    ANNALS_DIR: Path = Field(default=APP_DIR / "data" / "annals")

    # 2. Environment & Server
    ENV: str = Field(default="development", description="development | production")
    HOST: str = Field(default="0.0.0.0", description="API bind host")
    PORT: int = Field(default=8000, description="API port")
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"],
        description="Allowed CORS origins for Atlas UI",
    )

    # 3. LLM API Credentials & Parameters
    OPENAI_API_KEY: str = Field(default="", description="API key for chronicler/agent prompts")
    OPENAI_BASE_URL: str = Field(default="https://api.openai.com/v1", description="Custom or proxy base URL")
    LLM_MODEL: str = Field(default="gpt-4o-mini", description="Model name for lore generation")
    LLM_TEMPERATURE: float = Field(default=0.7, ge=0.0, le=2.0)

    # 4. Simulation Engine Clock & Demographics
    TICK_INTERVAL_SEC: float = Field(default=3.0, description="Real-world seconds per in-game hour")
    HOURS_PER_DAY: int = Field(default=24)
    STARTING_FOUNDERS: int = Field(default=25, description="Initial agents on cold start")
    
    # 5. Lifecycle Parameters
    INFANT_MAX_AGE: float = Field(default=4.0, description="True dependents requiring feeding")
    MATURITY_AGE: float = Field(default=16.0, description="Age threshold for mating and guild leadership")
    BASE_MORTALITY_AGE: float = Field(default=70.0, description="Natural end-of-life curve start")
    HUNGER_DAMAGE_THRESHOLD: int = Field(default=85, description="Hunger level triggering HP decay")

    def ensure_directories(self) -> None:
        """Creates storage directories on application startup if missing."""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.ANNALS_DIR.mkdir(parents=True, exist_ok=True)

# Global settings instance
settings = SimulationSettings()
