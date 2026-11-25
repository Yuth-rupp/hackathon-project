import { MonitoringLocation } from "@/lib/constants";

export type { MonitoringLocation };

// ============================================================
// GENERAL SYSTEM TYPES
// ============================================================

export type RiskLevel = "low" | "moderate" | "high" | "very_high";

export type FlowDirection = "reverse_inflow" | "normal_outflow" | "slack";

export type AlertSeverity = "info" | "warning" | "danger" | "critical";

export type SystemStatus = "operational" | "nominal" | "degraded" | "offline";

// ============================================================
// DASHBOARD KPI
// ============================================================

export interface DashboardKPIs {
  water_level_m: number;
  water_level_anomaly_m: number;
  inundation_area_km2: number;
  inundation_change_pct: number;
  lake_volume_bcm: number;
  flow_direction: FlowDirection;
  flow_rate_m3s: number;
  active_alerts_count: number;
  highest_risk_province: string;
  highest_risk_level: RiskLevel;
  last_updated: string;
}

// ============================================================
// WEATHER
// Real Open-Meteo weather observations and forecasts
// ============================================================

export interface WeatherData {
  location_id: string;
  location_name: string;

  temperature_c: number | null;
  precipitation_mm: number | null;
  precipitation_probability_pct: number | null;
  humidity_pct: number | null;
  wind_speed_kmh: number | null;
  wind_direction_deg: number | null;
  cloud_cover_pct: number | null;
  soil_moisture: number | null;

  weather_code: number | null;
  weather_description: string;

  timestamp: string;
  data_source: string;
  timezone: string;
}

export interface WeatherDailyForecast {
  date: string;

  temperature_max: number | null;
  temperature_min: number | null;

  precipitation_sum_mm: number | null;
  precipitation_probability_max: number | null;

  weather_code: number | null;
  weather_description: string;

  wind_speed_max_kmh: number | null;
}

export interface WeatherHourlyForecast {
  time: string;

  temperature_c: number | null;
  precipitation_mm: number | null;
  precipitation_probability_pct: number | null;
  relative_humidity_pct: number | null;
  cloud_cover_pct?: number | null;

  soil_moisture: number | null;

  soil_moisture_0_7cm: number | null;
  soil_moisture_7_28cm: number | null;
  soil_moisture_28_100cm: number | null;
}

export interface WeatherForecast {
  location_id: string;
  location_name: string;

  daily: WeatherDailyForecast[];
  hourly: WeatherHourlyForecast[];

  generated_at: string;
  data_source: string;
  timezone: string;
}

// ============================================================
// HISTORICAL RAINFALL
// ============================================================

export interface HistoricalRainfall {
  location_id: string;
  location_name: string;

  rainfall_30d_mm: number | null;

  start_date: string;
  end_date: string;

  data_source: string;
  retrieved_at: string;
}

// ============================================================
// RIVER DISCHARGE MONITORING
// Separate from hydrological gauge stations.
// Data source tables:
// monitoring_locations + river_discharge
// ============================================================

export interface DischargeForecastPoint {
  date: string;

  discharge_m3s: number | null;
  discharge_max: number | null;
  discharge_mean: number | null;
  discharge_median: number | null;

  data_source: string | null;
}

export type DischargeFlowStatus =
  | "NORMAL"
  | "HIGH"
  | "LOW"
  | "UNKNOWN"
  | "NO_DATA";

export interface RiverDischarge {
  location_id: number;
  location_name: string;
  province: string | null;

  current_discharge_m3s: number | null;
  historical_mean_m3s: number | null;
  anomaly_pct: number | null;

  flow_status: DischargeFlowStatus;

  forecast: DischargeForecastPoint[];

  data_sources: string[];
  updated_at: string | null;
}

// ============================================================
// HYDROLOGICAL GAUGE STATIONS
// Separate from discharge monitoring locations.
// Data source tables:
// stations + water_levels
// ============================================================

export type HydrologyStationStatus =
  | "NORMAL"
  | "WARNING"
  | "CRITICAL_FLOOD"
  | "NO_DATA";

export type DataFreshnessLevel =
  | "live"
  | "delayed"
  | "stale"
  | "baseline"
  | "no_data";

export interface Station {
  id: string;
  code: string;

  name: string;
  name_km: string | null;

  type: string | null;
  province: string | null;
  district: string | null;

  river: string | null;
  water_body: string | null;

  lat: number;
  lon: number;

  elevation: number | null;

  data_source: string | null;

