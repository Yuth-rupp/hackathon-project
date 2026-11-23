"""
FloodPulse AI - Background Job Scheduler & Telemetry Ingestion Service

Orchestrates automated weather retrieval, hydrological discharge tracking,
satellite catalog scanning, risk calculations, and emergency alert sweeps.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

import aiosqlite
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.database import get_db_path
from app.services.risk_engine import risk_engine
from app.services.alert_service import alert_service
from app.services.realtime import broker
from app.services.satellite_catalog import parse_stac_feature, store_scene

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


# ==============================================================================
# Job 1: Hourly Weather Ingestion
# ==============================================================================

async def fetch_weather_job() -> Dict[str, Any]:
    """
    Fetch weather data from Open-Meteo for all monitoring locations.
    """
    logger.info("Executing scheduled job: fetch_weather_job...")

    db_path = get_db_path()
    records_saved = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            "SELECT id, name, lat, lon FROM monitoring_locations"
        )
        locations = await cursor.fetchall()

        async with httpx.AsyncClient(timeout=15.0) as client:
            for loc in locations:
                url = (
                    f"{settings.OPEN_METEO_FORECAST_URL}"
                    f"?latitude={loc['lat']}&longitude={loc['lon']}"
                    "&current=temperature_2m,relative_humidity_2m,"
                    "precipitation,rain,weather_code,wind_speed_10m,"
                    "wind_direction_10m"
                    "&hourly=temperature_2m,precipitation,"
                    "soil_moisture_0_to_7cm"
                    "&forecast_days=3&timezone=UTC"
                )

                try:
                    resp = await client.get(url)

                    if resp.status_code != 200:
                        logger.warning(
                            "Open-Meteo returned status %s for %s",
                            resp.status_code,
                            loc["name"],
                        )
                        continue

                    data = resp.json()
                    curr = data.get("current", {})
                    hourly = data.get("hourly", {})

                    soil_moistures = hourly.get(
                        "soil_moisture_0_to_7cm", []
                    )[:24]

                    avg_soil = (
                        sum(v for v in soil_moistures if v is not None)
                        / len([v for v in soil_moistures if v is not None])
                        if any(v is not None for v in soil_moistures)
                        else None
                    )

                    await db.execute(
                        """
                        INSERT INTO weather_data (
                            location_id,
                            timestamp,
                            data_type,
                            temperature_c,
                            humidity_pct,
                            precipitation_mm,
                            rain_mm,
                            wind_speed_kmh,
                            wind_direction_deg,
                            soil_moisture,
                            weather_code,
                            data_source,
                            retrieval_timestamp
                        )
                        VALUES (?, ?, 'observation', ?, ?, ?, ?, ?, ?, ?, ?, 'Open-Meteo', ?)
                        """,
                        (
                            loc["id"],
                            curr.get("time", now_iso),
                            curr.get("temperature_2m"),
                            curr.get("relative_humidity_2m"),
                            curr.get("precipitation"),
                            curr.get("rain"),
                            curr.get("wind_speed_10m"),
                            curr.get("wind_direction_10m"),
                            round(avg_soil, 3) if avg_soil is not None else None,
                            curr.get("weather_code"),
                            now_iso,
                        ),
                    )

                    records_saved += 1

                except Exception as exc:
                    logger.exception(
                        "Failed to fetch weather for %s: %s",
                        loc["name"],
                        exc,
                    )

        await db.execute(
            """
            UPDATE data_sources
            SET status = 'active',
                last_successful_fetch = ?,
                last_error = NULL
            WHERE name LIKE '%Open-Meteo Weather%'
            """,
            (now_iso,),
        )

        await db.commit()

    logger.info(
        "fetch_weather_job completed: %s locations updated.",
        records_saved,
    )

    return {
        "status": "success",
        "records_saved": records_saved,
        "timestamp": now_iso,
    }


# ==============================================================================
# Job 2: Daily River Discharge Ingestion
# ==============================================================================

async def fetch_discharge_job() -> Dict[str, Any]:
    """
    Fetch GloFAS discharge forecasts for all monitoring locations.

    Duplicate prevention:
    Before inserting a new forecast for a location/date, delete the
    previous record from this scheduler's own data source.

    Missing values remain NULL instead of being converted to zero.
    """
    logger.info("Executing scheduled job: fetch_discharge_job...")

    db_path = get_db_path()
    records_saved = 0
    locations_processed = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            "SELECT id, name, lat, lon FROM monitoring_locations"
        )
        locations = await cursor.fetchall()

        async with httpx.AsyncClient(timeout=20.0) as client:
            for loc in locations:
                url = (
                    f"{settings.OPEN_METEO_FLOOD_URL}"
                    f"?latitude={loc['lat']}"
                    f"&longitude={loc['lon']}"
                    "&daily=river_discharge,"
                    "river_discharge_mean,"
                    "river_discharge_max,"
                    "river_discharge_median"
                    "&forecast_days=14"
                )

                try:
                    response = await client.get(url)

                    if response.status_code != 200:
                        logger.warning(
                            "GloFAS API returned status %s for %s",
                            response.status_code,
                            loc["name"],
                        )
                        continue

                    data = response.json()
                    daily = data.get("daily", {})

                    dates = daily.get("time", [])
                    discharges = daily.get("river_discharge", [])
                    max_values = daily.get("river_discharge_max", [])
                    mean_values = daily.get("river_discharge_mean", [])
                    median_values = daily.get("river_discharge_median", [])

                    if not dates:
                        logger.warning(
                            "No discharge forecast dates returned for %s",
                            loc["name"],
                        )
                        continue

                    location_records = 0

                    for index, forecast_date in enumerate(dates):

                        def get_value(values, position):
                            if position >= len(values):
                                return None

                            value = values[position]

                            if value is None:
                                return None

                            try:
                                return float(value)
                            except (TypeError, ValueError):
                                return None

                        discharge_value = get_value(
                            discharges, index
                        )
                        max_value = get_value(
                            max_values, index
                        )
                        mean_value = get_value(
                            mean_values, index
                        )
                        median_value = get_value(
                            median_values, index
                        )

                        # Replace only this scheduler's previous record.
                        # Other sources such as "Open-Meteo Flood" and
                        # "GloFAS Baseline" are retained.
                        await db.execute(
                            """
                            DELETE FROM river_discharge
                            WHERE location_id = ?
                              AND date = ?
                              AND data_source = 'GloFAS/Open-Meteo'
                            """,
                            (
                                loc["id"],
                                forecast_date,
                            ),
                        )

                        await db.execute(
                            """
                            INSERT INTO river_discharge (
                                location_id,
                                date,
                                discharge_m3s,
                                discharge_max,
                                discharge_mean,
                                discharge_median,
                                data_source,
                                retrieval_timestamp
                            )
                            VALUES (?, ?, ?, ?, ?, ?, 'GloFAS/Open-Meteo', ?)
                            """,
                            (
                                loc["id"],
                                forecast_date,
                                discharge_value,
                                max_value,
                                mean_value,
                                median_value,
                                now_iso,
                            ),
                        )

                        location_records += 1
                        records_saved += 1

                    locations_processed += 1

                    logger.info(
                        "Saved %s discharge forecast records for %s",
                        location_records,
                        loc["name"],
                    )

                except Exception as exc:
                    logger.exception(
                        "Failed to fetch discharge for %s: %s",
                        loc["name"],
                        exc,
                    )

        if locations_processed > 0:
            await db.execute(
                """
                UPDATE data_sources
                SET status = 'active',
                    last_successful_fetch = ?,
                    last_error = NULL
                WHERE name LIKE '%Global Flood%'
                """,
                (now_iso,),
            )

        await db.commit()

    logger.info(
        "fetch_discharge_job completed: %s records saved across %s locations.",
        records_saved,
        locations_processed,
    )

    if locations_processed > 0:
        broker.publish(
            "discharge_updated",
            {
                "locations_processed": locations_processed,
                "records_saved": records_saved,
            },
        )

    return {
        "status": "success",
        "records_saved": records_saved,
        "locations_processed": locations_processed,
        "timestamp": now_iso,
    }


# ==============================================================================
# Job 2b: Gauge (water level) polling
# ==============================================================================

async def fetch_gauge_job() -> Dict[str, Any]:
    """
    Poll the Mekong River Commission feed for new gauge readings and push a
    real-time event to connected browsers.

    Needs MRC_API_TOKEN. Without a token nothing is stored (no invented
    values); gauges can still be fed through POST /hydrology/telemetry.
    """
    from app.connectors.mrc import MRCConnector

    if not settings.MRC_API_TOKEN:
        logger.info("fetch_gauge_job skipped: MRC_API_TOKEN is not set.")
        return {"status": "skipped", "reason": "no_mrc_token"}

    connector = MRCConnector()
    stations_updated = 0
    new_readings = 0

    for code in connector.get_supported_stations():
        try:
            # The connector validates, de-duplicates, stores and broadcasts
            # ("station_reading" SSE events) the readings itself.
            result = await connector.fetch_station_readings(code)
            stored = int(result.get("stored") or 0)

            if stored:
                stations_updated += 1
                new_readings += stored
        except Exception as exc:
            logger.exception("Gauge fetch failed for %s: %s", code, exc)

    logger.info(
        "fetch_gauge_job completed: %s new readings across %s stations.",
        new_readings,
        stations_updated,
    )

    return {
        "status": "success",
        "stations_updated": stations_updated,
        "new_readings": new_readings,
    }


# ==============================================================================
# Job 3: Satellite STAC Catalog Query
# ==============================================================================

async def fetch_satellite_job() -> Dict[str, Any]:
    """
    Search live STAC catalogs for Sentinel-1 SAR scenes covering the Tonle Sap basin.
    Stores only scenes that are not already in the database and records the real result
    of the check (success time or error) so the dashboard can show true update times.
    """
    logger.info("Executing scheduled job: fetch_satellite_job...")

    db_path = get_db_path()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    start_date = (now - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")
    end_date = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    stac_payload = {
        "bbox": settings.TONLE_SAP_BBOX,
        "datetime": f"{start_date}/{end_date}",
        "limit": 20,
        "sortby": [{"field": "properties.datetime", "direction": "desc"}],
    }

    scenes_seen = 0
    scenes_indexed = 0
    error_text = None

    async with aiosqlite.connect(db_path) as db:
        try:
            from app.routers.satellite import _query_stac  # multi-provider, retries, real errors
            features, _provider, used_collection = await _query_stac(stac_payload)

            for feature in features:
                scene = parse_stac_feature(feature, used_collection)
                if not scene:
                    continue
                scenes_seen += 1
                if await store_scene(db, scene):
                    scenes_indexed += 1

            await db.execute(
                """
                UPDATE data_sources
                SET status = 'active', last_successful_fetch = ?, last_error = NULL
                WHERE name LIKE '%Sentinel-1 STAC%'
                """,
                (now_iso,),
            )

        except Exception as exc:
            error_text = str(exc)
            logger.exception("Satellite STAC query error: %s", exc)
            await db.execute(
                """
                UPDATE data_sources
                SET last_error = ?, last_error_time = ?
                WHERE name LIKE '%Sentinel-1 STAC%'
                """,
                (error_text[:300], now_iso),
            )

        await db.commit()

    logger.info(
        "fetch_satellite_job completed: %s scenes seen, %s new.", scenes_seen, scenes_indexed
    )

    return {
        "status": "error" if error_text else "success",
        "scenes_seen": scenes_seen,
        "scenes_indexed": scenes_indexed,
        "timestamp": now_iso,
    }


# ==============================================================================
# Job 4: Multi-Factor Risk Assessment
# ==============================================================================

async def assess_risk_job() -> Dict[str, Any]:
    """
    Run the flood risk assessment engine for all monitoring locations.
    """
    logger.info("Executing scheduled job: assess_risk_job...")

    db_path = get_db_path()

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        results = await risk_engine.assess_all_locations(db)
        assessments_count = len(results)

    logger.info(
        "assess_risk_job completed: %s locations assessed.",
        assessments_count,
    )

    return {
        "status": "success",
        "assessments_computed": assessments_count,
    }


# ==============================================================================
# Job 5: Emergency Alert Sweep
# ==============================================================================

async def check_alerts_job() -> Dict[str, Any]:
    """
    Evaluate hydrological thresholds and dispatch emergency alerts.
    """
    logger.info("Executing scheduled job: check_alerts_job...")

    db_path = get_db_path()

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        new_alerts = await alert_service.check_thresholds(db)

    logger.info(
        "check_alerts_job completed: %s new alerts triggered.",
        len(new_alerts),
    )

    return {
        "status": "success",
        "alerts_triggered": len(new_alerts),
    }


# ==============================================================================
# Scheduler Setup & Lifecycle
# ==============================================================================

def setup_scheduler(app=None) -> AsyncIOScheduler:
    """
    Configure and register all periodic background jobs.
    """
    if not settings.SCHEDULER_ENABLED:
        logger.info("Scheduler is disabled via configuration.")
        return scheduler

    scheduler.add_job(
        fetch_weather_job,
        trigger=IntervalTrigger(
            minutes=settings.WEATHER_REFRESH_INTERVAL_MINUTES
        ),
        id="fetch_weather_job",
        name="Hourly Open-Meteo Weather Ingestion",
        replace_existing=True,
    )

    scheduler.add_job(
        fetch_discharge_job,
        trigger=IntervalTrigger(
            hours=max(
                settings.DISCHARGE_REFRESH_INTERVAL_HOURS,
                6,
            )
        ),
        id="fetch_discharge_job",
        name="GloFAS Hydrological Discharge Forecast",
        replace_existing=True,
    )

    scheduler.add_job(
        fetch_gauge_job,
        trigger=IntervalTrigger(
            minutes=settings.GAUGE_REFRESH_INTERVAL_MINUTES
        ),
        id="fetch_gauge_job",
        name="MRC Gauge Water-Level Polling",
        replace_existing=True,
    )

    scheduler.add_job(
        fetch_satellite_job,
        trigger=IntervalTrigger(minutes=settings.SATELLITE_CATALOG_CHECK_MINUTES),
        id="fetch_satellite_job",
        name="Sentinel-1 SAR STAC Catalog Discovery",
        replace_existing=True,
    )

    scheduler.add_job(
        assess_risk_job,
        trigger=IntervalTrigger(hours=3),
        id="assess_risk_job",
        name="Tonle Sap Basin Flood Risk Computation",
        replace_existing=True,
    )

    scheduler.add_job(
        check_alerts_job,
        trigger=IntervalTrigger(minutes=30),
        id="check_alerts_job",
        name="Hydrological Threshold & Emergency Alert Monitor",
        replace_existing=True,
    )

    try:
        if not scheduler.running:
            scheduler.start()
            logger.info(
                "APScheduler background engine started successfully."
            )
    except Exception as exc:
        logger.exception("Error starting scheduler: %s", exc)

    return scheduler