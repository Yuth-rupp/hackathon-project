"""
FloodPulse AI - Pydantic v2 Request & Response Schemas
Type-safe models for all API endpoints, data ingestion pipelines, and ML inference.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict


# ==============================================================================
# 1. Gauging Stations & Water Level Models
# ==============================================================================

class StationBase(BaseModel):
    code: str = Field(..., description="Unique station identifier (e.g., MRC code)", examples=["020102"])
    name: str = Field(..., description="English name of station", examples=["Prek Kdam"])
    name_km: Optional[str] = Field(None, description="Khmer name of station", examples=["ព្រែកក្តាម"])
    type: Optional[str] = Field("hydrological", description="Station operational type", examples=["hydrological"])
    province: Optional[str] = Field(None, description="Province in Cambodia", examples=["Kandal"])
    district: Optional[str] = Field(None, description="District in Cambodia", examples=["Ponhea Lueu"])
    lat: float = Field(..., description="Latitude coordinate in WGS84", examples=[11.8153])
    lon: float = Field(..., description="Longitude coordinate in WGS84", examples=[104.8064])
    elevation: Optional[float] = Field(None, description="Station elevation in meters above MSL", examples=[7.2])
    water_body: Optional[str] = Field(None, description="Monitored body of water", examples=["Tonle Sap River"])
    data_source: Optional[str] = Field("MRC", description="Data provider or telemetry source", examples=["MRC"])
    alarm_level: Optional[float] = Field(None, description="Warning threshold level in meters", examples=[9.5])
    flood_level: Optional[float] = Field(None, description="Critical flood danger level in meters", examples=[10.0])
    is_active: bool = Field(True, description="Whether the station is currently monitored")
    metadata_json: Optional[str] = Field(None, description="JSON metadata string for custom attributes")


class StationResponse(StationBase):
    id: int = Field(..., description="Database primary key id", examples=[1])
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    latest_water_level: Optional[float] = Field(None, description="Most recent water level reading in meters", examples=[7.42])
    latest_reading_time: Optional[str] = Field(None, description="Timestamp of most recent reading")
    status: Optional[str] = Field("normal", description="Current status: normal, alarm, flood", examples=["normal"])

    model_config = ConfigDict(from_attributes=True)


class WaterLevelReading(BaseModel):
    id: Optional[int] = Field(None, description="Reading record ID", examples=[101])
    station_id: int = Field(..., description="Station foreign key ID", examples=[1])
    station_code: Optional[str] = Field(None, description="Station identifier code", examples=["020102"])
    station_name: Optional[str] = Field(None, description="Station display name", examples=["Prek Kdam"])
    timestamp: str = Field(..., description="ISO8601 observation timestamp", examples=["2026-11-18T00:00:00Z"])
    value: float = Field(..., description="Recorded water level in specified unit", examples=[7.85])
    unit: str = Field("m", description="Measurement unit (meters)", examples=["m"])
    data_source: Optional[str] = Field("MRC", description="Data provider", examples=["MRC"])
    retrieval_timestamp: Optional[str] = Field(None, description="Time ingested into FloodPulse")
    quality_flag: Optional[str] = Field("good", description="Quality validation flag (good, suspicious, interpolated)")

    model_config = ConfigDict(from_attributes=True)


class WaterLevelCreateRequest(BaseModel):
    station_id: int = Field(..., description="Target station ID")
    timestamp: str = Field(..., description="Observation timestamp in ISO8601")
    value: float = Field(..., description="Water level in meters")
    unit: str = Field("m", description="Unit of measurement")
    data_source: Optional[str] = Field("telemetry", description="Telemetry or manual upload source")
    quality_flag: Optional[str] = Field("good", description="Data quality classification")


# ==============================================================================
# 2. Weather & Meteorological Models (Open-Meteo)
# ==============================================================================

class WeatherDataResponse(BaseModel):
    id: Optional[int] = Field(None, description="Weather record ID")
    location_id: int = Field(..., description="Monitored location ID", examples=[1])
    location_name: Optional[str] = Field(None, description="Name of location", examples=["Siem Reap"])
    timestamp: str = Field(..., description="Time of observation or forecast", examples=["2026-11-18T03:00:00Z"])
    data_type: Optional[str] = Field("current", description="Type: current, hourly, daily, historical")
    temperature_c: Optional[float] = Field(None, description="2m Air Temperature in Celsius", examples=[29.4])
    humidity_pct: Optional[float] = Field(None, description="Relative Humidity percentage", examples=[78.0])
    precipitation_mm: Optional[float] = Field(None, description="Precipitation depth in mm", examples=[12.4])
    rain_mm: Optional[float] = Field(None, description="Liquid rain depth in mm", examples=[12.4])
    wind_speed_kmh: Optional[float] = Field(None, description="10m Wind speed in km/h", examples=[14.2])
    wind_direction_deg: Optional[float] = Field(None, description="Wind direction in degrees", examples=[210.0])
    soil_moisture: Optional[float] = Field(None, description="Volumetric soil water 0-7cm (m³/m³)", examples=[0.38])
    weather_code: Optional[int] = Field(None, description="WMO weather interpretation code", examples=[61])
    data_source: Optional[str] = Field("Open-Meteo", description="Data provider")
    retrieval_timestamp: Optional[str] = Field(None, description="Ingestion timestamp")

    model_config = ConfigDict(from_attributes=True)


class WeatherForecastResponse(BaseModel):
    location_id: int
    location_name: str
    latitude: float
    longitude: float
    current: WeatherDataResponse
    hourly: List[WeatherDataResponse] = Field(default_factory=list, description="48-hour outlook")
    daily_precipitation_accumulations: Dict[str, float] = Field(
        default_factory=dict,
        description="Accumulated rainfall (3d_mm, 7d_mm, 30d_mm)",
        examples=[{"3d_mm": 45.2, "7d_mm": 110.5, "30d_mm": 320.0}]
    )


# ==============================================================================
# 3. River Discharge Models (GloFAS / Open-Meteo Flood)
# ==============================================================================

class RiverDischargeResponse(BaseModel):
    id: Optional[int] = Field(None, description="Discharge record ID")
    location_id: int = Field(..., description="Monitored location ID", examples=[1])
    location_name: Optional[str] = Field(None, description="Location display name", examples=["Siem Reap"])
    date: str = Field(..., description="Discharge date (YYYY-MM-DD)", examples=["2026-11-18"])
    discharge_m3s: Optional[float] = Field(None, description="Discharge in m³/s", examples=[450.2])
    discharge_max: Optional[float] = Field(None, description="Ensemble maximum discharge m³/s", examples=[510.0])
    discharge_mean: Optional[float] = Field(None, description="Ensemble mean discharge m³/s", examples=[440.0])
    discharge_median: Optional[float] = Field(None, description="Ensemble median discharge m³/s", examples=[435.0])
    data_source: Optional[str] = Field("Open-Meteo Flood", description="Discharge forecast provider")
    retrieval_timestamp: Optional[str] = Field(None, description="Ingestion time")

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 4. Disaster & Historical Flood Event Models (ODC / NDMC)
# ==============================================================================

class FloodEventResponse(BaseModel):
    id: int = Field(..., description="Disaster record ID", examples=[1])
    event_date: Optional[str] = Field(None, description="Event start date", examples=["2020-10-06"])
    end_date: Optional[str] = Field(None, description="Event conclusion date", examples=["2020-10-28"])
    province: Optional[str] = Field(None, description="Affected Cambodian province", examples=["Pursat"])
    district: Optional[str] = Field(None, description="Affected district", examples=["Krakor"])
    commune: Optional[str] = Field(None, description="Affected commune", examples=["All"])
    deaths: int = Field(0, description="Reported human casualties", examples=[14])
    affected_people: int = Field(0, description="Number of individuals impacted", examples=[25000])
    houses_damaged: int = Field(0, description="Partially damaged homes", examples=[4800])
    houses_destroyed: int = Field(0, description="Completely destroyed homes", examples=[320])
    crop_area_ha: float = Field(0.0, description="Flooded agricultural area in hectares", examples=[18500.0])
    economic_loss_usd: float = Field(0.0, description="Estimated economic loss in USD", examples=[12500000.0])
    data_source: Optional[str] = Field("ODC", description="Disaster database provenance")
    source_event_id: Optional[str] = Field(None, description="External incident catalog identifier")
    notes: Optional[str] = Field(None, description="Qualitative storm or meteorologic description")

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 5. Satellite Earth Observation Models (Sentinel-1 SAR / Copernicus STAC)
# ==============================================================================

class SatelliteAcquisitionResponse(BaseModel):
    id: Optional[int] = Field(None, description="Acquisition database ID")
    satellite: str = Field(..., description="Platform identifier", examples=["Sentinel-1A"])
    acquisition_date: str = Field(..., description="Acquisition datetime in UTC", examples=["2026-11-15T22:50:12Z"])
    collection: Optional[str] = Field("sentinel-1-grd", description="STAC collection name")
    orbit_state: Optional[str] = Field(None, description="Orbit direction: ASCENDING or DESCENDING", examples=["DESCENDING"])
    instrument_mode: Optional[str] = Field("IW", description="Sensor mode (IW = Interferometric Wide)")
    bbox_geojson: Optional[str] = Field(None, description="GeoJSON polygon or bounding box coordinates")
    cloud_cover: Optional[float] = Field(0.0, description="Cloud cover percentage (0% for radar SAR)")
    stac_url: Optional[str] = Field(None, description="STAC item URL for metadata inspection")
    thumbnail_url: Optional[str] = Field(None, description="Quicklook thumbnail image URL")
    processed: int = Field(0, description="Processing status (0=pending, 1=analyzed)")
    water_extent_km2: Optional[float] = Field(None, description="Calculated surface water extent in km²", examples=[2850.4])
    processed_geojson_path: Optional[str] = Field(None, description="Path to extracted flood polygon geojson")
    metadata_json: Optional[str] = Field(None, description="Raw STAC metadata serialized as JSON")

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 6. Predictive Flood Risk Assessment Models (ML)
# ==============================================================================

class RiskAssessmentResponse(BaseModel):
    id: Optional[int] = Field(None, description="Risk assessment ID")
    location_id: int = Field(..., description="Monitored location ID", examples=[1])
    location_name: Optional[str] = Field(None, description="Location name", examples=["Siem Reap"])
    province: Optional[str] = Field(None, description="Province name", examples=["Siem Reap"])
    assessment_date: str = Field(..., description="Date of assessment", examples=["2026-11-18"])
    prediction_horizon_days: int = Field(7, description="Forecast window (e.g., 3, 7, 14 days)", examples=[7])
    risk_probability: float = Field(..., description="Calibrated flood probability (0.0 to 1.0)", examples=[0.42])
    risk_category: str = Field(..., description="Category: low, medium, high, severe", examples=["medium"])
    model_version: Optional[str] = Field("FloodPulse-XGB-v1.2", description="Inference model identifier")
    model_type: Optional[str] = Field("Ensemble-Hydrological", description="Architecture paradigm")
    contributing_factors: Optional[Dict[str, float]] = Field(
        default_factory=dict,
        description="Feature importances (upstream discharge, rainfall, soil saturation)",
        examples=[{"soil_moisture": 0.35, "upstream_discharge": 0.45, "forecast_rain_7d": 0.20}]
    )
    confidence_info: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Confidence bounds and uncertainty intervals"
    )
    created_at: Optional[str] = Field(None, description="Timestamp of inference")

    model_config = ConfigDict(from_attributes=True)


class RiskAssessmentCreateRequest(BaseModel):
    location_id: int = Field(..., description="Target location ID")
    prediction_horizon_days: int = Field(7, ge=1, le=30, description="Forecast window in days")
    risk_probability: float = Field(..., ge=0.0, le=1.0, description="Assessed probability")
    risk_category: str = Field(..., description="Risk tier: low, medium, high, severe")
    model_version: str = Field("manual-or-external", description="Model identifier")
    contributing_factors: Optional[Dict[str, float]] = Field(default_factory=dict)


# ==============================================================================
# 7. Emergency Alert Models (Telegram / Push)
# ==============================================================================

class AlertResponse(BaseModel):
    id: int = Field(..., description="Alert ID", examples=[1])
    alert_type: str = Field(..., description="Type: water_level_alarm, flash_flood, severe_rain", examples=["water_level_alarm"])
    severity: str = Field(..., description="Severity level: info, warning, danger, critical", examples=["warning"])
    title: str = Field(..., description="English alert title", examples=["Prek Kdam Approaching Warning Level"])
    title_km: Optional[str] = Field(None, description="Khmer alert title", examples=["ព្រែកក្តាម ជិតដល់កម្រិតប្រកាសអាសន្ន"])
    message: str = Field(..., description="English detailed advisory text")
    message_km: Optional[str] = Field(None, description="Khmer detailed advisory text")
    location_id: Optional[int] = Field(None, description="Associated location ID")
    province: Optional[str] = Field(None, description="Affected Cambodian province", examples=["Kandal"])
    trigger_source: Optional[str] = Field("hydrology_sensor", description="Source that triggered alert")
    trigger_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Raw parameters that breached threshold")
    status: str = Field("active", description="Status: active, resolved, dismissed", examples=["active"])
    telegram_sent: bool = Field(False, description="Whether alert was broadcasted to Telegram")
    telegram_message_id: Optional[str] = Field(None, description="Telegram message ID")
    created_at: str = Field(..., description="Issuance timestamp")
    resolved_at: Optional[str] = Field(None, description="Resolution timestamp")
    created_by: str = Field("system", description="Issuer (system or user)")

    model_config = ConfigDict(from_attributes=True)


class AlertCreateRequest(BaseModel):
    alert_type: str = Field(..., description="Type of alert", examples=["water_level_alarm"])
    severity: str = Field(..., description="Severity: info, warning, danger, critical", examples=["danger"])
    title: str = Field(..., description="Advisory title in English", examples=["High Flood Risk In Krakor"])
    title_km: Optional[str] = Field(None, description="Advisory title in Khmer", examples=["ការប្រកាសអាសន្នទឹកជំនន់នៅស្រុកក្រគរ"])
    message: str = Field(..., description="Advisory message body in English")
    message_km: Optional[str] = Field(None, description="Advisory message body in Khmer")
    location_id: Optional[int] = Field(None, description="Monitored location ID")
    province: Optional[str] = Field(None, description="Cambodian province")
    trigger_source: Optional[str] = Field("manual_operator", description="Origin of alert")
    trigger_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Diagnostic triggering parameters")
    broadcast_telegram: bool = Field(False, description="Flag to dispatch immediately to Telegram channel")


# ==============================================================================
# 8. Data Source Health & Connector Auditing Models
# ==============================================================================

class DataSourceStatusResponse(BaseModel):
    id: int = Field(..., description="Data source registry ID", examples=[1])
    name: str = Field(..., description="Source system name", examples=["Open-Meteo Weather Forecast"])
    provider: str = Field(..., description="Managing organization", examples=["Open-Meteo"])
    api_endpoint: Optional[str] = Field(None, description="Public endpoint URL")
    data_type: Optional[str] = Field(None, description="Domain type (meteorological, hydrological, satellite)")
    geographic_coverage: Optional[str] = Field(None, description="Spatial boundaries covered")
    temporal_coverage: Optional[str] = Field(None, description="Temporal depth and horizon")
    update_frequency: Optional[str] = Field(None, description="Polling schedule")
    license: Optional[str] = Field(None, description="Data license")
    status: str = Field("unknown", description="Status: active, degraded, auth_required, error", examples=["active"])
    last_successful_fetch: Optional[str] = Field(None, description="Timestamp of latest successful ingestion")
    last_error: Optional[str] = Field(None, description="Description of latest error encountered")
    last_error_time: Optional[str] = Field(None, description="Timestamp of latest error")

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 9. Monitoring Locations
# ==============================================================================

class MonitoringLocationResponse(BaseModel):
    id: int = Field(..., description="Location identifier", examples=[1])
    name: str = Field(..., description="English name", examples=["Siem Reap"])
    name_km: Optional[str] = Field(None, description="Khmer name", examples=["ក្រុងសៀមរាប"])
    type: Optional[str] = Field(None, description="Topological zone type", examples=["urban_floodplain"])
    province: str = Field(..., description="Province", examples=["Siem Reap"])
    lat: float = Field(..., description="Latitude", examples=[13.36])
    lon: float = Field(..., description="Longitude", examples=[103.86])
    elevation_m: Optional[float] = Field(None, description="Mean elevation in meters", examples=[18.0])
    distance_to_lake_km: Optional[float] = Field(None, description="Distance to Tonle Sap shore in km", examples=[12.5])
    flood_frequency_score: Optional[float] = Field(None, description="Historical flood susceptibility (0-1)", examples=[0.65])
    boundary_geojson_path: Optional[str] = Field(None, description="Relative path to boundary GeoJSON")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 10. Executive Dashboard KPI Aggregation
# ==============================================================================

class DashboardKPIResponse(BaseModel):
    lake_surface_water_extent_km2: float = Field(..., description="Current detected Tonle Sap water area in km²", examples=[2750.0])
    water_extent_change_30d_pct: float = Field(..., description="30-day percentage expansion/contraction", examples=[14.5])
    active_critical_alerts_count: int = Field(0, description="Active emergency warnings", examples=[1])
    monitored_stations_count: int = Field(..., description="Total active gauging stations", examples=[3])
    stations_in_alarm: int = Field(0, description="Stations exceeding warning threshold", examples=[0])
    stations_in_flood: int = Field(0, description="Stations exceeding flood threshold", examples=[0])
    high_risk_provinces: List[str] = Field(default_factory=list, description="Provinces currently in High or Severe risk", examples=[["Pursat", "Kampong Thom"]])
    mean_basin_soil_moisture_pct: float = Field(..., description="Average soil saturation percentage around lake", examples=[42.8])
    last_satellite_pass_utc: Optional[str] = Field(None, description="Timestamp of most recent Sentinel-1 SAR acquisition", examples=["2026-11-15T22:50:12Z"])
    data_sources_healthy: int = Field(..., description="Number of active online data feeds", examples=[5])
    total_data_sources: int = Field(..., description="Total registered data sources", examples=[7])
    system_timestamp_utc: str = Field(..., description="Server timestamp in UTC")


# ==============================================================================
# 11. Generic Operation / Health Responses
# ==============================================================================

class HealthCheckResponse(BaseModel):
    status: str = Field("healthy", examples=["healthy"])
    app_name: str = Field("FloodPulse AI", examples=["FloodPulse AI"])
    environment: str = Field("development", examples=["development"])
    database_connected: bool = Field(True, examples=[True])
    database_path: str = Field(..., examples=["floodpulse.db"])
    scheduler_running: bool = Field(True, examples=[True])
    active_sources_count: int = Field(..., examples=[6])
    timestamp_utc: str = Field(...)


class ApiResponse(BaseModel):
    success: bool = True
    message: str = "Operation completed successfully"
    data: Optional[Any] = None