  water_level_m: number | null;
  alarm_level_m: number | null;
  flood_level_m: number | null;

  last_reading_time: string | null;

  is_active: boolean;

  status: HydrologyStationStatus;

  pulse_flow_status: string | null;

  // Real-time metadata
  latest_data_source?: string | null;
  freshness?: DataFreshnessLevel;
  age_seconds?: number | null;

  // Optional compatibility fields
  discharge_m3s?: number | null;
  trend?: "rising" | "falling" | "stable" | "unknown";
}

// ============================================================
// HYDROLOGY TIME SERIES
// ============================================================

export interface HydrologyTimeSeriesPoint {
  timestamp: string;
  water_level_m: number | null;
  discharge_m3s: number | null;
  quality_flag: string;
}

export interface HydrologyStationComparison {
  station_id: number;
  station_code: string;
  station_name: string;
  river_name: string | null;
  timeseries: HydrologyTimeSeriesPoint[];
}

// ============================================================
// RISK ASSESSMENT
// ============================================================

export interface RiskFactor {
  score: number | null;
  weight: number;
  weighted_contribution: number | null;

  /** Extra values the engine stores per factor (rain_7d_mm, discharge_m3s, ...) */
  details?: Record<string, unknown>;
}

export type RiskFactorKey =
  | "rainfall"
  | "hydrology"
  | "soil"
  | "seasonal"
  | "historical";

export interface RiskAssessment {
  id: string;

  /** Slug used by the map and dashboard, e.g. "pursat" */
  location_id: string;

  /** Numeric database ID returned by the backend, e.g. 3 */
  backend_location_id?: number | null;

  location_name: string;
  location_name_km?: string;

  province: string;

  risk_level: RiskLevel;
  risk_score: number;

  primary_driver: string;
  factors: string[];
  recommended_actions: string[];

  contributing_factors?: Record<string, RiskFactor>;

  model_version?: string;
  model_type?: string;

  data_coverage_percent: number | null;
  data_status: string;

  /** Object from the backend: weather_*, discharge_*, water_level_* fields */
  data_freshness: Record<string, unknown>;

  explanation_en?: string;
  explanation_km?: string;

  assessment_date?: string;
  timestamp: string;
}

// ============================================================
// ALERTS
// ============================================================

export interface Alert {
  id: string;

  severity: AlertSeverity;

  title: string;
  title_km?: string;

  message: string;
  message_km?: string;

  location_id: string;
  location_name: string;
  province: string;

  category: "flood" | "hydrology" | "extreme_weather" | "infrastructure";

  issued_at: string;
  expires_at: string;

  status: "active" | "resolved";
}

// ============================================================
// SATELLITE DATA
// ============================================================

export interface SatelliteAcquisition {
  id: string;

  satellite: "Sentinel-1" | "Sentinel-2" | "Landsat-8" | "Landsat-9";

  /** Exact platform, e.g. "Sentinel-1A" or "Sentinel-1C" */
  platform_name?: string;

  /** When the satellite imaged the ground (ISO, UTC) */
  date: string;

  /** When the scene became available in the Copernicus catalog */
  published_at?: string;

  instrument: string;

  orbit_direction?: "ASCENDING" | "DESCENDING";
  relative_orbit?: number;
  polarization?: string;

  cloud_cover_pct: number;

  /** Null until the scene has actually been processed */
  water_extent_km2: number | null;

  processed: boolean;

  /** "live" = Copernicus answered just now, "cache" = served from local database */
  source: "live" | "cache";

  thumbnail_url: string;
  download_url: string;

  bbox: [number, number, number, number];
}

export interface SatelliteStatus {
  server_time: string;

  freshness: "fresh" | "aging" | "stale" | "unknown";

  latest_scene: {
    scene_id?: string | null;
    satellite: string;
    acquisition_date: string;
    published_at?: string | null;
    orbit_state?: string | null;
    relative_orbit?: number | null;
    age_hours: number;
  } | null;

  catalog: {
    last_successful_fetch?: string | null;
    last_error?: string | null;
    last_error_time?: string | null;
    source_status?: string | null;
    check_interval_minutes: number;
  };

  scenes_last_7d: number;
  scenes_last_30d: number;

  typical_revisit_hours?: number | null;

  /** Estimate from recent pass spacing, not an official schedule */
  estimated_next_pass?: string | null;
}

// ============================================================
// DATA SOURCES
// ============================================================

