"""
FloodPulse AI - Hydrology API

Provides:
- Hydrological station list and details
- Live per-station GloFAS river discharge curves (Open-Meteo Flood API)
- Actual stored water-level time series
- Multi-station comparison
- Station CSV export
- Stored & auto-refreshed GloFAS river-discharge forecasts for monitoring locations

Important:
Monitoring locations and hydrological stations are separate
database entities.

No synthetic readings or estimated discharge values are generated.
"""

import asyncio
import csv
import io
import json
import logging
import secrets

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import aiosqlite
import httpx

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    status,
)

from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.database import get_db
from app.services.realtime import broker


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/hydrology",
    tags=["Hydrology"],
)

OPEN_METEO_FLOOD_URL = "https://flood-api.open-meteo.com/v1/flood"

# In-memory cache for per-station live GloFAS curves (30 min TTL)
_STATION_DISCHARGE_CACHE: Dict[int, Tuple[datetime, Dict[str, Any]]] = {}
_STATION_CACHE_TTL_SECONDS = 1800


# ---------------------------------------------------------------------
# RESPONSE MODELS
# ---------------------------------------------------------------------

class StationDetail(BaseModel):
    id: int
    code: str
    name: str
    name_km: Optional[str] = None
    type: Optional[str] = None
    province: Optional[str] = None
    district: Optional[str] = None
    lat: float
    lon: float
    elevation: Optional[float] = None
    water_body: Optional[str] = None
    data_source: Optional[str] = None
    alarm_level: Optional[float] = None
    flood_level: Optional[float] = None
    is_active: bool
    current_water_level: Optional[float] = None
    latest_reading_time: Optional[str] = None
    status: str
    pulse_flow_status: Optional[str] = None

    # Real-time metadata
    latest_data_source: Optional[str] = None
    freshness: str = "no_data"          # live | delayed | stale | baseline | no_data
    age_seconds: Optional[int] = None


class TimeSeriesPoint(BaseModel):
    timestamp: str
    water_level_m: Optional[float] = None
    discharge_m3s: Optional[float] = None
    quality_flag: str = "unknown"
    data_source: Optional[str] = None


class ComparisonResult(BaseModel):
    station_id: int
    station_code: str
    station_name: str
    river_name: Optional[str] = None
    timeseries: List[TimeSeriesPoint]


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

def _station_status(
    water_level: Optional[float],
    alarm_level: Optional[float],
    flood_level: Optional[float],
) -> str:

    if water_level is None:
        return "NO_DATA"

    if flood_level is not None and water_level >= flood_level:
        return "CRITICAL_FLOOD"

    if alarm_level is not None and water_level >= alarm_level:
        return "WARNING"

    return "NORMAL"


