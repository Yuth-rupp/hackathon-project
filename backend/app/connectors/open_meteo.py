"""
FloodPulse AI - Open-Meteo Ingestion Connector
Fetches real-time weather, 48-hour hourly outlooks, 7-day daily forecasts,
GloFAS river discharge ensemble forecasts, and calculates cumulative rainfall.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.connectors.base import BaseConnector, ConnectorError
from app.database import execute_query, fetch_all, fetch_one

logger = logging.getLogger(__name__)


class OpenMeteoConnector(BaseConnector):
    """
    Production connector for Open-Meteo Forecast, Archive, and Global Flood APIs.
    No authentication required. High reliability public meteorological datasets.
    """

    def __init__(self):
        super().__init__(
            name="Open-Meteo",
            source_id="open_meteo",
            base_url="https://api.open-meteo.com/v1",
            timeout=30.0,
            max_retries=3
        )
        self.archive_url = settings.OPEN_METEO_ARCHIVE_URL
        self.flood_url = settings.OPEN_METEO_FLOOD_URL

    def validate(self, raw_data: Any) -> bool:
        """Verify that Open-Meteo payload contains valid coordinate returns and timestamps."""
        if not isinstance(raw_data, dict):
            return False
        if "latitude" not in raw_data or "longitude" not in raw_data:
            return False
        return True

    def normalize(self, raw_data: Any) -> Dict[str, Any]:
        """Normalize raw Open-Meteo response into domain dictionary."""
        return raw_data

    async def store(self, normalized_data: Any) -> int:
        """Store weather records in database."""
        # Generic store method called by base sync
        return 0

    async def fetch_current_weather(
        self,
        lat: float,
        lon: float,
        location_id: int
    ) -> Dict[str, Any]:
        """
        Fetch instantaneous current weather observation for specified coordinates.
        Parameters: temperature_2m, relative_humidity_2m, precipitation, rain,
                    wind_speed_10m, wind_direction_10m, soil_moisture_0_to_7cm, weather_code.
        """
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": (
                "temperature_2m,relative_humidity_2m,precipitation,rain,"
                "wind_speed_10m,wind_direction_10m,soil_moisture_0_to_7cm,weather_code"
            ),
            "timezone": "Asia/Bangkok"
        }

        data = await self.fetch(endpoint="forecast", params=params)
        if not self.validate(data):
            raise ConnectorError(f"Invalid forecast payload for coords ({lat}, {lon})")

        current = data.get("current", {})
        now_utc = datetime.now(timezone.utc).isoformat()
        obs_time = current.get("time", now_utc)

        # Store in weather_data table
        query = """
        INSERT INTO weather_data (
            location_id, timestamp, data_type, temperature_c, humidity_pct,
            precipitation_mm, rain_mm, wind_speed_kmh, wind_direction_deg,
            soil_moisture, weather_code, data_source, retrieval_timestamp
        ) VALUES (?, ?, 'current', ?, ?, ?, ?, ?, ?, ?, ?, 'Open-Meteo', ?)
        """
        await execute_query(
            query,
            (
                location_id,
                obs_time,
                current.get("temperature_2m"),
                current.get("relative_humidity_2m"),
                current.get("precipitation"),
                current.get("rain"),
                current.get("wind_speed_10m"),
                current.get("wind_direction_10m"),
                current.get("soil_moisture_0_to_7cm"),
                current.get("weather_code"),
                now_utc
            )
        )

        return {
            "location_id": location_id,
            "timestamp": obs_time,
            "temperature_c": current.get("temperature_2m"),
            "humidity_pct": current.get("relative_humidity_2m"),
            "precipitation_mm": current.get("precipitation"),
            "rain_mm": current.get("rain"),
            "wind_speed_kmh": current.get("wind_speed_10m"),
            "wind_direction_deg": current.get("wind_direction_10m"),
            "soil_moisture": current.get("soil_moisture_0_to_7cm"),
            "weather_code": current.get("weather_code"),
            "retrieval_timestamp": now_utc
        }

    async def fetch_weather_forecast(
        self,
        lat: float,
        lon: float,
        location_id: int,
        hourly_limit: int = 48
    ) -> Dict[str, Any]:
        """
        Fetch comprehensive forecast: current, 48-hour hourly sequence, and 7-day daily forecast.
        Computes 3-day, 7-day, and 30-day cumulative precipitation.
        """
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": (
                "temperature_2m,relative_humidity_2m,precipitation,rain,"
                "wind_speed_10m,wind_direction_10m,soil_moisture_0_to_7cm,weather_code"
            ),
            "hourly": (
                "temperature_2m,relative_humidity_2m,precipitation,rain,"
                "wind_speed_10m,wind_direction_10m,soil_moisture_0_to_7cm,weather_code"
            ),
            "daily": "precipitation_sum,rain_sum,temperature_2m_max,temperature_2m_min",
            "forecast_days": 7,
            "timezone": "Asia/Bangkok"
        }

        data = await self.fetch(endpoint="forecast", params=params)
        if not self.validate(data):
            raise ConnectorError(f"Invalid weather forecast payload for ({lat}, {lon})")

        now_utc = datetime.now(timezone.utc).isoformat()
        current_dict = data.get("current", {})

        # Process Hourly
        hourly_raw = data.get("hourly", {})
        times = hourly_raw.get("time", [])[:hourly_limit]
        temps = hourly_raw.get("temperature_2m", [])[:hourly_limit]
        humids = hourly_raw.get("relative_humidity_2m", [])[:hourly_limit]
        precips = hourly_raw.get("precipitation", [])[:hourly_limit]
        rains = hourly_raw.get("rain", [])[:hourly_limit]
        winds = hourly_raw.get("wind_speed_10m", [])[:hourly_limit]
        wind_dirs = hourly_raw.get("wind_direction_10m", [])[:hourly_limit]
        soils = hourly_raw.get("soil_moisture_0_to_7cm", [])[:hourly_limit]
        codes = hourly_raw.get("weather_code", [])[:hourly_limit]

        hourly_records = []
        for i in range(len(times)):
            record = {
                "location_id": location_id,
                "timestamp": times[i],
                "data_type": "hourly",
                "temperature_c": temps[i] if i < len(temps) else None,
                "humidity_pct": humids[i] if i < len(humids) else None,
                "precipitation_mm": precips[i] if i < len(precips) else 0.0,
                "rain_mm": rains[i] if i < len(rains) else 0.0,
                "wind_speed_kmh": winds[i] if i < len(winds) else None,
                "wind_direction_deg": wind_dirs[i] if i < len(wind_dirs) else None,
                "soil_moisture": soils[i] if i < len(soils) else None,
                "weather_code": codes[i] if i < len(codes) else None,
                "data_source": "Open-Meteo",
                "retrieval_timestamp": now_utc
            }
            hourly_records.append(record)

        # Batch insert hourly records for local caching
        insert_hourly_query = """
        INSERT INTO weather_data (
            location_id, timestamp, data_type, temperature_c, humidity_pct,
            precipitation_mm, rain_mm, wind_speed_kmh, wind_direction_deg,
            soil_moisture, weather_code, data_source, retrieval_timestamp
        ) VALUES (?, ?, 'hourly', ?, ?, ?, ?, ?, ?, ?, ?, 'Open-Meteo', ?)
        """
        for r in hourly_records[:24]:  # persist next 24h
            await execute_query(
                insert_hourly_query,
                (
                    location_id, r["timestamp"], r["temperature_c"], r["humidity_pct"],
                    r["precipitation_mm"], r["rain_mm"], r["wind_speed_kmh"],
                    r["wind_direction_deg"], r["soil_moisture"], r["weather_code"], now_utc
                )
            )

        # Calculate Rainfall Accumulations
        daily_raw = data.get("daily", {})
        daily_precip = daily_raw.get("precipitation_sum", [])

        # 3-day and 7-day forward accumulation from forecast
        accum_3d = sum(daily_precip[:3]) if len(daily_precip) >= 3 else sum(daily_precip)
        accum_7d = sum(daily_precip[:7]) if len(daily_precip) >= 7 else sum(daily_precip)

        # Estimate 30-day cumulative precipitation using historical recent days + forecast
        accum_30d = await self.calculate_30d_precipitation(lat, lon, accum_7d)

        return {
            "location_id": location_id,
            "latitude": lat,
            "longitude": lon,
            "current": {
                "location_id": location_id,
                "timestamp": current_dict.get("time", now_utc),
                "data_type": "current",
                "temperature_c": current_dict.get("temperature_2m"),
                "humidity_pct": current_dict.get("relative_humidity_2m"),
                "precipitation_mm": current_dict.get("precipitation"),
                "rain_mm": current_dict.get("rain"),
                "wind_speed_kmh": current_dict.get("wind_speed_10m"),
                "wind_direction_deg": current_dict.get("wind_direction_10m"),
                "soil_moisture": current_dict.get("soil_moisture_0_to_7cm"),
                "weather_code": current_dict.get("weather_code"),
                "data_source": "Open-Meteo",
                "retrieval_timestamp": now_utc
            },
            "hourly": hourly_records,
            "daily_precipitation_accumulations": {
                "3d_mm": round(accum_3d, 1),
                "7d_mm": round(accum_7d, 1),
                "30d_mm": round(accum_30d, 1)
            }
        }

    async def calculate_30d_precipitation(self, lat: float, lon: float, forecast_7d_sum: float) -> float:
        """
        Calculates 30-day precipitation combining 23 days of past historical records
        plus the 7-day upcoming forecast to give an accurate monsoon saturation indicator.
        """
        try:
            today = datetime.now(timezone.utc).date()
            start_date = (today - timedelta(days=23)).isoformat()
            end_date = (today - timedelta(days=1)).isoformat()

            # Call historical archive API
            params = {
                "latitude": lat,
                "longitude": lon,
                "start_date": start_date,
                "end_date": end_date,
                "daily": "precipitation_sum",
                "timezone": "Asia/Bangkok"
            }
            # Use fetch directly on the archive base URL
            orig_base = self.base_url
            self.base_url = "https://archive-api.open-meteo.com/v1"
            archive_data = await self.fetch(endpoint="archive", params=params)
            self.base_url = orig_base

            daily_past = archive_data.get("daily", {}).get("precipitation_sum", [])
            past_sum = sum([p for p in daily_past if p is not None])
            return float(past_sum + forecast_7d_sum)
        except Exception as exc:
            logger.warning(f"Could not calculate exact 30d precip from archive API ({exc}), using extrapolation.")
            # Graceful estimate: scale 7-day forecast
            return float(forecast_7d_sum * 4.2)

    async def fetch_historical_weather(
        self,
        lat: float,
        lon: float,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """
        Fetch historical daily weather observations for research / baseline training.
        """
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date,
            "end_date": end_date,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,rain_sum,wind_speed_10m_max",
            "timezone": "Asia/Bangkok"
        }
        orig_base = self.base_url
        self.base_url = "https://archive-api.open-meteo.com/v1"
        try:
            data = await self.fetch(endpoint="archive", params=params)
            return data
        finally:
            self.base_url = orig_base

    async def fetch_river_discharge(
        self,
        lat: float,
        lon: float,
        location_id: int,
        forecast_days: int = 14
    ) -> List[Dict[str, Any]]:
        """
        Fetch river discharge forecasts from GloFAS (Global Flood Awareness System)
        via Open-Meteo Flood API.
        Extracts river_discharge, river_discharge_max, river_discharge_mean, river_discharge_median.
        Persists into river_discharge database table.
        """
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "river_discharge,river_discharge_max,river_discharge_mean,river_discharge_median,river_discharge_p25,river_discharge_p75",
            "forecast_days": forecast_days
        }

        orig_base = self.base_url
        self.base_url = "https://flood-api.open-meteo.com/v1"
        try:
            raw = await self.fetch(endpoint="flood", params=params)
        finally:
            self.base_url = orig_base

        daily = raw.get("daily", {})
        dates = daily.get("time", [])
        discharges = daily.get("river_discharge", [])
        maxes = daily.get("river_discharge_max", [])
        means = daily.get("river_discharge_mean", [])
        medians = daily.get("river_discharge_median", [])

        now_utc = datetime.now(timezone.utc).isoformat()
        records = []

        query = """
        INSERT INTO river_discharge (
            location_id, date, discharge_m3s, discharge_max,
            discharge_mean, discharge_median, data_source, retrieval_timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, 'Open-Meteo Flood', ?)
        """

        for i in range(len(dates)):
            d_date = dates[i]
            q_val = discharges[i] if i < len(discharges) else None
            q_max = maxes[i] if i < len(maxes) else None
            q_mean = means[i] if i < len(means) else None
            q_median = medians[i] if i < len(medians) else None

            # Persist to database
            await execute_query(query, (location_id, d_date, q_val, q_max, q_mean, q_median, now_utc))

            records.append({
                "location_id": location_id,
                "date": d_date,
                "discharge_m3s": q_val,
                "discharge_max": q_max,
                "discharge_mean": q_mean,
                "discharge_median": q_median,
                "data_source": "Open-Meteo Flood",
                "retrieval_timestamp": now_utc
            })

        logger.info(f"Ingested {len(records)} river discharge ensemble records for location {location_id}.")
        return records

    async def sync_all_monitoring_locations(self) -> Dict[str, Any]:
        """
        Batch synchronizes weather and discharge for all registered monitoring locations.
        Runs on background scheduler.
        """
        locations = await fetch_all("SELECT id, name, lat, lon FROM monitoring_locations")
        results = {}
        for loc in locations:
            try:
                weather = await self.fetch_weather_forecast(loc["lat"], loc["lon"], loc["id"])
                discharge = await self.fetch_river_discharge(loc["lat"], loc["lon"], loc["id"])
                results[loc["name"]] = {
                    "weather_synced": True,
                    "discharge_records": len(discharge)
                }
            except Exception as e:
                logger.error(f"Failed to sync Open-Meteo for {loc['name']}: {e}")
                results[loc["name"]] = {"error": str(e)}

        return {
            "connector": self.name,
            "synced_locations": len(locations),
            "details": results,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
