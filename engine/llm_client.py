import sys
from pathlib import Path
from typing import Optional
from random import Random

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from openai import OpenAI
from config import settings

class NarrativeEngine:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        key = api_key or settings.OPENAI_API_KEY
        url = base_url or settings.OPENAI_BASE_URL

        self.is_configured = bool(key and not key.startswith("sk-your-") and key != "mock_key")
        if self.is_configured:
            try:
                self.client = OpenAI(api_key=key, base_url=url)
            except Exception as e:
                print(f"[NarrativeEngine] Client init fallback: {e}")
                self.client = None
        else:
            self.client = None

    def generate_chronicle(self, prompt: str, day: int = 1, system_prompt: Optional[str] = None) -> str:
        """Generates historical lore chapter. Uses OpenAI/Ollama if configured, or procedural synthesis."""
        if self.is_configured and self.client:
            sys_msg = system_prompt or (
                "You are the Chronicler of Pangaea, an ancient, objective historian. "
                "Write a formal, evocative historical chronicle of the recorded cycle events. "
                "Focus on kinship, death, scarcity, and civilization milestones."
            )
            try:
                response = self.client.chat.completions.create(
                    model=settings.LLM_MODEL,
                    messages=[
                        {"role": "system", "content": sys_msg},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=settings.LLM_TEMPERATURE,
                    max_tokens=800
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                print(f"[Chronicler Warning] Remote LLM failed ({e}); falling back to procedural synthesis.")

        return self._procedural_narrative(prompt, day=day)

    def _procedural_narrative(self, prompt: str, day: int = 1) -> str:
        """Procedural narrative generator seeded per day for restart reproducibility."""
        rng = Random(f"{settings.SIMULATION_SEED}:chronicle:{day}")

        openings = [
            "The cycle began under pale skies as citizens ventured forth from their dwellings.",
            "Scouring winds swept through the river valleys while the living gathered their strength.",
            "As another day broke across Pangaea, the community turned its attention to subsistence.",
            "Quiet dawn gave way to the daily labor of foraging across scrub and stone."
        ]
        closings = [
            "With nightfall, activity ceased and the community rested to regain energy for the dawn.",
            "Midnight quiet returned to the settlements as fires dimmed and another cycle concluded.",
            "Darkness brought necessary stillness across the encampments, preserving vitality for the morrow."
        ]

        intro = rng.choice(openings)
        conclusion = rng.choice(closings)

        event_lines = [
            line.strip().lstrip("-").strip() 
            for line in prompt.split("
") 
            if line.strip().startswith("-") and "peaceful" not in line.lower()
        ]

        if event_lines:
            events_text = " ".join(f"The records note: {ev.rstrip('.')}." for ev in event_lines[:5])
            body = f"{intro}

{events_text}

{conclusion}"
        else:
            body = f"{intro}

The day passed without notable births or passings; stores and energy were husbanded steadily.

{conclusion}"

        return body

narrator = NarrativeEngine()
