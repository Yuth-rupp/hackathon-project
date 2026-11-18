export interface MonitoringLocation {
  id: string;
  name: string;
  name_km: string;
  province: string;
  lat: number;
  lon: number;
  type: 'province' | 'station';
  elevation_m?: number;
}

export const MONITORING_LOCATIONS: MonitoringLocation[] = [
  // 5 Key Provinces around Tonle Sap
  {
    id: 'siem-reap',
    name: 'Siem Reap',
    name_km: 'សៀមរាប',
    province: 'Siem Reap',
    lat: 13.3671,
    lon: 103.8448,
    type: 'province',
    elevation_m: 18,
  },
  {
    id: 'battambang',
    name: 'Battambang',
    name_km: 'បាត់ដំបង',
    province: 'Battambang',
    lat: 13.0957,
    lon: 103.2022,
    type: 'province',
    elevation_m: 16,
  },
  {
    id: 'pursat',
    name: 'Pursat',
    name_km: 'ពោធិ៍សាត់',
    province: 'Pursat',
    lat: 12.5388,
    lon: 103.9192,
    type: 'province',
    elevation_m: 17,
  },
  {
    id: 'kampong-chhnang',
    name: 'Kampong Chhnang',
    name_km: 'កំពង់ឆ្នាំង',
    province: 'Kampong Chhnang',
    lat: 12.25,
    lon: 104.6667,
    type: 'province',
    elevation_m: 12,
  },
  {
    id: 'kampong-thom',
    name: 'Kampong Thom',
    name_km: 'កំពង់ធំ',
    province: 'Kampong Thom',
    lat: 12.709,
    lon: 104.888,
    type: 'province',
    elevation_m: 14,
  },

  // 3 Primary Hydrological Stations
  {
    id: 'station-prek-kdam',
    name: 'Prek Kdam Hydrological Station',
    name_km: 'ស្ថានីយជលសាស្ត្រព្រែកក្តាម',
    province: 'Kandal / Tonle Sap River',
    lat: 11.8153,
    lon: 104.8064,
    type: 'station',
    elevation_m: 8.5,
  },
  {
    id: 'station-kampong-luong',
    name: 'Kampong Luong Floating Station',
    name_km: 'ស្ថានីយជលសាស្ត្រកំពង់ហ្លួង',
    province: 'Pursat / Tonle Sap Lake',
    lat: 12.2539,
    lon: 104.0486,
    type: 'station',
    elevation_m: 5.2,
  },
  {
    id: 'station-kampong-thom',
    name: 'Kampong Thom River Gauge',
    name_km: 'ស្ថានីយជលសាស្ត្រស្ទឹងសែន កំពង់ធំ',
    province: 'Kampong Thom / Stung Sen',
    lat: 12.7114,
    lon: 104.8886,
    type: 'station',
    elevation_m: 9.8,
  },
];

export const RISK_COLORS = {
  low: '#22c55e',
  moderate: '#f59e0b',
  high: '#f97316',
  very_high: '#ef4444',
} as const;

export const TONLE_SAP_CENTER: [number, number] = [12.9, 104.1];

export const TONLE_SAP_BBOX: [number, number, number, number] = [
  102.5, // minLon
  12.0,  // minLat
  105.5, // maxLon
  14.0,  // maxLat
];

export const API_BASE_URL: string =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

// JRC Global Surface Water WMS / WMTS / XYZ Layers
export const JRC_TILE_LAYERS = {
  occurrence: {
    name: 'Water Occurrence (1984-2021)',
    description: 'Frequency with which water was present on the surface',
    url: 'https://storage.googleapis.com/global-surface-water/tiles2021/occurrence/{z}/{x}/{y}.png',
    attribution: 'EC JRC / Google Earth Engine',
  },
  seasonality: {
    name: 'Water Seasonality',
    description: 'Months water was present during the year',
    url: 'https://storage.googleapis.com/global-surface-water/tiles2021/seasonality/{z}/{x}/{y}.png',
    attribution: 'EC JRC / Google Earth Engine',
  },
  recurrence: {
    name: 'Water Recurrence',
    description: 'Degree to which water recurs from year to year',
    url: 'https://storage.googleapis.com/global-surface-water/tiles2021/recurrence/{z}/{x}/{y}.png',
    attribution: 'EC JRC / Google Earth Engine',
  },
  transitions: {
    name: 'Water Transitions',
    description: 'Changes in water state between first and last periods',
    url: 'https://storage.googleapis.com/global-surface-water/tiles2021/transitions/{z}/{x}/{y}.png',
    attribution: 'EC JRC / Google Earth Engine',
  },
  extent: {
    name: 'Maximum Water Extent',
    description: 'Binary union of all detected water bodies',
    url: 'https://storage.googleapis.com/global-surface-water/tiles2021/extent/{z}/{x}/{y}.png',
    attribution: 'EC JRC / Google Earth Engine',
  },
};

