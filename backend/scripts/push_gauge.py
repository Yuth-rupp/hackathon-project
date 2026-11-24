"""
Push REAL gauge readings into FloodPulse via POST /hydrology/telemetry.

Use this when you have actual measurements (MRC / MoWRAM bulletin, data
logger, sensor) and no MRC API token.

Single reading:
  python scripts/push_gauge.py --url http://localhost:8000 --key YOUR_KEY \
      --station 020102 --level 6.82 --time 2026-11-23T08:00:00+07:00

CSV (columns: station,water_level_m,timestamp):
  python scripts/push_gauge.py --url https://YOUR-BACKEND --key YOUR_KEY --csv readings.csv

--key must equal TELEMETRY_API_KEY in the backend .env.
Omit --time to use "now". Only send measured values.
"""

import argparse
import csv
import sys

import httpx


def build_readings(args):
    if args.csv:
        readings = []
        with open(args.csv, newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                item = {
                    "station": row["station"].strip(),
                    "water_level_m": float(row["water_level_m"]),
                    "source": args.source,
                }
                if row.get("timestamp"):
                    item["timestamp"] = row["timestamp"].strip()
                readings.append(item)
        return readings

    if not args.station or args.level is None:
        sys.exit("Provide --station and --level, or --csv.")

    item = {"station": args.station, "water_level_m": args.level, "source": args.source}
    if args.time:
        item["timestamp"] = args.time
    return [item]


def main():
    parser = argparse.ArgumentParser(description="Push real gauge readings to FloodPulse")
    parser.add_argument("--url", required=True, help="Backend base URL, e.g. http://localhost:8000")
    parser.add_argument("--key", required=True, help="TELEMETRY_API_KEY")
    parser.add_argument("--station", help="Station code (020102, 020106, 610101) or id")
    parser.add_argument("--level", type=float, help="Water level in metres")
    parser.add_argument("--time", help="ISO 8601 timestamp (default: now)")
    parser.add_argument("--csv", help="CSV file with station,water_level_m,timestamp")
    parser.add_argument("--source", default="MRC-manual", help="Source label stored with the reading")
    args = parser.parse_args()

    response = httpx.post(
        args.url.rstrip("/") + "/hydrology/telemetry",
        json={"readings": build_readings(args)},
        headers={"X-API-Key": args.key},
        timeout=30.0,
    )

    print(response.status_code, response.text)
    response.raise_for_status()


if __name__ == "__main__":
    main()