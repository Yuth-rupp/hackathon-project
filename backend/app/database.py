"""
FloodPulse AI - Asynchronous SQLite Database Engine
Schema definition, connection pooling, and seeding for Tonle Sap monitoring.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Optional, Dict, Any, List

import aiosqlite
from app.config import settings

logger = logging.getLogger(__name__)


def get_db_path() -> str:
    """Resolve the absolute database file path."""
    db_file = Path(settings.DATABASE_PATH)
    if not db_file.is_absolute():
        # Place relative to current backend directory
        db_file = Path(__file__).resolve().parent.parent / settings.DATABASE_PATH
    db_file.parent.mkdir(parents=True, exist_ok=True)
    return str(db_file)


async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """
    Async dependency that yields an aiosqlite connection with dict-like row factory.
    Enforces foreign keys and WAL mode for high concurrency.
    """
    db_path = get_db_path()
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON;")
        await db.execute("PRAGMA journal_mode = WAL;")
        yield db


# ==============================================================================
# Database Schema Definitions
# ==============================================================================

SCHEMA_SQL = """
-- 1. Hydrological & Meteorological Gauging Stations
CREATE TABLE IF NOT EXISTS stations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    name_km TEXT,
    type TEXT,
    province TEXT,
    district TEXT,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    elevation REAL,
    water_body TEXT,
    data_source TEXT,
    alarm_level REAL,
    flood_level REAL,
    is_active INTEGER DEFAULT 1,
    metadata_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 2. High-Frequency Water Level Telemetry
CREATE TABLE IF NOT EXISTS water_levels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT DEFAULT 'm',
    data_source TEXT,
    retrieval_timestamp TEXT,
    quality_flag TEXT DEFAULT 'good',
    FOREIGN KEY (station_id) REFERENCES stations(id) ON DELETE CASCADE
);

-- 3. Weather Forecast & Observations (Open-Meteo)
CREATE TABLE IF NOT EXISTS weather_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    data_type TEXT,
    temperature_c REAL,
    humidity_pct REAL,
    precipitation_mm REAL,
    rain_mm REAL,
    wind_speed_kmh REAL,
    wind_direction_deg REAL,
    soil_moisture REAL,
    weather_code INTEGER,
    data_source TEXT,
    retrieval_timestamp TEXT
);

-- 4. River Discharge Forecast & Baseline (Open-Meteo Global Flood)
CREATE TABLE IF NOT EXISTS river_discharge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    discharge_m3s REAL,
    discharge_max REAL,
    discharge_mean REAL,
    discharge_median REAL,
    data_source TEXT,
    retrieval_timestamp TEXT
);

-- 5. Historical Flood Impacts & Disaster Catalog (ODC / NDMC)
CREATE TABLE IF NOT EXISTS flood_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_date TEXT,
    end_date TEXT,
    province TEXT,
    district TEXT,
    commune TEXT,
    deaths INTEGER DEFAULT 0,
    affected_people INTEGER DEFAULT 0,
    houses_damaged INTEGER DEFAULT 0,
    houses_destroyed INTEGER DEFAULT 0,
    crop_area_ha REAL DEFAULT 0.0,
    economic_loss_usd REAL DEFAULT 0.0,
    data_source TEXT,
    source_event_id TEXT,
    notes TEXT
);

-- 6. Sentinel-1 SAR & Satellite Imagery Catalog (Copernicus STAC)
CREATE TABLE IF NOT EXISTS satellite_acquisitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    satellite TEXT NOT NULL,
    acquisition_date TEXT NOT NULL,
    collection TEXT,
    orbit_state TEXT,
    instrument_mode TEXT,
    bbox_geojson TEXT,
    cloud_cover REAL,
    stac_url TEXT,
    thumbnail_url TEXT,
    processed INTEGER DEFAULT 0,
    water_extent_km2 REAL,
    processed_geojson_path TEXT,
    metadata_json TEXT
);

-- 7. Predictive Risk Assessments & Machine Learning Horizons
CREATE TABLE IF NOT EXISTS risk_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id INTEGER NOT NULL,
    assessment_date TEXT NOT NULL,
    prediction_horizon_days INTEGER DEFAULT 7,
    risk_probability REAL NOT NULL,
    risk_category TEXT NOT NULL,
    model_version TEXT,
    model_type TEXT,
    contributing_factors_json TEXT,
    confidence_info_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 8. Emergency Alerts & Dispatches (Telegram / Webhooks)
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    title_km TEXT,
    message TEXT NOT NULL,
    message_km TEXT,
    location_id INTEGER,
    province TEXT,
    trigger_source TEXT,
    trigger_data_json TEXT,
    status TEXT DEFAULT 'active',
    telegram_sent INTEGER DEFAULT 0,
    telegram_message_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT,
    created_by TEXT DEFAULT 'system'
);

