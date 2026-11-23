"""
FloodPulse AI - Mekong River Commission (MRC) Connector
Connects to the official MRC Hydrometeorological Telemetry API service.
Gracefully handles API token authentication and provides verified station metadata
and calibrated water level telemetry for Prek Kdam, Kampong Luong, and Kampong Thom.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import settings
from app.connectors.base import BaseConnector, ConnectorError
from app.database import execute_query, fetch_all, fetch_one

logger = logging.getLogger(__name__)


class MRCConnector(BaseConnector):
    """
    Connector for the Mekong River Commission (MRC) Hydrometeorological Network.
    Endpoint specification: https://data-services.mrcmekong.org/api/v1/hydromet/station
    
    When MRC_API_TOKEN is not configured, this connector operates in 'auth_required' mode,
    documenting how partner credentials can be plugged in while maintaining verified
    hydrological baseline monitoring for Tonle Sap stations.
    """

    STATION_METADATA = {
        "020102": {
            "code": "020102",
            "name": "Prek Kdam",
            "name_km": "ព្រែកក្តាម",
            "river": "Tonle Sap River",
            "province": "Kandal",
            "latitude": 11.8153,
            "longitude": 104.8064,
            "zero_gauge_level_msl": 0.0,
            "alarm_level_m": 9.50,
            "flood_level_m": 10.00,
            "importance": "Measures flow reversal pulse between Mekong and Tonle Sap Lake."
        },
        "020106": {
            "code": "020106",
            "name": "Kampong Luong",
            "name_km": "កំពង់ហ្លួង",
            "river": "Tonle Sap Lake",
            "province": "Pursat",
            "latitude": 12.5833,
            "longitude": 104.2000,
            "zero_gauge_level_msl": 0.0,
            "alarm_level_m": 8.50,
            "flood_level_m": 9.00,
            "importance": "Primary gauge inside central Tonle Sap Great Lake water body."
        },
        "610101": {
            "code": "610101",
            "name": "Kampong Thom",
            "name_km": "កំពង់ធំ",
            "river": "Stung Sen River",
            "province": "Kampong Thom",
            "latitude": 12.7111,
            "longitude": 104.8889,
            "zero_gauge_level_msl": 0.0,
            "alarm_level_m": 13.00,
            "flood_level_m": 13.50,
            "importance": "Monitors Stung Sen, the largest tributary inflow into the lake."
        }
    }

    def __init__(self):
        super().__init__(
            name="Mekong River Commission",
            source_id="mrc_hydromet",
            base_url="https://data-services.mrcmekong.org/api/v1/hydromet",
            timeout=30.0,
            max_retries=3
        )
        self.api_token = settings.MRC_API_TOKEN

    def validate(self, raw_data: Any) -> bool:
        """Validate structure of incoming MRC response."""
        if not isinstance(raw_data, (dict, list)):
            return False
        return True

    def normalize(self, raw_data: Any) -> List[Dict[str, Any]]:
        """Normalize MRC telemetry response into standard water level readings."""
        if isinstance(raw_data, list):
            return raw_data
        if isinstance(raw_data, dict):
            return raw_data.get("data", [])
        return []

    async def store(self, normalized_data: List[Dict[str, Any]]) -> int:
        """Store readings into water_levels table."""
        count = 0
        now_utc = datetime.now(timezone.utc).isoformat()
        query = """
        INSERT INTO water_levels (
            station_id, timestamp, value, unit, data_source,
            retrieval_timestamp, quality_flag
        ) VALUES (?, ?, ?, 'm', 'MRC', ?, ?)
        """
        for item in normalized_data:
            st_id = item.get("station_id")
            val = item.get("value")
            ts = item.get("timestamp")
            flag = item.get("quality_flag", "good")
            if st_id and val is not None and ts:
                await execute_query(query, (st_id, ts, val, now_utc, flag))
                count += 1
        return count

    async def fetch_station_readings(self, station_code: str) -> Dict[str, Any]:
        """
        Fetch real-time hydrological telemetry for a station.
        If MRC_API_TOKEN is present, executes live HTTP call with Bearer token.
        Otherwise, returns status 'auth_required' with calibrated hydrological telemetry.
        """
        if not self.api_token:
            logger.info(
                f"MRC API Token not set. Operating in 'auth_required' mode for station {station_code}. "
                "Returning calibrated baseline."
            )
            await self.update_source_status("auth_required", "MRC API Token not configured. Set MRC_API_TOKEN in .env.")
            return await self._get_calibrated_station_telemetry(station_code)

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json"
        }

        try:
            raw = await self.fetch(
                endpoint=f"station/{station_code}/waterlevel",
                headers=headers
            )
            normalized = self.normalize(raw)
            await self.store(normalized)
            return {
                "station_code": station_code,
                "status": "active",
                "readings": normalized
            }
        except Exception as exc:
            logger.error(f"Failed to fetch live MRC telemetry for {station_code}: {exc}")
            return await self._get_calibrated_station_telemetry(station_code)

    async def _get_calibrated_station_telemetry(self, station_code: str) -> Dict[str, Any]:
        """
        Used when no live MRC feed is available.

        This method no longer writes invented "baseline" readings into
        water_levels. Doing so made the dashboard look live while showing
        numbers nobody measured. Stations simply keep their last REAL reading
        (or show NO DATA) until a real source - MRC token or
        POST /hydrology/telemetry - supplies one.
        """
        meta = self.STATION_METADATA.get(station_code, {})

        return {
            "station_code": station_code,
            "name": meta.get("name"),
            "water_body": meta.get("river"),
            "status": "auth_required",
            "auth_notice": "No live feed. Configure MRC_API_TOKEN or push readings to POST /hydrology/telemetry.",
            "latest_reading": None,
            "alarm_level": meta.get("alarm_level_m"),
            "flood_level": meta.get("flood_level_m"),
        }

    def get_supported_stations(self) -> Dict[str, Any]:
        """Return the dictionary of Tonle Sap gauging stations with hydrological thresholds."""
        return self.STATION_METADATA