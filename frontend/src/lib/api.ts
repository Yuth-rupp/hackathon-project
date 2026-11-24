import {
  API_BASE_URL,
  MONITORING_LOCATIONS,
  DATA_SOURCES,
  TONLE_SAP_BBOX,
} from "@/lib/constants";

import {
  Alert,
  CommunityProfile,
  CommunityRiskLive,
  DashboardKPIs,
  DataSource,
  FloodEvent,
  RiskAssessment,
  RiverDischarge,
  SatelliteAcquisition,
  SatelliteStatus,
  Station,
  WeatherDailyForecast,
  WeatherData,
  WeatherForecast,
  WeatherHourlyForecast,
} from "@/types";

// ============================================================
// INTERFACES
// ============================================================

export interface WeatherRainfallAccumulation {
  location_id: string;
  location_name: string;
  rainfall_3d_mm: number | null;
  rainfall_7d_mm: number | null;
  rainfall_30d_mm: number | null;
  rainfall_30d_start: string | null;
  rainfall_30d_end: string | null;
  soil_saturation_index: number | null;
  flood_threat_level: string;
  data_source: string;
  retrieved_at: string;
}

export interface WeatherSoilMoisture {
  location_id: string;
  location_name: string;
  topsoil_moisture_0_7cm: number | null;
  root_zone_moisture_7_28cm: number | null;
  deep_moisture_28_100cm: number | null;
  timestamp: string | null;
  data_source: string;
}

export interface SatelliteProcessResult {
  scene_id: string;
  water_extent_km2: number;
  covered_area_km2: number;
  water_fraction: number;
  confidence: "good" | "low";
  band: string;
}

export interface SatelliteSearchMeta {
  source: "cache" | "live";
  provider?: string;
  error?: string;
}

// ============================================================
// HELPER FUNCTIONS
// ============================================================

function toNullableNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }

  const parsed = Number(value);

  return Number.isFinite(parsed) ? parsed : null;
}

function toSafeString(value: unknown, fallback = ""): string {
  if (value === null || value === undefined) {
    return fallback;
  }

  return String(value);
}

async function readErrorMessage(
  response: Response,
  fallback: string,
): Promise<string> {
  try {
    const body = await response.json();

    if (body?.detail) {
      return String(body.detail);
    }

    if (body?.message) {
      return String(body.message);
    }
  } catch {
    // Use fallback message.
  }

  return fallback;
}

// ============================================================
// WEATHER CODE
// ============================================================

export function decodeWeatherCode(code: number): string {
  switch (code) {
    case 0:
      return "Clear sky";

    case 1:
      return "Mainly clear";

    case 2:
      return "Partly cloudy";

    case 3:
      return "Overcast";

    case 45:
    case 48:
      return "Fog / Depositing rime fog";

    case 51:
    case 53:
    case 55:
      return "Drizzle (Light/Mod/Dense)";

    case 61:
    case 63:
    case 65:
      return "Monsoon Rain (Slight to Heavy)";

    case 80:
    case 81:
    case 82:
      return "Torrential Rain Showers";

    case 95:
      return "Thunderstorm with heavy squall";

    case 96:
    case 99:
      return "Severe Thunderstorm with Hail";

    default:
      return "Tropical weather";
  }
}

// ============================================================
// DASHBOARD KPIs
// ============================================================

export async function fetchDashboardKPIs(): Promise<DashboardKPIs> {
  try {
    const response = await fetch(`${API_BASE_URL}/kpis`, {
      cache: "no-store",
    });

    if (response.ok) {
      const data = await response.json();

      if (
        data &&
        !Array.isArray(data) &&
        typeof data.water_level_m === "number" &&
        typeof data.water_level_anomaly_m === "number" &&
        typeof data.inundation_area_km2 === "number" &&
        typeof data.inundation_change_pct === "number" &&
        typeof data.lake_volume_bcm === "number" &&
        typeof data.flow_rate_m3s === "number" &&
        typeof data.active_alerts_count === "number" &&
        typeof data.highest_risk_province === "string" &&
        typeof data.last_updated === "string"
      ) {
        return data as DashboardKPIs;
      }

      throw new Error("Unexpected dashboard KPI response.");
    }
  } catch (error) {
    console.warn("Dashboard KPI API unavailable:", error);
  }

  // External source is used only for river discharge.
  try {
    const prekKdam =
      MONITORING_LOCATIONS.find(
        (location) => location.id === "station-prek-kdam",
      ) ?? MONITORING_LOCATIONS[0];

    if (prekKdam) {
      const floodResponse = await fetch(
        `https://flood-api.open-meteo.com/v1/flood?latitude=${prekKdam.lat}&longitude=${prekKdam.lon}&daily=river_discharge,river_discharge_mean,river_discharge_median&forecast_days=7`,
        { cache: "no-store" },
      );

      if (floodResponse.ok) {
        const floodData = await floodResponse.json();
        const dischargeToday = floodData.daily?.river_discharge?.[0];

        if (
          typeof dischargeToday === "number" &&
          Number.isFinite(dischargeToday)
        ) {
          return {
            water_level_m: 7.82,
            water_level_anomaly_m: 0.45,
            inundation_area_km2: 8420.5,
            inundation_change_pct: 3.4,
            lake_volume_bcm: 38.6,
            flow_direction:
              dischargeToday > 2500 ? "reverse_inflow" : "normal_outflow",
            flow_rate_m3s: Math.round(dischargeToday),
            active_alerts_count: 2,
            highest_risk_province: "Kampong Chhnang",
            highest_risk_level: "moderate",
            last_updated: new Date().toISOString(),
          };
        }
      }
    }
  } catch (error) {
    console.warn("Open-Meteo flood fallback unavailable:", error);
  }

  // Demo baseline values from the original project.
  return {
    water_level_m: 7.65,
    water_level_anomaly_m: 0.32,
    inundation_area_km2: 8120.0,
    inundation_change_pct: 2.1,
    lake_volume_bcm: 36.4,
    flow_direction: "reverse_inflow",
    flow_rate_m3s: 3420,
    active_alerts_count: 1,
    highest_risk_province: "Pursat",
    highest_risk_level: "moderate",
    last_updated: new Date().toISOString(),
  };
}

