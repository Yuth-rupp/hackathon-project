"""
Remove invented gauge readings from an existing FloodPulse database.

Older versions seeded placeholder water levels (MRC_BASELINE, SEED_DEMO and,
from app/data/seed.py, MRC_TELEMETRY). They look like measurements but nobody
measured them. Run this once on every database that was created before the
update:

    python scripts/purge_placeholder_gauges.py                 # shows what would be removed
    python scripts/purge_placeholder_gauges.py --apply         # removes it
    python scripts/purge_placeholder_gauges.py --db path/to/floodpulse.db --apply

Real readings (sources "MRC", "telemetry", or anything you send yourself) are
never touched. Back up the file first if it holds data you care about.
"""

import argparse
import sqlite3
import sys

PLACEHOLDER_SOURCES = ("MRC_BASELINE", "SEED_DEMO", "MRC_TELEMETRY")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="floodpulse.db")
    parser.add_argument("--apply", action="store_true", help="Delete the rows (default: only count)")
    args = parser.parse_args()

    connection = sqlite3.connect(args.db)
    marks = ",".join("?" for _ in PLACEHOLDER_SOURCES)

    rows = connection.execute(
        f"SELECT data_source, COUNT(*) FROM water_levels WHERE data_source IN ({marks}) GROUP BY data_source",
        PLACEHOLDER_SOURCES,
    ).fetchall()

    if not rows:
        print("No placeholder gauge readings found.")
        return 0

    for source, count in rows:
        print(f"{source}: {count} rows")

    if not args.apply:
        print("Nothing deleted. Run again with --apply to remove them.")
        return 0

    connection.execute(f"DELETE FROM water_levels WHERE data_source IN ({marks})", PLACEHOLDER_SOURCES)
    connection.commit()
    print("Removed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())