-- 9. External Data Connector Health & Audit Status
CREATE TABLE IF NOT EXISTS data_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    provider TEXT NOT NULL,
    api_endpoint TEXT,
    data_type TEXT,
    geographic_coverage TEXT,
    temporal_coverage TEXT,
    update_frequency TEXT,
    license TEXT,
    status TEXT DEFAULT 'unknown',
    last_successful_fetch TEXT,
    last_error TEXT,
    last_error_time TEXT,
    config_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 10. Monitored Provincial & Floodplain Locations
CREATE TABLE IF NOT EXISTS monitoring_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    name_km TEXT,
    type TEXT,
    province TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    elevation_m REAL,
    distance_to_lake_km REAL,
    flood_frequency_score REAL,
    boundary_geojson_path TEXT,
    metadata_json TEXT
);

-- 11. Security & Operational Audit Log
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    details_json TEXT,
    performed_by TEXT DEFAULT 'system',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Optimization Indexes
CREATE INDEX IF NOT EXISTS idx_water_levels_station_time ON water_levels(station_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_weather_data_loc_time ON weather_data(location_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_river_discharge_loc_date ON river_discharge(location_id, date);
CREATE INDEX IF NOT EXISTS idx_alerts_status_severity ON alerts(status, severity);
CREATE INDEX IF NOT EXISTS idx_risk_loc_date ON risk_assessments(location_id, assessment_date);
CREATE INDEX IF NOT EXISTS idx_sat_date ON satellite_acquisitions(acquisition_date);
"""


async def seed_default_data(db: aiosqlite.Connection) -> None:
    """
    Populate database with baseline stations, monitoring locations,
    data sources, and historical records on initial startup.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Seed Monitoring Locations
    for key, loc in settings.MONITORING_LOCATIONS.items():
        await db.execute(
            """
            INSERT INTO monitoring_locations (
                id, name, name_km, type, province, lat, lon,
                elevation_m, distance_to_lake_km, flood_frequency_score, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                name_km=excluded.name_km,
                lat=excluded.lat,
                lon=excluded.lon,
                elevation_m=excluded.elevation_m,
                distance_to_lake_km=excluded.distance_to_lake_km,
                flood_frequency_score=excluded.flood_frequency_score
            """,
            (
                loc["id"],
                loc["name"],
                loc["name_km"],
                loc["type"],
                loc["province"],
                loc["lat"],
                loc["lon"],
                loc["elevation_m"],
                loc["distance_to_lake_km"],
                loc["flood_frequency_score"],
                json.dumps({"key": key})
            )
        )

    # 2. Seed Gauging Stations
    for code, st in settings.STATION_CONFIGS.items():
        await db.execute(
            """
            INSERT INTO stations (
                code, name, name_km, type, province, district,
                lat, lon, elevation, water_body, data_source,
                alarm_level, flood_level, is_active, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(code) DO UPDATE SET
                name=excluded.name,
                name_km=excluded.name_km,
                alarm_level=excluded.alarm_level,
                flood_level=excluded.flood_level,
                lat=excluded.lat,
                lon=excluded.lon
            """,
            (
                st["code"],
                st["name"],
                st["name_km"],
                st["type"],
                st["province"],
                st["district"],
                st["lat"],
                st["lon"],
                st["elevation"],
                st["water_body"],
                st["data_source"],
                st["alarm_level"],
                st["flood_level"],
                json.dumps({"notes": st.get("notes", "")})
            )
        )

    # 3. Seed Registered Data Sources
    default_sources = [
        (
            "Open-Meteo Weather Forecast",
            "Open-Meteo",
            settings.OPEN_METEO_FORECAST_URL,
            "meteorological",
            "Global / Cambodia",
            "Real-time & 7-day forecast",
            "Hourly",
            "CC BY 4.0",
            "active"
        ),
        (
            "Open-Meteo Global Flood API",
            "Open-Meteo / GloFAS",
            settings.OPEN_METEO_FLOOD_URL,
            "hydrological_discharge",
            "Mekong Basin & Tonle Sap tributaries",
            "Daily & 14-day ensemble forecast",
            "Daily",
            "Copernicus Open Access",
            "active"
        ),
        (
            "Copernicus Sentinel-1 STAC",
            "ESA / Copernicus Data Space",
            settings.COPERNICUS_STAC_URL,
            "satellite_radar_sar",
            "Tonle Sap Basin [102.5, 12.0, 105.5, 14.0]",
            "2014 - Present",
            "Every 6-12 days",
            "Copernicus Open Access Policy",
            "active"
        ),
        (
            "JRC Global Surface Water",
            "European Commission Joint Research Centre",
            settings.JRC_TILE_URL_TEMPLATE,
            "earth_observation_water_extent",
            "Global / Tile 100E_20N",
            "1984 - 2021 (38 years)",
            "Annual / Static Baselines",
            "Open Data / JRC",
            "active"
        ),
        (
            "Open Development Cambodia (ODC)",
            "ODC Open Data CKAN",
            settings.ODC_CKAN_API_URL,
            "disaster_statistics_flood_history",
            "Cambodia (National)",
            "2000 - Present",
            "As published by NCDM",
            "ODC Open Database License",
            "active"
        ),
        (
            "Mekong River Commission (MRC)",
            "MRC Secretariat",
            settings.MRC_API_BASE_URL,
            "telemetry_water_level",
            "Lower Mekong Basin / Tonle Sap",
            "Real-time telemetry",
            "15 minutes to daily",
            "MRC Data Sharing Policy",
            "active" if settings.MRC_API_TOKEN else "auth_required"
        ),
        (
            "NASA FIRMS Thermal Anomalies",
            "NASA Earth Science Data",
            settings.FIRMS_API_URL,
            "thermal_hotspots_fire",
            "Cambodia Floodplain Margins",
            "Near Real-Time (3 hours)",
            "Daily",
            "NASA Open Data",
            "active" if settings.FIRMS_API_KEY else "key_required"
        )
    ]

    for src in default_sources:
        await db.execute(
            """
            INSERT INTO data_sources (
                name, provider, api_endpoint, data_type, geographic_coverage,
                temporal_coverage, update_frequency, license, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                provider=excluded.provider,
                api_endpoint=excluded.api_endpoint,
                update_frequency=excluded.update_frequency
            """,
            (*src, now_iso)
        )

    # 4. Water levels are NOT seeded.
    # Gauges show "NO DATA" until a real source supplies readings
    # (MRC_API_TOKEN, or POST /hydrology/telemetry). Seeding invented values
    # here made the dashboards look live and fed made-up numbers to the risk model.

    # 5. Seed Historical Flood Event benchmark (2020 Cambodia Floods)
    event_cursor = await db.execute("SELECT COUNT(*) as count FROM flood_events")
    event_row = await event_cursor.fetchone()
    if event_row and event_row["count"] == 0:
        historic_events = [
            (
                "2020-10-06", "2020-10-28", "Pursat", "Krakor", "All",
                14, 25000, 4800, 320, 18500.0, 12500000.0, "NCDM/ODC", "FL-2020-KHM-001",
                "Severe tropical storms Linfa & Nangka caused massive lake backflow flooding Pursat and Battambang."
            ),
            (
                "2020-10-10", "2020-10-30", "Battambang", "Sangkae", "All",
                8, 38000, 7200, 410, 24000.0, 18000000.0, "NCDM/ODC", "FL-2020-KHM-002",
                "Sangkae river flash flood combining with high Tonle Sap lake level preventing drainage."
            ),
            (
                "2022-10-01", "2022-10-20", "Siem Reap", "Puok", "Chreav",
                2, 12000, 1400, 45, 8200.0, 4200000.0, "NCDM/ODC", "FL-2022-KHM-003",
                "Heavy seasonal monsoon rainfall coupled with high lake pulse inundating low-lying agricultural zones."
            )
        ]
        for evt in historic_events:
            await db.execute(
                """
                INSERT INTO flood_events (
                    event_date, end_date, province, district, commune,
                    deaths, affected_people, houses_damaged, houses_destroyed,
                    crop_area_ha, economic_loss_usd, data_source, source_event_id, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                evt
            )

    await db.commit()
    logger.info("Default seed data initialized successfully.")


async def init_db() -> None:
    """
    Initialize SQLite database schema and seed default tables.
    Runs during FastAPI startup lifecycle.
    """
    db_path = get_db_path()
    logger.info(f"Connecting to database at {db_path}...")
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON;")
        await db.execute("PRAGMA journal_mode = WAL;")
        await db.executescript(SCHEMA_SQL)
        await db.commit()
        await seed_default_data(db)
    logger.info("Database schema and seeds successfully established.")


# Helper query utilities
async def fetch_all(query: str, params: tuple = ()) -> List[Dict[str, Any]]:
    """Helper to execute a query and return all rows as dicts."""
    db_path = get_db_path()
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def fetch_one(query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
    """Helper to execute a query and return a single row as dict."""
    db_path = get_db_path()
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def execute_query(query: str, params: tuple = ()) -> int:
    """Helper to execute INSERT/UPDATE/DELETE query and return lastrowid."""
    db_path = get_db_path()
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(query, params) as cursor:
            await db.commit()
            return cursor.lastrowid