BASELINE_MARKERS = ("CALIBRATED", "BASELINE", "SIMULATED", "SEED", "DEMO")


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO timestamp. Timestamps without a timezone are treated as UTC."""
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _freshness(
    data_source: Optional[str],
    timestamp: Optional[str],
):
    """
    Classify how trustworthy 'current' a gauge reading is.

    baseline : stored placeholder/calibrated value - NOT a live measurement
    live     : measured recently
    delayed  : measured, but older than the live window
    stale    : measured, but very old
    no_data  : nothing stored
    """
    parsed = _parse_timestamp(timestamp)

    if parsed is None:
        return "no_data", None

    age_seconds = max(
        0,
        int((datetime.now(timezone.utc) - parsed).total_seconds()),
    )

    source = (data_source or "").upper()

    if any(marker in source for marker in BASELINE_MARKERS):
        return "baseline", age_seconds

    if age_seconds <= settings.GAUGE_LIVE_MAX_AGE_MINUTES * 60:
        return "live", age_seconds

    if age_seconds <= settings.GAUGE_STALE_AFTER_HOURS * 3600:
        return "delayed", age_seconds

    return "stale", age_seconds


def _station_from_row(
    row: aiosqlite.Row,
) -> StationDetail:

    water_level = row["current_water_level"]
    alarm_level = row["alarm_level"]
    flood_level = row["flood_level"]

    water_level = (
        float(water_level)
        if water_level is not None
        else None
    )

    alarm_level = (
        float(alarm_level)
        if alarm_level is not None
        else None
    )

    flood_level = (
        float(flood_level)
        if flood_level is not None
        else None
    )

    water_body = row["water_body"]

    latest_source = row["latest_data_source"]
    freshness, age_seconds = _freshness(
        latest_source,
        row["latest_reading_time"],
    )

    return StationDetail(
        id=row["id"],
        code=row["code"],
        name=row["name"],
        name_km=row["name_km"],
        type=row["type"],
        province=row["province"],
        district=row["district"],
        lat=row["lat"],
        lon=row["lon"],
        elevation=row["elevation"],
        water_body=water_body,
        data_source=row["data_source"],
        alarm_level=alarm_level,
        flood_level=flood_level,
        is_active=bool(row["is_active"]),
        current_water_level=(
            round(water_level, 2)
            if water_level is not None
            else None
        ),
        latest_reading_time=row["latest_reading_time"],
        status=_station_status(
            water_level,
            alarm_level,
            flood_level,
        ),
        pulse_flow_status=water_body,
        latest_data_source=latest_source,
        freshness=freshness,
        age_seconds=age_seconds,
    )


async def _get_station_row(
    db: aiosqlite.Connection,
    station_id: str,
):

    query = """
        SELECT
            s.id,
            s.code,
            s.name,
            s.name_km,
            s.type,
            s.province,
            s.district,
            s.lat,
            s.lon,
            s.elevation,
            s.water_body,
            s.data_source,
            s.alarm_level,
            s.flood_level,
            s.is_active,
            wl.value AS current_water_level,
            wl.timestamp AS latest_reading_time,
            wl.data_source AS latest_data_source
        FROM stations s
        LEFT JOIN water_levels wl
            ON wl.id = (
                SELECT w.id
                FROM water_levels w
                WHERE w.station_id = s.id
                ORDER BY w.timestamp DESC, w.id DESC
                LIMIT 1
            )
        WHERE CAST(s.id AS TEXT) = ?
           OR s.code = ?
        LIMIT 1
    """

    cursor = await db.execute(
        query,
        (station_id, station_id),
    )

    return await cursor.fetchone()


async def _get_station_timeseries(
    db: aiosqlite.Connection,
    station_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
) -> List[TimeSeriesPoint]:

    query = """
        SELECT
            timestamp,
            value,
            quality_flag,
            data_source
        FROM water_levels
        WHERE station_id = ?
    """

    params: List[Any] = [station_id]

    if start_date:
        query += " AND timestamp >= ?"
        params.append(start_date)

    if end_date:
        query += " AND timestamp <= ?"
        params.append(end_date + "T23:59:59")

    query += """
        ORDER BY timestamp DESC, id DESC
        LIMIT ?
    """

    params.append(limit)

    cursor = await db.execute(
        query,
        tuple(params),
    )

    rows = await cursor.fetchall()

    points = []

    for row in reversed(rows):

        value = row["value"]

        points.append(
            TimeSeriesPoint(
                timestamp=row["timestamp"],
                water_level_m=(
                    round(float(value), 2)
                    if value is not None
                    else None
                ),
                discharge_m3s=None,
                quality_flag=(
                    row["quality_flag"] or "unknown"
                ),
                data_source=row["data_source"],
            )
        )

    return points


# ---------------------------------------------------------------------
# RIVER DISCHARGE FORECAST (AUTO-LIVE GLOFAS SYNC)
# ---------------------------------------------------------------------

async def _fetch_and_store_glofas(
    db: aiosqlite.Connection,
    location_id: int,
    lat: float,
    lon: float,
) -> Optional[str]:
    """
    Fetch live GloFAS river discharge forecast from Open-Meteo Flood API
    and store it in river_discharge. Returns the new retrieval_timestamp.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "river_discharge,river_discharge_mean,river_discharge_median,river_discharge_max",
        "past_days": 3,
        "forecast_days": 14,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(OPEN_METEO_FLOOD_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        daily = data.get("daily", {})
        dates = daily.get("time", [])
        if not dates:
            return None

        discharges = daily.get("river_discharge", [])
        means = daily.get("river_discharge_mean", [])
        medians = daily.get("river_discharge_median", [])
        maxes = daily.get("river_discharge_max", [])

        now_iso = datetime.now(timezone.utc).isoformat()
        source_label = "Open-Meteo GloFAS v4"

        for i, date_str in enumerate(dates):
            val = discharges[i] if i < len(discharges) else None
            val_mean = means[i] if i < len(means) else None
            val_median = medians[i] if i < len(medians) else None
            val_max = maxes[i] if i < len(maxes) else None

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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    location_id,
                    date_str,
                    val,
                    val_max,
                    val_mean,
                    val_median,
                    source_label,
                    now_iso,
                ),
            )

        await db.commit()
        broker.publish("discharge_updated", {"location_id": location_id})
        return now_iso

    except Exception as exc:
        logger.warning(
            "Live GloFAS fetch failed for location %s (%s, %s): %s",
            location_id,
            lat,
            lon,
            exc,
        )
        return None


