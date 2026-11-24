"""FloodPulse AI - Live Weather & Atmospheric API.

Uses Open-Meteo Forecast and Archive APIs with:
- Unified per-location caching & request coalescing (prevents burst 429s)
- Automatic live fallback to MET Norway (api.met.no) for current/hourly/daily weather
- Automatic NASA POWER satellite fallback (power.larc.nasa.gov) for 30-day rainfall & soil moisture
- SQLite stored-observation fallback as final safety net
"""

import asyncio
import logging
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

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
MET_NO_URL = "https://api.met.no/weatherapi/locationforecast/2.0/complete"
NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
MET_NO_HEADERS = {
    "User-Agent": "FloodPulse-AI/1.0 (https://floodpulse-ai.vercel.app)"
}
TIMEZONE = "Asia/Phnom_Penh"
LOCAL_UTC_OFFSET = timedelta(hours=7)

# In-memory TTL caches and per-key locks to collapse parallel frontend calls
FORECAST_CACHE_TTL_SECONDS = 1200   # 20 minutes
ARCHIVE_CACHE_TTL_SECONDS = 21600   # 6 hours
NASA_CACHE_TTL_SECONDS = 21600      # 6 hours
RATE_LIMIT_COOLDOWN_SECONDS = 900   # 15 minutes

_FORECAST_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_ARCHIVE_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_NASA_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_KEY_LOCKS: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
_OPEN_METEO_COOLDOWN_UNTIL: float = 0.0

# Typical alluvial clay/loam porosity in Tonle Sap basin (m3/m3 at 100% wetness)
SOIL_POROSITY_M3M3 = 0.48


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
    fallback_reason: Optional[str] = None
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
# WEATHER CODE & PROBABILITY HELPERS
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


def _wmo_code_from_met_symbol(symbol: Optional[str]) -> Optional[int]:
    if not symbol:
        return None
    s = symbol.lower()
    if "thunder" in s:
        return 95
    if "heavyrainshowers" in s:
        return 82
    if "rainshowers" in s:
        return 80
    if "heavyrain" in s:
        return 65
    if "lightrain" in s:
        return 61
    if "rain" in s:
        return 63
    if "fog" in s:
        return 45
    if "clearsky" in s:
        return 0
    if "fair" in s:
        return 1
    if "partlycloudy" in s:
        return 2
    if "cloudy" in s:
        return 3
    return 2


def _soil_risk_level(saturation_pct: Optional[float]) -> str:
    if saturation_pct is None:
        return "Unavailable"
    if saturation_pct >= 80.0:
        return "Critical"
    if saturation_pct >= 65.0:
        return "High"
    if saturation_pct >= 45.0:
        return "Moderate"
    return "Low"


# ============================================================
# NASA POWER SATELLITE FALLBACK (30-DAY RAINFALL + SOIL MOISTURE)
# ============================================================