export interface DataSourceItem {
  id: string;
  name: string;
  provider: string;
  type: 'Hydrology' | 'Satellite EO' | 'Meteorology' | 'Geospatial' | 'Elevation';
  updateFrequency: string;
  description: string;
  endpoint: string;
  status: 'operational' | 'nominal' | 'degraded';
}

export const DATA_SOURCES: DataSourceItem[] = [
  {
    id: 'open-meteo-flood',
    name: 'GloFAS River Discharge & Flood API',
    provider: 'Open-Meteo / ECMWF GloFAS v4.0',
    type: 'Hydrology',
    updateFrequency: 'Hourly reanalysis & 7-day forecast',
    description:
      'Seamless ensemble river discharge simulations calibrated for Mekong Basin tributaries and Tonle Sap reverse flow.',
    endpoint: 'https://flood-api.open-meteo.com/v1/flood',
    status: 'operational',
  },
  {
    id: 'open-meteo-weather',
    name: 'High-Resolution Weather & Precipitation Forecast',
    provider: 'Open-Meteo / DWD ICON & ECMWF IFS',
    type: 'Meteorology',
    updateFrequency: 'Hourly updates, 16-day forecast horizon',
    description:
      'Surface precipitation, atmospheric pressure, relative humidity, wind vectors, and convective rain indices over Cambodia.',
    endpoint: 'https://api.open-meteo.com/v1/forecast',
    status: 'operational',
  },
  {
    id: 'copernicus-sentinel',
    name: 'Copernicus Sentinel-1 SAR & Sentinel-2 MSI STAC',
    provider: 'European Space Agency (ESA) Copernicus Hub',
    type: 'Satellite EO',
    updateFrequency: 'Every 5 to 6 days repeat orbit',
    description:
      'Cloud-penetrating Synthetic Aperture Radar (SAR C-Band) VV/VH polarization for all-weather flood inundation delineation.',
    endpoint: 'https://earth-search.aws.element84.com/v1',
    status: 'operational',
  },
  {
    id: 'jrc-surface-water',
    name: 'JRC Global Surface Water (GSW)',
    provider: 'European Commission Joint Research Centre',
    type: 'Geospatial',
    updateFrequency: 'Multi-decadal baseline (38+ years archive)',
    description:
      'Historical monthly and yearly water history (1984–2021) at 30m resolution, identifying permanent vs seasonal pulse areas.',
    endpoint: 'https://global-surface-water.appspot.com',
    status: 'operational',
  },
  {
    id: 'odc-geodata',
    name: 'Cambodia Water Resources & Protected Wetlands',
    provider: 'Open Development Cambodia (ODC)',
    type: 'Geospatial',
    updateFrequency: 'Annual administrative updates',
    description:
      'Official commune boundaries, Ramsar conservation zones, floating village anchor areas, and national road vulnerability.',
    endpoint: 'https://data.opendevelopmentcambodia.net',
    status: 'operational',
  },
  {
    id: 'mrc-telemetry',
    name: 'Mekong River Commission Telemetric Gauge Portal',
    provider: 'Mekong River Commission (MRC)',
    type: 'Hydrology',
    updateFrequency: 'Daily 07:00 AM & Real-time gauges',
    description:
      'Water levels and discharge measurements from Prek Kdam, Kampong Luong, and Stung Sen hydro-stations.',
    endpoint: 'https://portal.mrcmekong.org/monitoring/river-monitoring-telemetry',
    status: 'operational',
  },
  {
    id: 'nasa-dem',
    name: 'FABDEM & SRTM Digital Elevation Model',
    provider: 'University of Bristol / NASA JPL',
    type: 'Elevation',
    updateFrequency: 'Static 30m bare-earth baseline',
    description:
      'Forest And Buildings removed Cop-DEM providing true hydraulic floodplain contours for depth hazard calculations.',
    endpoint: 'https://data.bris.ac.uk/data/dataset/25wfy0f9ukoge2gs7a5mqpq2gy',
    status: 'operational',
  },
];