@router.get("/discharge")
async def get_discharge_forecast(
    location_id: int = Query(..., ge=1),
    refresh: bool = Query(False, description="Force a live GloFAS refresh"),
    db: aiosqlite.Connection = Depends(get_db),
) -> Dict[str, Any]:
    """
    Return records from the latest discharge ingestion run.
    Automatically fetches live GloFAS data if none exists, data is >6h old, or refresh=True.
    """

    # 1. Find monitoring location (including coordinates for live fetch).
    cursor = await db.execute(
        """
        SELECT *
        FROM monitoring_locations
        WHERE id = ?
        """,
        (location_id,),
    )
    location = await cursor.fetchone()

    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitoring location not found.",
        )

    loc_keys = location.keys()
    lat = (
        location["lat"]
        if "lat" in loc_keys
        else location["latitude"]
        if "latitude" in loc_keys
        else None
    )
    lon = (
        location["lon"]
        if "lon" in loc_keys
        else location["longitude"]
        if "longitude" in loc_keys
        else None
    )

    # 2. Find the latest retrieval timestamp.
    cursor = await db.execute(
        """
        SELECT MAX(retrieval_timestamp) AS latest_timestamp
        FROM river_discharge
        WHERE location_id = ?
        """,
        (location_id,),
    )
    timestamp_row = await cursor.fetchone()
    latest_timestamp = (
        timestamp_row["latest_timestamp"]
        if timestamp_row
        else None
    )

    # 3. Auto-fetch live GloFAS forecast if missing, stale (>6h), or refresh=True.
    needs_fetch = refresh or not latest_timestamp
    if latest_timestamp and not needs_fetch:
        parsed_ts = _parse_timestamp(latest_timestamp)
        if parsed_ts:
            age_hours = (
                datetime.now(timezone.utc) - parsed_ts
            ).total_seconds() / 3600
            if age_hours >= 6:
                needs_fetch = True

    if needs_fetch and lat is not None and lon is not None:
        new_ts = await _fetch_and_store_glofas(
            db, location_id, float(lat), float(lon)
        )
        if new_ts:
            latest_timestamp = new_ts

    # 4. Return empty response if still no forecast exists.
    if not latest_timestamp:
        return {
            "location_id": location["id"],
            "location_name": location["name"],
            "province": location["province"],
            "current_discharge_m3s": None,
            "historical_mean_m3s": None,
            "forecast_reference_mean_m3s": None,
            "anomaly_pct": None,
            "flow_status": "NO_DATA",
            "forecast": [],
            "data_sources": [],
            "updated_at": None,
        }

    # 5. Retrieve only the latest ingestion run.
    cursor = await db.execute(
        """
        SELECT
            date,
            discharge_m3s,
            discharge_max,
            discharge_mean,
            discharge_median,
            data_source,
            retrieval_timestamp
        FROM river_discharge
        WHERE location_id = ?
          AND retrieval_timestamp = ?
        ORDER BY date ASC, id ASC
        """,
        (location_id, latest_timestamp),
    )
    rows = await cursor.fetchall()

    # 6. Build forecast records.
    forecast = []
    sources = set()

    for row in rows:
        forecast.append({
            "date": row["date"],
            "discharge_m3s": row["discharge_m3s"],
            "discharge_max": row["discharge_max"],
            "discharge_mean": row["discharge_mean"],
            "discharge_median": row["discharge_median"],
            "data_source": row["data_source"],
        })
        if row["data_source"]:
            sources.add(row["data_source"])

    # 7. Find the first available discharge value.
    first_valid = next(
        (
            item
            for item in forecast
            if item["discharge_m3s"] is not None
        ),
        None,
    )
    first_discharge = (
        first_valid["discharge_m3s"]
        if first_valid is not None
        else None
    )
    reference_mean = (
        first_valid["discharge_mean"]
        if first_valid is not None
        else None
    )

    # 8. Calculate deviation from forecast reference mean.
    anomaly_pct = None
    if (
        first_discharge is not None
        and reference_mean is not None
        and reference_mean != 0
    ):
        anomaly_pct = round(
            ((first_discharge - reference_mean) / reference_mean) * 100,
            1,
        )

    # 9. Classify forecast status.
    if first_valid is None:
        flow_status = "NO_DATA"
    elif anomaly_pct is None:
        flow_status = "UNKNOWN"
    elif anomaly_pct >= 25:
        flow_status = "HIGH"
    elif anomaly_pct <= -25:
        flow_status = "LOW"
    else:
        flow_status = "NORMAL"

    return {
        "location_id": location["id"],
        "location_name": location["name"],
        "province": location["province"],
        "current_discharge_m3s": first_discharge,
        "historical_mean_m3s": reference_mean,
        "forecast_reference_mean_m3s": reference_mean,
        "anomaly_pct": anomaly_pct,
        "flow_status": flow_status,
        "forecast": forecast,
        "data_sources": sorted(sources),
        "updated_at": latest_timestamp,
    }


