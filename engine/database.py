import os
import sys
import sqlite3
from pathlib import Path
from typing import Optional

# Ensure project root is in sys.path when run directly
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import settings

def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    target_path = db_path or str(settings.DB_PATH)
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    conn = sqlite3.connect(target_path, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn

def init_db(db_path: Optional[str] = None) -> None:
    conn = get_connection(db_path)
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS world_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day INTEGER NOT NULL,
            hour INTEGER NOT NULL,
            weather TEXT DEFAULT 'Clear',
            active_events TEXT DEFAULT '[]',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            generation INTEGER DEFAULT 1,
            age REAL DEFAULT 18.0,
            current_region TEXT NOT NULL,
            profession TEXT NOT NULL,
            health REAL DEFAULT 100.0,
            hunger REAL DEFAULT 0.0,
            energy REAL DEFAULT 100.0,
            inventory TEXT DEFAULT '{}',
            lineage TEXT DEFAULT '{}',
            traits TEXT DEFAULT '[]',
            is_alive INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS regions (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            biome TEXT NOT NULL,
            resources TEXT DEFAULT '{}',
            danger_level REAL DEFAULT 0.1
        );

        CREATE TABLE IF NOT EXISTS chronicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day INTEGER NOT NULL,
            title TEXT NOT NULL,
            content_path TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
    conn.close()

if __name__ == "__main__":
    init_db()
    print(f"Database initialized successfully at: {settings.DB_PATH}")
