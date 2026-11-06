#!/usr/bin/env python3
"""
Pangaea Automated Chronicler & Serialized Content Engine
Parses daily historical milestones from civilization.db and generates serialized
markdown lore chapters for publication (Discord, Substack, Patreon, RSS).
"""

import os
import sys
import json
import sqlite3
import argparse
from datetime import datetime
import database

DB_PATH = getattr(database, "DB_PATH", "civilization.db")
DB_DIR = os.getenv("DATA_DIR", "data")
OUTPUT_DIR = os.getenv("ANNALS_DIR", os.path.join(DB_DIR, "annals"))

def get_db_connection():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database not found at {DB_PATH}")
    return sqlite3.connect(DB_PATH)

def fetch_day_metrics(conn, target_day: int):
    c = conn.cursor()
    c.execute("""
        SELECT COUNT(*), MIN(age), MAX(age), MIN(generation), MAX(generation)
        FROM agents;
    """)
    pop, min_age, max_age, min_gen, max_gen = c.fetchone()

    c.execute("""
        SELECT current_region, COUNT(*)
        FROM agents
        GROUP BY current_region;
    """)
    region_counts = dict(c.fetchall())

    return {
        "total_population": pop,
        "min_age": round(min_age, 2) if min_age is not None else 0.0,
        "max_age": round(max_age, 2) if max_age is not None else 0.0,
        "min_gen": min_gen or 1,
        "max_gen": max_gen or 1,
        "regional_breakdown": region_counts
    }

def fetch_events_by_category(conn, target_day: int):
    c = conn.cursor()
    c.execute("""
        SELECT hour, agent_name, memory_text
        FROM agent_memories
        WHERE day = ?
        ORDER BY id ASC;
    """, (target_day,))
    
    rows = c.fetchall()
    
    events = {
        "births": [],
        "war_raids": [],
        "conspiracies": [],
        "heresies": [],
        "divine": [],
        "hardships": [],
        "feasts_kinship": []
    }

    for hour, agent, text in rows:
        time_tag = f"[{hour:02d}:00]"
        clean_name = agent.replace("_", " ")

        if "Dynastic Lore: Born to" in text:
            events["births"].append(f"{time_tag} **{clean_name}** — {text}")
        elif "WAR DECREED" in text or "raiding war party" in text or "military raids" in text:
            events["war_raids"].append(f"{time_tag} **{clean_name}** — {text}")
        elif "CONSPIRACY" in text or "met in shadows" in text or "secret plots" in text:
            events["conspiracies"].append(f"{time_tag} **{clean_name}** — {text}")
        elif "APOSTASY" in text or "preached defiance" in text or "heretic" in text.lower():
            events["heresies"].append(f"{time_tag} **{clean_name}** — {text}")
        elif "Blessed by" in text or "Smitten by" in text or "divine majesty" in text:
            events["divine"].append(f"{time_tag} **{clean_name}** — {text}")
        elif "starvation" in text.lower() or "severe" in text.lower() or "drought" in text.lower() or "blight" in text.lower():
            events["hardships"].append(f"{time_tag} **{clean_name}** — {text}")
        elif "Provided rations to care for child" in text or "Nourished with meals" in text or "shared food" in text:
            events["feasts_kinship"].append(f"{time_tag} **{clean_name}** — {text}")

    return events