async def get_nasa_power_data(loc: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch 30-day observed rainfall (PRECTOTCORR) and 3-layer soil moisture
    (GWETTOP, GWETROOT, GWETPROF) from NASA POWER MERRA-2 API."""
    cache_key = f"nasa:{loc['id']}"
    now = time.time()

    cached = _NASA_CACHE.get(cache_key)
    if cached and (now - cached[0]) < NASA_CACHE_TTL_SECONDS:
        return cached[1]

    async with _KEY_LOCKS[cache_key]:
        now = time.time()
        cached = _NASA_CACHE.get(cache_key)
        if cached and (now - cached[0]) < NASA_CACHE_TTL_SECONDS:
            return cached[1]

        today = datetime.now(timezone.utc).date()
        end_date = today - timedelta(days=1)
        # Fetch 36 days to absorb NASA MERRA-2's 2-4 day satellite processing lag
        start_date = end_date - timedelta(days=35)

        params = {
            "parameters": "PRECTOTCORR,GWETTOP,GWETROOT,GWETPROF",
            "community": "AG",
            "longitude": round(float(loc["lon"]), 4),
            "latitude": round(float(loc["lat"]), 4),
            "start": start_date.strftime("%Y%m%d"),
            "end": end_date.strftime("%Y%m%d"),
            "format": "JSON",
        }

        try:
            async with httpx.AsyncClient(timeout=25.0, headers=MET_NO_HEADERS) as client:
                response = await client.get(NASA_POWER_URL, params=params)
                response.raise_for_status()
                raw = response.json()

            param_block = (raw.get("properties") or {}).get("parameter") or {}
            precip_map: Dict[str, Any] = param_block.get("PRECTOTCORR") or {}
            top_map: Dict[str, Any] = param_block.get("GWETTOP") or {}
            root_map: Dict[str, Any] = param_block.get("GWETROOT") or {}
            prof_map: Dict[str, Any] = param_block.get("GWETPROF") or {}

            # Valid observed daily rainfall (NASA uses -999.0 for missing/unprocessed days)
            valid_rain_days = [
                (day_str, float(val))
                for day_str, val in sorted(precip_map.items())
                if val is not None and float(val) >= 0.0
            ]
            last_30_rain = valid_rain_days[-30:]
            rainfall_30d = (
                round(sum(v for _, v in last_30_rain), 2)
                if last_30_rain
                else None
            )

            def _latest_valid(series: Dict[str, Any]) -> Tuple[Optional[float], Optional[str]]:
                for day_str in sorted(series.keys(), reverse=True):
                    val = series[day_str]
                    if val is not None and float(val) >= 0.0:
                        iso_day = f"{day_str[:4]}-{day_str[4:6]}-{day_str[6:8]}T00:00"
                        return float(val), iso_day
                return None, None

            gwet_top, soil_ts = _latest_valid(top_map)
            gwet_root, _ = _latest_valid(root_map)
            gwet_prof, _ = _latest_valid(prof_map)

            # Convert NASA wetness fraction (0-1) to volumetric moisture (m3/m3)
            topsoil_m3m3 = round(gwet_top * SOIL_POROSITY_M3M3, 3) if gwet_top is not None else None
            root_m3m3 = round(gwet_root * SOIL_POROSITY_M3M3, 3) if gwet_root is not None else None
            deep_m3m3 = round(gwet_prof * SOIL_POROSITY_M3M3, 3) if gwet_prof is not None else None
            saturation_pct = round(gwet_top * 100.0, 1) if gwet_top is not None else None

            result = {
                "rainfall_30d_mm": rainfall_30d,
                "topsoil_moisture_0_7cm": topsoil_m3m3,
                "root_zone_moisture_7_28cm": root_m3m3,
                "deep_moisture_28_100cm": deep_m3m3,
                "saturation_percentage": saturation_pct,
                "soil_timestamp": soil_ts,
                "source": "NASA POWER (MERRA-2)",
            }
            _NASA_CACHE[cache_key] = (time.time(), result)
            return result

        except Exception as exc:
            logger.warning("NASA POWER fallback request failed: %s", exc)
            if cached:
                return cached[1]
            return {
                "rainfall_30d_mm": None,
                "topsoil_moisture_0_7cm": None,
                "root_zone_moisture_7_28cm": None,
                "deep_moisture_28_100cm": None,
                "saturation_percentage": None,
                "soil_timestamp": None,
                "source": "Unavailable",
            }


# ============================================================
# MET NORWAY LIVE FALLBACK ADAPTER
# ============================================================

async def _fetch_met_norway_as_open_meteo(loc: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch live weather from MET Norway (/complete) and enrich soil moisture
    from NASA POWER so every dashboard card and chart populates."""
    lat, lon = loc["lat"], loc["lon"]
    async with httpx.AsyncClient(timeout=20.0, headers=MET_NO_HEADERS) as client:
        response = await client.get(
            MET_NO_URL,
            params={"lat": round(float(lat), 4), "lon": round(float(lon), 4)},
        )
        response.raise_for_status()
        raw = response.json()

    timeseries = (raw.get("properties") or {}).get("timeseries") or []
    if not timeseries:
        raise ValueError("MET Norway returned empty timeseries")

    # Fetch NASA POWER soil moisture so hourly forecast points also carry soil depths
    nasa = await get_nasa_power_data(loc)

    hourly_time: List[str] = []
    hourly_temp: List[Optional[float]] = []
    hourly_precip: List[Optional[float]] = []
    hourly_prob: List[Optional[float]] = []
    hourly_humid: List[Optional[float]] = []
    hourly_cloud: List[Optional[float]] = []

    daily_buckets: Dict[str, Dict[str, Any]] = {}
    last_6h_counted_end: Optional[datetime] = None

    current_payload: Dict[str, Any] = {}

    for idx, entry in enumerate(timeseries):
        utc_str = entry.get("time")
        if not utc_str:
            continue
        dt_utc = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        dt_local = dt_utc + LOCAL_UTC_OFFSET
        local_hour_str = dt_local.strftime("%Y-%m-%dT%H:%M")
        local_date_str = dt_local.strftime("%Y-%m-%d")

        data_block = entry.get("data") or {}
        instant = (data_block.get("instant") or {}).get("details") or {}
        next_1h = data_block.get("next_1_hours") or {}
        next_6h = data_block.get("next_6_hours") or {}

        temp = instant.get("air_temperature")
        humid = instant.get("relative_humidity")
        cloud = instant.get("cloud_area_fraction")
        wind_ms = instant.get("wind_speed")
        wind_kmh = round(float(wind_ms) * 3.6, 1) if wind_ms is not None else None
        wind_dir = instant.get("wind_from_direction")

        details_1h = next_1h.get("details") or {}
        details_6h = next_6h.get("details") or {}
        precip_1h = details_1h.get("precipitation_amount")
        precip_6h = details_6h.get("precipitation_amount")

        symbol = (
            (next_1h.get("summary") or {}).get("symbol_code")
            or (next_6h.get("summary") or {}).get("symbol_code")
        )
        wmo_code = _wmo_code_from_met_symbol(symbol)

        step_precip = precip_1h
        if step_precip is None and precip_6h is not None:
            step_precip = round(float(precip_6h) / 6.0, 2)

        raw_prob = (
            details_1h.get("probability_of_precipitation")
            if details_1h.get("probability_of_precipitation") is not None
            else details_6h.get("probability_of_precipitation")
        )
        # Never invent a probability: if the provider omits it, leave it empty.
        step_prob = float(raw_prob) if raw_prob is not None else None

        if idx == 0:
            current_payload = {
                "time": local_hour_str,
                "temperature_2m": temp,
                "relative_humidity_2m": humid,
                "precipitation": step_precip,
                "precipitation_probability": step_prob,
                "weather_code": wmo_code,
                "wind_speed_10m": wind_kmh,
                "wind_direction_10m": wind_dir,
                "cloud_cover": cloud,
            }

        if len(hourly_time) < 72:
            hourly_time.append(local_hour_str)
            hourly_temp.append(temp)
            hourly_precip.append(step_precip)
            hourly_prob.append(step_prob)
            hourly_humid.append(humid)
            hourly_cloud.append(cloud)

        if local_date_str not in daily_buckets and len(daily_buckets) < 7:
            daily_buckets[local_date_str] = {
                "temps": [],
                "winds": [],
                "precip_sum": 0.0,
                "probs": [],
                "codes": [],
            }

        if local_date_str in daily_buckets:
            bucket = daily_buckets[local_date_str]
            if temp is not None:
                bucket["temps"].append(float(temp))
            if wind_kmh is not None:
                bucket["winds"].append(float(wind_kmh))
            if wmo_code is not None:
                bucket["codes"].append(wmo_code)
            if step_prob is not None:
                bucket["probs"].append(float(step_prob))

            if precip_1h is not None:
                bucket["precip_sum"] += float(precip_1h)
            elif precip_6h is not None:
                if last_6h_counted_end is None or dt_utc >= last_6h_counted_end:
                    bucket["precip_sum"] += float(precip_6h)
                    last_6h_counted_end = dt_utc + timedelta(hours=6)

    daily_dates = sorted(daily_buckets.keys())[:7]
    daily_temp_max = []
    daily_temp_min = []
    daily_precip_sum = []
    daily_prob_max = []
    daily_wind_max = []
    daily_codes = []

    for day in daily_dates:
        b = daily_buckets[day]
        daily_temp_max.append(round(max(b["temps"]), 1) if b["temps"] else None)
        daily_temp_min.append(round(min(b["temps"]), 1) if b["temps"] else None)
        daily_precip_sum.append(round(b["precip_sum"], 1))
        daily_prob_max.append(round(max(b["probs"]), 0) if b["probs"] else None)
        daily_wind_max.append(round(max(b["winds"]), 1) if b["winds"] else None)
        daily_codes.append(max(b["codes"]) if b["codes"] else None)

    n_hours = len(hourly_time)
    top_soil_series = (
        [nasa["topsoil_moisture_0_7cm"]] * n_hours
        if nasa["topsoil_moisture_0_7cm"] is not None
        else []
    )
    root_soil_series = (
        [nasa["root_zone_moisture_7_28cm"]] * n_hours
        if nasa["root_zone_moisture_7_28cm"] is not None
        else []
    )
    deep_soil_series = (
        [nasa["deep_moisture_28_100cm"]] * n_hours
        if nasa["deep_moisture_28_100cm"] is not None
        else []
    )

    return {
        "timezone": TIMEZONE,
        "utc_offset_seconds": 7 * 3600,
        "current": current_payload,
        "hourly": {
            "time": hourly_time,
            "temperature_2m": hourly_temp,
            "precipitation": hourly_precip,
            "precipitation_probability": hourly_prob,
            "relative_humidity_2m": hourly_humid,
            "cloud_cover": hourly_cloud,
            "soil_moisture_0_to_7cm": top_soil_series,
            "soil_moisture_7_to_28cm": root_soil_series,
            "soil_moisture_28_to_100cm": deep_soil_series,
        },
        "daily": {
            "time": daily_dates,
            "weather_code": daily_codes,
            "temperature_2m_max": daily_temp_max,
            "temperature_2m_min": daily_temp_min,
            "precipitation_sum": daily_precip_sum,
            "precipitation_probability_max": daily_prob_max,
            "wind_speed_10m_max": daily_wind_max,
        },
        "_data_source": "MET Norway & NASA POWER (Live Fallback)",
        "_soil_meta": nasa,
    }


# ============================================================
# UNIFIED CACHED WEATHER FETCHER
# ============================================================

async def get_unified_forecast(loc: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch all current, hourly, daily, and soil data for a location in ONE
    cached request, falling back to MET Norway + NASA POWER if Open-Meteo returns 429."""
    global _OPEN_METEO_COOLDOWN_UNTIL

    cache_key = f"loc:{loc['id']}"
    now = time.time()

    cached = _FORECAST_CACHE.get(cache_key)
    if cached and (now - cached[0]) < FORECAST_CACHE_TTL_SECONDS:
        return cached[1]

    async with _KEY_LOCKS[cache_key]:
        now = time.time()
        cached = _FORECAST_CACHE.get(cache_key)
        if cached and (now - cached[0]) < FORECAST_CACHE_TTL_SECONDS:
            return cached[1]

        fallback_reason: Optional[str] = None

        if now >= _OPEN_METEO_COOLDOWN_UNTIL:
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
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    response = await client.get(FORECAST_URL, params=params)
                    response.raise_for_status()
                    result = response.json()
                    if isinstance(result, dict):
                        result["_data_source"] = "Open-Meteo"
                        _FORECAST_CACHE[cache_key] = (time.time(), result)
                        return result
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    _OPEN_METEO_COOLDOWN_UNTIL = time.time() + RATE_LIMIT_COOLDOWN_SECONDS
                    fallback_reason = "Open-Meteo rate-limited (HTTP 429)"
                    logger.warning("Open-Meteo 429 rate-limited; switching to MET Norway + NASA POWER.")
                else:
                    fallback_reason = f"Open-Meteo HTTP error {exc.response.status_code}"
                    logger.warning("Open-Meteo HTTP error %s; switching to fallback.", exc.response.status_code)
            except (httpx.HTTPError, ValueError) as exc:
                fallback_reason = f"Open-Meteo request failed: {type(exc).__name__}"
                logger.warning("Open-Meteo request error (%s); switching to fallback.", exc)

        if fallback_reason is None:
            fallback_reason = "Open-Meteo paused after a recent rate limit (cooldown)"

        try:
            fallback_data = await _fetch_met_norway_as_open_meteo(loc)
            fallback_data["_fallback_reason"] = fallback_reason
            _FORECAST_CACHE[cache_key] = (time.time(), fallback_data)
            return fallback_data
        except Exception as exc:
            logger.warning("MET Norway fallback also failed: %s", exc)

        if cached:
            return cached[1]

        raise HTTPException(
            status_code=502,
            detail="All live weather providers are temporarily unavailable."
        )


async def get_30d_archive_rainfall(
    loc: Dict[str, Any],
    start_day: str,
    end_day: str,
    db: aiosqlite.Connection,
) -> Tuple[Optional[float], str]:
    """Fetch 30-day historical rainfall: Open-Meteo Archive -> NASA POWER -> SQLite."""
    global _OPEN_METEO_COOLDOWN_UNTIL

    cache_key = f"archive:{loc['id']}:{start_day}:{end_day}"
    now = time.time()

    cached = _ARCHIVE_CACHE.get(cache_key)
    if cached and (now - cached[0]) < ARCHIVE_CACHE_TTL_SECONDS:
        return cached[1]["rainfall_30d"], cached[1]["source"]

    async with _KEY_LOCKS[cache_key]:
        now = time.time()
        cached = _ARCHIVE_CACHE.get(cache_key)
        if cached and (now - cached[0]) < ARCHIVE_CACHE_TTL_SECONDS:
            return cached[1]["rainfall_30d"], cached[1]["source"]

        # 1. Try Open-Meteo Archive
        if now >= _OPEN_METEO_COOLDOWN_UNTIL:
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    response = await client.get(
                        ARCHIVE_URL,
                        params={
                            "latitude": loc["lat"],
                            "longitude": loc["lon"],
                            "start_date": start_day,
                            "end_date": end_day,
                            "hourly": "precipitation",
                            "timezone": TIMEZONE,
                        },
                    )
                    response.raise_for_status()
                    archive = response.json()
                    values = (archive.get("hourly") or {}).get("precipitation") or []
                    valid_values = [float(v) for v in values if v is not None]
                    if valid_values:
                        total = round(sum(valid_values), 2)
                        _ARCHIVE_CACHE[cache_key] = (
                            time.time(),
                            {"rainfall_30d": total, "source": "Open-Meteo Archive"},
                        )
                        return total, "Open-Meteo Archive"
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    _OPEN_METEO_COOLDOWN_UNTIL = time.time() + RATE_LIMIT_COOLDOWN_SECONDS
                    logger.warning("Open-Meteo Archive 429 rate-limited; using NASA POWER.")
            except Exception as exc:
                logger.warning("Open-Meteo Archive request failed: %s", exc)

        # 2. Fallback to NASA POWER satellite precipitation
        nasa = await get_nasa_power_data(loc)
        if nasa["rainfall_30d_mm"] is not None:
            _ARCHIVE_CACHE[cache_key] = (
                time.time(),
                {"rainfall_30d": nasa["rainfall_30d_mm"], "source": nasa["source"]},
            )
            return nasa["rainfall_30d_mm"], nasa["source"]

    # 3. Fallback to SQLite stored observations
    try:
        cursor = await db.execute(
            """
            SELECT SUM(COALESCE(precipitation_mm, 0)) AS total_rain, COUNT(*) AS cnt
            FROM weather_data
            WHERE id IN (
                SELECT MAX(id)
                FROM weather_data
                WHERE location_id = ?
                  AND COALESCE(data_type, '') != 'current'
                  AND timestamp >= ?
                  AND timestamp <= ?
                GROUP BY timestamp
            )
            """,
            (loc["id"], start_day, f"{end_day}T23:59:59"),
        )
        row = await cursor.fetchone()
        if row and (row["cnt"] or 0) > 0:
            return round(float(row["total_rain"] or 0.0), 2), "FloodPulse Stored Observations"
    except Exception as exc:
        logger.warning("SQLite 30-day rainfall fallback failed: %s", exc)

    return None, "Unavailable"


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
    data = await get_unified_forecast(loc)

    current = data.get("current") or {}
    hourly = data.get("hourly") or {}

    current_time = current.get("time")

    probability = current.get("precipitation_probability")
    hourly_cloud = None

    times = hourly.get("time") or []
    probabilities = hourly.get("precipitation_probability") or []
    clouds = hourly.get("cloud_cover") or []

    hour_key = (current_time or "")[:13]
    index = next(
        (i for i, t in enumerate(times) if str(t)[:13] == hour_key),
        None,
    )

    if index is not None:
        if probability is None and index < len(probabilities):
            probability = probabilities[index]
        if index < len(clouds):
            hourly_cloud = clouds[index]

    cloud_cover = current.get("cloud_cover")
    if cloud_cover is None:
        cloud_cover = hourly_cloud

    code = current.get("weather_code")
    soil_meta = data.get("_soil_meta") or {}

    return CurrentWeatherResponse(
        location_id=int(loc["id"]),
        location_name=loc["name"],
        province=loc.get("province") or loc["name"],

        timestamp=current_time or datetime.now(timezone.utc).isoformat(),

        temperature_c=current.get("temperature_2m"),
        humidity_pct=current.get("relative_humidity_2m"),
        precipitation_mm=current.get("precipitation"),
        precipitation_probability_pct=probability,

        wind_speed_kmh=current.get("wind_speed_10m"),
        wind_direction_deg=current.get("wind_direction_10m"),
        cloud_cover_pct=cloud_cover,

        weather_code=code,
        condition=condition_from_code(code),

        soil_moisture=soil_meta.get("topsoil_moisture_0_7cm"),

        data_source=data.get("_data_source", "Open-Meteo"),
        fallback_reason=data.get("_fallback_reason"),
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
    data = await get_unified_forecast(loc)

    hourly_data = data.get("hourly") or {}
    daily_data = data.get("daily") or {}

    hourly_times = hourly_data.get("time") or []
    daily_times = daily_data.get("time") or []

    hourly_points = []

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
                precipitation_probability=hourly_value("precipitation_probability"),
                relative_humidity_pct=hourly_value("relative_humidity_2m"),
                cloud_cover_pct=hourly_value("cloud_cover"),

                soil_moisture_0_7cm=hourly_value("soil_moisture_0_to_7cm"),
                soil_moisture_7_28cm=hourly_value("soil_moisture_7_to_28cm"),
                soil_moisture_28_100cm=hourly_value("soil_moisture_28_to_100cm"),
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

                precipitation_sum_mm=daily_value("precipitation_sum"),
                precipitation_probability_max=daily_value("precipitation_probability_max"),
                wind_speed_max_kmh=daily_value("wind_speed_10m_max"),

                weather_code=code,
                condition=condition_from_code(code),
            )
        )

    if not hourly_points and not daily_points:
        raise HTTPException(
            status_code=502,
            detail="Weather provider returned no forecast records."
        )

    return WeatherForecastResponse(
        location_id=int(loc["id"]),
        location_name=loc["name"],
        province=loc.get("province") or loc["name"],

        hourly=hourly_points,
        daily=daily_points,

        retrieved_at=datetime.now(timezone.utc).isoformat(),

        data_source=data.get("_data_source", "Open-Meteo"),
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

    cursor = await db.execute(query, tuple(params))

    records = [dict(row) for row in await cursor.fetchall()]

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
    end_day = today - timedelta(days=1)
    start_day = end_day - timedelta(days=29)

    forecast = await get_unified_forecast(loc)
    forecast_source = forecast.get("_data_source", "Open-Meteo")

    rainfall_30d, archive_source = await get_30d_archive_rainfall(
        loc=loc,
        start_day=start_day.isoformat(),
        end_day=end_day.isoformat(),
        db=db,
    )

    daily_values = (forecast.get("daily") or {}).get("precipitation_sum") or []

    first_three = [float(v) for v in daily_values[:3] if v is not None]
    first_seven = [float(v) for v in daily_values[:7] if v is not None]

    rainfall_3d = round(sum(first_three), 1) if first_three else None
    rainfall_7d = round(sum(first_seven), 1) if first_seven else None

    soil_meta = forecast.get("_soil_meta") or await get_nasa_power_data(loc)
    saturation_pct = soil_meta.get("saturation_percentage")

    threat_level = "Low"
    if (rainfall_7d or 0.0) >= 150.0 or (saturation_pct or 0.0) >= 80.0:
        threat_level = "High"
    elif (rainfall_7d or 0.0) >= 75.0 or (saturation_pct or 0.0) >= 60.0:
        threat_level = "Moderate"

    combined_source = (
        f"{forecast_source} & {archive_source}"
        if archive_source not in ("Unavailable", forecast_source) and archive_source not in forecast_source
        else forecast_source
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

        soil_saturation_index=saturation_pct,
        flood_threat_level=threat_level,

        data_source=combined_source,
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
    data = await get_unified_forecast(loc)
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
    times = hourly.get("time") or []
    timestamp = times[-1] if times else None
    source = data.get("_data_source", "Open-Meteo")
    saturation: Optional[float] = None

    soil_meta = data.get("_soil_meta")
    if topsoil is None or root_zone is None or deep_soil is None:
        nasa = soil_meta or await get_nasa_power_data(loc)
        if topsoil is None:
            topsoil = nasa["topsoil_moisture_0_7cm"]
        if root_zone is None:
            root_zone = nasa["root_zone_moisture_7_28cm"]
        if deep_soil is None:
            deep_soil = nasa["deep_moisture_28_100cm"]
        if nasa["soil_timestamp"]:
            timestamp = nasa["soil_timestamp"]
        if nasa["source"] != "Unavailable":
            source = nasa["source"]
        saturation = nasa["saturation_percentage"]

    if saturation is None and topsoil is not None:
        saturation = round(min(100.0, (topsoil / SOIL_POROSITY_M3M3) * 100.0), 1)

    if topsoil is None:
        cursor = await db.execute(
            """
            SELECT soil_moisture, timestamp
            FROM weather_data
            WHERE location_id = ?
              AND soil_moisture IS NOT NULL
            ORDER BY id DESC
            LIMIT 1
            """,
            (loc["id"],),
        )
        row = await cursor.fetchone()
        if row:
            topsoil = float(row["soil_moisture"])
            saturation = round(min(100.0, (topsoil / SOIL_POROSITY_M3M3) * 100.0), 1)
            timestamp = row["timestamp"]
            source = "FloodPulse Stored Observations"

    return SoilMoistureProfile(
        location_id=int(loc["id"]),
        location_name=loc["name"],

        topsoil_moisture_0_7cm=topsoil,
        root_zone_moisture_7_28cm=root_zone,
        deep_moisture_28_100cm=deep_soil,

        saturation_percentage=saturation,
        risk_level=_soil_risk_level(saturation),

        timestamp=timestamp,
        data_source=source,
    )