# ---------------------------------------------------------------------
# HYDROLOGICAL STATIONS
# ---------------------------------------------------------------------

@router.get(
    "/stations",
    response_model=List[StationDetail],
)
async def list_hydrological_stations(
    is_active: Optional[bool] = Query(
        None,
        description="Filter stations by active status.",
    ),
    db: aiosqlite.Connection = Depends(get_db),
) -> List[StationDetail]:
    """
    List hydrological gauge stations.

    These records come from stations and water_levels,
    not monitoring_locations and river_discharge.
    """

    query = """
        SELECT
            s.id,
            s.code,
            s.name,
            s.name_km,
            s.type,
            s.province,
            s.district,
            s.lat,
            s.lon,
            s.elevation,
            s.water_body,
            s.data_source,
            s.alarm_level,
            s.flood_level,
            s.is_active,
            wl.value AS current_water_level,
            wl.timestamp AS latest_reading_time,
            wl.data_source AS latest_data_source
        FROM stations s
        LEFT JOIN water_levels wl
            ON wl.id = (
                SELECT w.id
                FROM water_levels w
                WHERE w.station_id = s.id
                ORDER BY w.timestamp DESC, w.id DESC
                LIMIT 1
            )
    """

    params = []

    if is_active is not None:
        query += " WHERE s.is_active = ?"
        params.append(1 if is_active else 0)

    query += " ORDER BY s.id ASC"

    cursor = await db.execute(
        query,
        tuple(params),
    )

    rows = await cursor.fetchall()

    return [
        _station_from_row(row)
        for row in rows
    ]


@router.get(
    "/stations/{station_id}",
    response_model=StationDetail,
)
async def get_hydrological_station(
    station_id: str,
    db: aiosqlite.Connection = Depends(get_db),
) -> StationDetail:
    """
    Retrieve one station by numeric ID or station code.
    """

    row = await _get_station_row(
        db,
        station_id,
    )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Station '{station_id}' not found.",
        )

    return _station_from_row(row)


