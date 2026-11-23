
"""
FloodPulse AI - Copernicus STAC Sentinel-1 Catalog Connector
Queries the Copernicus Data Space STAC catalog for Sentinel-1 Synthetic Aperture Radar (SAR)
acquisitions covering the Tonle Sap Lake basin in Cambodia.
Requires NO AUTH for catalog discovery and metadata access.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import aiosqlite

from app.config import settings
from app.connectors.base import BaseConnector, ConnectorError
from app.database import fetch_one, get_db_path
from app.services.satellite_catalog import parse_stac_feature, store_scene

logger = logging.getLogger(__name__)


class CopernicusSTACConnector(BaseConnector):
    """
    STAC Catalog client querying the European Space Agency's Copernicus Data Space Ecosystem.
    Specifically indexes Sentinel-1 C-band Synthetic Aperture Radar (SAR) Ground Range Detected (GRD)
    scenes. SAR penetrates cloud cover, making it the gold standard for monsoon flood monitoring.
    """

    def __init__(self):
        super().__init__(
            name="Copernicus STAC Sentinel-1",
            source_id="copernicus_stac",
            base_url="https://stac.dataspace.copernicus.eu/v1",
            timeout=35.0,
            max_retries=3
        )
        self.collection = settings.COPERNICUS_COLLECTION or "sentinel-1-grd"
        self.default_bbox = settings.TONLE_SAP_BBOX  # [102.5, 12.0, 105.5, 14.0]

    def validate(self, raw_data: Any) -> bool:
        """Validate that response adheres to STAC FeatureCollection specification."""
        if not isinstance(raw_data, dict):
            return False
        if raw_data.get("type") != "FeatureCollection":
            return False
        return "features" in raw_data

    def normalize(self, raw_data: Any) -> List[Dict[str, Any]]:
        """Normalize STAC features using the shared parser (same format as the API router)."""
        normalized = []
        for feature in raw_data.get("features", []):
            scene = parse_stac_feature(feature, self.collection)
            if scene:  # skips features without a usable acquisition time
                normalized.append(scene)
        return normalized

    async def store(self, normalized_data: List[Dict[str, Any]]) -> int:
        """Persist satellite acquisitions to database, avoiding duplicate scenes."""
        insert_count = 0

        async with aiosqlite.connect(get_db_path()) as db:
            for scene in normalized_data:
                if await store_scene(db, scene):
                    insert_count += 1
            await db.commit()

        logger.info(f"Stored {insert_count} new Sentinel-1 acquisitions from Copernicus STAC.")
        return insert_count

    async def search_acquisitions(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        bbox: Optional[List[float]] = None,
        limit: int = 25
    ) -> List[Dict[str, Any]]:
        """
        Query the Copernicus Data Space STAC /search endpoint.
        Uses POST with JSON search criteria adhering to STAC API 1.0.0.
        Results are requested newest-first.
        """
        bbox = bbox or self.default_bbox

        # Default to previous 30 days if no date range supplied
        if not end_date:
            end_date = datetime.now(timezone.utc).isoformat()
        if not start_date:
            past = datetime.now(timezone.utc) - timedelta(days=30)
            start_date = past.isoformat()

        datetime_range = f"{start_date}/{end_date}"

        payload = {
            "collections": [self.collection],
            "bbox": bbox,
            "datetime": datetime_range,
            "limit": limit,
            "sortby": [{"field": "properties.datetime", "direction": "desc"}],
            "query": {
                "sar:instrument_mode": {
                    "eq": "IW"
                }
            }
        }

        logger.info(f"Searching Copernicus STAC for collection {self.collection} between {datetime_range}...")

        try:
            raw = await self.fetch(
                endpoint="search",
                method="POST",
                json_body=payload
            )
        except Exception as exc:
            logger.warning(f"POST to STAC search returned {exc}. Falling back to GET search...")
            # Fallback to GET query parameters
            params = {
                "collections": self.collection,
                "bbox": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
                "datetime": datetime_range,
                "limit": limit,
                "sortby": "-properties.datetime"
            }
            raw = await self.fetch(endpoint="search", method="GET", params=params)

        if not self.validate(raw):
            logger.warning("STAC search response validation failed or returned empty catalog.")
            return []

        normalized = self.normalize(raw)
        await self.store(normalized)
        return normalized

    async def get_latest_acquisition(self) -> Optional[Dict[str, Any]]:
        """Retrieve the most recent satellite acquisition recorded in the system."""
        row = await fetch_one(
            "SELECT * FROM satellite_acquisitions "
            "WHERE COALESCE(collection, '') != 'admin_upload' "
            "ORDER BY acquisition_date DESC LIMIT 1"
        )
        return row
