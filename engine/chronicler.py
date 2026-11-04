import sys
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import settings
from engine.database import get_connection
from engine.llm_client import narrator

def record_daily_annal(day: int) -> Path:
    """Generates Markdown chronicle chapter for the completed day."""
    conn = get_connection()
    settings.ensure_directories()

    with conn:
        state = conn.execute("SELECT active_events FROM world_state ORDER BY id DESC LIMIT 1").fetchone()
        events = json.loads(state["active_events"] or "[]") if state else []

        living = conn.execute("SELECT COUNT(*) FROM agents WHERE is_alive = 1").fetchone()[0]
        deceased = conn.execute("SELECT COUNT(*) FROM agents WHERE is_alive = 0").fetchone()[0]

    conn.close()

    events_summary = "\n".join(f"- {e}" for e in events) if events else "- The settlements remained peaceful."
    prompt = f"""
Day {day} Census & Daily Record:
Living Population: {living}
Total Fallen: {deceased}

Notable Recorded Events:
{events_summary}
"""

    lore_text = narrator.generate_chronicle(prompt, day=day)
    filename = f"cycle_{day:04d}.md"
    file_path = settings.ANNALS_DIR / filename

    content = f"""# The Annals of Pangaea — Cycle {day}

**Living Inhabitants:** {living} | **Deceased:** {deceased}

---

{lore_text}

---
*Archived automatically by the Morgul Engine.*
"""
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    conn = get_connection()
    with conn:
        conn.execute("""
            INSERT INTO chronicles (day, title, content_path)
            VALUES (?, ?, ?)
        """, (day, f"Cycle {day}", str(file_path)))
    conn.close()

    return file_path