@router.get("/stations/{station_id}/discharge")
async def get_station_live_discharge(
    station_id: str,
    refresh: bool = Query(
        False,
        description="Bypass cache and fetch live GloFAS discharge",
    ),
    db: aiosqlite.Connection = Depends(get_db),
) -> Dict[str, Any]:
    """
    Fetch real live GloFAS river discharge (past 7 days + next 14 days)
    for a specific hydrological station's GPS coordinates.
    """
    station = await _get_station_row(db, station_id)
    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Station '{station_id}' not found.",
        )

    st_id = int(station["id"])
    now = datetime.now(timezone.utc)

    if not refresh and st_id in _STATION_DISCHARGE_CACHE:
        cached_at, cached_payload = _STATION_DISCHARGE_CACHE[st_id]
        if (now - cached_at).total_seconds() < _STATION_CACHE_TTL_SECONDS:
            return cached_payload

    params = {
        "latitude": float(station["lat"]),
        "longitude": float(station["lon"]),
        "daily": "river_discharge,river_discharge_mean,river_discharge_median,river_discharge_max",
        "past_days": 7,
        "forecast_days": 14,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(OPEN_METEO_FLOOD_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning(
            "Live station GloFAS fetch failed for %s: %s",
            station["code"],
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to reach Open-Meteo Flood API for live station discharge.",
        ) from exc

    daily = data.get("daily", {})
    dates = daily.get("time", [])
    discharges = daily.get("river_discharge", [])
    means = daily.get("river_discharge_mean", [])
    medians = daily.get("river_discharge_median", [])
    maxes = daily.get("river_discharge_max", [])

    records = [
        {
            "date": date_str,
            "discharge_m3s": discharges[i] if i < len(discharges) else None,
            "discharge_mean": means[i] if i < len(means) else None,
            "discharge_median": medians[i] if i < len(medians) else None,
            "discharge_max": maxes[i] if i < len(maxes) else None,
            "data_source": "Open-Meteo GloFAS v4",
        }
        for i, date_str in enumerate(dates)
    ]

    payload = {
        "station_id": st_id,
        "station_code": station["code"],
        "station_name": station["name"],
        "province": station["province"],
        "water_body": station["water_body"],
        "lat": station["lat"],
        "lon": station["lon"],
        "data_source": "Open-Meteo GloFAS v4",
        "updated_at": now.isoformat(),
        "timeseries": records,
    }
    _STATION_DISCHARGE_CACHE[st_id] = (now, payload)
    return payload


# ---------------------------------------------------------------------
# STATION WATER-LEVEL TIME SERIES
# ---------------------------------------------------------------------

@router.get(
    "/stations/{station_id}/timeseries",
    response_model=List[TimeSeriesPoint],
)
async def get_station_timeseries(
    station_id: str,
    start_date: Optional[str] = Query(
        None,
        description="Start date in YYYY-MM-DD format.",
    ),
    end_date: Optional[str] = Query(
        None,
        description="End date in YYYY-MM-DD format.",
    ),
    limit: int = Query(100, ge=1, le=1000),
    db: aiosqlite.Connection = Depends(get_db),
) -> List[TimeSeriesPoint]:
    """
    Return actual stored water-level readings.

    Discharge is not estimated from water level.
    If no separate discharge measurement exists, it remains null.
    """

    cursor = await db.execute(
        """
        SELECT id
        FROM stations
        WHERE CAST(id AS TEXT) = ?
           OR code = ?
        LIMIT 1
        """,
        (station_id, station_id),
    )

    station = await cursor.fetchone()

    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Station not found.",
        )

    return await _get_station_timeseries(
        db=db,
        station_id=station["id"],
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )


# ---------------------------------------------------------------------
# MULTI-STATION COMPARISON
# ---------------------------------------------------------------------

@router.get(
    "/compare",
    response_model=List[ComparisonResult],
)
async def compare_hydrological_stations(
    stations: str = Query(
        ...,
        description="Comma-separated station IDs or codes.",
    ),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: aiosqlite.Connection = Depends(get_db),
) -> List[ComparisonResult]:
    """
    Compare actual water-level time series from multiple stations.
    """

    station_identifiers = [
        value.strip()
        for value in stations.split(",")
        if value.strip()
    ]

    if not station_identifiers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one station ID or code.",
        )

    results = []

    for identifier in station_identifiers:

        cursor = await db.execute(
            """
            SELECT
                id,
                code,
                name,
                water_body
            FROM stations
            WHERE CAST(id AS TEXT) = ?
               OR code = ?
            LIMIT 1
            """,
            (identifier, identifier),
        )

        station = await cursor.fetchone()

        if station is None:
            continue

        points = await _get_station_timeseries(
            db=db,
            station_id=station["id"],
            start_date=start_date,
            end_date=end_date,
            limit=100,
        )

        results.append(
            ComparisonResult(
                station_id=station["id"],
                station_code=station["code"],
                station_name=station["name"],
                river_name=station["water_body"],
                timeseries=points,
            )
        )

    return results


