"""
Remove placeholder rows (CALIBRATED / BASELINE / SIMULATED / SEED / DEMO)
from water_levels so charts only contain real measurements.

Run from the backend folder:
  python scripts/clean_baseline.py            (preview only)
  python scripts/clean_baseline.py --apply    (deletes; backs up the DB first)
"""

import shutil
import sqlite3
import sys

DB_PATH = "floodpulse.db"
MARKERS = ("CALIBRATED", "BASELINE", "SIMULATED", "SEED", "DEMO")

where = " OR ".join(f"UPPER(COALESCE(data_source,'')) LIKE '%{m}%'" for m in MARKERS)

conn = sqlite3.connect(DB_PATH)
rows = conn.execute(
    f"SELECT data_source, COUNT(*) FROM water_levels WHERE {where} GROUP BY 1"
).fetchall()

print("Placeholder rows found:", rows or "none")

if "--apply" in sys.argv and rows:
    shutil.copyfile(DB_PATH, DB_PATH + ".bak")
    conn.execute(f"DELETE FROM water_levels WHERE {where}")
    conn.commit()
    print("Deleted. Backup saved as", DB_PATH + ".bak")

conn.close()