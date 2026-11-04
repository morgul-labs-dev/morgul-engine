import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import settings
from engine.core import engine
from engine.chronicler import record_daily_annal

def run_loop():
    print(f"[*] Starting Autonomous Simulation Loop (Tick interval: {settings.TICK_INTERVAL_SEC}s)...")
    try:
        while True:
            res = engine.tick_hour()
            day, hour = res["day"], res["hour"]
            print(f"[Cycle {day:04d} | {hour:02d}:00] Active Agents Checked.", end="")
            
            if res.get("events"):
                print(f" Events ({len(res['events'])}): {', '.join(res['events'])}")
            else:
                print(" All calm.")

            if res.get("cycle_completed"):
                print(f"\n[+] Cycle {day} ended. Penning daily chronicles...")
                annal_path = record_daily_annal(day)
                print(f"[+] Chapter archived at {annal_path}\n")

            time.sleep(settings.TICK_INTERVAL_SEC)
    except KeyboardInterrupt:
        print("\n[!] Simulation loop stopped by user.")

if __name__ == "__main__":
    run_loop()