# ---------------------------------------------------------------------
# REAL-TIME: STREAM, STATUS AND TELEMETRY INGESTION
# ---------------------------------------------------------------------

def _sse(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/stream")
async def hydrology_stream(request: Request) -> StreamingResponse:
    """
    Server-Sent Events stream.

    Events: hello, heartbeat, station_reading, discharge_updated.
    The browser reacts to an event by re-fetching the REST endpoints, so the
    stream only needs to carry small notifications.
    """

    async def event_generator():
        queue = broker.subscribe()

        try:
            yield "retry: 5000\n\n"
            yield _sse(
                "hello",
                {
                    "server_time": datetime.now(timezone.utc).isoformat(),
                    "heartbeat_seconds": 15,
                },
            )

            while True:
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    yield _sse(event["type"], event)
                except asyncio.TimeoutError:
                    yield _sse(
                        "heartbeat",
                        {
                            "server_time": datetime.now(
                                timezone.utc
                            ).isoformat()
                        },
                    )
        finally:
            broker.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/status")
async def hydrology_status(
    db: aiosqlite.Connection = Depends(get_db),
) -> Dict[str, Any]:
    """
    Honest health report: how fresh is each data feed?
    """

    cursor = await db.execute("SELECT id FROM stations ORDER BY id ASC")
    station_ids = [row["id"] for row in await cursor.fetchall()]

    stations = []

    for station_id in station_ids:
        row = await _get_station_row(db, str(station_id))
        if row is not None:
            station = _station_from_row(row)
            stations.append(
                {
                    "code": station.code,
                    "name": station.name,
                    "freshness": station.freshness,
                    "age_seconds": station.age_seconds,
                    "latest_reading_time": station.latest_reading_time,
                    "latest_data_source": station.latest_data_source,
                }
            )

    cursor = await db.execute(
        "SELECT MAX(retrieval_timestamp) AS latest FROM river_discharge"
    )
    discharge_row = await cursor.fetchone()
    discharge_latest = discharge_row["latest"] if discharge_row else None

    discharge_parsed = _parse_timestamp(discharge_latest)
    discharge_age = (
        int((datetime.now(timezone.utc) - discharge_parsed).total_seconds())
        if discharge_parsed
        else None
    )

    return {
        "server_time": datetime.now(timezone.utc).isoformat(),
        "stream_clients": broker.subscriber_count,
        "telemetry_ingestion_enabled": bool(settings.TELEMETRY_API_KEY),
        "mrc_token_configured": bool(settings.MRC_API_TOKEN),
        "stations": stations,
        "discharge_forecast": {
            "latest_retrieval": discharge_latest,
            "age_seconds": discharge_age,
            "refresh_interval_hours": max(
                settings.DISCHARGE_REFRESH_INTERVAL_HOURS, 6
            ),
            "note": "Modelled GloFAS forecast, not a live measurement.",
        },
    }


class TelemetryReading(BaseModel):
    station: str = Field(..., description="Station code or numeric id")
    water_level_m: float = Field(..., ge=-5, le=40)
    timestamp: Optional[str] = Field(
        None,
        description="ISO 8601. Defaults to the time of the request.",
    )
    quality_flag: str = "good"
    source: str = Field("telemetry", max_length=40)


class TelemetryBatch(BaseModel):
    readings: List[TelemetryReading] = Field(..., min_length=1, max_length=500)


@router.post("/telemetry")
async def ingest_telemetry(
    batch: TelemetryBatch,
    x_api_key: Optional[str] = Header(None),
    db: aiosqlite.Connection = Depends(get_db),
) -> Dict[str, Any]:
    """
    Push real gauge readings into FloodPulse (sensor, data logger, script).

    Send header  X-API-Key: <TELEMETRY_API_KEY from backend/.env>
    Every stored reading is broadcast to open browsers immediately.
    """

    if not settings.TELEMETRY_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telemetry ingestion is disabled. Set TELEMETRY_API_KEY.",
        )

    if not x_api_key or not secrets.compare_digest(
        x_api_key, settings.TELEMETRY_API_KEY
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )

    now = datetime.now(timezone.utc)
    stored = 0
    duplicates = 0
    errors: List[str] = []
    events: List[Dict[str, Any]] = []

    for index, reading in enumerate(batch.readings):

        station = await _get_station_row(db, reading.station)

        if station is None:
            errors.append(f"[{index}] unknown station '{reading.station}'")
            continue

        if reading.timestamp:
            parsed = _parse_timestamp(reading.timestamp)
            if parsed is None:
                errors.append(f"[{index}] invalid timestamp")
                continue
        else:
            parsed = now

        if parsed > now + timedelta(minutes=5):
            errors.append(f"[{index}] timestamp is in the future")
            continue

        timestamp = parsed.isoformat()

        cursor = await db.execute(
            """
            SELECT 1 FROM water_levels
            WHERE station_id = ? AND timestamp = ? AND data_source = ?
            LIMIT 1
            """,
            (station["id"], timestamp, reading.source),
        )

        if await cursor.fetchone():
            duplicates += 1
            continue

        await db.execute(
            """
            INSERT INTO water_levels (
                station_id, timestamp, value, unit,
                data_source, retrieval_timestamp, quality_flag
            )
            VALUES (?, ?, ?, 'm', ?, ?, ?)
            """,
            (
                station["id"],
                timestamp,
                reading.water_level_m,
                reading.source,
                now.isoformat(),
                reading.quality_flag,
            ),
        )

        stored += 1
        events.append(
            {
                "station_id": station["id"],
                "station_code": station["code"],
                "water_level_m": reading.water_level_m,
                "timestamp": timestamp,
            }
        )

    await db.commit()

    for event in events:
        broker.publish("station_reading", event)

    # New real gauge reading: queue ONE debounced risk + alert sweep, so the
    # Risk page, Community page and alerts follow the new water level.
    if events:
        try:
            from app.services.scheduler import _schedule_followups

            _schedule_followups("telemetry")
        except Exception:
            logger.exception("Could not queue follow-up risk/alert sweep.")

    return {
        "stored": stored,
        "duplicates_skipped": duplicates,
        "errors": errors,
    }


