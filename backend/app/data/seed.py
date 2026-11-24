"""
FloodPulse AI - Comprehensive Database Seeding Script
Populates baseline monitoring locations, hydrological stations, external data feeds,
and historical Cambodia flood disasters (2000, 2011, 2013, 2020).

Usage:
    python -m app.data.seed
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import aiosqlite

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.config import settings
from app.database import init_db, get_db_path, SCHEMA_SQL

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed")


MONITORING_PROVINCES = [
    {
        "id": 1,
        "name": "Siem Reap",
        "name_km": "ខេត្តសៀមរាប",
        "type": "urban_floodplain",
        "province": "Siem Reap",
        "lat": 13.3633,
        "lon": 103.8564,
        "elevation_m": 18.0,
        "distance_to_lake_km": 12.5,
        "flood_frequency_score": 0.65,
        "metadata": {
            "key": "siem_reap",
            "population": 1014234,
            "vulnerable_communes": 24,
            "area_km2": 10299.0,
            "drainage_basin": "Siem Reap & Puok Rivers"
        }
    },
    {
        "id": 2,
        "name": "Battambang",
        "name_km": "ខេត្តបាត់ដំបង",
        "type": "riverine_plain",
        "province": "Battambang",
        "lat": 13.1000,
        "lon": 103.2000,
        "elevation_m": 16.0,
        "distance_to_lake_km": 38.0,
        "flood_frequency_score": 0.58,
        "metadata": {
            "key": "battambang",
            "population": 997169,
            "vulnerable_communes": 31,
            "area_km2": 11702.0,
            "drainage_basin": "Sangkae River"
        }
    },
    {
        "id": 3,
        "name": "Pursat",
        "name_km": "ខេត្តពោធិ៍សាត់",
        "type": "tributary_delta",
        "province": "Pursat",
        "lat": 12.5333,
        "lon": 103.9167,
        "elevation_m": 15.0,
        "distance_to_lake_km": 24.0,
        "flood_frequency_score": 0.72,
        "metadata": {
            "key": "pursat",
            "population": 419952,
            "vulnerable_communes": 28,
            "area_km2": 12692.0,
            "drainage_basin": "Pursat River & Krakor Lake Margin"
        }
    },
    {
        "id": 4,
        "name": "Kampong Thom",
        "name_km": "ខេត្តកំពង់ធំ",
        "type": "river_mouth",
        "province": "Kampong Thom",
        "lat": 12.7111,
        "lon": 104.8887,
        "elevation_m": 12.0,
        "distance_to_lake_km": 18.0,
        "flood_frequency_score": 0.78,
        "metadata": {
            "key": "kampong_thom",
            "population": 677260,
            "vulnerable_communes": 35,
            "area_km2": 13814.0,
            "drainage_basin": "Stung Sen River"
        }
    },
    {
        "id": 5,
        "name": "Kampong Chhnang",
        "name_km": "ខេត្តកំពង់ឆ្នាំង",
        "type": "lake_outlet",
        "province": "Kampong Chhnang",
        "lat": 12.2500,
        "lon": 104.6667,
        "elevation_m": 11.0,
        "distance_to_lake_km": 8.0,
        "flood_frequency_score": 0.85,
        "metadata": {
            "key": "kampong_chhnang",
            "population": 525932,
            "vulnerable_communes": 38,
            "area_km2": 5521.0,
            "drainage_basin": "Tonle Sap River Outlet & Chhnang Floodplain"
        }
    }
]


HYDROLOGICAL_STATIONS = [
    {
        "code": "020102",
        "name": "Prek Kdam",
        "name_km": "ព្រែកក្តាម",
        "type": "hydrological",
        "province": "Kandal",
        "district": "Ponhea Lueu",
        "lat": 11.8153,
        "lon": 104.8064,
        "elevation": 7.2,
        "water_body": "Tonle Sap River",
        "data_source": "MRC",
        "alarm_level": 9.5,
        "flood_level": 10.0,
        "notes": "Primary gauge measuring the vital hydrological pulse reversal between Mekong and Tonle Sap."
    },
    {
        "code": "020106",
        "name": "Kampong Luong",
        "name_km": "កំពង់ហ្លួង",
        "type": "lake_gauge",
        "province": "Pursat",
        "district": "Krakor",
        "lat": 12.5833,
        "lon": 104.2000,
        "elevation": 5.0,
        "water_body": "Tonle Sap Lake",
        "data_source": "MRC",
        "alarm_level": 8.5,
        "flood_level": 9.0,
        "notes": "Central Great Lake water level gauge reflecting the storage buffer volume of Cambodia."
    },
    {
        "code": "610101",
        "name": "Kampong Thom",
        "name_km": "កំពង់ធំ",
        "type": "tributary_gauge",
        "province": "Kampong Thom",
        "district": "Stueng Saen",
        "lat": 12.7111,
        "lon": 104.8889,
        "elevation": 8.5,
        "water_body": "Stung Sen River",
        "data_source": "MRC",
        "alarm_level": 13.0,
        "flood_level": 13.5,
        "notes": "Monitors Stung Sen tributary flow, which contributes ~35% of total tributary inflow into the lake."
    }
]


DATA_SOURCES = [
    {
        "name": "Open-Meteo Weather Forecast API",
        "provider": "Open-Meteo",
        "api_endpoint": settings.OPEN_METEO_FORECAST_URL,
        "data_type": "meteorological_forecast",
        "geographic_coverage": "Cambodia / Tonle Sap Basin",
        "temporal_coverage": "Real-time & Hourly 7-day",
        "update_frequency": "Hourly",
        "license": "CC BY 4.0",
        "status": "active"
    },
    {
        "name": "Open-Meteo Global Flood API (GloFAS)",
        "provider": "Copernicus / ECMWF GloFAS",
        "api_endpoint": settings.OPEN_METEO_FLOOD_URL,
        "data_type": "river_discharge",
        "geographic_coverage": "Lower Mekong Basin",
        "temporal_coverage": "Daily & 14-day ensemble forecast",
        "update_frequency": "Daily",
        "license": "Copernicus Open Access",
        "status": "active"
    },
    {
        "name": "Copernicus Sentinel-1 STAC API",
        "provider": "ESA / Copernicus Data Space Ecosystem",
        "api_endpoint": settings.COPERNICUS_STAC_URL,
        "data_type": "satellite_sar_cband",
        "geographic_coverage": "Tonle Sap Basin [102.5, 12.0, 105.5, 14.0]",
        "temporal_coverage": "2014 - Present",
        "update_frequency": "Every 6-12 days",
        "license": "Copernicus Open Access Policy",
        "status": "active"
    },
    {
        "name": "JRC Global Surface Water",
        "provider": "European Commission Joint Research Centre",
        "api_endpoint": settings.JRC_TILE_URL_TEMPLATE,
        "data_type": "earth_observation_water_extent",
        "geographic_coverage": "Tile 100E_20N (Mekong Basin)",
        "temporal_coverage": "1984 - 2021 (38 years)",
        "update_frequency": "Annual / Static Baselines",
        "license": "Open Data / EC JRC",
        "status": "active"
    },
    {
        "name": "Open Development Cambodia (ODC)",
        "provider": "ODC Open Data CKAN",
        "api_endpoint": settings.ODC_CKAN_API_URL,
        "data_type": "disaster_statistics_flood_history",
        "geographic_coverage": "Cambodia (National)",
        "temporal_coverage": "2000 - Present",
        "update_frequency": "As published by NCDM",
        "license": "ODC Open Database License (ODbL)",
        "status": "active"
    },
    {
        "name": "Mekong River Commission (MRC)",
        "provider": "MRC Secretariat Telemetry Network",
        "api_endpoint": settings.MRC_API_BASE_URL,
        "data_type": "telemetry_water_level",
        "geographic_coverage": "Lower Mekong Basin / Tonle Sap",
        "temporal_coverage": "15-minute to daily observations",
        "update_frequency": "Real-time",
        "license": "MRC Data Sharing Policy",
        "status": "active" if settings.MRC_API_TOKEN else "auth_required"
    },
    {
        "name": "NASA FIRMS Thermal Anomalies",
        "provider": "NASA Earth Science Data",
        "api_endpoint": settings.FIRMS_API_URL,
        "data_type": "thermal_hotspots_fire",
        "geographic_coverage": "Cambodia Floodplain Margins",
        "temporal_coverage": "Near Real-Time (3 hours)",
        "update_frequency": "Daily",
        "license": "NASA Open Data Policy",
        "status": "active" if settings.FIRMS_API_KEY else "key_required"
    }
]


HISTORICAL_FLOOD_DISASTERS = [
    {
        "event_date": "2000-09-01",
        "end_date": "2000-11-15",
        "province": "Kandal & Tonle Sap Basin",
        "district": "All Floodplains",
        "commune": "National Emergency",
        "deaths": 347,
        "affected_people": 3448000,
        "houses_damaged": 318000,
        "houses_destroyed": 7000,
        "crop_area_ha": 374000.0,
        "economic_loss_usd": 160000000.0,
        "data_source": "NCDM / ODC Historical Archive",
        "source_event_id": "FL-2000-KHM-HISTORIC",
        "notes": "The 2000 Great Flood: One of the worst catastrophes in Cambodian modern history. Extraordinary monsoon rainfall coupled with Typhoon Wukong caused the Tonle Sap lake to expand to over 16,500 km²."
    },
    {
        "event_date": "2011-09-15",
        "end_date": "2011-11-05",
        "province": "Kampong Cham, Kampong Thom, Siem Reap, Battambang",
        "district": "18 Provinces",
        "commune": "Widespread",
        "deaths": 250,
        "affected_people": 1640000,
        "houses_damaged": 268000,
        "houses_destroyed": 4200,
        "crop_area_ha": 431000.0,
        "economic_loss_usd": 521000000.0,
        "data_source": "NCDM / ODC Historical Archive",
        "source_event_id": "FL-2011-KHM-MEKONG",
        "notes": "2011 Mekong Basin Mega-Flood: Severe backwater flooding submerging 18 Cambodian provinces. Over 400,000 hectares of rice paddies lost right before harvest season."
    },
    {
        "event_date": "2013-09-20",
        "end_date": "2013-10-25",
        "province": "Battambang, Pursat, Siem Reap, Kampong Thom, Kampong Chhnang",
        "district": "Tonle Sap Riparian Districts",
        "commune": "Basin-wide",
        "deaths": 168,
        "affected_people": 1700000,
        "houses_damaged": 240000,
        "houses_destroyed": 2800,
        "crop_area_ha": 240000.0,
        "economic_loss_usd": 356000000.0,
        "data_source": "NCDM / ODC Historical Archive",
        "source_event_id": "FL-2013-KHM-DOKSURI",
        "notes": "2013 Typhoon Doksuri & Severe Monsoon: Torrential rainfall overwhelmed tributary reservoirs and caused catastrophic lake edge flooding in Battambang and Pursat."
    },
    {
        "event_date": "2020-10-06",
        "end_date": "2020-10-31",
        "province": "Pursat, Battambang, Kampong Chhnang",
        "district": "Krakor, Sangkae, Boribor",
        "commune": "Floodplain delta",
        "deaths": 44,
        "affected_people": 800000,
        "houses_damaged": 134000,
        "houses_destroyed": 1200,
        "crop_area_ha": 150000.0,
        "economic_loss_usd": 200000000.0,
        "data_source": "NCDM / ODC Historical Archive",
        "source_event_id": "FL-2020-KHM-LINFA",
        "notes": "2020 Flash Floods & Tropical Storms Linfa/Nangka: Sudden flash inundation as mountain runoff from Cardamom range met high Tonle Sap lake backflow, drowning low-lying villages."
    }
]


async def seed_all() -> None:
    """
    Execute complete seeding transaction across all database tables.
    """
    logger.info("Initializing database schema...")
    await init_db()

    db_path = get_db_path()
    logger.info(f"Connecting to database at {db_path} for data population...")

    now_iso = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        # 1. Seed Monitoring Locations
        logger.info(f"Seeding {len(MONITORING_PROVINCES)} Tonle Sap monitoring provinces...")
        for p in MONITORING_PROVINCES:
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
                    flood_frequency_score=excluded.flood_frequency_score,
                    metadata_json=excluded.metadata_json
                """,
                (
                    p["id"], p["name"], p["name_km"], p["type"], p["province"],
                    p["lat"], p["lon"], p["elevation_m"], p["distance_to_lake_km"],
                    p["flood_frequency_score"], json.dumps(p["metadata"])
                )
            )

        # 2. Seed Hydrological Stations
        logger.info(f"Seeding {len(HYDROLOGICAL_STATIONS)} hydrological stations...")
        for s in HYDROLOGICAL_STATIONS:
            await db.execute(
                """
                INSERT INTO stations (
                    code, name, name_km, type, province, district,
                    lat, lon, elevation, water_body, data_source,
                    alarm_level, flood_level, is_active, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    name=excluded.name,
                    name_km=excluded.name_km,
                    alarm_level=excluded.alarm_level,
                    flood_level=excluded.flood_level,
                    lat=excluded.lat,
                    lon=excluded.lon
                """,
                (
                    s["code"], s["name"], s["name_km"], s["type"], s["province"], s["district"],
                    s["lat"], s["lon"], s["elevation"], s["water_body"], s["data_source"],
                    s["alarm_level"], s["flood_level"], json.dumps({"notes": s["notes"]}), now_iso
                )
            )

        # 3. Seed Registered Data Sources
        logger.info(f"Seeding {len(DATA_SOURCES)} real data source connectors...")
        for src in DATA_SOURCES:
            await db.execute(
                """
                INSERT INTO data_sources (
                    name, provider, api_endpoint, data_type, geographic_coverage,
                    temporal_coverage, update_frequency, license, status,
                    last_successful_fetch, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    provider=excluded.provider,
                    api_endpoint=excluded.api_endpoint,
                    data_type=excluded.data_type,
                    update_frequency=excluded.update_frequency
                """,
                (
                    src["name"], src["provider"], src["api_endpoint"], src["data_type"],
                    src["geographic_coverage"], src["temporal_coverage"], src["update_frequency"],
                    src["license"], src["status"], now_iso, now_iso
                )
            )

        # 4. Seed Historical Flood Disasters
        logger.info(f"Seeding {len(HISTORICAL_FLOOD_DISASTERS)} historical Cambodia flood disasters...")
        for evt in HISTORICAL_FLOOD_DISASTERS:
            # Check if event already exists
            cur = await db.execute("SELECT id FROM flood_events WHERE source_event_id = ?", (evt["source_event_id"],))
            if not await cur.fetchone():
                await db.execute(
                    """
                    INSERT INTO flood_events (
                        event_date, end_date, province, district, commune,
                        deaths, affected_people, houses_damaged, houses_destroyed,
                        crop_area_ha, economic_loss_usd, data_source, source_event_id, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        evt["event_date"], evt["end_date"], evt["province"], evt["district"],
                        evt["commune"], evt["deaths"], evt["affected_people"], evt["houses_damaged"],
                        evt["houses_destroyed"], evt["crop_area_ha"], evt["economic_loss_usd"],
                        evt["data_source"], evt["source_event_id"], evt["notes"]
                    )
                )

        # 5. Seed Initial Telemetry Time Series if empty
        w_cur = await db.execute("SELECT COUNT(*) as count FROM weather_data")
        w_count = (await w_cur.fetchone())["count"]
        if w_count == 0:
            logger.info("Generating realistic recent weather time series (past 14 days)...")
            for p in MONITORING_PROVINCES:
                for d in range(14, 0, -1):
                    dt_str = (datetime.now(timezone.utc) - timedelta(days=d)).strftime("%Y-%m-%dT12:00:00Z")
                    rain_val = 12.0 + (d % 4) * 8.5
                    await db.execute(
                        """
                        INSERT INTO weather_data (
                            location_id, timestamp, data_type, temperature_c,
                            humidity_pct, precipitation_mm, rain_mm, wind_speed_kmh,
                            wind_direction_deg, soil_moisture, weather_code, data_source, retrieval_timestamp
                        ) VALUES (?, ?, 'observation', 29.5, 76.0, ?, ?, 11.5, 185.0, 0.35, 61, 'Open-Meteo Baseline', ?)
                        """,
                        (p["id"], dt_str, rain_val, rain_val, now_iso)
                    )

        # 6. Seed Initial River Discharge Telemetry if empty
        rd_cur = await db.execute("SELECT COUNT(*) as count FROM river_discharge")
        rd_count = (await rd_cur.fetchone())["count"]
        if rd_count == 0:
            logger.info("Generating realistic recent discharge time series (past 14 days)...")
            for p in MONITORING_PROVINCES:
                for d in range(14, 0, -1):
                    dt_str = (datetime.now(timezone.utc) - timedelta(days=d)).strftime("%Y-%m-%d")
                    disc_val = 1200.0 + (14 - d) * 65.0
                    await db.execute(
                        """
                        INSERT INTO river_discharge (
                            location_id, date, discharge_m3s, discharge_max,
                            discharge_mean, discharge_median, data_source, retrieval_timestamp
                        ) VALUES (?, ?, ?, ?, ?, ?, 'GloFAS Baseline', ?)
                        """,
                        (p["id"], dt_str, disc_val, disc_val + 200.0, disc_val, disc_val - 50.0, now_iso)
                    )

        # 7. Seed Initial Water Levels if empty
        wl_cur = await db.execute("SELECT COUNT(*) as count FROM water_levels")
        wl_count = (await wl_cur.fetchone())["count"]
        if wl_count == 0:
            logger.info("Generating realistic station water levels (past 14 days)...")
            st_cur = await db.execute("SELECT id, code FROM stations")
            st_rows = await st_cur.fetchall()
            for st in st_rows:
                base_wl = 6.8 if st["code"] == "020102" else (5.4 if st["code"] == "020106" else 9.2)
                for d in range(14, 0, -1):
                    dt_str = (datetime.now(timezone.utc) - timedelta(days=d)).strftime("%Y-%m-%dT12:00:00Z")
                    await db.execute(
                        """
                        INSERT INTO water_levels (station_id, timestamp, value, unit, data_source, retrieval_timestamp, quality_flag)
                        VALUES (?, ?, ?, 'm', 'SEED_DEMO', ?, 'demo')
                        """,
                        (st["id"], dt_str, round(base_wl + (14 - d) * 0.05, 2), now_iso)
                    )

        # 8. Seed Initial Risk Assessments & Alert
        ra_cur = await db.execute("SELECT COUNT(*) as count FROM risk_assessments")
        ra_count = (await ra_cur.fetchone())["count"]
        if ra_count == 0:
            logger.info("Seeding initial risk assessments and emergency alert...")
            for p in MONITORING_PROVINCES:
                cat = "Moderate" if p["id"] in (3, 5) else "Low"
                prob = 42.5 if cat == "Moderate" else 18.0
                await db.execute(
                    """
                    INSERT INTO risk_assessments (
                        location_id, assessment_date, prediction_horizon_days,
                        risk_probability, risk_category, model_version, model_type,
                        contributing_factors_json, confidence_info_json, created_at
                    ) VALUES (?, ?, 7, ?, ?, 'v1.2.0-tonle-calibrated', 'MultiFactorRuleEngine', ?, ?, ?)
                    """,
                    (
                        p["id"],
                        now_iso,
                        prob,
                        cat,
                        json.dumps({
                            "rainfall": {"score": 25.0, "weight": 0.25},
                            "hydrology": {"score": 35.0, "weight": 0.30},
                            "soil": {"score": 30.0, "weight": 0.15},
                            "seasonal": {"score": 40.0, "weight": 0.15},
                            "historical": {"score": p["flood_frequency_score"] * 100, "weight": 0.15}
                        }),
                        json.dumps({
                            "explanation_en": f"Standard baseline flood risk assessment for {p['name']}.",
                            "explanation_km": f"ការវាយតម្លៃហានិភ័យទឹកជំនន់កម្រិតស្តង់ដារសម្រាប់{p['name_km']}។"
                        }),
                        now_iso
                    )
                )

            # Seed an active alert for demonstration
            await db.execute(
                """
                INSERT INTO alerts (
                    alert_type, severity, title, title_km, message, message_km,
                    location_id, province, trigger_source, status, telegram_sent,
                    created_at, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, 3, 'Pursat', 'RiskAssessmentEngine', 'active', 0, ?, 'system')
                """,
                (
                    "FLOOD_EARLY_WARNING",
                    "Moderate",
                    "FLOOD ADVISORY: Heightened Water Levels in Krakor",
                    "សេចក្តីជូនដំណឹងអំពីទឹកជំនន់៖ កម្ពស់ទឹកកើនឡើងនៅស្រុកក្រគរ",
                    "Moderate flood advisory (42.5%) for Pursat Province. Inflow into Tonle Sap Lake margins is increasing.",
                    "ការជូនដំណឹងអំពីទឹកជំនន់កម្រិតមធ្យម (៤២.៥%) សម្រាប់ខេត្តពោធិ៍សាត់។ លំហូរទឹកចូលមាត់បឹងទន្លេសាបកំពុងកើនឡើង។",
                    now_iso
                )
            )

        await db.commit()
        logger.info("Database seeding successfully completed!")


if __name__ == "__main__":
    asyncio.run(seed_all())