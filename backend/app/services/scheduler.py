"""
FloodPulse AI - Background Job Scheduler & Telemetry Ingestion Service

Orchestrates automated weather retrieval, hydrological discharge tracking,
observed gauge polling, satellite catalog scanning, risk calculations, and
emergency alert sweeps.

Design rules for a trustworthy "real-time" system:
  * A source is marked 'active' ONLY when data was actually retrieved.
  * Every failure is written to data_sources (status + last_error).
  * Jobs run once shortly after startup, not only after a full interval.
  * New data triggers a risk + alert sweep within seconds (event-driven),
    the periodic jobs are only a safety net.
  * River discharge is compared against a real historical (1991-2020)
    same-season climatology, never against the forecast's own statistics.
"""

import asyncio
import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

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

scheduler = AsyncIOScheduler(
    job_defaults={
        "coalesce": True,          # collapse missed runs into one
        "max_instances": 1,        # never run the same job twice in parallel
        "misfire_grace_time": 300,
    }
)


# ==============================================================================
# Shared helpers
# ==============================================================================

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _mark_source(
    name_like: str,
    ok: bool,
    error: Optional[str] = None,
    status: Optional[str] = None,
    db: Optional[aiosqlite.Connection] = None,
) -> None:
    """
    Record the REAL outcome of a job in the data_sources audit table.
    ok=True  -> status 'active', last_successful_fetch = now, error cleared.
    ok=False -> status 'error' (or a custom status), last_error/time recorded.
    If no connection is passed, a short-lived one is opened and committed.
    """
    if db is None:
        try:
            async with aiosqlite.connect(get_db_path()) as own:
                await _mark_source(name_like, ok, error, status, db=own)
                await own.commit()
        except Exception as exc:
            logger.warning("Could not update data_sources for %s: %s", name_like, exc)
        return

    now_iso = _utc_now().isoformat()
    try:
        if ok:
            await db.execute(
                """
                UPDATE data_sources
                SET status = 'active', last_successful_fetch = ?, last_error = NULL
                WHERE name LIKE ?
                """,
                (now_iso, name_like),
            )
        else:
            await db.execute(
                """
                UPDATE data_sources
                SET status = ?, last_error = ?, last_error_time = ?
                WHERE name LIKE ?
                """,
                (status or "error", (error or "Unspecified error")[:300], now_iso, name_like),
            )
    except Exception as exc:
        logger.warning("Could not update data_sources for %s: %s", name_like, exc)


def _job_status(ok_count: int, failure_count: int) -> str:
    if ok_count > 0 and failure_count == 0:
        return "success"
    if ok_count > 0:
        return "partial"
    return "error"


def _to_float(values: List[Any], position: int) -> Optional[float]:
    """Safe float conversion. Missing values stay None (never converted to 0)."""
    if position >= len(values):
        return None
    value = values[position]
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def _followup_job() -> None:
    """Event-driven sweep: runs right after new data arrives."""
    await assess_risk_job()
    await check_alerts_job()


def _schedule_followups(reason: str) -> None:
    """
    Queue ONE risk + alert sweep a few seconds from now. Using a fixed job id
    with replace_existing debounces bursts (e.g. weather + discharge finishing
    together) into a single sweep.
    """
    if not scheduler.running:
        return
    try:
        scheduler.add_job(
            _followup_job,
            trigger="date",
            run_date=_utc_now() + timedelta(seconds=5),
            id="followup_risk_alerts",
            name=f"Follow-up risk & alert sweep ({reason})",
            replace_existing=True,
        )
    except Exception as exc:
        logger.warning("Could not schedule follow-up sweep: %s", exc)


# ==============================================================================
# Job 1: Weather Ingestion (Open-Meteo "current" conditions, 15-min resolution)
# ==============================================================================