// ============================================================
// CURRENT WEATHER
// ============================================================

async function fetchWeatherCurrentFromBackend(
  locationId: string,
): Promise<WeatherData> {
  const response = await fetch(
    `${API_BASE_URL}/weather/current/${encodeURIComponent(locationId)}`,
    { cache: "no-store" },
  );

  if (!response.ok) {
    throw new Error(`Current weather failed: HTTP ${response.status}`);
  }

  const item = await response.json();

  return {
    location_id: String(item.location_id),
    location_name: String(item.location_name ?? locationId),
    temperature_c: item.temperature_c ?? null,
    precipitation_mm: item.precipitation_mm ?? null,
    precipitation_probability_pct: item.precipitation_probability_pct ?? null,
    humidity_pct: item.humidity_pct ?? null,
    wind_speed_kmh: item.wind_speed_kmh ?? null,
    wind_direction_deg: item.wind_direction_deg ?? null,
    cloud_cover_pct: item.cloud_cover_pct ?? null,
    soil_moisture: item.soil_moisture ?? null,
    weather_code: item.weather_code ?? null,
    weather_description: String(item.condition ?? "Unavailable"),
    timestamp: String(item.timestamp ?? ""),
    data_source: String(item.data_source ?? "Open-Meteo"),
    timezone: String(item.timezone ?? "Asia/Phnom_Penh"),
  };
}

// ============================================================
// WEATHER FORECAST
// ============================================================

async function fetchWeatherForecastFromBackend(
  locationId: string,
): Promise<WeatherForecast> {
  const response = await fetch(
    `${API_BASE_URL}/weather/forecast/${encodeURIComponent(locationId)}`,
    { cache: "no-store" },
  );

  if (!response.ok) {
    throw new Error(`Weather forecast failed: HTTP ${response.status}`);
  }

  const item = await response.json();

  return {
    location_id: String(item.location_id),
    location_name: String(item.location_name ?? locationId),

    daily: (item.daily ?? []).map((day: any) => ({
      date: String(day.date),
      temperature_max: day.temp_max_c ?? null,
      temperature_min: day.temp_min_c ?? null,
      precipitation_sum_mm: day.precipitation_sum_mm ?? null,
      precipitation_probability_max: day.precipitation_probability_max ?? null,
      weather_code: day.weather_code ?? null,
      weather_description: String(day.condition ?? "Unavailable"),
      wind_speed_max_kmh: day.wind_speed_max_kmh ?? null,
    })),

    hourly: (item.hourly ?? []).map((hour: any) => ({
      time: String(hour.time),
      temperature_c: hour.temperature_c ?? null,
      precipitation_mm: hour.precipitation_mm ?? null,
      precipitation_probability_pct: hour.precipitation_probability ?? null,
      relative_humidity_pct: hour.relative_humidity_pct ?? null,
      cloud_cover_pct: hour.cloud_cover_pct ?? null,
      soil_moisture_0_7cm: hour.soil_moisture_0_7cm ?? null,
      soil_moisture_7_28cm: hour.soil_moisture_7_28cm ?? null,
      soil_moisture_28_100cm: hour.soil_moisture_28_100cm ?? null,
    })),

    generated_at: String(item.retrieved_at ?? ""),
    data_source: String(item.data_source ?? "Open-Meteo"),
    timezone: String(item.timezone ?? "Asia/Phnom_Penh"),
  };
}

// ============================================================
// RAINFALL ACCUMULATION
// ============================================================

async function fetchWeatherRainfallAccumulationFromBackend(
  locationId: string,
): Promise<WeatherRainfallAccumulation> {
  const response = await fetch(
    `${API_BASE_URL}/weather/rainfall-accumulation/${encodeURIComponent(locationId)}`,
    { cache: "no-store" },
  );

  if (!response.ok) {
    throw new Error(`Rainfall request failed: HTTP ${response.status}`);
  }

  const item = await response.json();

  return {
    location_id: String(item.location_id),
    location_name: String(item.location_name ?? locationId),
    rainfall_3d_mm: item.rainfall_3d_mm ?? null,
    rainfall_7d_mm: item.rainfall_7d_mm ?? null,
    rainfall_30d_mm: item.rainfall_30d_mm ?? null,
    rainfall_30d_start: item.rainfall_30d_start ?? null,
    rainfall_30d_end: item.rainfall_30d_end ?? null,
    soil_saturation_index: item.soil_saturation_index ?? null,
    flood_threat_level: String(item.flood_threat_level ?? "Unavailable"),
    data_source: String(item.data_source ?? "Open-Meteo"),
    retrieved_at: String(item.retrieved_at ?? ""),
  };
}

// ============================================================
// SOIL MOISTURE
// ============================================================

async function fetchWeatherSoilMoistureFromBackend(
  locationId: string,
): Promise<WeatherSoilMoisture> {
  const response = await fetch(
    `${API_BASE_URL}/weather/soil-moisture/${encodeURIComponent(locationId)}`,
    { cache: "no-store" },
  );

  if (!response.ok) {
    throw new Error(`Soil moisture request failed: HTTP ${response.status}`);
  }

  const item = await response.json();

  return {
    location_id: String(item.location_id),
    location_name: String(item.location_name ?? locationId),
    topsoil_moisture_0_7cm: item.topsoil_moisture_0_7cm ?? null,
    root_zone_moisture_7_28cm: item.root_zone_moisture_7_28cm ?? null,
    deep_moisture_28_100cm: item.deep_moisture_28_100cm ?? null,
    timestamp: item.timestamp ?? null,
    data_source: String(item.data_source ?? "Open-Meteo"),
  };
}

// ============================================================
// DIRECT OPEN-METEO (browser -> Open-Meteo, backend as fallback)
//
// Open-Meteo limits requests per IP address. A shared hosting server
// quickly hits that limit (HTTP 429), but every visitor's own browser has
// its own IP, so the browser asks Open-Meteo directly. If that fails, the
// FloodPulse backend (MET Norway / NASA POWER fallback) is used instead.
// ============================================================

const OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast";
const OPEN_METEO_TIMEZONE = "Asia/Phnom_Penh";
const OPEN_METEO_CACHE_MS = 5 * 60 * 1000; // Open-Meteo itself updates ~every 15 min
const OPEN_METEO_PAST_CACHE_MS = 30 * 60 * 1000;
const OPEN_METEO_SOURCE_LABEL = "Open-Meteo (live, direct)";
const SOIL_POROSITY_M3M3 = 0.48;

interface OpenMeteoBundle {
  current: Record<string, any>;
  hourly: Record<string, any[]>;
  daily: Record<string, any[]>;
}

const openMeteoCache = new Map<string, { at: number; promise: Promise<any> }>();

function cachedOpenMeteoJson<T>(
  key: string,
  params: Record<string, string>,
  ttlMs: number,
  validate: (json: any) => boolean,
): Promise<T> {
  const cached = openMeteoCache.get(key);

  if (cached && Date.now() - cached.at < ttlMs) {
    return cached.promise as Promise<T>;
  }

  const query = new URLSearchParams(params).toString();

  const promise = fetch(`${OPEN_METEO_FORECAST_URL}?${query}`, {
    cache: "no-store",
  }).then(async (response) => {
    if (!response.ok) {
      throw new Error(`Open-Meteo HTTP ${response.status}`);
    }

    const json = await response.json();

    if (!validate(json)) {
      throw new Error("Open-Meteo returned incomplete data");
    }

    return json as T;
  });

  openMeteoCache.set(key, { at: Date.now(), promise });

  // Never keep a failed request in the cache.
  promise.catch(() => {
    if (openMeteoCache.get(key)?.promise === promise) {
      openMeteoCache.delete(key);
    }
  });

  return promise;
}

