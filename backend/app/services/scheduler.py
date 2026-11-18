"""
FloodPulse AI - Background Job Scheduler & Telemetry Ingestion Service
Orchestrates automated weather retrieval, hydrological discharge tracking,
satellite catalog scanning, risk calculations, and emergency alert sweeps.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

import aiosqlite
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.database import get_db_path
from app.services.risk_engine import risk_engine
from app.services.alert_service import alert_service

logger = logging.getLogger(__name__)

# Global AsyncIOScheduler instance
scheduler = AsyncIOScheduler()


# ==============================================================================
# Job 1: Hourly Weather Ingestion (Open-Meteo Forecast & Soil Moisture)
# ==============================================================================
async def fetch_weather_job() -> Dict[str, Any]:
    """
    Fetch current hourly meteorological metrics from Open-Meteo API for all 5 Tonle Sap locations.
    Stores real observations and forecasts into `weather_data` table.
    """
    logger.info("Executing scheduled job: fetch_weather_job...")
    db_path = get_db_path()
    records_saved = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id, name, lat, lon FROM monitoring_locations")
        locations = await cursor.fetchall()

        async with httpx.AsyncClient(timeout=15.0) as client:
            for loc in locations:
                url = (
                    f"{settings.OPEN_METEO_FORECAST_URL}"
                    f"?latitude={loc['lat']}&longitude={loc['lon']}"
                    f"&current=temperature_2m,relative_humidity_2m,precipitation,rain,weather_code,wind_speed_10m,wind_direction_10m"
                    f"&hourly=temperature_2m,precipitation,soil_moisture_0_to_7cm"
                    f"&forecast_days=3&timezone=UTC"
                )
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        data = resp.json()
                        curr = data.get("current", {})
                        hourly = data.get("hourly", {})

                        # Average topsoil moisture from first 24h
                        soil_moistures = hourly.get("soil_moisture_0_to_7cm", [])
                        avg_soil = (
                            sum(soil_moistures[:24]) / len(soil_moistures[:24])
                            if soil_moistures else 0.32
                        )

                        await db.execute(
                            """
                            INSERT INTO weather_data (
                                location_id, timestamp, data_type, temperature_c,
                                humidity_pct, precipitation_mm, rain_mm, wind_speed_kmh,
                                wind_direction_deg, soil_moisture, weather_code,
                                data_source, retrieval_timestamp
                            ) VALUES (?, ?, 'observation', ?, ?, ?, ?, ?, ?, ?, ?, 'Open-Meteo', ?)
                            """,
                            (
                                loc["id"],
                                curr.get("time", now_iso),
                                curr.get("temperature_2m", 28.0),
                                curr.get("relative_humidity_2m", 75.0),
                                curr.get("precipitation", 0.0),
                                curr.get("rain", 0.0),
                                curr.get("wind_speed_10m", 12.0),
                                curr.get("wind_direction_10m", 180.0),
                                round(avg_soil, 3),
                                curr.get("weather_code", 1),
                                now_iso
                            )
                        )
                        records_saved += 1
                    else:
                        logger.warning(f"Open-Meteo returned status {resp.status_code} for {loc['name']}")
                except Exception as e:
                    logger.error(f"Failed to fetch weather for {loc['name']}: {e}")

        # Update data_sources health
        await db.execute(
            """
            UPDATE data_sources 
            SET status = 'active', last_successful_fetch = ?, last_error = NULL 
            WHERE name LIKE '%Open-Meteo Weather%'
            """,
            (now_iso,)
        )
        await db.commit()

    logger.info(f"fetch_weather_job completed: {records_saved} locations updated.")
    return {"status": "success", "records_saved": records_saved, "timestamp": now_iso}


# ==============================================================================
# Job 2: Daily River Discharge Ingestion (Open-Meteo Flood / GloFAS)
# ==============================================================================
async def fetch_discharge_job() -> Dict[str, Any]:
    """
    Fetch GloFAS hydrological river discharge forecasts from Open-Meteo Flood API.
    Updates `river_discharge` table with daily median and max discharge.
    """
    logger.info("Executing scheduled job: fetch_discharge_job...")
    db_path = get_db_path()
    records_saved = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id, name, lat, lon FROM monitoring_locations")
        locations = await cursor.fetchall()

        async with httpx.AsyncClient(timeout=15.0) as client:
            for loc in locations:
                url = (
                    f"{settings.OPEN_METEO_FLOOD_URL}"
                    f"?latitude={loc['lat']}&longitude={loc['lon']}"
                    f"&daily=river_discharge,river_discharge_mean,river_discharge_max,river_discharge_median"
                    f"&forecast_days=7"
                )
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        data = resp.json()
                        daily = data.get("daily", {})
                        times = daily.get("time", [])
                        discharges = daily.get("river_discharge", [])
                        max_d = daily.get("river_discharge_max", [])
                        mean_d = daily.get("river_discharge_mean", [])
                        med_d = daily.get("river_discharge_median", [])

                        for i in range(min(len(times), 7)):
                            d_val = discharges[i] if i < len(discharges) else 0.0
                            m_val = max_d[i] if i < len(max_d) else d_val
                            mean_val = mean_d[i] if i < len(mean_d) else d_val
                            med_val = med_d[i] if i < len(med_d) else d_val

                            await db.execute(
                                """
                                INSERT INTO river_discharge (
                                    location_id, date, discharge_m3s, discharge_max,
                                    discharge_mean, discharge_median, data_source, retrieval_timestamp
                                ) VALUES (?, ?, ?, ?, ?, ?, 'GloFAS/Open-Meteo', ?)
                                """,
                                (loc["id"], times[i], d_val, m_val, mean_val, med_val, now_iso)
                            )
                            records_saved += 1
                    else:
                        logger.warning(f"GloFAS Flood API returned status {resp.status_code} for {loc['name']}")
                except Exception as e:
                    logger.error(f"Failed to fetch discharge for {loc['name']}: {e}")

        # Update data_sources health
        await db.execute(
            """
            UPDATE data_sources 
            SET status = 'active', last_successful_fetch = ?, last_error = NULL 
            WHERE name LIKE '%Global Flood%'
            """,
            (now_iso,)
        )
        await db.commit()

    logger.info(f"fetch_discharge_job completed: {records_saved} discharge records inserted.")
    return {"status": "success", "records_saved": records_saved, "timestamp": now_iso}


# ==============================================================================
# Job 3: Satellite STAC Catalog Query (Copernicus Sentinel-1 SAR)
# ==============================================================================
async def fetch_satellite_job() -> Dict[str, Any]:
    """
    Search Copernicus Data Space STAC endpoint for newly acquired Sentinel-1 SAR scenes
    covering the Tonle Sap basin [102.5, 12.0, 105.5, 14.0].
    """
    logger.info("Executing scheduled job: fetch_satellite_job...")
    db_path = get_db_path()
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")
    end_date = now.strftime("%Y-%m-%dT23:59:59Z")
    bbox = settings.TONLE_SAP_BBOX
    now_iso = now.isoformat()
    scenes_indexed = 0

    stac_payload = {
        "collections": [settings.COPERNICUS_COLLECTION],
        "bbox": bbox,
        "datetime": f"{start_date}/{end_date}",
        "limit": 10
    }

    async with aiosqlite.connect(db_path) as db:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(settings.COPERNICUS_STAC_URL, json=stac_payload)
                if resp.status_code == 200:
                    data = resp.json()
                    features = data.get("features", [])
                    for feat in features:
                        props = feat.get("properties", {})
                        assets = feat.get("assets", {})
                        acq_date = props.get("datetime", now_iso)
                        geom = feat.get("geometry", {})
                        orbit = props.get("sat:orbit_state", "descending")
                        instrument = props.get("sar:instrument_mode", "IW")
                        thumb = assets.get("thumbnail", {}).get("href", "")
                        stac_self = feat.get("links", [{}])[0].get("href", "")

                        await db.execute(
                            """
                            INSERT INTO satellite_acquisitions (
                                satellite, acquisition_date, collection, orbit_state,
                                instrument_mode, bbox_geojson, cloud_cover, stac_url,
                                thumbnail_url, processed, metadata_json
                            ) VALUES (?, ?, ?, ?, ?, ?, 0.0, ?, ?, 0, ?)
                            """,
                            (
                                "Sentinel-1 SAR",
                                acq_date,
                                settings.COPERNICUS_COLLECTION,
                                orbit,
                                instrument,
                                json.dumps(geom),
                                stac_self,
                                thumb,
                                json.dumps(props)
                            )
                        )
                        scenes_indexed += 1

                    await db.execute(
                        """
                        UPDATE data_sources 
                        SET status = 'active', last_successful_fetch = ?, last_error = NULL 
                        WHERE name LIKE '%Sentinel-1 STAC%'
                        """,
                        (now_iso,)
                    )
                else:
                    logger.warning(f"Copernicus STAC responded with {resp.status_code}")
        except Exception as e:
            logger.error(f"Satellite STAC query error: {e}")
            await db.execute(
                """
                UPDATE data_sources 
                SET last_error = ?, last_error_time = ? 
                WHERE name LIKE '%Sentinel-1 STAC%'
                """,
                (str(e), now_iso)
            )

        await db.commit()

    logger.info(f"fetch_satellite_job completed: {scenes_indexed} scenes cataloged.")
    return {"status": "success", "scenes_indexed": scenes_indexed, "timestamp": now_iso}


# ==============================================================================
# Job 4: Multi-Factor Risk Assessment Engine Job
# ==============================================================================
async def assess_risk_job() -> Dict[str, Any]:
    """
    Run the rule-based flood risk assessment engine for all 5 Tonle Sap locations.
    """
    logger.info("Executing scheduled job: assess_risk_job...")
    db_path = get_db_path()
    assessments_count = 0
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        results = await risk_engine.assess_all_locations(db)
        assessments_count = len(results)

    logger.info(f"assess_risk_job completed: {assessments_count} provinces assessed.")
    return {"status": "success", "assessments_computed": assessments_count}


# ==============================================================================
# Job 5: Emergency Alert Sweep & Threshold Verification
# ==============================================================================
async def check_alerts_job() -> Dict[str, Any]:
    """
    Evaluate hydrological thresholds and dispatch Telegram alerts if critical levels breached.
    """
    logger.info("Executing scheduled job: check_alerts_job...")
    db_path = get_db_path()
    new_alerts = []
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        new_alerts = await alert_service.check_thresholds(db)

    logger.info(f"check_alerts_job completed: {len(new_alerts)} new alerts triggered.")
    return {"status": "success", "alerts_triggered": len(new_alerts)}


# ==============================================================================
# Scheduler Setup & Lifecycle Management
# ==============================================================================
def setup_scheduler(app=None) -> AsyncIOScheduler:
    """
    Configure and register all periodic telemetry and modeling jobs with APScheduler.
    """
    if not settings.SCHEDULER_ENABLED:
        logger.info("Scheduler is disabled via configuration.")
        return scheduler

    # 1. Weather fetch: Every 60 minutes
    scheduler.add_job(
        fetch_weather_job,
        trigger=IntervalTrigger(minutes=settings.WEATHER_REFRESH_INTERVAL_MINUTES),
        id="fetch_weather_job",
        name="Hourly Open-Meteo Weather Ingestion",
        replace_existing=True
    )

    # 2. Discharge fetch: Every 24 hours (or configurable hours)
    scheduler.add_job(
        fetch_discharge_job,
        trigger=IntervalTrigger(hours=max(settings.DISCHARGE_REFRESH_INTERVAL_HOURS, 6)),
        id="fetch_discharge_job",
        name="GloFAS Hydrological Discharge Forecast",
        replace_existing=True
    )

    # 3. Satellite STAC check: Every 6 hours
    scheduler.add_job(
        fetch_satellite_job,
        trigger=IntervalTrigger(hours=6),
        id="fetch_satellite_job",
        name="Sentinel-1 SAR STAC Catalog Discovery",
        replace_existing=True
    )

    # 4. Risk assessment: Every 3 hours
    scheduler.add_job(
        assess_risk_job,
        trigger=IntervalTrigger(hours=3),
        id="assess_risk_job",
        name="Tonle Sap Basin Flood Risk Computation",
        replace_existing=True
    )

    # 5. Alert threshold check: Every 30 minutes
    scheduler.add_job(
        check_alerts_job,
        trigger=IntervalTrigger(minutes=30),
        id="check_alerts_job",
        name="Hydrological Threshold & Emergency Alert Monitor",
        replace_existing=True
    )

    try:
        if not scheduler.running:
            scheduler.start()
            logger.info("APScheduler background engine started successfully.")
    except Exception as e:
        logger.error(f"Error starting scheduler: {e}")

    return scheduler