export interface DataSource {
  id: string;
  name: string;
  provider: string;
  type: string;
  updateFrequency: string;
  description: string;
  endpoint: string;

  status: "operational" | "nominal" | "degraded";

  lastPingMs?: number;
}

// ============================================================
// HISTORICAL FLOOD EVENTS
// ============================================================

export interface FloodEvent {
  id: string;
  year: number;
  title: string;

  provinces_affected: string[];

  peak_water_level_m: number;
  estimated_damage_usd: number;
  affected_population: number;
  duration_days: number;

  summary: string;
  significance: string;
}

// ============================================================
// COMMUNITY PROFILES
// ============================================================

export interface CommunityProfile {
  province: string;
  province_km: string;

  population: number;

  floating_villages_count: number;
  vulnerable_households: number;
  evacuation_shelters_count: number;

  main_livelihoods: string[];

  flood_preparedness_score: number;

  safe_zone_elevation_m: number;

  contact_hotline: string;
}

// ============================================================
// LIVE COMMUNITY RISK (GET /community/risk-live)
// ============================================================

export interface CommunityRiskFactor {
  name: string;
  label: string;
  score: number | null;
  weight: number | null;
  contribution: number | null;
}

export interface CommunityRiskModel {
  available: boolean;
  category: string | null;
  level: RiskLevel | null;
  score: number | null;
  primary_driver?: string | null;
  assessment_date?: string | null;
  age_minutes?: number | null;
  freshness: string;
  data_status?: string | null;
  data_coverage_percent?: number | null;
  explanation_en?: string;
  explanation_km?: string;
  model_version?: string;
  factors: CommunityRiskFactor[];
}

export interface CommunityRiskTrend {
  direction: "rising" | "falling" | "steady" | "unknown";
  delta: number | null;
  window_hours: number;
  points: { t: string; score: number }[];
}

export interface CommunityGauge {
  code: string;
  name: string;
  name_km: string | null;
  water_level_m: number | null;
  alarm_level_m: number | null;
  flood_level_m: number | null;
  status: string;
  freshness: string;
  age_seconds: number | null;
  timestamp: string | null;
  counts_for_risk: boolean;
}

export interface CommunityAlert {
  id: number;
  severity: string;
  title: string;
  title_km: string | null;
  message: string;
  message_km: string | null;
  status: string;
  trigger_source: string | null;
  created_at: string;
}

export interface CommunityAction {
  index: number;
  level: RiskLevel;
  category: string;
  code: string;
  label_en: string;
  label_km: string;
  guidance_en: string;
  driven_by: { source: string; level: string }[];
  escalated: boolean;
}

export interface CommunitySafeSite {
  name: string;
  name_km: string;
  type: string;
  group: "shelter" | "health" | "structure";
  capacity_people: number | null;
  elevation_m: number;
  lat: number;
  lon: number;
  posture: { code: string; label_en: string; label_km: string };
}

export interface CommunityDischarge {
  current_m3s: number | null;
  current_date: string | null;
  current_status: string;
  forecast_peak_m3s: number | null;
  forecast_peak_date: string | null;
  forecast_peak_status: string;
  source: string | null;
  retrieved_at: string | null;
  warning_m3s: number;
  alarm_m3s: number;
}

export interface CommunityFloodHistory {
  recorded_events: number;
  last_event_date: string | null;
  last_event_affected_people: number | null;
}

export interface CommunityProvinceRisk {
  location_id: number;
  key: string;
  name: string;
  name_km: string;
  province: string;
  province_code?: string | null;
  population?: number | null;
  vulnerable_communes?: number | null;
  elevation_m: number | null;
  risk: CommunityRiskModel;
  trend: CommunityRiskTrend;
  action: CommunityAction;
  gauges: CommunityGauge[];
  alerts: CommunityAlert[];
  discharge: CommunityDischarge;
  safe_sites: CommunitySafeSite[];
  shelter_capacity_people: number;
  flood_history: CommunityFloodHistory;
}

export interface CommunityBasinSummary {
  live_gauges: number;
  gauges_in_alarm: number;
  gauges_in_flood: number;
  newest_gauge_reading: string | null;
  open_alerts: number;
  provinces_total: number;
  provinces_at_alert_or_above: number;
  satellite: {
    last_pass: string | null;
    last_processed_pass: string | null;
    last_water_extent_km2: number | null;
  };
}

export interface CommunityRiskLive {
  generated_at: string;
  model_version: string;
  basin: CommunityBasinSummary;
  provinces: CommunityProvinceRisk[];
}