function normalizeKey(value: unknown): string {
  return String(value ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
}

function findProvinceLocation(locationId: string): any | null {
  const wanted = normalizeKey(locationId);

  const match = (MONITORING_LOCATIONS as any[]).find(
    (loc) =>
      normalizeKey(loc.id) === wanted || normalizeKey(loc.name) === wanted,
  );

  if (
    !match ||
    !Number.isFinite(Number(match.lat)) ||
    !Number.isFinite(Number(match.lon))
  ) {
    return null;
  }

  return match;
}

function fetchOpenMeteoBundle(
  lat: number,
  lon: number,
): Promise<OpenMeteoBundle> {
  return cachedOpenMeteoJson<OpenMeteoBundle>(
    `bundle:${lat.toFixed(3)},${lon.toFixed(3)}`,
    {
      latitude: String(lat),
      longitude: String(lon),
      current:
        "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,wind_direction_10m,cloud_cover",
      hourly:
        "temperature_2m,precipitation,precipitation_probability,relative_humidity_2m,cloud_cover,soil_moisture_0_to_7cm,soil_moisture_7_to_28cm,soil_moisture_28_to_100cm",
      daily:
        "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max",
      forecast_days: "7",
      timezone: OPEN_METEO_TIMEZONE,
    },
    OPEN_METEO_CACHE_MS,
    (json) => Boolean(json?.current && json?.hourly?.time && json?.daily?.time),
  );
}

function valueAt(series: unknown, index: number): number | null {
  if (!Array.isArray(series) || index < 0 || index >= series.length) {
    return null;
  }

  return toNullableNumber(series[index]);
}

/** Index of the hourly entry for the current local hour (or the next one). */
function currentHourIndex(bundle: OpenMeteoBundle): number {
  const times: string[] = (bundle.hourly.time ?? []).map(String);
  const key = String(bundle.current.time ?? "").slice(0, 13);

  const exact = times.findIndex((t) => t.slice(0, 13) === key);
  if (exact >= 0) return exact;

  const next = times.findIndex((t) => t.slice(0, 13) >= key);
  return next >= 0 ? next : 0;
}

// ---------------- current weather ----------------

export async function fetchWeatherCurrent(
  locationId: string,
): Promise<WeatherData> {
  const loc = findProvinceLocation(locationId);

  if (loc) {
    try {
      const bundle = await fetchOpenMeteoBundle(
        Number(loc.lat),
        Number(loc.lon),
      );

      const cur = bundle.current;
      const hourIndex = currentHourIndex(bundle);
      const code = toNullableNumber(cur.weather_code);

      return {
        location_id: String(loc.id),
        location_name: String(loc.name ?? locationId),
        temperature_c: toNullableNumber(cur.temperature_2m),
        precipitation_mm: toNullableNumber(cur.precipitation),
        precipitation_probability_pct: valueAt(
          bundle.hourly.precipitation_probability,
          hourIndex,
        ),
        humidity_pct: toNullableNumber(cur.relative_humidity_2m),
        wind_speed_kmh: toNullableNumber(cur.wind_speed_10m),
        wind_direction_deg: toNullableNumber(cur.wind_direction_10m),
        cloud_cover_pct: toNullableNumber(cur.cloud_cover),
        soil_moisture: valueAt(bundle.hourly.soil_moisture_0_to_7cm, hourIndex),
        weather_code: code,
        weather_description:
          code === null ? "Unavailable" : decodeWeatherCode(code),
        timestamp: String(cur.time ?? ""),
        data_source: OPEN_METEO_SOURCE_LABEL,
        timezone: OPEN_METEO_TIMEZONE,
      };
    } catch (err) {
      console.warn("Open-Meteo direct request failed, using backend:", err);
    }
  }

  return fetchWeatherCurrentFromBackend(locationId);
}

// ---------------- forecast ----------------

export async function fetchWeatherForecast(
  locationId: string,
): Promise<WeatherForecast> {
  const loc = findProvinceLocation(locationId);

  if (loc) {
    try {
      const bundle = await fetchOpenMeteoBundle(
        Number(loc.lat),
        Number(loc.lon),
      );

      const dailyTimes: string[] = (bundle.daily.time ?? []).map(String);
      const hourlyTimes: string[] = (bundle.hourly.time ?? []).map(String);
      const start = currentHourIndex(bundle);
      const end = Math.min(start + 48, hourlyTimes.length);

      const daily: WeatherDailyForecast[] = dailyTimes
        .slice(0, 7)
        .map((date, i) => {
          const code = valueAt(bundle.daily.weather_code, i);

          return {
            date,
            temperature_max: valueAt(bundle.daily.temperature_2m_max, i),
            temperature_min: valueAt(bundle.daily.temperature_2m_min, i),
            precipitation_sum_mm: valueAt(bundle.daily.precipitation_sum, i),
            precipitation_probability_max: valueAt(
              bundle.daily.precipitation_probability_max,
              i,
            ),
            weather_code: code,
            weather_description:
              code === null ? "Unavailable" : decodeWeatherCode(code),
            wind_speed_max_kmh: valueAt(bundle.daily.wind_speed_10m_max, i),
          };
        });

      const hourly: WeatherHourlyForecast[] = [];

      for (let i = start; i < end; i++) {
        const topsoil = valueAt(bundle.hourly.soil_moisture_0_to_7cm, i);

        hourly.push({
          time: hourlyTimes[i],
          temperature_c: valueAt(bundle.hourly.temperature_2m, i),
          precipitation_mm: valueAt(bundle.hourly.precipitation, i),
          precipitation_probability_pct: valueAt(
            bundle.hourly.precipitation_probability,
            i,
          ),
          relative_humidity_pct: valueAt(bundle.hourly.relative_humidity_2m, i),
          cloud_cover_pct: valueAt(bundle.hourly.cloud_cover, i),
          soil_moisture: topsoil,
          soil_moisture_0_7cm: topsoil,
          soil_moisture_7_28cm: valueAt(
            bundle.hourly.soil_moisture_7_to_28cm,
            i,
          ),
          soil_moisture_28_100cm: valueAt(
            bundle.hourly.soil_moisture_28_to_100cm,
            i,
          ),
        });
      }

      if (daily.length > 0 && hourly.length > 0) {
        return {
          location_id: String(loc.id),
          location_name: String(loc.name ?? locationId),
          daily,
          hourly,
          generated_at: new Date().toISOString(),
          data_source: OPEN_METEO_SOURCE_LABEL,
          timezone: OPEN_METEO_TIMEZONE,
        };
      }
    } catch (err) {
      console.warn("Open-Meteo direct request failed, using backend:", err);
    }
  }

  return fetchWeatherForecastFromBackend(locationId);
}

// ---------------- rainfall accumulation (3 / 7 / 30 day) ----------------

export async function fetchWeatherRainfallAccumulation(
  locationId: string,
): Promise<WeatherRainfallAccumulation> {
  const loc = findProvinceLocation(locationId);

  if (loc) {
    try {
      const lat = Number(loc.lat);
      const lon = Number(loc.lon);

      const [bundle, past] = await Promise.all([
        fetchOpenMeteoBundle(lat, lon),
        cachedOpenMeteoJson<{
          daily: { time: string[]; precipitation_sum: any[] };
        }>(
          `past30:${lat.toFixed(3)},${lon.toFixed(3)}`,
          {
            latitude: String(lat),
            longitude: String(lon),
            daily: "precipitation_sum",
            past_days: "30",
            forecast_days: "1",
            timezone: OPEN_METEO_TIMEZONE,
          },
          OPEN_METEO_PAST_CACHE_MS,
          (json) =>
            Array.isArray(json?.daily?.time) &&
            Array.isArray(json?.daily?.precipitation_sum),
        ),
      ]);

      // past_days=30 + today: drop today (last entry) -> 30 completed days.
      const pastTimes = past.daily.time.slice(0, -1);
      const pastValues = past.daily.precipitation_sum.slice(0, -1);
      const validPast = pastValues
        .map((v) => toNullableNumber(v))
        .filter((v): v is number => v !== null);

      const rainfall30d =
        pastTimes.length > 0 && validPast.length >= pastTimes.length * 0.8
          ? Math.round(validPast.reduce((a, b) => a + b, 0) * 10) / 10
          : null;

      const dailySums = (bundle.daily.precipitation_sum ?? []).map((v) =>
        toNullableNumber(v),
      );
      const sumFirst = (n: number): number | null => {
        const slice = dailySums.slice(0, n);
        if (slice.length === 0 || slice.some((v) => v === null)) return null;
        return (
          Math.round(slice.reduce<number>((a, b) => a + (b ?? 0), 0) * 10) / 10
        );
      };

      const rain7d = sumFirst(7);
      const topsoil = valueAt(
        bundle.hourly.soil_moisture_0_to_7cm,
        currentHourIndex(bundle),
      );
      const saturation =
        topsoil === null
          ? null
          : Math.round(
              Math.min(100, (topsoil / SOIL_POROSITY_M3M3) * 100) * 10,
            ) / 10;

      let threat = "Low";
      if ((rain7d ?? 0) >= 150 || (saturation ?? 0) >= 80) threat = "High";
      else if ((rain7d ?? 0) >= 75 || (saturation ?? 0) >= 60)
        threat = "Moderate";

      return {
        location_id: String(loc.id),
        location_name: String(loc.name ?? locationId),
        rainfall_3d_mm: sumFirst(3),
        rainfall_7d_mm: rain7d,
        rainfall_30d_mm: rainfall30d,
        rainfall_30d_start: pastTimes[0] ?? null,
        rainfall_30d_end: pastTimes[pastTimes.length - 1] ?? null,
        soil_saturation_index: saturation,
        flood_threat_level: threat,
        data_source: OPEN_METEO_SOURCE_LABEL,
        retrieved_at: new Date().toISOString(),
      };
    } catch (err) {
      console.warn("Open-Meteo rainfall request failed, using backend:", err);
    }
  }

  return fetchWeatherRainfallAccumulationFromBackend(locationId);
}

// ---------------- soil moisture ----------------

export async function fetchWeatherSoilMoisture(
  locationId: string,
): Promise<WeatherSoilMoisture> {
  const loc = findProvinceLocation(locationId);

  if (loc) {
    try {
      const bundle = await fetchOpenMeteoBundle(
        Number(loc.lat),
        Number(loc.lon),
      );

      const index = currentHourIndex(bundle);
      const top = valueAt(bundle.hourly.soil_moisture_0_to_7cm, index);
      const root = valueAt(bundle.hourly.soil_moisture_7_to_28cm, index);
      const deep = valueAt(bundle.hourly.soil_moisture_28_to_100cm, index);

      if (top !== null || root !== null || deep !== null) {
        return {
          location_id: String(loc.id),
          location_name: String(loc.name ?? locationId),
          topsoil_moisture_0_7cm: top,
          root_zone_moisture_7_28cm: root,
          deep_moisture_28_100cm: deep,
          timestamp: String(bundle.current.time ?? ""),
          data_source: OPEN_METEO_SOURCE_LABEL,
        };
      }
    } catch (err) {
      console.warn("Open-Meteo soil request failed, using backend:", err);
    }
  }

  return fetchWeatherSoilMoistureFromBackend(locationId);
}

// ============================================================
// RIVER DISCHARGE
// ============================================================

export async function fetchRiverDischarge(
  locationId: string | number,
): Promise<RiverDischarge> {
  const locationMap: Record<string, number> = {
    "siem-reap": 1,
    battambang: 2,
    pursat: 3,
    "kampong-thom": 4,
    "kampong-chhnang": 5,
  };

  const key = String(locationId);
  const numericId = locationMap[key] ?? Number(key);

  if (!Number.isInteger(numericId) || numericId < 1) {
    throw new Error(`Invalid discharge monitoring location: ${key}`);
  }

  const response = await fetch(
    `${API_BASE_URL}/hydrology/discharge?location_id=${numericId}`,
    { cache: "no-store" },
  );

  if (!response.ok) {
    throw new Error(
      `Failed to fetch discharge forecast: HTTP ${response.status}`,
    );
  }

  const data = await response.json();

  return {
    location_id: data.location_id,
    location_name: data.location_name,
    province: data.province ?? null,
    current_discharge_m3s: data.current_discharge_m3s ?? null,
    historical_mean_m3s: data.historical_mean_m3s ?? null,
    anomaly_pct: data.anomaly_pct ?? null,
    flow_status: data.flow_status ?? "UNKNOWN",

    forecast: (data.forecast ?? []).map((item: any) => ({
      date: item.date,
      discharge_m3s: item.discharge_m3s ?? null,
      discharge_max: item.discharge_max ?? null,
      discharge_mean: item.discharge_mean ?? null,
      discharge_median: item.discharge_median ?? null,
      data_source: item.data_source ?? null,
    })),

    data_sources: data.data_sources ?? [],
    updated_at: data.updated_at ?? null,
  };
}

// ============================================================
// RISK ASSESSMENT NORMALIZATION
// ============================================================

function normalizeRiskLevel(value: unknown): RiskAssessment["risk_level"] {
  const category = String(value ?? "")
    .toLowerCase()
    .trim()
    .replace(/[\s-]+/g, "_");

  if (category === "very_high") {
    return "very_high";
  }

  if (category === "high") {
    return "high";
  }

  if (category === "moderate" || category === "medium") {
    return "moderate";
  }

  if (category === "low") {
    return "low";
  }

  // Do not crash the whole page because one record has an unknown label.
  console.warn("Unknown risk category returned by backend:", category);
  return "low";
}

function normalizeContributingFactors(
  input: unknown,
): NonNullable<RiskAssessment["contributing_factors"]> {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    return {};
  }

  const result: NonNullable<RiskAssessment["contributing_factors"]> = {};

  for (const [name, rawValue] of Object.entries(input)) {
    if (!rawValue || typeof rawValue !== "object" || Array.isArray(rawValue)) {
      continue;
    }

    const { score, weight, weighted_contribution, ...details } =
      rawValue as Record<string, unknown>;

    result[name] = {
      score: toNullableNumber(score),
      weight: toNullableNumber(weight) ?? 0,
      weighted_contribution: toNullableNumber(weighted_contribution),
      // Keep the extra engine values (rain_7d_mm, discharge_m3s, ...)
      details,
    };
  }

  return result;
}

