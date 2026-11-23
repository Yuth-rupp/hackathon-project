"""
FloodPulse AI - Application Configuration
Tonle Sap Lake Flood Monitoring Platform for Cambodia
"""

import os
from functools import lru_cache
from typing import Dict, List, Any
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    Uses Pydantic v2 Settings management.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )

    # Core Application Settings
    APP_NAME: str = "FloodPulse AI"
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "floodpulse_dev_key_tonlesap_2026"

    # Database
    DATABASE_PATH: str = "floodpulse.db"

    # CORS Allowed Origins
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173,*"

    @property
    def cors_origins_list(self) -> List[str]:
        """Convert comma-separated CORS origins into a list."""
        if not self.CORS_ORIGINS:
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    # ==========================================================================
    # Real External API Endpoints
    # ==========================================================================

    # Open-Meteo APIs (Free, high-resolution ECMWF / GFS weather & flood discharge models)
    OPEN_METEO_FORECAST_URL: str = "https://api.open-meteo.com/v1/forecast"
    OPEN_METEO_ARCHIVE_URL: str = "https://archive-api.open-meteo.com/v1/archive"
    OPEN_METEO_FLOOD_URL: str = "https://flood-api.open-meteo.com/v1/flood"

    # Copernicus Data Space STAC Catalog (Sentinel-1 SAR GRD search)
    COPERNICUS_STAC_URL: str = "https://stac.dataspace.copernicus.eu/v1/search"
    COPERNICUS_COLLECTION: str = "sentinel-1-grd"

    # JRC Global Surface Water (Google Cloud Public Storage)
    JRC_TILE_URL_TEMPLATE: str = (
        "https://storage.googleapis.com/global-surface-water/tiles2021/{layer}/{z}/{x}/{y}.png"
    )
    JRC_DOWNLOAD_URL_TEMPLATE: str = (
        "https://storage.googleapis.com/global-surface-water/downloads2021/{layer}/{layer}_100E_20N.tif"
    )

    # Open Development Cambodia CKAN Data API
    ODC_CKAN_API_URL: str = "https://data.opendevelopmentcambodia.net/api/3/action/package_search"

    # Mekong River Commission (MRC) Hydrological Services
    MRC_API_BASE_URL: str = "https://data-services.mrcmekong.org/api/v1/hydromet"
    MRC_API_TOKEN: str = ""

    # NASA FIRMS (Fire Information for Resource Management System)
    FIRMS_API_KEY: str = ""
    FIRMS_API_URL: str = "https://firms.modaps.eosdis.nasa.gov/api/country/csv"

    # Telegram Alert Integration
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    TELEGRAM_ALERTS_ENABLED: bool = False
    TELEGRAM_BOT_ENABLED: bool = False

    # Scheduler Settings
    SCHEDULER_ENABLED: bool = True
    WEATHER_REFRESH_INTERVAL_MINUTES: int = 60
    DISCHARGE_REFRESH_INTERVAL_HOURS: int = 6
    SATELLITE_CATALOG_CHECK_HOURS: int = 12  # legacy, no longer used by the scheduler
    SATELLITE_CATALOG_CHECK_MINUTES: int = 60  # how often Copernicus is polled for new scenes

    # Real-time hydrology
    GAUGE_REFRESH_INTERVAL_MINUTES: int = 15
    # A gauge reading newer than this is "live"; older than STALE is "stale".
    GAUGE_LIVE_MAX_AGE_MINUTES: int = 120
    GAUGE_STALE_AFTER_HOURS: int = 24
    # Secret for POST /hydrology/telemetry (sensors, data loggers, scripts).
    # Leave empty to disable the ingestion endpoint.
    TELEMETRY_API_KEY: str = ""

    # ==========================================================================
    # Geographic Domains & Presets
    # ==========================================================================

    # Tonle Sap Basin Bounding Box [min_lon, min_lat, max_lon, max_lat]
    TONLE_SAP_BBOX: List[float] = [102.5, 12.0, 105.5, 14.0]

    # Monitored Urban & Floodplain Centers around Tonle Sap
    MONITORING_LOCATIONS: Dict[str, Dict[str, Any]] = {
        "siem_reap": {
            "id": 1,
            "name": "Siem Reap",
            "name_km": "ក្រុងសៀមរាប",
            "province": "Siem Reap",
            "lat": 13.36,
            "lon": 103.86,
            "elevation_m": 18.0,
            "distance_to_lake_km": 12.5,
            "flood_frequency_score": 0.65,
            "type": "urban_floodplain"
        },
        "battambang": {
            "id": 2,
            "name": "Battambang",
            "name_km": "ក្រុងបាត់ដំបង",
            "province": "Battambang",
            "lat": 13.10,
            "lon": 103.20,
            "elevation_m": 16.0,
            "distance_to_lake_km": 38.0,
            "flood_frequency_score": 0.58,
            "type": "riverine_plain"
        },
        "pursat": {
            "id": 3,
            "name": "Pursat",
            "name_km": "ក្រុងពោធិ៍សាត់",
            "province": "Pursat",
            "lat": 12.54,
            "lon": 103.92,
            "elevation_m": 15.0,
            "distance_to_lake_km": 24.0,
            "flood_frequency_score": 0.72,
            "type": "tributary_delta"
        },
        "kampong_thom": {
            "id": 4,
            "name": "Kampong Thom",
            "name_km": "ក្រុងស្ទឹងសែន",
            "province": "Kampong Thom",
            "lat": 12.71,
            "lon": 104.89,
            "elevation_m": 12.0,
            "distance_to_lake_km": 18.0,
            "flood_frequency_score": 0.78,
            "type": "river_mouth"
        },
        "kampong_chhnang": {
            "id": 5,
            "name": "Kampong Chhnang",
            "name_km": "ក្រុងកំពង់ឆ្នាំង",
            "province": "Kampong Chhnang",
            "lat": 12.25,
            "lon": 104.67,
            "elevation_m": 11.0,
            "distance_to_lake_km": 8.0,
            "flood_frequency_score": 0.85,
            "type": "lake_outlet"
        }
    }

    # Hydrological stations monitored through the MRC data portal (keyed by MRC station code)
    STATION_CONFIGS: Dict[str, Dict[str, Any]] = {
        "020102": {
            "code": "020102",
            "name": "Prek Kdam",
            "name_km": "ព្រែកក្តាម",
            "type": "hydrological",
            "province": "Kandal",
            "district": "Ponhea Lueu",
            "lat": 11.8153,
            "lon": 104.8064,
            "elevation": 7.2,
            "water_body": "Tonle Sap River",
            "data_source": "MRC",
            "alarm_level": 9.5,
            "flood_level": 10.0,
            "notes": "Measures the critical pulse reversal between Mekong and Tonle Sap"
        },
        "020106": {
            "code": "020106",
            "name": "Kampong Luong",
            "name_km": "កំពង់ហ្លួង",
            "type": "lake_gauge",
            "province": "Pursat",
            "district": "Krakor",
            "lat": 12.5833,
            "lon": 104.2,
            "elevation": 5.0,
            "water_body": "Tonle Sap Lake",
            "data_source": "MRC",
            "alarm_level": 8.5,
            "flood_level": 9.0,
            "notes": "Primary gauge inside the central Great Lake body"
        },
        "610101": {
            "code": "610101",
            "name": "Kampong Thom",
            "name_km": "កំពង់ធំ",
            "type": "tributary_gauge",
            "province": "Kampong Thom",
            "district": "Stueng Saen",
            "lat": 12.7111,
            "lon": 104.8889,
            "elevation": 8.5,
            "water_body": "Stung Sen River",
            "data_source": "MRC",
            "alarm_level": 13.0,
            "flood_level": 13.5,
            "notes": "Monitors Stung Sen tributary inflow into Tonle Sap"
        }
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()