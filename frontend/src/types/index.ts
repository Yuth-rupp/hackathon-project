import { MonitoringLocation } from '@/lib/constants';

export type { MonitoringLocation };

export type RiskLevel = 'low' | 'moderate' | 'high' | 'very_high';
export type FlowDirection = 'reverse_inflow' | 'normal_outflow' | 'slack';
export type AlertSeverity = 'info' | 'warning' | 'danger' | 'critical';
export type SystemStatus = 'operational' | 'nominal' | 'degraded' | 'offline';

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

export interface WeatherData {
  location_id: string;
  location_name: string;
  temperature_c: number;
  precipitation_mm: number;
  precipitation_probability_pct: number;
  humidity_pct: number;
  wind_speed_kmh: number;
  wind_direction_deg: number;
  cloud_cover_pct: number;
  weather_code: number;
  weather_description: string;
  timestamp: string;
}

export interface WeatherDailyForecast {
  date: string;
  temperature_max: number;
  temperature_min: number;
  precipitation_sum_mm: number;
  precipitation_probability_max: number;
  weather_code: number;
  weather_description: string;
  wind_speed_max_kmh: number;
}

export interface WeatherHourlyForecast {
  time: string;
  temperature_c: number;
  precipitation_mm: number;
  relative_humidity_pct: number;
}

export interface WeatherForecast {
  location_id: string;
  location_name: string;
  daily: WeatherDailyForecast[];
  hourly?: WeatherHourlyForecast[];
  generated_at: string;
}

export interface DischargeForecastPoint {
  date: string;
  discharge_m3s: number;
  discharge_median: number;
  discharge_p75?: number;
  discharge_p25?: number;
}

export interface RiverDischarge {
  station_id: string;
  station_name: string;
  current_discharge_m3s: number;
  historical_mean_m3s: number;
  anomaly_pct: number;
  flow_status: 'normal' | 'flooding' | 'low';
  forecast: DischargeForecastPoint[];
  updated_at: string;
}

export interface RiskAssessment {
  id: string;
  location_id: string;
  location_name: string;
  location_name_km?: string;
  province: string;
  risk_level: RiskLevel;
  risk_score: number; // 0-100
  hazard_score: number; // 0-100
  vulnerability_score: number; // 0-100
  exposure_score: number; // 0-100
  primary_driver: string;
  factors: string[];
  recommended_actions: string[];
  confidence_pct: number;
  timestamp: string;
}

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
  category: 'flood' | 'hydrology' | 'extreme_weather' | 'infrastructure';
  issued_at: string;
  expires_at: string;
  status: 'active' | 'resolved';
}

export interface SatelliteAcquisition {
  id: string;
  satellite: 'Sentinel-1' | 'Sentinel-2' | 'Landsat-8' | 'Landsat-9';
  date: string;
  instrument: string;
  orbit_direction?: 'ASCENDING' | 'DESCENDING';
  polarization?: string;
  cloud_cover_pct: number;
  water_extent_km2: number;
  thumbnail_url: string;
  download_url: string;
  bbox: [number, number, number, number];
}

export interface DataSource {
  id: string;
  name: string;
  provider: string;
  type: string;
  updateFrequency: string;
  description: string;
  endpoint: string;
  status: 'operational' | 'nominal' | 'degraded';
  lastPingMs?: number;
}

export interface Station {
  id: string;
  name: string;
  name_km: string;
  river: string;
  lat: number;
  lon: number;
  water_level_m: number;
  alarm_level_m: number;
  flood_level_m: number;
  discharge_m3s: number;
  trend: 'rising' | 'falling' | 'stable';
  last_reading_time: string;
  status: 'active' | 'maintenance' | 'offline';
}

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

export interface CommunityProfile {
  province: string;
  province_km: string;
  population: number;
  floating_villages_count: number;
  vulnerable_households: number;
  evacuation_shelters_count: number;
  main_livelihoods: string[];
  flood_preparedness_score: number; // 0 - 100
  safe_zone_elevation_m: number;
  contact_hotline: string;
}