/**
 * Backend data_freshness is an object containing timestamps,
 * ages and freshness flags. Keep it as an object.
 */
function normalizeDataFreshness(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }

  return value as Record<string, unknown>;
}

// The backend returns numeric location IDs (1-5), but the map, dashboard
// and MONITORING_LOCATIONS all use slugs such as "pursat".
const LOCATION_SLUG_BY_BACKEND_ID: Record<number, string> = {
  1: "siem-reap",
  2: "battambang",
  3: "pursat",
  4: "kampong-thom",
  5: "kampong-chhnang",
};

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[\s_]+/g, "-");
}

function resolveLocationSlug(item: any): string {
  const knownSlugs = MONITORING_LOCATIONS.filter(
    (location) => location.type === "province",
  ).map((location) => location.id);

  const candidates = [item.location_name, item.province, item.location_id]
    .filter((value) => value !== null && value !== undefined && value !== "")
    .map((value) => slugify(String(value)));

  for (const candidate of candidates) {
    if (knownSlugs.includes(candidate)) {
      return candidate;
    }
  }

  const numericId = Number(item.location_id);

  if (Number.isInteger(numericId) && LOCATION_SLUG_BY_BACKEND_ID[numericId]) {
    return LOCATION_SLUG_BY_BACKEND_ID[numericId];
  }

  return String(item.location_id ?? "");
}

