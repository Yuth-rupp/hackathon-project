"""
Send a REAL gauge reading to FloodPulse AI.

Use it for readings from a gauge observer, a data logger, a phone report from
MoWRAM / provincial staff, or a cron job that copies a bulletin. The reading
goes through POST /hydrology/telemetry, which stores it, updates every open
browser instantly, re-runs the flood risk for that province, and raises an alert
if the level is above the alarm / flood level.

Setup (once)
    1. Create a secret key and put it in backend/.env :
           TELEMETRY_API_KEY=<long random text>
       (python -c "import secrets; print(secrets.token_urlsafe(32))")
    2. Restart the backend.

Examples
    python scripts/push_gauge_reading.py --station 020106 --level 7.85 \
        --url http://localhost:8000/api/v1 --key YOUR_KEY

    python scripts/push_gauge_reading.py --station 020102 --level 6.40 \
        --time 2026-11-23T08:00:00+07:00 --source mowram_bulletin \
        --url https://YOUR-BACKEND/api/v1 --key YOUR_KEY

Station codes: 020102 Prek Kdam, 020106 Kampong Luong, 610101 (see /hydrology/stations).
Only send measured values. Do not send estimates or test numbers to a live system.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a real gauge reading to FloodPulse AI.")
    parser.add_argument("--url", default="http://localhost:8000/api/v1", help="API base URL")
    parser.add_argument("--key", required=True, help="TELEMETRY_API_KEY from backend/.env")
    parser.add_argument("--station", required=True, help="Station code, e.g. 020106")
    parser.add_argument("--level", required=True, type=float, help="Water level in metres")
    parser.add_argument("--time", help="ISO 8601 time of the measurement (default: now)")
    parser.add_argument("--source", default="telemetry", help="Where the value came from")
    args = parser.parse_args()

    reading = {"station": args.station, "water_level_m": args.level, "source": args.source}
    if args.time:
        reading["timestamp"] = args.time

    request = urllib.request.Request(
        f"{args.url.rstrip('/')}/hydrology/telemetry",
        data=json.dumps({"readings": [reading]}).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-API-Key": args.key},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            print(response.status, response.read().decode("utf-8"))
        return 0
    except urllib.error.HTTPError as error:
        print(error.code, error.read().decode("utf-8"))
        return 1
    except urllib.error.URLError as error:
        print("Could not reach the backend:", error.reason)
        return 1


if __name__ == "__main__":
    sys.exit(main())