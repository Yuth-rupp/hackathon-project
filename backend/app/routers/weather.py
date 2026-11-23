"""FloodPulse AI - Live Weather & Atmospheric API.

Uses Open-Meteo Forecast and Archive APIs.
Missing measurements remain None; provider failures return HTTP 502.
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import aiosqlite
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.database import get_db
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/weather", tags=["Weather"])

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
TIMEZONE = "Asia/Phnom_Penh"


# ============================================================
# RESPONSE MODELS
# ============================================================

class CurrentWeatherResponse(BaseModel):
    location_id: int
    location_name: str
    province: str
    timestamp: str

    temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    precipitation_mm: Optional[float] = None
    precipitation_probability_pct: Optional[float] = None

    wind_speed_kmh: Optional[float] = None
    wind_direction_deg: Optional[float] = None
    cloud_cover_pct: Optional[float] = None

    weather_code: Optional[int] = None
    condition: str = "Unavailable"

    soil_moisture: Optional[float] = None

    data_source: str = "Open-Meteo"
    timezone: str = TIMEZONE


class HourlyForecastPoint(BaseModel):
    time: str

    temperature_c: Optional[float] = None
    precipitation_mm: Optional[float] = None
    precipitation_probability: Optional[float] = None
    relative_humidity_pct: Optional[float] = None
    cloud_cover_pct: Optional[float] = None

    soil_moisture_0_7cm: Optional[float] = None
    soil_moisture_7_28cm: Optional[float] = None
    soil_moisture_28_100cm: Optional[float] = None


class DailyForecastPoint(BaseModel):
    date: str

    temp_max_c: Optional[float] = None
    temp_min_c: Optional[float] = None

    precipitation_sum_mm: Optional[float] = None
    precipitation_probability_max: Optional[float] = None
    wind_speed_max_kmh: Optional[float] = None

    weather_code: Optional[int] = None
    condition: str = "Unavailable"


class WeatherForecastResponse(BaseModel):
    location_id: int
    location_name: str
    province: str

    hourly: List[HourlyForecastPoint]
    daily: List[DailyForecastPoint]

    retrieved_at: str
    data_source: str = "Open-Meteo"
    timezone: str = TIMEZONE


class RainfallAccumulationResponse(BaseModel):
    location_id: int
    location_name: str
    province: str

    rainfall_3d_mm: Optional[float] = None
    rainfall_7d_mm: Optional[float] = None
    rainfall_30d_mm: Optional[float] = None

    rainfall_30d_start: Optional[str] = None
    rainfall_30d_end: Optional[str] = None

    soil_saturation_index: Optional[float] = None
    flood_threat_level: str = "Unavailable"

    data_source: str = "Open-Meteo"
    retrieved_at: str


class SoilMoistureProfile(BaseModel):
    location_id: int
    location_name: str

    topsoil_moisture_0_7cm: Optional[float] = None
    root_zone_moisture_7_28cm: Optional[float] = None
    deep_moisture_28_100cm: Optional[float] = None

    saturation_percentage: Optional[float] = None
    risk_level: str = "Unavailable"

    timestamp: Optional[str] = None
    data_source: str = "Open-Meteo"


# ============================================================
# LOCATION RESOLUTION
# ============================================================

def _normalize_key(value: Any) -> str:
    """Compare names ignoring case, spaces, hyphens and underscores:
    'siem-reap', 'Siem Reap', 'siem_reap' and 'siemreap' all become 'siemreap'."""
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


async def resolve_location(
    location_id: str,
    db: aiosqlite.Connection
) -> Dict[str, Any]:

    wanted = _normalize_key(location_id)

    cursor = await db.execute(
        "SELECT id, name, name_km, province, lat, lon FROM monitoring_locations"
    )

    for row in await cursor.fetchall():
        item = dict(row)

        if (
            str(item["id"]) == str(location_id)
            or _normalize_key(item.get("name")) == wanted
            or _normalize_key(item.get("province")) == wanted
        ):
            return item

    # Check configured monitoring locations.
    for key, value in settings.MONITORING_LOCATIONS.items():

        if (
            str(value.get("id")) == str(location_id)
            or _normalize_key(key) == wanted
            or _normalize_key(value.get("name")) == wanted
            or _normalize_key(value.get("province")) == wanted
        ):
            return value

    raise HTTPException(
        status_code=404,
        detail=f"Monitoring location '{location_id}' not found."
    )


# ============================================================
# WEATHER CODE TRANSLATION
# ============================================================

def condition_from_code(code: Optional[int]) -> str:

    if code is None:
        return "Unavailable"

    conditions = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        56: "Freezing drizzle",
        57: "Dense freezing drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        66: "Freezing rain",
        67: "Heavy freezing rain",
        71: "Slight snowfall",
        73: "Moderate snowfall",
        75: "Heavy snowfall",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with hail",
        99: "Severe thunderstorm with hail",
    }

    return conditions.get(code, "Unknown conditions")


# ============================================================
# OPEN-METEO REQUEST HELPER
# ============================================================

async def get_provider_data(
    url: str,
    params: Dict[str, Any]
) -> Dict[str, Any]:

    try:

        async with httpx.AsyncClient(timeout=25.0) as client:

            response = await client.get(
                url,
                params=params
            )

            response.raise_for_status()

            result = response.json()

            if not isinstance(result, dict):
                raise ValueError("Invalid weather provider response")

            return result

    except (httpx.HTTPError, ValueError) as exc:

        logger.exception("Open-Meteo request failed")

        raise HTTPException(
            status_code=502,
            detail=f"Weather provider unavailable: {exc}"
        ) from exc


# ============================================================
# CURRENT WEATHER
# GET /weather/current/{location_id}
# ============================================================

@router.get(
    "/current/{location_id}",
    response_model=CurrentWeatherResponse
)
async def get_current_weather(
    location_id: str,
    db: aiosqlite.Connection = Depends(get_db)
):

    loc = await resolve_location(location_id, db)

    params = {
        "latitude": loc["lat"],
        "longitude": loc["lon"],

        "current": (
            "temperature_2m,"
            "relative_humidity_2m,"
            "precipitation,"
            "weather_code,"
            "wind_speed_10m,"
            "wind_direction_10m,"
            "cloud_cover"
        ),

        "hourly": "precipitation_probability,cloud_cover",

        "forecast_days": 1,
        "timezone": TIMEZONE,
    }

    data = await get_provider_data(
        FORECAST_URL,
        params
    )

    current = data.get("current") or {}
    hourly = data.get("hourly") or {}

    current_time = current.get("time")

    probability = None
    hourly_cloud = None

    times = hourly.get("time") or []
    probabilities = hourly.get("precipitation_probability") or []
    clouds = hourly.get("cloud_cover") or []

    # "current" is reported at 15-minute resolution (e.g. 23:15) while hourly
    # data is on the hour (23:00), so match on the hour, not the exact string.
    hour_key = (current_time or "")[:13]
    index = next(
        (i for i, t in enumerate(times) if str(t)[:13] == hour_key),
        None,
    )

    if index is not None:
        if index < len(probabilities):
            probability = probabilities[index]
        if index < len(clouds):
            hourly_cloud = clouds[index]

    cloud_cover = current.get("cloud_cover")
    if cloud_cover is None:
        cloud_cover = hourly_cloud

    code = current.get("weather_code")

    return CurrentWeatherResponse(
        location_id=int(loc["id"]),
        location_name=loc["name"],
        province=loc.get("province") or loc["name"],

        timestamp=current_time or datetime.now(
            timezone.utc
        ).isoformat(),

        temperature_c=current.get("temperature_2m"),
        humidity_pct=current.get("relative_humidity_2m"),
        precipitation_mm=current.get("precipitation"),
        precipitation_probability_pct=probability,

        wind_speed_kmh=current.get("wind_speed_10m"),
        wind_direction_deg=current.get("wind_direction_10m"),
        cloud_cover_pct=cloud_cover,

        weather_code=code,
        condition=condition_from_code(code),

        # Current endpoint does not fabricate soil moisture.
        soil_moisture=None,

        data_source="Open-Meteo",
        timezone=data.get("timezone", TIMEZONE),
    )


# ============================================================
# WEATHER FORECAST
# GET /weather/forecast/{location_id}
# ============================================================

@router.get(
    "/forecast/{location_id}",
    response_model=WeatherForecastResponse
)
async def get_weather_forecast(
    location_id: str,
    db: aiosqlite.Connection = Depends(get_db)
):

    loc = await resolve_location(location_id, db)

    params = {
        "latitude": loc["lat"],
        "longitude": loc["lon"],

        "hourly": (
            "temperature_2m,"
            "precipitation,"
            "precipitation_probability,"
            "relative_humidity_2m,"
            "cloud_cover,"
            "soil_moisture_0_to_7cm,"
            "soil_moisture_7_to_28cm,"
            "soil_moisture_28_to_100cm"
        ),

        "daily": (
            "weather_code,"
            "temperature_2m_max,"
            "temperature_2m_min,"
            "precipitation_sum,"
            "precipitation_probability_max,"
            "wind_speed_10m_max"
        ),

        "forecast_days": 7,
        "timezone": TIMEZONE,
    }

    data = await get_provider_data(
        FORECAST_URL,
        params
    )

    hourly_data = data.get("hourly") or {}
    daily_data = data.get("daily") or {}

    hourly_times = hourly_data.get("time") or []
    daily_times = daily_data.get("time") or []

    hourly_points = []

    # Open-Meteo returns hourly data from 00:00 today. Start the 48-hour
    # window at the current hour (in the location's timezone) instead.
    utc_offset = int(data.get("utc_offset_seconds") or 7 * 3600)
    now_local = datetime.now(timezone.utc) + timedelta(seconds=utc_offset)
    now_hour_key = now_local.strftime("%Y-%m-%dT%H")

    start_index = next(
        (i for i, t in enumerate(hourly_times) if str(t)[:13] >= now_hour_key),
        0,
    )

    for index in range(start_index, min(start_index + 48, len(hourly_times))):

        timestamp = hourly_times[index]

        def hourly_value(key):

            values = hourly_data.get(key) or []

            if index < len(values):
                return values[index]

            return None

        hourly_points.append(
            HourlyForecastPoint(
                time=timestamp,

                temperature_c=hourly_value("temperature_2m"),
                precipitation_mm=hourly_value("precipitation"),
                precipitation_probability=hourly_value(
                    "precipitation_probability"
                ),
                relative_humidity_pct=hourly_value(
                    "relative_humidity_2m"
                ),
                cloud_cover_pct=hourly_value("cloud_cover"),

                soil_moisture_0_7cm=hourly_value(
                    "soil_moisture_0_to_7cm"
                ),
                soil_moisture_7_28cm=hourly_value(
                    "soil_moisture_7_to_28cm"
                ),
                soil_moisture_28_100cm=hourly_value(
                    "soil_moisture_28_to_100cm"
                ),
            )
        )

    daily_points = []

    for index, day in enumerate(daily_times[:7]):

        def daily_value(key):

            values = daily_data.get(key) or []

            if index < len(values):
                return values[index]

            return None

        code = daily_value("weather_code")

        daily_points.append(
            DailyForecastPoint(
                date=day,

                temp_max_c=daily_value("temperature_2m_max"),
                temp_min_c=daily_value("temperature_2m_min"),

                precipitation_sum_mm=daily_value(
                    "precipitation_sum"
                ),

                precipitation_probability_max=daily_value(
                    "precipitation_probability_max"
                ),

                wind_speed_max_kmh=daily_value(
                    "wind_speed_10m_max"
                ),

                weather_code=code,
                condition=condition_from_code(code),
            )
        )

    if not hourly_points and not daily_points:

        raise HTTPException(
            status_code=502,
            detail="Open-Meteo returned no forecast records."
        )

    return WeatherForecastResponse(
        location_id=int(loc["id"]),
        location_name=loc["name"],
        province=loc.get("province") or loc["name"],

        hourly=hourly_points,
        daily=daily_points,

        retrieved_at=datetime.now(timezone.utc).isoformat(),

        data_source="Open-Meteo",
        timezone=data.get("timezone", TIMEZONE),
    )


# ============================================================
# HISTORICAL WEATHER
# GET /weather/historical/{location_id}
# ============================================================

@router.get("/historical/{location_id}")
async def get_historical_weather(
    location_id: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: aiosqlite.Connection = Depends(get_db)
):

    loc = await resolve_location(location_id, db)

    query = """
        SELECT
            timestamp,
            temperature_c,
            humidity_pct,
            precipitation_mm,
            soil_moisture
        FROM weather_data
        WHERE location_id = ?
    """

    params: List[Any] = [loc["id"]]

    if start_date:
        query += " AND timestamp >= ?"
        params.append(start_date)

    if end_date:
        query += " AND timestamp <= ?"
        params.append(end_date + "T23:59:59")

    query += " ORDER BY timestamp ASC LIMIT 1000"

    cursor = await db.execute(
        query,
        tuple(params)
    )

    records = [
        dict(row)
        for row in await cursor.fetchall()
    ]

    return {
        "location_id": loc["id"],
        "location_name": loc["name"],
        "records_count": len(records),
        "data": records,
        "data_source": "FloodPulse stored observations",
    }


# ============================================================
# RAINFALL ACCUMULATION
# GET /weather/rainfall-accumulation/{location_id}
# ============================================================

@router.get(
    "/rainfall-accumulation/{location_id}",
    response_model=RainfallAccumulationResponse
)
async def get_rainfall_accumulation(
    location_id: str,
    db: aiosqlite.Connection = Depends(get_db)
):

    loc = await resolve_location(location_id, db)

    today = datetime.now(timezone.utc).date()

    # Archive API: previous 30 complete days.
    end_day = today - timedelta(days=1)
    start_day = end_day - timedelta(days=29)

    archive = await get_provider_data(
        ARCHIVE_URL,
        {
            "latitude": loc["lat"],
            "longitude": loc["lon"],

            "start_date": start_day.isoformat(),
            "end_date": end_day.isoformat(),

            "hourly": "precipitation",
            "timezone": TIMEZONE,
        }
    )

    values = (
        archive.get("hourly") or {}
    ).get("precipitation") or []

    valid_values = [
        float(value)
        for value in values
        if value is not None
    ]

    rainfall_30d = (
        round(sum(valid_values), 2)
        if valid_values
        else None
    )

    # Separate forecast totals from historical rainfall.
    forecast = await get_provider_data(
        FORECAST_URL,
        {
            "latitude": loc["lat"],
            "longitude": loc["lon"],

            "daily": "precipitation_sum",

            "forecast_days": 7,
            "timezone": TIMEZONE,
        }
    )

    daily_values = (
        forecast.get("daily") or {}
    ).get("precipitation_sum") or []

    first_three = [
        float(value)
        for value in daily_values[:3]
        if value is not None
    ]

    first_seven = [
        float(value)
        for value in daily_values[:7]
        if value is not None
    ]

    rainfall_3d = (
        round(sum(first_three), 1)
        if first_three
        else None
    )

    rainfall_7d = (
        round(sum(first_seven), 1)
        if first_seven
        else None
    )

    return RainfallAccumulationResponse(
        location_id=int(loc["id"]),
        location_name=loc["name"],
        province=loc.get("province") or loc["name"],

        rainfall_3d_mm=rainfall_3d,
        rainfall_7d_mm=rainfall_7d,

        rainfall_30d_mm=rainfall_30d,

        rainfall_30d_start=start_day.isoformat(),
        rainfall_30d_end=end_day.isoformat(),

        # No saturation score without validated soil measurements.
        soil_saturation_index=None,
        flood_threat_level="Unavailable: requires validated soil and hydrology inputs",

        data_source="Open-Meteo Archive and Forecast",
        retrieved_at=datetime.now(timezone.utc).isoformat(),
    )


# ============================================================
# SOIL MOISTURE PROFILE
# GET /weather/soil-moisture/{location_id}
# ============================================================

@router.get(
    "/soil-moisture/{location_id}",
    response_model=SoilMoistureProfile
)
async def get_soil_moisture(
    location_id: str,
    db: aiosqlite.Connection = Depends(get_db)
):

    loc = await resolve_location(location_id, db)

    data = await get_provider_data(
        FORECAST_URL,
        {
            "latitude": loc["lat"],
            "longitude": loc["lon"],

            "hourly": (
                "soil_moisture_0_to_7cm,"
                "soil_moisture_7_to_28cm,"
                "soil_moisture_28_to_100cm"
            ),

            "forecast_hours": 1,
            "timezone": TIMEZONE,
        }
    )

    hourly = data.get("hourly") or {}

    def latest_value(key):

        values = hourly.get(key) or []

        for value in reversed(values):

            if value is not None:
                return float(value)

        return None

    topsoil = latest_value("soil_moisture_0_to_7cm")
    root_zone = latest_value("soil_moisture_7_to_28cm")
    deep_soil = latest_value("soil_moisture_28_to_100cm")

    # This is a volumetric moisture value, not a calibrated saturation
    # percentage. Do not invent a saturation percentage.
    saturation = None
    risk = "Unavailable"

    times = hourly.get("time") or []

    return SoilMoistureProfile(
        location_id=int(loc["id"]),
        location_name=loc["name"],

        topsoil_moisture_0_7cm=topsoil,
        root_zone_moisture_7_28cm=root_zone,
        deep_moisture_28_100cm=deep_soil,

        saturation_percentage=saturation,
        risk_level=risk,

        timestamp=times[-1] if times else None,
        data_source="Open-Meteo",
    )