function normalizeRiskAssessment(item: any): RiskAssessment {
  if (!item || typeof item !== "object") {
    throw new Error("Invalid risk assessment record.");
  }

  const locationId = resolveLocationSlug(item);

  if (!locationId) {
    throw new Error("Risk assessment is missing its location ID.");
  }

  const backendId = toNullableNumber(item.location_id);

  const rawFactors =
    item.contributing_factors &&
    typeof item.contributing_factors === "object" &&
    !Array.isArray(item.contributing_factors)
      ? item.contributing_factors
      : {};

  const contributingFactors = normalizeContributingFactors(rawFactors);

  const generatedFactors = Object.entries(rawFactors).map(
    ([name, raw]: [string, any]) => {
      const score = toNullableNumber(raw?.score);
      const label = name.replace(/_/g, " ");

      return score === null ? label : `${label}: ${score}`;
    },
  );

  const factors = Array.isArray(item.factors)
    ? item.factors.map((factor: unknown) => String(factor))
    : generatedFactors;

  const riskScore = toNullableNumber(item.risk_score ?? item.risk_probability);

  if (riskScore === null) {
    throw new Error(`Risk score is missing for location ${locationId}.`);
  }

  const assessmentDate = String(item.assessment_date ?? item.timestamp ?? "");

  return {
    id: String(item.id ?? locationId),
    location_id: locationId,
    backend_location_id: backendId,
    location_name: String(item.location_name ?? "Unknown"),
    location_name_km: item.location_name_km ?? undefined,
    province: String(item.province ?? "Unknown"),

    risk_level: normalizeRiskLevel(item.risk_category ?? item.risk_level),
    risk_score: riskScore,

    primary_driver: String(item.primary_driver ?? ""),

    factors,

    recommended_actions: Array.isArray(item.recommended_actions)
      ? item.recommended_actions.map((action: unknown) => String(action))
      : [],

    contributing_factors: contributingFactors,

    model_version: String(item.model_version ?? "Not available"),
    model_type: String(item.model_type ?? "Not available"),

    data_coverage_percent: toNullableNumber(item.data_coverage_percent),
    data_status: String(item.data_status ?? "unknown"),
    data_freshness: normalizeDataFreshness(item.data_freshness),

    explanation_en: String(item.explanation_en ?? ""),
    explanation_km: String(item.explanation_km ?? ""),

    assessment_date: assessmentDate,
    timestamp: assessmentDate,
  };
}

// ============================================================
// FETCH ALL RISK ASSESSMENTS
// ============================================================

export async function fetchRiskAssessments(): Promise<RiskAssessment[]> {
  const response = await fetch(`${API_BASE_URL}/risk/assessments`, {
    cache: "no-store",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    const message = await readErrorMessage(
      response,
      `Risk assessment API failed: HTTP ${response.status}`,
    );

    throw new Error(message);
  }

  const records = await response.json();

  if (!Array.isArray(records)) {
    throw new Error("Invalid risk assessment response: expected an array.");
  }

  return records.map(normalizeRiskAssessment);
}

// ============================================================
// FETCH ONE RISK ASSESSMENT
// ============================================================

export async function fetchRiskDetail(
  locationId: string,
): Promise<RiskAssessment> {
  const assessments = await fetchRiskAssessments();

  const requestedId = String(locationId);

  const match = assessments.find(
    (assessment) =>
      assessment.location_id === requestedId || assessment.id === requestedId,
  );

  if (!match) {
    throw new Error(`No risk assessment found for location: ${requestedId}`);
  }

  return match;
}

// ============================================================
// RUN A NEW RISK ASSESSMENT
// ============================================================

export async function triggerRiskAssessment(): Promise<number> {
  const response = await fetch(`${API_BASE_URL}/risk/assess`, {
    method: "POST",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({}),
  });

  if (!response.ok) {
    const message = await readErrorMessage(
      response,
      `Risk assessment run failed: HTTP ${response.status}`,
    );

    throw new Error(message);
  }

  const data = await response.json();

  return Number(data?.triggered_count ?? 0);
}

// ============================================================
// ALERTS
// ============================================================

export async function fetchAlerts(): Promise<Alert[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/alerts`, {
      cache: "no-store",
    });

    if (response.ok) {
      return await response.json();
    }
  } catch (error) {
    console.warn("Alerts API unavailable:", error);
  }

  // Original demo alerts retained for the existing UI.
  return [
    {
      id: "alt-001",
      severity: "warning",
      title: "Hydrological Surge: Kampong Chhnang Bottleneck",
      title_km: "ការកើនឡើងកម្ពស់ទឹកយ៉ាងគំហុកនៅតំបន់កំពង់ឆ្នាំង",
      message:
        "GloFAS ensemble predicts reverse flow velocity exceeding 1.85 m/s at Prek Kdam. Low-lying agricultural polders in Boribor district are at high risk of rapid inundation over the next 48 hours.",
      message_km:
        "លំហូរទឹកបញ្ច្រាសតាមព្រែកក្តាមមានល្បឿនខ្លាំងលើសពី ១.៨៥ ម៉ែត្រក្នុងមួយវិនាទី។ សូមប្រុងប្រយ័ត្នចំពោះការជន់លិចដីស្រែទំនាបនៅស្រុកបរិបូណ៌។",
      location_id: "kampong-chhnang",
      location_name: "Kampong Chhnang",
      province: "Kampong Chhnang",
      category: "flood",
      issued_at: new Date(Date.now() - 3600000 * 3).toISOString(),
      expires_at: new Date(Date.now() + 3600000 * 45).toISOString(),
      status: "active",
    },
    {
      id: "alt-002",
      severity: "warning",
      title: "Flash Runoff Advisory: Cardamom Mountain Catchment",
      title_km: "សេចក្តីជូនដំណឹងអំពីជំនន់ទឹកភ្លៀងហូរពីជួរភ្នំក្រវាញ",
      message:
        "High convective rainfall observed over Upper Pursat basin. Expect sudden stage height increase of +0.65m along Stung Pursat through Krakor floating village corridor.",
      message_km:
        "ទឹកភ្លៀងធ្លាក់ខ្លាំងនៅតំបន់ជួរភ្នំក្រវាញ អាចបណ្ដាលឱ្យកម្ពស់ទឹកស្ទឹងពោធិ៍សាត់ឡើងខ្ពស់ថែម ០.៦៥ ម៉ែត្រ។",
      location_id: "pursat",
      location_name: "Pursat",
      province: "Pursat",
      category: "extreme_weather",
      issued_at: new Date(Date.now() - 3600000 * 7).toISOString(),
      expires_at: new Date(Date.now() + 3600000 * 36).toISOString(),
      status: "active",
    },
  ];
}

// ============================================================
// SATELLITE PROCESSING
// ============================================================

export async function processSatelliteScene(
  sceneId: string,
): Promise<SatelliteProcessResult> {
  const response = await fetch(
    `${API_BASE_URL}/satellite/process?scene_id=${encodeURIComponent(sceneId)}`,
    {
      method: "POST",
      cache: "no-store",
    },
  );

  if (!response.ok) {
    const message = await readErrorMessage(
      response,
      `Satellite processing failed: HTTP ${response.status}`,
    );

    throw new Error(message);
  }

  return (await response.json()) as SatelliteProcessResult;
}

// ============================================================
// SATELLITE SEARCH
// ============================================================

export async function fetchSatelliteSearch(
  startDate?: string,
  endDate?: string,
): Promise<{
  scenes: SatelliteAcquisition[];
  meta: SatelliteSearchMeta;
}> {
  const params = new URLSearchParams();

  if (startDate) {
    params.set("start_date", startDate.slice(0, 10));
  }

  if (endDate) {
    params.set("end_date", endDate.slice(0, 10));
  }

  params.set("limit", "12");

  const response = await fetch(
    `${API_BASE_URL}/satellite/search?${params.toString()}`,
    { cache: "no-store" },
  );

  if (!response.ok) {
    throw new Error(`Satellite API returned HTTP ${response.status}`);
  }

  const scenes = await response.json();

  if (!Array.isArray(scenes)) {
    throw new Error("Invalid satellite API response.");
  }

  const meta: SatelliteSearchMeta = {
    source:
      response.headers.get("X-Catalog-Source") === "cache" ? "cache" : "live",
    provider: response.headers.get("X-Catalog-Provider") ?? undefined,
    error: response.headers.get("X-Catalog-Error") ?? undefined,
  };

  const mapped = scenes.map((scene: any): SatelliteAcquisition => {
    const name = String(scene.satellite ?? "").toLowerCase();

    let satellite: SatelliteAcquisition["satellite"] = "Sentinel-1";

    if (name.includes("sentinel-2")) {
      satellite = "Sentinel-2";
    } else if (name.includes("landsat-8")) {
      satellite = "Landsat-8";
    } else if (name.includes("landsat-9")) {
      satellite = "Landsat-9";
    }

    return {
      id: String(
        scene.scene_id ??
          scene.id ??
          scene.stac_url ??
          scene.acquisition_date ??
          "unknown",
      ),

      satellite,
      platform_name: scene.platform ?? undefined,
      date: String(scene.acquisition_date ?? ""),
      published_at: scene.published_at ?? undefined,

      instrument: String(
        scene.instrument_mode ?? scene.collection ?? "Unknown instrument",
      ),

      orbit_direction:
        scene.orbit_state === "ascending"
          ? "ASCENDING"
          : scene.orbit_state === "descending"
            ? "DESCENDING"
            : undefined,

      relative_orbit:
        typeof scene.relative_orbit === "number"
          ? scene.relative_orbit
          : undefined,

      polarization: scene.polarization ?? undefined,
      cloud_cover_pct: Number(scene.cloud_cover ?? 0),

      water_extent_km2:
        scene.water_extent_km2 === null || scene.water_extent_km2 === undefined
          ? null
          : Number(scene.water_extent_km2),

      processed: Boolean(scene.processed),
      source: scene.source === "cache" ? "cache" : "live",
      thumbnail_url: String(scene.thumbnail_url ?? ""),
      download_url: String(scene.stac_url ?? ""),

      bbox:
        Array.isArray(scene.bbox) && scene.bbox.length === 4
          ? scene.bbox
          : TONLE_SAP_BBOX,
    };
  });

  return {
    scenes: mapped,
    meta,
  };
}

// ============================================================
// SATELLITE STATUS
// ============================================================

export async function fetchSatelliteStatus(): Promise<SatelliteStatus> {
  const response = await fetch(`${API_BASE_URL}/satellite/status`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Satellite status API returned HTTP ${response.status}`);
  }

  return (await response.json()) as SatelliteStatus;
}

