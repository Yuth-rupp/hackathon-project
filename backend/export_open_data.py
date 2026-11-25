"""
FloodPulse AI - Open data export.

Writes the real (non-sample) data your project uses to CSV files, plus a
README.md that lists every source, its licence and the attribution text.
Upload the generated `open_data` folder to GitHub and share that link.

Run from the backend folder:

    python export_open_data.py
    python export_open_data.py path/to/floodpulse.db
"""

import csv
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BACKEND_DIR / "floodpulse.db"
OUTPUT_DIR = BACKEND_DIR / "open_data"

# Rows created by the first-launch seed are sample data, not measurements.
NOT_SAMPLE = "COALESCE(data_source, '') NOT LIKE '%Baseline%'"

DATASETS = [
    {
        "file": "monitoring_locations.csv",
        "title": "Monitoring locations (five Tonle Sap provinces)",
        "query": "SELECT * FROM monitoring_locations",
        "source": "Project configuration",
    },
    {
        "file": "weather_hourly.csv",
        "title": "Hourly rainfall, soil moisture and weather",
        "query": f"SELECT * FROM weather_data WHERE {NOT_SAMPLE} ORDER BY location_id, timestamp",
        "source": "Open-Meteo (CC BY 4.0)",
    },
    {
        "file": "river_discharge.csv",
        "title": "River discharge (GloFAS via Open-Meteo Flood API)",
        "query": f"SELECT * FROM river_discharge WHERE {NOT_SAMPLE} ORDER BY location_id, date",
        "source": "Open-Meteo Flood API / GloFAS (CC BY 4.0)",
    },
    {
        "file": "satellite_acquisitions.csv",
        "title": "Satellite scene metadata",
        "query": "SELECT * FROM satellite_acquisitions",
        "source": "Copernicus Sentinel-1 (STAC catalogue)",
    },
    {
        "file": "risk_assessments.csv",
        "title": "FloodPulse AI risk assessments (project output)",
        "query": "SELECT * FROM risk_assessments ORDER BY id",
        "source": "Calculated by this project from the data above",
    },
]

SOURCES_TABLE = """| Source | Used for | Licence / access |
|---|---|---|
| [Open-Meteo](https://open-meteo.com/) | Rainfall, soil moisture, weather | CC BY 4.0, no key, free for non-commercial use |
| [Open-Meteo Flood API](https://open-meteo.com/en/docs/flood-api) (GloFAS) | River discharge forecast | CC BY 4.0, no key |
| [Copernicus Sentinel-1](https://dataspace.copernicus.eu/) | Radar satellite scenes | Free and open, check the Copernicus terms |
| [JRC Global Surface Water](https://global-surface-water.appspot.com/) | Surface water map layer | Free, cite Pekel et al. (2016) |
| [Open Development Cambodia](https://opendevelopmentcambodia.net/) | Cambodian reference datasets | Licence is set per dataset |
| [OpenStreetMap](https://www.openstreetmap.org/copyright) | Street map tiles | ODbL, credit contributors |

Not included in this export: Mekong River Commission gauge data (access
requires a token), and sample baseline rows created on first launch.
"""


def export() -> None:
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB

    if not db_path.exists():
        sys.exit(f"Database not found: {db_path}")

    OUTPUT_DIR.mkdir(exist_ok=True)

    connection = sqlite3.connect(db_path)
    summary = []

    for dataset in DATASETS:
        try:
            cursor = connection.execute(dataset["query"])
        except sqlite3.Error as exc:
            print(f"Skipped {dataset['file']}: {exc}")
            continue

        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()

        with open(
            OUTPUT_DIR / dataset["file"], "w", newline="", encoding="utf-8"
        ) as handle:
            writer = csv.writer(handle)
            writer.writerow(columns)
            writer.writerows(rows)

        summary.append((dataset, len(rows)))
        print(f"{dataset['file']}: {len(rows)} rows")

    connection.close()

    lines = [
        "# FloodPulse AI - Open Data",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "Real data used by the FloodPulse AI flood monitoring system for the",
        "Tonle Sap Basin, Cambodia. Sample rows are excluded.",
        "",
        "## Files",
        "",
        "| File | Content | Source | Rows |",
        "|---|---|---|---|",
    ]

    for dataset, count in summary:
        lines.append(
            f"| `{dataset['file']}` | {dataset['title']} | "
            f"{dataset['source']} | {count} |"
        )

    lines += [
        "",
        "## Data sources and licences",
        "",
        SOURCES_TABLE,
        "",
        "## Attribution",
        "",
        "Weather data by [Open-Meteo.com](https://open-meteo.com/).",
        "",
    ]

    (OUTPUT_DIR / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Done. Files are in: {OUTPUT_DIR}")


if __name__ == "__main__":
    export()