async def fetch_weather_job() -> Dict[str, Any]:
    """
    Fetch weather data from Open-Meteo for all monitoring locations.
    Only stores a row when Open-Meteo reports a NEW 'current' timestamp, so the
    table holds one row per real update instead of one per poll.
    """
    logger.info("Executing scheduled job: fetch_weather_job...")

    db_path = get_db_path()
    now_iso = _utc_now().isoformat()
    new_records = 0
    unchanged = 0
    failures: List[str] = []

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
                        failures.append(f"{loc['name']}: HTTP {resp.status_code}")
                        logger.warning(
                            "Open-Meteo returned status %s for %s",
                            resp.status_code,
                            loc["name"],
                        )
                        continue

                    data = resp.json()
                    curr = data.get("current") or {}
                    hourly = data.get("hourly") or {}

                    if not curr:
                        failures.append(f"{loc['name']}: no 'current' block returned")
                        continue

                    observed_at = curr.get("time") or now_iso

                    # Skip if this exact observation time is already stored.
                    existing = await db.execute(
                        """
                        SELECT 1 FROM weather_data
                        WHERE location_id = ? AND timestamp = ?
                          AND data_type = 'observation'
                        LIMIT 1
                        """,
                        (loc["id"], observed_at),
                    )
                    if await existing.fetchone():
                        unchanged += 1
                        continue

                    soil_values = [
                        v for v in (hourly.get("soil_moisture_0_to_7cm") or [])[:24]
                        if v is not None
                    ]
                    avg_soil = sum(soil_values) / len(soil_values) if soil_values else None

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
                            observed_at,
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
                    new_records += 1

                except Exception as exc:
                    failures.append(f"{loc['name']}: {exc}")
                    logger.exception("Failed to fetch weather for %s: %s", loc["name"], exc)

        reached_api = new_records + unchanged
        if reached_api > 0:
            await _mark_source("%Open-Meteo Weather%", ok=True, db=db)
        else:
            await _mark_source(
                "%Open-Meteo Weather%",
                ok=False,
                error="; ".join(failures) or "No weather data returned",
                db=db,
            )

        await db.commit()

    logger.info(
        "fetch_weather_job completed: %s new, %s unchanged, %s failed.",
        new_records, unchanged, len(failures),
    )

    if new_records > 0:
        broker.publish(
            "weather_updated",
            {"new_records": new_records, "timestamp": now_iso},
        )
        _schedule_followups("weather")

    return {
        "status": _job_status(new_records + unchanged, len(failures)),
        "records_saved": new_records,
        "unchanged": unchanged,
        "failed": failures,
        "timestamp": now_iso,
    }


# ==============================================================================
# Job 2: River Discharge Ingestion (GloFAS forecast via Open-Meteo)
# ==============================================================================

async def fetch_discharge_job() -> Dict[str, Any]:
    """
    Fetch GloFAS discharge forecasts for all monitoring locations.

    NOTE: river_discharge_mean / _median / _max are ENSEMBLE statistics of the
    forecast itself, not a historical baseline. Do not use them as the
    "reference" for anomaly detection - use discharge_climatology instead
    (see refresh_discharge_climatology_job / classify_discharge).

    Duplicate prevention: the previous record for the same location/date from
    this scheduler's own data source is replaced. Other sources such as
    "Open-Meteo Flood" and "GloFAS Baseline" are retained.
    A location whose response contains no discharge values at all is skipped,
    so good stored rows are never overwritten with NULLs.
    """
    logger.info("Executing scheduled job: fetch_discharge_job...")

    db_path = get_db_path()
    records_saved = 0
    locations_processed = 0
    failures: List[str] = []
    now_iso = _utc_now().isoformat()

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
                        failures.append(f"{loc['name']}: HTTP {response.status_code}")
                        logger.warning(
                            "GloFAS API returned status %s for %s",
                            response.status_code, loc["name"],
                        )
                        continue

                    daily = response.json().get("daily") or {}
                    dates = daily.get("time", [])
                    discharges = daily.get("river_discharge", [])
                    max_values = daily.get("river_discharge_max", [])
                    mean_values = daily.get("river_discharge_mean", [])
                    median_values = daily.get("river_discharge_median", [])

                    if not dates:
                        failures.append(f"{loc['name']}: no forecast dates returned")
                        continue

                    if all(v is None for v in discharges):
                        failures.append(f"{loc['name']}: response had no discharge values")
                        continue

                    location_records = 0
                    for index, forecast_date in enumerate(dates):
                        await db.execute(
                            """
                            DELETE FROM river_discharge
                            WHERE location_id = ?
                              AND date = ?
                              AND data_source = 'GloFAS/Open-Meteo'
                            """,
                            (loc["id"], forecast_date),
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
                                _to_float(discharges, index),
                                _to_float(max_values, index),
                                _to_float(mean_values, index),
                                _to_float(median_values, index),
                                now_iso,
                            ),
                        )
                        location_records += 1

                    # Commit per location so one bad location can't lose the rest.
                    await db.commit()
                    records_saved += location_records
                    locations_processed += 1
                    logger.info(
                        "Saved %s discharge forecast records for %s",
                        location_records, loc["name"],
                    )

                except Exception as exc:
                    await db.rollback()
                    failures.append(f"{loc['name']}: {exc}")
                    logger.exception("Failed to fetch discharge for %s: %s", loc["name"], exc)

        if locations_processed > 0:
            await _mark_source("%Global Flood%", ok=True, db=db)
        else:
            await _mark_source(
                "%Global Flood%",
                ok=False,
                error="; ".join(failures) or "No discharge data returned",
                db=db,
            )
        await db.commit()

    logger.info(
        "fetch_discharge_job completed: %s records saved across %s locations (%s failed).",
        records_saved, locations_processed, len(failures),
    )

    if locations_processed > 0:
        broker.publish(
            "discharge_updated",
            {
                "locations_processed": locations_processed,
                "records_saved": records_saved,
                "timestamp": now_iso,
            },
        )
        _schedule_followups("discharge")

    return {
        "status": _job_status(locations_processed, len(failures)),
        "records_saved": records_saved,
        "locations_processed": locations_processed,
        "failed": failures,
        "timestamp": now_iso,
    }