// ============================================================
// DATA SOURCES
// ============================================================

export async function fetchDataSources(): Promise<DataSource[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/datasources`, {
      cache: "no-store",
    });

    if (response.ok) {
      return await response.json();
    }
  } catch (error) {
    console.warn("Data sources API unavailable:", error);
  }

  return DATA_SOURCES.map((source) => ({
    ...source,
    lastPingMs: 42,
  }));
}

// ============================================================
// HYDROLOGY STATIONS
// ============================================================

export async function fetchHydrologyStations(): Promise<Station[]> {
  const response = await fetch(`${API_BASE_URL}/hydrology/stations`, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(
      `Failed to fetch hydrology stations: HTTP ${response.status}`,
    );
  }

  const data = await response.json();

  if (!Array.isArray(data)) {
    throw new Error("Invalid hydrology stations response.");
  }

  return data.map(
    (station: any): Station => ({
      id: String(station.id),
      code: String(station.code),
      name: station.name,
      name_km: station.name_km ?? null,
      type: station.type ?? null,
      province: station.province ?? null,
      district: station.district ?? null,
      river: station.water_body ?? null,
      water_body: station.water_body ?? null,
      lat: Number(station.lat),
      lon: Number(station.lon),
      elevation: station.elevation ?? null,
      data_source: station.data_source ?? null,
      water_level_m: station.current_water_level ?? null,
      alarm_level_m: station.alarm_level ?? null,
      flood_level_m: station.flood_level ?? null,
      last_reading_time: station.latest_reading_time ?? null,
      is_active: Boolean(station.is_active),
      status: station.status ?? "NO_DATA",
      pulse_flow_status: station.pulse_flow_status ?? null,
      latest_data_source: station.latest_data_source ?? null,
      freshness: station.freshness ?? "no_data",
      age_seconds: station.age_seconds ?? null,
      discharge_m3s: null,
      trend: "unknown",
    }),
  );
}

// ============================================================
// HISTORICAL FLOOD EVENTS
// ============================================================

export async function fetchFloodHistory(
  province?: string,
): Promise<FloodEvent[]> {
  const events: FloodEvent[] = [
    {
      id: "flood-2000",
      year: 2000,
      title: "2000 Historic Great Mekong & Tonle Sap Inundation",
      provinces_affected: [
        "Siem Reap",
        "Battambang",
        "Pursat",
        "Kampong Chhnang",
        "Kampong Thom",
        "Kandal",
      ],
      peak_water_level_m: 10.42,
      estimated_damage_usd: 157000000,
      affected_population: 3448000,
      duration_days: 72,
      summary:
        "The benchmark 50-year catastrophic flood event across Cambodia. Reverse flow persisted into late November, submerging vast agricultural tracts and low-lying floating communities.",
      significance: "Primary baseline benchmark for maximum hazard envelope",
    },
    {
      id: "flood-2011",
      year: 2011,
      title: "2011 Typhoon Nesat & Nalgae Convective Flood",
      provinces_affected: [
        "Siem Reap",
        "Battambang",
        "Kampong Thom",
        "Pursat",
        "Kampong Chhnang",
      ],
      peak_water_level_m: 10.15,
      estimated_damage_usd: 521000000,
      affected_population: 1700000,
      duration_days: 58,
      summary:
        "Consecutive typhoons triggered intense catchment runoff while Tonle Sap water was already high, breaching National Road 5 and isolating floating commune anchor sites.",
      significance:
        "Exemplifies combined typhoon flash-flood and lake backwater surge",
    },
    {
      id: "flood-2020",
      year: 2020,
      title: "2020 Intense Monsoon Storms Linfa & Nangka",
      provinces_affected: ["Battambang", "Pursat", "Kampong Thom", "Siem Reap"],
      peak_water_level_m: 9.38,
      estimated_damage_usd: 110000000,
      affected_population: 800000,
      duration_days: 35,
      summary:
        "Localized tributary flash floods combined with rapid Tonle Sap expansion heavily devastated Pursat and Battambang rice paddies before harvest.",
      significance: "Highlights high vulnerability in tributary confluences",
    },
  ];

  if (!province) {
    return events;
  }

  return events.filter((event) =>
    event.provinces_affected.some((name) =>
      name.toLowerCase().includes(province.toLowerCase()),
    ),
  );
}

// ============================================================
// COMMUNITY PROFILE
// ============================================================

export async function fetchCommunityProfile(
  provinceName: string,
): Promise<CommunityProfile> {
  try {
    const response = await fetch(
      `${API_BASE_URL}/community/profile?province=${encodeURIComponent(provinceName)}`,
      { cache: "no-store" },
    );

    if (response.ok) {
      return await response.json();
    }
  } catch (error) {
    console.warn("Community profile API unavailable:", error);
  }

  const profiles: Record<string, CommunityProfile> = {
    pursat: {
      province: "Pursat",
      province_km: "ខេត្តពោធិ៍សាត់",
      population: 464000,
      floating_villages_count: 14,
      vulnerable_households: 18200,
      evacuation_shelters_count: 26,
      main_livelihoods: [
        "Inland Freshwater Fishery",
        "Wet-season Rice Paddies",
        "Floating Aquaculture",
      ],
      flood_preparedness_score: 72,
      safe_zone_elevation_m: 22.0,
      contact_hotline: "1294 (NCDM Free Hotline) / 052 740 011",
    },

    "kampong-chhnang": {
      province: "Kampong Chhnang",
      province_km: "ខេត្តកំពង់ឆ្នាំង",
      population: 526000,
      floating_villages_count: 19,
      vulnerable_households: 24500,
      evacuation_shelters_count: 31,
      main_livelihoods: [
        "Artisanal Fishery",
        "Pottery Clay Craft",
        "Polder Agriculture",
        "Aquaculture",
      ],
      flood_preparedness_score: 68,
      safe_zone_elevation_m: 20.5,
      contact_hotline: "1294 (NCDM Free Hotline) / 026 770 012",
    },

    "siem-reap": {
      province: "Siem Reap",
      province_km: "ខេត្តសៀមរាប",
      population: 1015000,
      floating_villages_count: 12,
      vulnerable_households: 16400,
      evacuation_shelters_count: 42,
      main_livelihoods: [
        "Ecotourism Boat Transport",
        "Deepwater Rice",
        "Floating House Fishery",
      ],
      flood_preparedness_score: 84,
      safe_zone_elevation_m: 25.0,
      contact_hotline: "1294 (NCDM Free Hotline) / 063 760 033",
    },

    battambang: {
      province: "Battambang",
      province_km: "ខេត្តបាត់ដំបង",
      population: 997000,
      floating_villages_count: 8,
      vulnerable_households: 15300,
      evacuation_shelters_count: 38,
      main_livelihoods: [
        "Rice Granary Cultivation",
        "Horticulture",
        "Wetland Fishery",
      ],
      flood_preparedness_score: 78,
      safe_zone_elevation_m: 24.0,
      contact_hotline: "1294 (NCDM Free Hotline) / 053 730 021",
    },

    "kampong-thom": {
      province: "Kampong Thom",
      province_km: "ខេត្តកំពង់ធំ",
      population: 681000,
      floating_villages_count: 9,
      vulnerable_households: 19800,
      evacuation_shelters_count: 29,
      main_livelihoods: [
        "Stung Sen Riverine Agriculture",
        "Floating Net Fishing",
        "Cashew Farming",
      ],
      flood_preparedness_score: 71,
      safe_zone_elevation_m: 21.0,
      contact_hotline: "1294 (NCDM Free Hotline) / 062 750 014",
    },
  };

  const key = provinceName.toLowerCase().trim().replace(/\s+/g, "-");

  const profile = profiles[key];

  if (profile) {
    return profile;
  }

  // Original project's generic fallback profile.
  return {
    province: provinceName,
    province_km: "ខេត្ត",
    population: 500000,
    floating_villages_count: 10,
    vulnerable_households: 15000,
    evacuation_shelters_count: 25,
    main_livelihoods: ["Fisheries", "Agriculture"],
    flood_preparedness_score: 70,
    safe_zone_elevation_m: 20.0,
    contact_hotline: "1294 (NCDM Free Hotline)",
  };
}

// ============================================================
// LIVE COMMUNITY RISK
// ============================================================

/**
 * Live risk, gauges, alerts, discharge and safe-site posture for every
 * province. Real data only: when the API is down this throws, and the page
 * shows that honestly instead of inventing numbers.
 */
export async function fetchCommunityRiskLive(): Promise<CommunityRiskLive> {
  const response = await fetch(`${API_BASE_URL}/community/risk-live`, {
    cache: "no-store",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    const message = await readErrorMessage(
      response,
      `Community risk API failed: HTTP ${response.status}`,
    );

    throw new Error(message);
  }

  return (await response.json()) as CommunityRiskLive;
}