# ---------------------------------------------------------------------
# CSV EXPORT
# ---------------------------------------------------------------------

@router.get("/stations/{station_id}/download")
async def download_station_csv(
    station_id: str,
    db: aiosqlite.Connection = Depends(get_db),
) -> StreamingResponse:
    """
    Export actual stored station water-level readings as CSV.
    """

    cursor = await db.execute(
        """
        SELECT
            id,
            code,
            name
        FROM stations
        WHERE CAST(id AS TEXT) = ?
           OR code = ?
        LIMIT 1
        """,
        (station_id, station_id),
    )

    station = await cursor.fetchone()

    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Station not found.",
        )

    points = await _get_station_timeseries(
        db=db,
        station_id=station["id"],
        limit=1000,
    )

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Station Code",
        "Station Name",
        "Timestamp",
        "Water Level (m)",
        "Discharge (m3/s)",
        "Quality Flag",
    ])

    for point in points:
        writer.writerow([
            station["code"],
            station["name"],
            point.timestamp,
            point.water_level_m,
            point.discharge_m3s,
            point.quality_flag,
        ])

    output.seek(0)

    filename = (
        f"floodpulse_{station['code']}_"
        f"{datetime.now().strftime('%Y%m%d')}.csv"
    )

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f"attachment; filename={filename}"
            )
        },
    )