# ==============================================================================
# Job 2a: Historical discharge climatology (the real "reference" baseline)
# ==============================================================================

CLIMATOLOGY_START = "1991-01-01"   # standard 30-year climatological normal
CLIMATOLOGY_END = "2020-12-31"
CLIMATOLOGY_WINDOW_DAYS = 7        # +/- days around each day-of-year
CLIMATOLOGY_MIN_SAMPLES = 30
CLIMATOLOGY_REFRESH_DAYS = 30


def _percentile(sorted_values: List[float], q: float) -> float:
    """Linear-interpolated percentile of an already sorted list (0 <= q <= 1)."""
    position = (len(sorted_values) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (position - lower)


def build_climatology(
    dates: List[str],
    values: List[Optional[float]],
    window: int = CLIMATOLOGY_WINDOW_DAYS,
) -> Dict[int, Dict[str, float]]:
    """
    Turn a long daily series into per-day-of-year statistics, pooling +/- `window`
    days (wrapping around the year) so each day has enough samples.
    """
    by_doy: Dict[int, List[float]] = {d: [] for d in range(1, 367)}
    for date_str, value in zip(dates, values):
        if value is None:
            continue
        try:
            doy = date.fromisoformat(date_str).timetuple().tm_yday
        except ValueError:
            continue
        by_doy[doy].append(float(value))

    result: Dict[int, Dict[str, float]] = {}
    for doy in range(1, 367):
        pool: List[float] = []
        for offset in range(-window, window + 1):
            neighbour = ((doy - 1 + offset) % 366) + 1
            pool.extend(by_doy[neighbour])
        if len(pool) < CLIMATOLOGY_MIN_SAMPLES:
            continue
        pool.sort()
        result[doy] = {
            "mean": sum(pool) / len(pool),
            "median": _percentile(pool, 0.50),
            "p25": _percentile(pool, 0.25),
            "p75": _percentile(pool, 0.75),
            "p90": _percentile(pool, 0.90),
            "samples": float(len(pool)),
        }
    return result


async def refresh_discharge_climatology_job(force: bool = False) -> Dict[str, Any]:
    """
    Build per-location, per-day-of-year discharge statistics from the 1991-2020
    GloFAS archive. Skips locations computed in the last 30 days unless force=True.

    Caveat: the archive is GloFAS reanalysis and the live values are a forecast
    model, so small systematic differences are possible. Treat the comparison as
    "relative to the usual range for this time of year", not as an exact anomaly.
    """
    logger.info("Executing scheduled job: refresh_discharge_climatology_job...")

    db_path = get_db_path()
    now = _utc_now()
    computed = 0
    skipped = 0
    failures: List[str] = []

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS discharge_climatology (
                location_id  INTEGER NOT NULL,
                day_of_year  INTEGER NOT NULL,
                mean_m3s     REAL,
                median_m3s   REAL,
                p25_m3s      REAL,
                p75_m3s      REAL,
                p90_m3s      REAL,
                samples      INTEGER,
                period       TEXT,
                computed_at  TEXT,
                PRIMARY KEY (location_id, day_of_year)
            )
            """
        )

        cursor = await db.execute("SELECT id, name, lat, lon FROM monitoring_locations")
        locations = await cursor.fetchall()

        async with httpx.AsyncClient(timeout=60.0) as client:
            for loc in locations:
                if not force:
                    last_cur = await db.execute(
                        "SELECT MAX(computed_at) AS last FROM discharge_climatology WHERE location_id = ?",
                        (loc["id"],),
                    )
                    last_row = await last_cur.fetchone()
                    if last_row and last_row["last"]:
                        try:
                            last_dt = datetime.fromisoformat(last_row["last"])
                            if last_dt.tzinfo is None:
                                last_dt = last_dt.replace(tzinfo=timezone.utc)
                            if now - last_dt < timedelta(days=CLIMATOLOGY_REFRESH_DAYS):
                                skipped += 1
                                continue
                        except ValueError:
                            pass  # unreadable timestamp -> recompute

                url = (
                    f"{settings.OPEN_METEO_FLOOD_URL}"
                    f"?latitude={loc['lat']}&longitude={loc['lon']}"
                    "&daily=river_discharge"
                    f"&start_date={CLIMATOLOGY_START}&end_date={CLIMATOLOGY_END}"
                )

                try:
                    response = await client.get(url)
                    if response.status_code != 200:
                        failures.append(f"{loc['name']}: HTTP {response.status_code}")
                        continue

                    daily = response.json().get("daily") or {}
                    dates = daily.get("time", [])
                    values = daily.get("river_discharge", [])
                    clim = build_climatology(dates, values)

                    if not clim:
                        failures.append(f"{loc['name']}: not enough historical data")
                        continue

                    period = f"{CLIMATOLOGY_START[:4]}-{CLIMATOLOGY_END[:4]}"
                    computed_at = now.isoformat()
                    rows = [
                        (
                            loc["id"], doy, s["mean"], s["median"],
                            s["p25"], s["p75"], s["p90"], int(s["samples"]),
                            period, computed_at,
                        )
                        for doy, s in clim.items()
                    ]
                    await db.execute(
                        "DELETE FROM discharge_climatology WHERE location_id = ?",
                        (loc["id"],),
                    )
                    await db.executemany(
                        """
                        INSERT INTO discharge_climatology (
                            location_id, day_of_year, mean_m3s, median_m3s,
                            p25_m3s, p75_m3s, p90_m3s, samples, period, computed_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        rows,
                    )
                    await db.commit()
                    computed += 1
                    logger.info("Climatology stored for %s (%s days)", loc["name"], len(rows))

                except Exception as exc:
                    await db.rollback()
                    failures.append(f"{loc['name']}: {exc}")
                    logger.exception("Climatology failed for %s: %s", loc["name"], exc)

                await asyncio.sleep(0.5)  # be polite to the free API

    return {
        "status": _job_status(computed + skipped, len(failures)),
        "locations_computed": computed,
        "locations_skipped": skipped,
        "failed": failures,
    }


async def get_climatology(
    db: aiosqlite.Connection, location_id: int, on_date: str
) -> Optional[Dict[str, float]]:
    """Climatology row for a location and an ISO date (YYYY-MM-DD), or None."""
    try:
        doy = date.fromisoformat(on_date[:10]).timetuple().tm_yday
    except ValueError:
        return None
    try:
        cur = await db.execute(
            """
            SELECT mean_m3s, median_m3s, p25_m3s, p75_m3s, p90_m3s, samples
            FROM discharge_climatology
            WHERE location_id = ? AND day_of_year = ?
            """,
            (location_id, doy),
        )
    except Exception:
        return None  # table not created yet
    row = await cur.fetchone()
    if not row:
        return None
    return {
        "mean": row[0], "median": row[1], "p25": row[2],
        "p75": row[3], "p90": row[4], "samples": row[5],
    }


def classify_discharge(
    value: Optional[float], clim: Optional[Dict[str, float]]
) -> Dict[str, Any]:
    """
    Compare a discharge value with the same-season historical range.
    Returns UNKNOWN (never a fake NORMAL) when there is no value or baseline.
    """
    if value is None:
        return {"classification": "UNKNOWN", "pct_vs_mean": None, "basis": "no_value"}
    if not clim or clim.get("mean") is None:
        return {"classification": "UNKNOWN", "pct_vs_mean": None, "basis": "no_climatology"}

    mean = clim["mean"]
    pct = round((value - mean) / mean * 100, 1) if mean else None

    if value < clim["p25"]:
        label = "LOW"
    elif value <= clim["p75"]:
        label = "NORMAL"
    elif value <= clim["p90"]:
        label = "ELEVATED"
    else:
        label = "HIGH"

    return {
        "classification": label,
        "pct_vs_mean": pct,
        "reference_mean": round(mean, 3),
        "basis": f"{CLIMATOLOGY_START[:4]}-{CLIMATOLOGY_END[:4]} same-season climatology",
    }


# ==============================================================================
# Job 2b: Gauge (water level) polling - the only OBSERVED hydrology source
# ==============================================================================

async def fetch_gauge_job() -> Dict[str, Any]:
    """
    Poll the Mekong River Commission feed for new gauge readings and push a
    real-time event to connected browsers.

    Needs MRC_API_TOKEN. Without a token nothing is stored (no invented
    values) and the source is marked 'not_configured' so the dashboard can say
    plainly that no observed gauge data is being ingested. Gauges can still be
    fed through POST /hydrology/telemetry.
    """
    from app.connectors.mrc import MRCConnector

    if not settings.MRC_API_TOKEN:
        logger.info("fetch_gauge_job skipped: MRC_API_TOKEN is not set.")
        await _mark_source(
            "%MRC%",
            ok=False,
            status="not_configured",
            error="MRC_API_TOKEN not set - no observed gauge data is being ingested",
        )
        return {"status": "skipped", "reason": "no_mrc_token"}

    connector = MRCConnector()
    stations_updated = 0
    stations_ok = 0
    new_readings = 0
    failures: List[str] = []

    for code in connector.get_supported_stations():
        try:
            # The connector validates, de-duplicates, stores and broadcasts
            # ("station_reading" SSE events) the readings itself.
            result = await connector.fetch_station_readings(code)
            stations_ok += 1
            stored = int(result.get("stored") or 0)

            if stored:
                stations_updated += 1
                new_readings += stored
        except Exception as exc:
            failures.append(f"{code}: {exc}")
            logger.exception("Gauge fetch failed for %s: %s", code, exc)

    if stations_ok > 0:
        await _mark_source("%MRC%", ok=True)
    else:
        await _mark_source("%MRC%", ok=False, error="; ".join(failures) or "No stations reachable")

    logger.info(
        "fetch_gauge_job completed: %s new readings across %s stations (%s failed).",
        new_readings, stations_updated, len(failures),
    )

    if new_readings > 0:
        _schedule_followups("gauge")

    return {
        "status": _job_status(stations_ok, len(failures)),
        "stations_updated": stations_updated,
        "new_readings": new_readings,
        "failed": failures,
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
    now = _utc_now()
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

            await _mark_source("%Sentinel-1 STAC%", ok=True, db=db)

        except Exception as exc:
            error_text = str(exc)
            logger.exception("Satellite STAC query error: %s", exc)
            await _mark_source("%Sentinel-1 STAC%", ok=False, error=error_text, db=db)

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
    Runs every few hours as a safety net AND seconds after any new data arrives.
    """
    logger.info("Executing scheduled job: assess_risk_job...")

    db_path = get_db_path()

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        results = await risk_engine.assess_all_locations(db)
        assessments_count = len(results)

    logger.info("assess_risk_job completed: %s locations assessed.", assessments_count)

    broker.publish(
        "risk_updated",
        {"assessments_computed": assessments_count, "timestamp": _utc_now().isoformat()},
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

    logger.info("check_alerts_job completed: %s new alerts triggered.", len(new_alerts))

    if new_alerts:
        broker.publish(
            "alerts_updated",
            {"new_alerts": len(new_alerts), "timestamp": _utc_now().isoformat()},
        )

    return {
        "status": "success",
        "alerts_triggered": len(new_alerts),
    }


# ==============================================================================
# Scheduler Setup & Lifecycle
# ==============================================================================

def _startup(offset_seconds: int) -> Dict[str, Any]:
    """
    kwargs that make a job run once shortly after boot, staggered so the jobs
    don't all hit the database at the same moment. Returns {} when disabled.
    (Passing next_run_time=None to APScheduler would PAUSE the job, so the
    argument is only added when it has a real value.)
    """
    if getattr(settings, "SCHEDULER_RUN_ON_STARTUP", True):
        return {"next_run_time": _utc_now() + timedelta(seconds=offset_seconds)}
    return {}


def setup_scheduler(app=None) -> AsyncIOScheduler:
    """
    Configure and register all periodic background jobs.
    """
    if not settings.SCHEDULER_ENABLED:
        logger.info("Scheduler is disabled via configuration.")
        return scheduler

    if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        logger.warning(
            "Serverless runtime detected. APScheduler needs a long-running process; "
            "jobs will not tick reliably here. Host the backend on a persistent "
            "server, or trigger the job functions from an external cron."
        )

    scheduler.add_job(
        fetch_weather_job,
        trigger=IntervalTrigger(minutes=settings.WEATHER_REFRESH_INTERVAL_MINUTES),
        id="fetch_weather_job",
        name="Open-Meteo Weather Ingestion",
        replace_existing=True,
        **_startup(5),
    )

    scheduler.add_job(
        fetch_discharge_job,
        trigger=IntervalTrigger(
            hours=max(settings.DISCHARGE_REFRESH_INTERVAL_HOURS, 6)
        ),
        id="fetch_discharge_job",
        name="GloFAS Hydrological Discharge Forecast",
        replace_existing=True,
        **_startup(15),
    )

    scheduler.add_job(
        refresh_discharge_climatology_job,
        trigger=IntervalTrigger(days=7),
        id="refresh_discharge_climatology_job",
        name="GloFAS Historical Discharge Climatology (1991-2020)",
        replace_existing=True,
        **_startup(30),
    )

    scheduler.add_job(
        fetch_gauge_job,
        trigger=IntervalTrigger(minutes=settings.GAUGE_REFRESH_INTERVAL_MINUTES),
        id="fetch_gauge_job",
        name="MRC Gauge Water-Level Polling",
        replace_existing=True,
        **_startup(20),
    )

    scheduler.add_job(
        fetch_satellite_job,
        trigger=IntervalTrigger(minutes=settings.SATELLITE_CATALOG_CHECK_MINUTES),
        id="fetch_satellite_job",
        name="Sentinel-1 SAR STAC Catalog Discovery",
        replace_existing=True,
        **_startup(40),
    )

    scheduler.add_job(
        assess_risk_job,
        trigger=IntervalTrigger(hours=3),
        id="assess_risk_job",
        name="Tonle Sap Basin Flood Risk Computation",
        replace_existing=True,
        **_startup(60),
    )

    scheduler.add_job(
        check_alerts_job,
        trigger=IntervalTrigger(minutes=30),
        id="check_alerts_job",
        name="Hydrological Threshold & Emergency Alert Monitor",
        replace_existing=True,
        **_startup(75),
    )

    try:
        if not scheduler.running:
            scheduler.start()
            logger.info("APScheduler background engine started successfully.")
    except Exception as exc:
        logger.exception("Error starting scheduler: %s", exc)

    return scheduler


def shutdown_scheduler() -> None:
    """Stop the scheduler cleanly. Call from the app's shutdown hook."""
    try:
        if scheduler.running:
            scheduler.shutdown(wait=False)
            logger.info("APScheduler stopped.")
    except Exception as exc:
        logger.warning("Error stopping scheduler: %s", exc)


def get_scheduler_status() -> Dict[str, Any]:
    """Job list with next run times - expose via an endpoint for the dashboard."""
    jobs = []
    for job in scheduler.get_jobs():
        next_run = getattr(job, "next_run_time", None)
        jobs.append(
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": next_run.isoformat() if next_run else None,
            }
        )
    return {"running": scheduler.running, "jobs": jobs}