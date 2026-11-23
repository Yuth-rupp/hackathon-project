"""
FloodPulse AI - NASA FIRMS (Fire Information for Resource Management System) Connector
Connects to NASA EOSDIS FIRMS API to fetch VIIRS & MODIS active thermal anomalies and fire hotspots
across Cambodia (KHM) and Tonle Sap floodplain margins.
Active only if FIRMS_API_KEY is configured.
"""

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import settings
from app.connectors.base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)


class FIRMSConnector(BaseConnector):
    """
    Connector for NASA Earth Science Data FIRMS.
    Endpoint: https://firms.modaps.eosdis.nasa.gov/api/country/csv/{KEY}/VIIRS_SNPP_NRT/KHM/{days}
    
    Used to track seasonal floodplain drying, agricultural burning, and peatland fire risk
    around the Tonle Sap Biosphere Reserve during the dry season recession.
    """

    def __init__(self):
        super().__init__(
            name="NASA FIRMS",
            source_id="nasa_firms",
            base_url="https://firms.modaps.eosdis.nasa.gov/api/country/csv",
            timeout=30.0,
            max_retries=3
        )
        self.api_key = settings.FIRMS_API_KEY

    def validate(self, raw_data: Any) -> bool:
        """Validate that CSV data contains standard FIRMS header fields."""
        if not isinstance(raw_data, str):
            return False
        return "latitude" in raw_data and "longitude" in raw_data

    def normalize(self, raw_data: str) -> List[Dict[str, Any]]:
        """Parse raw CSV response into structured thermal hotspot records."""
        records = []
        reader = csv.DictReader(io.StringIO(raw_data))
        for row in reader:
            try:
                lat = float(row.get("latitude", 0))
                lon = float(row.get("longitude", 0))
                brightness = float(row.get("bright_ti4") or row.get("brightness", 0))
                scan = float(row.get("scan", 0))
                track = float(row.get("track", 0))
                acq_date = row.get("acq_date", "")
                acq_time = row.get("acq_time", "")
                confidence = row.get("confidence", "nominal")
                frp = float(row.get("frp", 0))  # Fire Radiative Power (MW)

                # Filter within or near Tonle Sap basin [102.5, 12.0, 105.5, 14.0]
                if 12.0 <= lat <= 14.0 and 102.5 <= lon <= 105.5:
                    records.append({
                        "latitude": lat,
                        "longitude": lon,
                        "brightness_k": brightness,
                        "fire_radiative_power_mw": frp,
                        "acquisition_date": acq_date,
                        "acquisition_time": acq_time,
                        "confidence": confidence,
                        "satellite": row.get("satellite", "VIIRS"),
                        "instrument": row.get("instrument", "VIIRS")
                    })
            except (ValueError, KeyError) as e:
                continue
        return records

    async def store(self, normalized_data: Any) -> int:
        return len(normalized_data)

    async def fetch_hotspots(self, days: int = 2) -> Dict[str, Any]:
        """
        Fetch active thermal anomaly hotspots for Cambodia (KHM) within the last N days (1-10).
        Requires a free NASA FIRMS MAP_KEY.
        """
        if not self.api_key:
            logger.info("NASA FIRMS API key not configured. Operating in 'key_required' mode.")
            await self.update_source_status("key_required", "FIRMS_API_KEY is not set in environment.")
            return {
                "status": "key_required",
                "notice": "Register for a free MAP KEY at https://firms.modaps.eosdis.nasa.gov/api/map_key/ and add FIRMS_API_KEY to .env",
                "hotspots": []
            }

        endpoint = f"{self.api_key}/VIIRS_SNPP_NRT/KHM/{days}"
        
        try:
            raw_csv = await self.fetch(endpoint=endpoint)
            if not self.validate(raw_csv):
                logger.warning("Invalid CSV returned by FIRMS API.")
                return {"status": "error", "hotspots": []}

            hotspots = self.normalize(raw_csv)
            logger.info(f"Retrieved {len(hotspots)} thermal anomalies in Tonle Sap basin from NASA FIRMS.")
            return {
                "status": "active",
                "days_requested": days,
                "total_hotspots_in_tonle_sap_basin": len(hotspots),
                "hotspots": hotspots
            }
        except Exception as exc:
            logger.error(f"Failed to query NASA FIRMS: {exc}")
            return {
                "status": "error",
                "error": str(exc),
                "hotspots": []
            }
