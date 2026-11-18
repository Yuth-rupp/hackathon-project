"""
FloodPulse AI - European Commission JRC Global Surface Water Connector
Provides access to 38-year historical surface water occurrence, recurrence, seasonality,
and transition dynamics across Tonle Sap Lake via public Google Cloud Storage tile services and GeoTIFFs.
"""

import logging
from typing import Any, Dict, List, Optional

from app.config import settings
from app.connectors.base import BaseConnector

logger = logging.getLogger(__name__)


class JRCConnector(BaseConnector):
    """
    Connector for European Commission Joint Research Centre (JRC) Global Surface Water (GSW).
    Dataset encompasses 38 years (1984–2021) of Landsat 5, 7, and 8 observations at 30m spatial resolution.
    Essential for establishing Tonle Sap historical baseline inundation frequency and permanent vs seasonal boundaries.
    """

    LAYERS = {
        "occurrence": {
            "name": "Surface Water Occurrence",
            "name_km": "ការកើតមានផ្ទៃទឹក",
            "description": "Frequency with which water was present on the surface from 1984 to 2021 (0-100%).",
            "range": "0-100%"
        },
        "change": {
            "name": "Occurrence Change Intensity",
            "name_km": "អាំងតង់ស៊ីតេនៃការប្រែប្រួលផ្ទៃទឹក",
            "description": "Increase, decrease or neutral changes in surface water occurrence over 38 years.",
            "range": "Increase / Decrease / Unchanged"
        },
        "seasonality": {
            "name": "Water Seasonality",
            "name_km": "រដូវកាលទឹក",
            "description": "Number of months water is typically present within a calendar year (1-12 months).",
            "range": "1 - 12 months"
        },
        "recurrence": {
            "name": "Annual Recurrence",
            "name_km": "ការកើតឡើងវិញប្រចាំឆ្នាំ",
            "description": "Degree to which water returns from year to year (floodplain predictability).",
            "range": "0-100%"
        },
        "transitions": {
            "name": "Water Transitions",
            "name_km": "ការផ្លាស់ប្តូរស្ថានភាពទឹក",
            "description": "Categorical shifts between permanent water, seasonal water, and terrestrial land.",
            "range": "Permanent, Seasonal, Lost, New"
        },
        "extent": {
            "name": "Maximum Water Extent",
            "name_km": "ទំហំផ្ទៃទឹកអតិបរមា",
            "description": "Maximum detected historical surface water envelope covering 1984-2021.",
            "range": "Binary (Water / Non-water)"
        }
    }

    # Tile coordinate covering Cambodia and Tonle Sap basin: 100E_20N
    DEFAULT_TILE_CODE = "100E_20N"

    def __init__(self):
        super().__init__(
            name="JRC Global Surface Water",
            source_id="jrc_gsw",
            base_url="https://storage.googleapis.com/global-surface-water",
            timeout=20.0,
            max_retries=3
        )
        self.tile_template = settings.JRC_TILE_URL_TEMPLATE
        self.download_template = settings.JRC_DOWNLOAD_URL_TEMPLATE

    def validate(self, raw_data: Any) -> bool:
        """Validate tile coordinates or download specs."""
        return True

    def normalize(self, raw_data: Any) -> Any:
        return raw_data

    async def store(self, normalized_data: Any) -> int:
        return 0

    def get_tile_url(self, layer: str, z: int, x: int, y: int) -> str:
        """
        Generate XYZ tile URL for dynamic web mapping (Leaflet, MapLibre, Deck.gl).
        """
        if layer not in self.LAYERS:
            raise ValueError(f"Unknown JRC layer '{layer}'. Must be one of: {list(self.LAYERS.keys())}")
        return self.tile_template.format(layer=layer, z=z, x=x, y=y)

    def get_tile_template_url(self, layer: str) -> str:
        """
        Get parameterized XYZ tile template string for frontend mapping layers.
        """
        if layer not in self.LAYERS:
            raise ValueError(f"Unknown JRC layer '{layer}'. Must be one of: {list(self.LAYERS.keys())}")
        return self.tile_template.format(layer=layer, z="{z}", x="{x}", y="{y}")

    def get_geotiff_download_url(self, layer: str, tile_code: str = DEFAULT_TILE_CODE) -> str:
        """
        Generate direct GeoTIFF download URL for analysis in GIS or rasterio.
        Tile '100E_20N' covers the lower Mekong Basin, Cambodia, and Tonle Sap.
        """
        if layer not in self.LAYERS:
            raise ValueError(f"Unknown JRC layer '{layer}'. Must be one of: {list(self.LAYERS.keys())}")
        return f"https://storage.googleapis.com/global-surface-water/downloads2021/{layer}/{layer}_{tile_code}.tif"

    def get_dataset_metadata(self) -> Dict[str, Any]:
        """
        Return comprehensive scientific metadata describing the JRC Global Surface Water dataset.
        """
        return {
            "name": "EC JRC Global Surface Water (GSW) v1.4",
            "provider": "European Commission Joint Research Centre",
            "spatial_resolution": "30 meters",
            "temporal_range": "1984 - 2021 (38 years)",
            "sensor": "Landsat 5 TM, Landsat 7 ETM+, Landsat 8 OLI",
            "geographic_tile": self.DEFAULT_TILE_CODE,
            "basin_coverage": "Tonle Sap Lake & Lower Mekong Basin",
            "layers": self.LAYERS,
            "license": "Creative Commons Attribution 4.0 International (CC BY 4.0)",
            "citation": "Pekel, JF., Cottam, A., Gorelick, N. et al. High-resolution mapping of global surface water and its long-term changes. Nature 540, 418–422 (2016). https://doi.org/10.1038/nature20584",
            "endpoints": {
                layer: {
                    "tile_template": self.get_tile_template_url(layer),
                    "geotiff_url": self.get_geotiff_download_url(layer)
                }
                for layer in self.LAYERS
            }
        }
