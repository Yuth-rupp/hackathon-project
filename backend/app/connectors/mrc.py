"""
FloodPulse AI - Mekong River Commission (MRC) Connector

Fetches REAL gauge water levels for Prek Kdam, Kampong Luong and Kampong Thom
and stores them in the water_levels table.

Rules:
- Nothing is ever invented. No token / no response / bad data => nothing stored.
- Readings are de-duplicated, range-checked and never future-dated.
- Every stored reading is broadcast to open browsers (SSE "station_reading").

The MRC endpoint path and response shape are configurable (see config.py:
MRC_WATERLEVEL_PATH) because the portal's response format must be confirmed
against the credentials you receive. The parser accepts the common JSON shapes.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import aiosqlite

from app.config import settings
from app.connectors.base import BaseConnector
from app.database import get_db_path

logger = logging.getLogger(__name__)

MIN_LEVEL_M = -5.0
MAX_LEVEL_M = 40.0

TIME_KEYS = ("timestamp", "datetime", "date_time", "time", "date", "measured_at", "observed_at")
VALUE_KEYS = ("value", "water_level_m", "water_level", "waterlevel", "level", "wl", "hh")
LIST_KEYS = ("data", "results", "readings", "items", "values", "records")


class MRCConnector(BaseConnector):
    """Connector for the Mekong River Commission hydromet network."""

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
            "importance": "Measures flow reversal pulse between Mekong and Tonle Sap Lake.",
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
            "importance": "Primary gauge inside central Tonle Sap Great Lake water body.",
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
            "importance": "Monitors Stung Sen, the largest tributary inflow into the lake.",
        },
    }

    def __init__(self):
        super().__init__(
            name="Mekong River Commission",
            source_id="mrc_hydromet",
            base_url=getattr(
                settings,
                "MRC_API_BASE_URL",
                "https://data-services.mrcmekong.org/api/v1/hydromet",
            ),
            timeout=30.0,
            max_retries=3,
        )
        self.api_token = settings.MRC_API_TOKEN

    # ------------------------------------------------------------------
    # BaseConnector interface
    # ------------------------------------------------------------------

    def validate(self, raw_data: Any) -> bool:
        return isinstance(raw_data, (dict, list))

    def normalize(self, raw_data: Any) -> List[Dict[str, Any]]:
        """Extract the list of reading objects from an MRC response."""
        if isinstance(raw_data, list):
            return [item for item in raw_data if isinstance(item, dict)]

        if isinstance(raw_data, dict):
            for key in LIST_KEYS:
                value = raw_data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
                if isinstance(value, dict):
                    nested = self.normalize(value)
                    if nested:
                        return nested

        return []

    async def store(self, normalized_data: List[Dict[str, Any]]) -> int:
        """
        Store pre-parsed readings: [{"station_code", "timestamp", "value"}].
        Returns the number of NEW rows written.
        """
        by_station: Dict[str, List[Dict[str, Any]]] = {}
        for item in normalized_data:
            code = item.get("station_code")
            if code:
                by_station.setdefault(str(code), []).append(item)

        total = 0
        for code, items in by_station.items():
            total += await self._store_readings(code, items)
        return total

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _naive_offset_hours() -> float:
        return float(getattr(settings, "MRC_NAIVE_TZ_OFFSET_HOURS", 7.0))

    def _parse_timestamp(self, value: Any) -> Optional[datetime]:
        if value is None:
            return None

        try:
            if isinstance(value, (int, float)):
                seconds = value / 1000 if value > 1e11 else value
                return datetime.fromtimestamp(seconds, tz=timezone.utc)

            parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except (ValueError, OverflowError, OSError):
            return None

        if parsed.tzinfo is None:
            # MRC publishes local (Indochina) time without a zone marker.
            parsed = parsed.replace(
                tzinfo=timezone(timedelta(hours=self._naive_offset_hours()))
            )

        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _first(item: Dict[str, Any], keys) -> Any:
        lowered = {str(k).lower(): v for k, v in item.items()}
        for key in keys:
            if key in lowered and lowered[key] is not None:
                return lowered[key]
        return None

    def parse_readings(self, raw: Any, station_code: str) -> List[Dict[str, Any]]:
        """Turn a raw MRC payload into clean, validated readings."""
        if not self.validate(raw):
            return []

        now = datetime.now(timezone.utc)
        clean: List[Dict[str, Any]] = []

        for item in self.normalize(raw):
            parsed_time = self._parse_timestamp(self._first(item, TIME_KEYS))
            raw_value = self._first(item, VALUE_KEYS)

            if parsed_time is None or raw_value is None:
                continue

            try:
                level = float(raw_value)
            except (TypeError, ValueError):
                continue

            if not (MIN_LEVEL_M <= level <= MAX_LEVEL_M):
                continue

            if parsed_time > now + timedelta(minutes=5):
                continue

            clean.append(
                {
                    "station_code": station_code,
                    "timestamp": parsed_time.isoformat(),
                    "value": round(level, 3),
                    "quality_flag": str(item.get("quality_flag") or item.get("quality") or "good"),
                }
            )

        return clean

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    async def _store_readings(self, station_code: str, readings: List[Dict[str, Any]]) -> int:
        if not readings:
            return 0

        now_iso = datetime.now(timezone.utc).isoformat()
        stored = 0
        events: List[Dict[str, Any]] = []

        async with aiosqlite.connect(get_db_path()) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute(
                "SELECT id, code FROM stations WHERE code = ? LIMIT 1",
                (station_code,),
            )
            station = await cursor.fetchone()

            if station is None:
                logger.warning("MRC: station code %s not found in stations table.", station_code)
                return 0

            for reading in readings:
                cursor = await db.execute(
                    """
                    SELECT 1 FROM water_levels
                    WHERE station_id = ? AND timestamp = ? AND data_source = 'MRC'
                    LIMIT 1
                    """,
                    (station["id"], reading["timestamp"]),
                )
                if await cursor.fetchone():
                    continue

                await db.execute(
                    """
                    INSERT INTO water_levels (
                        station_id, timestamp, value, unit, data_source,
                        retrieval_timestamp, quality_flag
                    ) VALUES (?, ?, ?, 'm', 'MRC', ?, ?)
                    """,
                    (
                        station["id"],
                        reading["timestamp"],
                        reading["value"],
                        now_iso,
                        reading["quality_flag"],
                    ),
                )
                stored += 1
                events.append(
                    {
                        "station_id": station["id"],
                        "station_code": station["code"],
                        "water_level_m": reading["value"],
                        "timestamp": reading["timestamp"],
                    }
                )

            await db.commit()

        if events:
            try:
                from app.services.realtime import broker  # lazy: avoids circular import

                for event in events:
                    broker.publish("station_reading", event)
            except Exception as exc:  # broadcasting must never break ingestion
                logger.warning("MRC: could not broadcast readings: %s", exc)

        return stored

    # ------------------------------------------------------------------
    # Public fetch API (used by fetch_gauge_job)
    # ------------------------------------------------------------------

    async def fetch_station_readings(self, station_code: str) -> Dict[str, Any]:
        """Fetch and store real readings for one station. Never invents data."""
        meta = self.STATION_METADATA.get(station_code, {})

        base = {
            "station_code": station_code,
            "name": meta.get("name"),
            "water_body": meta.get("river"),
            "alarm_level": meta.get("alarm_level_m"),
            "flood_level": meta.get("flood_level_m"),
        }

        if not self.api_token:
            await self.update_source_status(
                "auth_required",
                "MRC_API_TOKEN not set. Set it in .env or push readings to POST /hydrology/telemetry.",
            )
            return {
                **base,
                "status": "auth_required",
                "auth_notice": "No live feed. Configure MRC_API_TOKEN or push readings to POST /hydrology/telemetry.",
                "latest_reading": None,
                "stored": 0,
            }

        path_template = getattr(
            settings, "MRC_WATERLEVEL_PATH", "station/{code}/waterlevel"
        )

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
        }

        try:
            raw = await self.fetch(
                endpoint=path_template.format(code=station_code),
                headers=headers,
            )
            readings = self.parse_readings(raw, station_code)
            stored = await self._store_readings(station_code, readings)

            await self.update_source_status(
                "active",
                f"{stored} new reading(s) for {station_code}; {len(readings)} valid in response.",
            )

            return {
                **base,
                "status": "active",
                "stored": stored,
                "received": len(readings),
                "latest_reading": readings[-1] if readings else None,
            }

        except Exception as exc:
            logger.error("MRC fetch failed for %s: %s", station_code, exc)
            await self.update_source_status("error", f"MRC fetch failed for {station_code}: {exc}")
            return {
                **base,
                "status": "error",
                "error": str(exc),
                "stored": 0,
                "latest_reading": None,
            }

    async def fetch_all_stations(self) -> List[Dict[str, Any]]:
        results = []
        for code in self.STATION_METADATA:
            results.append(await self.fetch_station_readings(code))
        return results

    def get_supported_stations(self) -> Dict[str, Any]:
        return self.STATION_METADATA