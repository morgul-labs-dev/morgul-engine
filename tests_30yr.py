import subprocess
import time
import json
from engine.core import engine
from engine.chronicler import record_daily_annal

import sys
subprocess.run([sys.executable, "init_sim.py", "--force"], check=True)
conn = engine.get_conn()
conn.execute("PRAGMA synchronous = OFF")

start = time.time()
deaths_20_30 = 0
births_20_30 = 0

for year in range(1, 31):
    prev_d = conn.execute("SELECT COUNT(*) FROM agents WHERE is_alive=0").fetchone()[0]
    prev_t = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]

    for day in range(1, 366):
        for _ in range(24):
            r = engine.tick_hour()
            assert "error" not in r, r
        if year == 1 and day <= 5:
            record_daily_annal(r["day"])

    cur_d = conn.execute("SELECT COUNT(*) FROM agents WHERE is_alive=0").fetchone()[0]
    cur_t = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
    nd = cur_d - prev_d
    nb = cur_t - prev_t

    if year >= 20:
        deaths_20_30 += nd
        births_20_30 += nb

    if year in [1, 5, 10, 15, 20, 25, 30]:
        liv = conn.execute("SELECT COUNT(*) FROM agents WHERE is_alive=1").fetchone()[0]
        inf = conn.execute("SELECT COUNT(*) FROM agents WHERE is_alive=0 AND age<=3.0").fetchone()[0]
        invs = conn.execute("SELECT inventory FROM agents WHERE is_alive=1").fetchall()
        rats = [json.loads(i[0] or "{}").get("rations", 0) for i in invs]
        oldest = conn.execute("SELECT MAX(age) FROM agents WHERE is_alive=1").fetchone()[0] or 0.0
        avg_r = sum(rats) / max(1, len(rats))
        max_r = max(rats) if rats else 0
        print(f"Year {year:02d}: Living={liv:2d} | Deaths={cur_d:2d} (+{nd:2d}, Inf={inf:2d}) | Births=+{nb:2d} | Oldest={oldest:.1f} | Rations: Avg={avg_r:.1f}, Max={max_r}")

liv = conn.execute("SELECT COUNT(*) FROM agents WHERE is_alive=1").fetchone()[0]
tot_d = conn.execute("SELECT COUNT(*) FROM agents WHERE is_alive=0").fetchone()[0]
inf_d = conn.execute("SELECT COUNT(*) FROM agents WHERE is_alive=0 AND age<=3.0").fetchone()[0]
invs = conn.execute("SELECT inventory FROM agents WHERE is_alive=1").fetchall()
max_r = max([json.loads(i[0] or "{}").get("rations", 0) for i in invs] or [0])
reg_c = conn.execute("SELECT COUNT(*) FROM regions").fetchone()[0]

print("=" * 60)
print(f"Summary: Living={liv}, Total Deaths={tot_d}, Infant Deaths={inf_d}, Regions={reg_c}")
print(f"Years 20-30 Continuity: Births={births_20_30}, Deaths={deaths_20_30}")
print(f"Completed in {time.time()-start:.1f}s")

assert 45 <= liv <= 85, f"Population out of bounds: {liv}"
assert max_r <= 100, f"Max rations too high: {max_r}"
assert reg_c == 4, f"Regions not seeded correctly: {reg_c}"
assert deaths_20_30 > 0, f"No deaths between Years 20-30: {deaths_20_30}"
assert births_20_30 > 0, f"No births between Years 20-30: {births_20_30}"
if tot_d > 0:
    inf_pct = (inf_d / tot_d) * 100
    print(f"Infant Death %: {inf_pct:.1f}%")
    assert inf_pct <= 35.0, f"Infant mortality too high: {inf_pct:.1f}%"

print("✓ ALL 30-YEAR CHECKS PASSED!")