def build_chapter(target_day: int, metrics: dict, events: dict) -> str:
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    
    regions_md = ", ".join([f"**{r}** ({count})" for r, count in metrics["regional_breakdown"].items()])
    
    md = []
    md.append(f"# 📜 The Annals of Pangaea: Year {target_day}")
    md.append(f"*Transcribed on {timestamp} • Historical Record for Solar Cycle {target_day}*\n")
    md.append("---\n")

    md.append("## 🌍 Demographic State of the Realm")
    md.append(f"- **Total Living Citizens**: {metrics['total_population']}")
    md.append(f"- **Dynastic Span**: Generations {metrics['min_gen']} through {metrics['max_gen']}")
    md.append(f"- **Age Spread**: {metrics['min_age']}y to {metrics['max_age']}y")
    md.append(f"- **Regional Populations**: {regions_md or 'Desolate'}\n")

    md.append("## 👶 Dynastic Successions & Births")
    if events["births"]:
        for item in events["births"]:
            md.append(f"- {item}")
    else:
        md.append("- *No heirs were brought into the crèches during this cycle.*")
    md.append("")

    md.append("## ⚔️ Raids, Conflicts & Territorial Ambitions")
    if events["war_raids"]:
        for item in events["war_raids"][:10]:
            md.append(f"- {item}")
    else:
        md.append("- *Borders remained quiet; no war horns pierced the valleys.*")
    md.append("")

    md.append("## 🕯️ Heresies & Apostasy")
    if events["heresies"]:
        for item in events["heresies"][:8]:
            md.append(f"- {item}")
    else:
        md.append("- *The priesthoods maintained orthodox tranquility across the shrines.*")
    md.append("")

    md.append("## 🗡️ Shadow Conspiracies")
    if events["conspiracies"]:
        for item in events["conspiracies"][:8]:
            md.append(f"- {item}")
    else:
        md.append("- *No whispers of rebellion or covert pacts escaped the taverns.*")
    md.append("")

    md.append("## 🍞 Kinship, Sustenance & Hearth")
    if events["feasts_kinship"]:
        for item in events["feasts_kinship"][:6]:
            md.append(f"- {item}")
    else:
        md.append("- *Settlers subsisted on solitary provisions; no communal rations logged.*")
    md.append("")

    if events["divine"]:
        md.append("## ⚡ Divine Omens & Interventions")
        for item in events["divine"][:6]:
            md.append(f"- {item}")
        md.append("")

    md.append("---\n")
    md.append("*Read live telemetry and intervene in regional politics at [Pangaea Atlas](https://pangaea.morgul-labs.com).*")
    
    return "\n".join(md)

def run_chronicler(day: int = None, output_file: str = None):
    conn = get_db_connection()
    c = conn.cursor()

    if day is None:
        c.execute("SELECT MAX(day) FROM world_state;")
        row = c.fetchone()
        day = row[0] if (row and row[0] is not None) else 1

    print(f"[Chronicler] Aggregating historical chronicle for Day {day}...")
    metrics = fetch_day_metrics(conn, day)
    events = fetch_events_by_category(conn, day)
    conn.close()

    chapter_md = build_chapter(day, metrics, events)

    if not output_file:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output_file = os.path.join(OUTPUT_DIR, f"annals_day_{day:03d}.md")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(chapter_md)

    # Update index.html chapter list
    try:
        idx_path = os.path.join(OUTPUT_DIR, "index.html")
        if os.path.exists(idx_path):
            files = sorted([f for f in os.listdir(OUTPUT_DIR) if f.startswith("annals_day_") and f.endswith(".md")], reverse=True)
            with open(idx_path, "r") as inf:
                html = inf.read()
            target_str = "const available = "
            if target_str in html:
                pre, post = html.split(target_str, 1)
                _, rest = post.split(";", 1)
                html = pre + target_str + json.dumps(files) + ";" + rest
                with open(idx_path, "w") as outf:
                    outf.write(html)
    except Exception as e:
        print(f"[Chronicler] Warning: Failed to refresh index.html: {e}")

    print(f"[Chronicler] Successfully compiled {output_file} ({len(chapter_md)} bytes).")
    return output_file, chapter_md

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pangaea Automated Chronicle Generator")
    parser.add_argument("--day", type=int, default=None, help="Specific simulation day to transcribe")
    parser.add_argument("--out", type=str, default=None, help="Custom output path for the markdown file")
    args = parser.parse_args()

    out_path, content = run_chronicler(args.day, args.out)
