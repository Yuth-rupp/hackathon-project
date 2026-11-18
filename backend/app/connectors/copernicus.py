"""
FloodPulse AI - Copernicus STAC Sentinel-1 Catalog Connector
Queries the Copernicus Data Space STAC catalog for Sentinel-1 Synthetic Aperture Radar (SAR)
acquisitions covering the Tonle Sap Lake basin in Cambodia.
Requires NO AUTH for catalog discovery and metadata access.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from app.config import settings
from app.connectors.base import BaseConnector, ConnectorError
from app.database import execute_query, fetch_all, fetch_one

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
        """Extract and normalize STAC features into satellite_acquisitions schema."""
        features = raw_data.get("features", [])
        normalized = []

        for f in features:
            props = f.get("properties", {})
            assets = f.get("assets", {})
            geometry = f.get("geometry", {})

            # Extract satellite platform (e.g., Sentinel-1A / Sentinel-1C)
            platform = props.get("platform", "Sentinel-1")
            if "sat:platform_international_designator" in props:
                platform = f"Sentinel-1 ({props['sat:platform_international_designator']})"

            # Extract acquisition datetime
            dt = props.get("datetime") or props.get("start_datetime") or datetime.now(timezone.utc).isoformat()

            # Orbit direction (Ascending / Descending)
            orbit_direction = (
                props.get("sat:orbit_state") or
                props.get("orbit_state") or
                props.get("sat:orbit_direction") or
                "DESCENDING"
            ).upper()

            # Instrument mode (e.g., IW, EW)
            mode = props.get("sar:instrument_mode", "IW")

            # Thumbnail / Quicklook Asset
            thumbnail_url = None
            if "thumbnail" in assets:
                thumbnail_url = assets["thumbnail"].get("href")
            elif "quicklook" in assets:
                thumbnail_url = assets["quicklook"].get("href")

            # STAC self link
            links = f.get("links", [])
            stac_url = None
            for link in links:
                if link.get("rel") == "self":
                    stac_url = link.get("href")
                    break

            normalized.append({
                "satellite": platform,
                "acquisition_date": dt,
                "collection": self.collection,
                "orbit_state": orbit_direction,
                "instrument_mode": mode,
                "bbox_geojson": json.dumps(geometry),
                "cloud_cover": 0.0,  # Radar SAR is unaffected by clouds
                "stac_url": stac_url or f"https://stac.dataspace.copernicus.eu/v1/collections/{self.collection}/items/{f.get('id', '')}",
                "thumbnail_url": thumbnail_url,
                "metadata_json": json.dumps({
                    "stac_id": f.get("id"),
                    "polarizations": props.get("sar:polarizations", ["VV", "VH"]),
                    "resolution": props.get("sar:resolution_range", 10.0),
                    "relative_orbit": props.get("sat:relative_orbit")
                })
            })

        return normalized

    async def store(self, normalized_data: List[Dict[str, Any]]) -> int:
        """Persist satellite acquisitions to database, avoiding duplicate scenes."""
        insert_count = 0
        now_utc = datetime.now(timezone.utc).isoformat()

        query = """
        INSERT INTO satellite_acquisitions (
            satellite, acquisition_date, collection, orbit_state,
            instrument_mode, bbox_geojson, cloud_cover, stac_url,
            thumbnail_url, processed, water_extent_km2, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?)
        """

        for item in normalized_data:
            # Check for existing scene by satellite and acquisition_date
            existing = await fetch_one(
                "SELECT id FROM satellite_acquisitions WHERE satellite = ? AND acquisition_date = ?",
                (item["satellite"], item["acquisition_date"])
            )
            if not existing:
                await execute_query(
                    query,
                    (
                        item["satellite"],
                        item["acquisition_date"],
                        item["collection"],
                        item["orbit_state"],
                        item["instrument_mode"],
                        item["bbox_geojson"],
                        item["cloud_cover"],
                        item["stac_url"],
                        item["thumbnail_url"],
                        item["metadata_json"]
                    )
                )
                insert_count += 1

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
                "limit": limit
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
            "SELECT * FROM satellite_acquisitions ORDER BY acquisition_date DESC LIMIT 1"
        )
        return row
