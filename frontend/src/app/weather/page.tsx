"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";

import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { HourlyRainChart } from "@/components/charts/HourlyRainChart";

import {
  fetchWeatherCurrent,
  fetchWeatherForecast,
  fetchWeatherRainfallAccumulation,
  fetchWeatherSoilMoisture,
  WeatherRainfallAccumulation,
  WeatherSoilMoisture,
} from "@/lib/api";

import { MONITORING_LOCATIONS } from "@/lib/constants";

import { WeatherData, WeatherForecast, WeatherHourlyForecast } from "@/types";

import {
  CloudRain,
  Thermometer,
  Droplets,
  Wind,
  Gauge,
  Sun,
  CloudLightning,
  Calendar,
  RefreshCw,
  AlertCircle,
} from "lucide-react";

function formatNumber(value: number | null | undefined, decimals = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "—";
  }

  return value.toFixed(decimals);
}

function formatDate(value: string): string {
  if (!value) return "—";

  const date = new Date(`${value}T00:00:00`);

  if (Number.isNaN(date.getTime())) return value;

  return date.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

function getCompleteRainfallTotal(
  days: WeatherForecast["daily"],
  count: number,
): number | null {
  const selectedDays = days.slice(0, count);

  if (selectedDays.length === 0) return null;

  if (selectedDays.some((day) => day.precipitation_sum_mm === null)) {
    return null;
  }

  return selectedDays.reduce(
    (total, day) => total + (day.precipitation_sum_mm ?? 0),
    0,
  );
}

export default function WeatherPage() {
  const [selectedLocationId, setSelectedLocationId] =
    useState<string>("pursat");

  const [currentWeather, setCurrentWeather] = useState<WeatherData | null>(
    null,
  );

  const [forecast, setForecast] = useState<WeatherForecast | null>(null);

  const [rainfall, setRainfall] = useState<WeatherRainfallAccumulation | null>(
    null,
  );
  const [soil, setSoil] = useState<WeatherSoilMoisture | null>(null);
  const [soilError, setSoilError] = useState<string | null>(null);
  const [rainfallError, setRainfallError] = useState<string | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  // Ignore responses from an older request (e.g. after switching province).
  const requestIdRef = useRef(0);

  const provinces = MONITORING_LOCATIONS.filter(
    (location) => location.type === "province",
  );

  const loadWeatherData = useCallback(
    async (locationId: string, silent = false) => {
      const requestId = ++requestIdRef.current;

      try {
        // Background refreshes keep the current numbers on screen.
        if (!silent) setLoading(true);

        const [current, forecastData] = await Promise.all([
          fetchWeatherCurrent(locationId),
          fetchWeatherForecast(locationId),
        ]);

        if (requestId !== requestIdRef.current) return;

        setCurrentWeather(current);
        setForecast(forecastData);
        setError(null);
        setLastChecked(new Date());

        // Secondary data: a failure here must not blank the whole page.
        const [rainfallResult, soilResult] = await Promise.allSettled([
          fetchWeatherRainfallAccumulation(locationId),
          fetchWeatherSoilMoisture(locationId),
        ]);

        if (requestId !== requestIdRef.current) return;

        if (rainfallResult.status === "fulfilled") {
          setRainfall(rainfallResult.value);
          setRainfallError(null);
        } else {
          setRainfall(null);
          setRainfallError("30-day rainfall could not be loaded.");
        }

        if (soilResult.status === "fulfilled") {
          setSoil(soilResult.value);
          setSoilError(null);
        } else {
          setSoil(null);
          setSoilError("Soil moisture could not be loaded.");
        }
      } catch (err) {
        if (requestId !== requestIdRef.current) return;

        console.error("Error fetching weather data:", err);

        setError(
          err instanceof Error
            ? err.message
            : "Unable to retrieve weather data.",
        );
      } finally {
        if (requestId === requestIdRef.current) setLoading(false);
      }
    },
    [],
  );

  // Initial load + reload when the province changes.
  useEffect(() => {
    setCurrentWeather(null);
    setForecast(null);
    setRainfall(null);
    setSoil(null);
    loadWeatherData(selectedLocationId);
  }, [selectedLocationId, loadWeatherData]);

  // Real-time updates: refresh every 60 s, and immediately when the tab
  // becomes visible again (browsers throttle timers in background tabs).
  useEffect(() => {
    const REFRESH_MS = 60_000;

    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        loadWeatherData(selectedLocationId, true);
      }
    }, REFRESH_MS);

    const onVisible = () => {
      if (document.visibilityState === "visible") {
        loadWeatherData(selectedLocationId, true);
      }
    };

    document.addEventListener("visibilitychange", onVisible);

    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [selectedLocationId, loadWeatherData]);

  const dailyForecasts = forecast?.daily ?? [];
  const hourlyForecasts = forecast?.hourly ?? [];

  const rain3Day = getCompleteRainfallTotal(dailyForecasts, 3);

  const rain7Day = getCompleteRainfallTotal(dailyForecasts, 7);

  // Prefer the value from the current-weather endpoint; fall back to the
  // forecast entry for the same hour (current time is 15-min resolution,
  // hourly data is on the hour, so compare only "YYYY-MM-DDTHH").
  const currentHourKey = (currentWeather?.timestamp ?? "").slice(0, 13);

  const currentHourForecast = hourlyForecasts.find(
    (item) => item.time.slice(0, 13) === currentHourKey,
  );

  const currentPrecipitationProbability =
    currentWeather?.precipitation_probability_pct ??
    currentHourForecast?.precipitation_probability_pct ??
    null;

  const cloudCover =
    currentWeather?.cloud_cover_pct ??
    currentHourForecast?.cloud_cover_pct ??
    null;

  const rain30Day = rainfall?.rainfall_30d_mm ?? null;

  const hourlyRainTotal = hourlyForecasts.reduce(
    (total, hour) => total + (hour.precipitation_mm ?? 0),
    0,
  );

  const locationName =
    currentWeather?.location_name ??
    provinces.find((location) => location.id === selectedLocationId)?.name ??
    selectedLocationId;

  return (
    <DashboardLayout
      title="Meteorological & Convective Rainfall Intelligence"
      subtitle="High-resolution atmospheric observations, 7-day numerical forecasts, and soil saturation analytics over Tonle Sap Basin"
      actions={
        <div className="flex items-center gap-2">
          <label
            htmlFor="weather-location-select"
            className="text-xs text-slate-400"
          >
            Province:
          </label>

          <select
            id="weather-location-select"
            value={selectedLocationId}
            onChange={(event) => setSelectedLocationId(event.target.value)}
            className="rounded-lg border border-navy-700 bg-navy-950 px-3 py-1.5 text-xs text-slate-100 focus:border-cyan-500 focus:outline-none"
          >
            {provinces.map((province) => (
              <option key={province.id} value={province.id}>
                {province.name} ({province.name_km})
              </option>
            ))}
          </select>

          <button
            type="button"
            onClick={() => loadWeatherData(selectedLocationId)}
            disabled={loading}
            className="rounded-lg border border-navy-700 bg-navy-950 p-2 text-cyan-400 hover:bg-navy-800 disabled:opacity-50"
            title="Refresh weather"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      }
    >
      {/* API Error */}
      {error && (
        <div className="mb-5 flex items-start gap-3 rounded-xl border border-red-500/30 bg-red-500/10 p-4">
          <AlertCircle className="h-5 w-5 text-red-400" />

          <div>
            <p className="text-sm font-semibold text-red-300">
              Weather data unavailable
            </p>

            <p className="mt-1 text-xs text-red-200">{error}</p>
          </div>
        </div>
      )}

      {/* Current Weather Observation */}
      <section className="rounded-xl border border-navy-800 bg-navy-900/60 p-6 shadow-xl backdrop-blur-md">
        <div className="flex flex-col gap-4 border-b border-navy-800 pb-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="flex h-2.5 w-2.5 animate-pulse rounded-full bg-emerald-400" />

              <span className="text-xs font-semibold uppercase tracking-wider text-cyan-400">
                Live Weather Observation
              </span>
            </div>

            <h2 className="mt-1 text-2xl font-bold text-white">
              {locationName} Province
            </h2>

            <p className="text-xs text-slate-400">
              Source: {currentWeather?.data_source ?? "Not available"}
              {" • "}
              {currentWeather?.timezone ?? "Timezone not reported"}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <span className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-400">
              {loading ? "Updating" : error ? "Unavailable" : "API Connected"}
            </span>

            <span className="text-[11px] text-slate-400">
              {lastChecked
                ? `Checked ${lastChecked.toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  })} · auto-refresh 60s`
                : "Checking…"}
            </span>

            <span className="rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-2.5 py-1 text-xs font-medium text-cyan-300">
              {currentWeather?.timestamp
                ? new Date(currentWeather.timestamp).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                : "—"}
            </span>
          </div>
        </div>

        {/* Weather Metric Cards */}
        <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          {/* Temperature */}
          <div className="rounded-lg border border-navy-800 bg-navy-950/80 p-3.5">
            <div className="mb-1 flex items-center gap-1.5 text-xs text-slate-400">
              <Thermometer className="h-4 w-4 text-rose-400" />
              Temperature
            </div>

            <div className="font-mono text-2xl font-bold text-white">
              {formatNumber(currentWeather?.temperature_c)}°C
            </div>

            <span className="mt-1 block text-[10px] text-slate-400">
              Temperature at 2m
            </span>
          </div>

          {/* Current Rain */}
          <div className="rounded-lg border border-navy-800 bg-navy-950/80 p-3.5">
            <div className="mb-1 flex items-center gap-1.5 text-xs text-slate-400">
              <CloudRain className="h-4 w-4 text-cyan-400" />
              Current Rain
            </div>

            <div className="font-mono text-2xl font-bold text-cyan-300">
              {formatNumber(currentWeather?.precipitation_mm)} mm
            </div>

            <span className="mt-1 block text-[10px] text-slate-400">
              Provider observation
            </span>
          </div>

          {/* Rain Probability */}
          <div className="rounded-lg border border-navy-800 bg-navy-950/80 p-3.5">
            <div className="mb-1 flex items-center gap-1.5 text-xs text-slate-400">
              <CloudLightning className="h-4 w-4 text-amber-400" />
              Probability
            </div>

            <div className="font-mono text-2xl font-bold text-amber-300">
              {formatNumber(currentPrecipitationProbability, 0)}%
            </div>

            <span className="mt-1 block text-[10px] text-slate-400">
              Precipitation probability
            </span>
          </div>

          {/* Humidity */}
          <div className="rounded-lg border border-navy-800 bg-navy-950/80 p-3.5">
            <div className="mb-1 flex items-center gap-1.5 text-xs text-slate-400">
              <Droplets className="h-4 w-4 text-blue-400" />
              Humidity
            </div>

            <div className="font-mono text-2xl font-bold text-slate-200">
              {formatNumber(currentWeather?.humidity_pct, 0)}%
            </div>

            <span className="mt-1 block text-[10px] text-slate-400">
              Relative humidity
            </span>
          </div>

          {/* Wind Speed */}
          <div className="rounded-lg border border-navy-800 bg-navy-950/80 p-3.5">
            <div className="mb-1 flex items-center gap-1.5 text-xs text-slate-400">
              <Wind className="h-4 w-4 text-teal-400" />
              Wind Speed
            </div>

            <div className="font-mono text-2xl font-bold text-slate-200">
              {formatNumber(currentWeather?.wind_speed_kmh)}{" "}
              <span className="text-xs">km/h</span>
            </div>

            <span className="mt-1 block text-[10px] text-slate-400">
              Direction: {formatNumber(currentWeather?.wind_direction_deg, 0)}°
            </span>
          </div>

          {/* Cloud Cover */}
          <div className="rounded-lg border border-navy-800 bg-navy-950/80 p-3.5">
            <div className="mb-1 flex items-center gap-1.5 text-xs text-slate-400">
              <Gauge className="h-4 w-4 text-purple-400" />
              Cloud Cover
            </div>

            <div className="font-mono text-2xl font-bold text-slate-200">
              {formatNumber(cloudCover, 0)}%
            </div>

            <span className="mt-1 block text-[10px] text-slate-400">
              Cloud coverage
            </span>
          </div>
        </div>
      </section>

      {/* Rainfall Accumulation */}
      <section className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-navy-800 bg-navy-900/60 p-4 shadow-lg backdrop-blur-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              3-Day Precipitation
            </span>

            <span className="rounded border border-cyan-800/60 bg-cyan-950 px-2 py-0.5 text-[10px] font-mono text-cyan-400">
              Forecast
            </span>
          </div>

          <div className="mt-3 flex items-baseline gap-2">
            <span className="font-mono text-3xl font-extrabold text-cyan-300">
              {formatNumber(rain3Day)}
            </span>

            <span className="text-xs font-medium text-slate-400">mm</span>
          </div>

          <p className="mt-2 text-xs text-slate-400">
            Total precipitation across the next three forecast days.
          </p>
        </div>

        <div className="rounded-xl border border-navy-800 bg-navy-900/60 p-4 shadow-lg backdrop-blur-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              7-Day Precipitation
            </span>

            <span className="rounded border border-blue-800/60 bg-blue-950 px-2 py-0.5 text-[10px] font-mono text-blue-400">
              Forecast
            </span>
          </div>

          <div className="mt-3 flex items-baseline gap-2">
            <span className="font-mono text-3xl font-extrabold text-white">
              {formatNumber(rain7Day)}
            </span>

            <span className="text-xs font-medium text-slate-400">mm</span>
          </div>

          <p className="mt-2 text-xs text-slate-400">
            Total precipitation across the available seven-day forecast.
          </p>
        </div>

        <div className="rounded-xl border border-navy-800 bg-navy-900/60 p-4 shadow-lg backdrop-blur-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              30-Day Historical Rainfall
            </span>

            <span className="rounded border border-purple-800/60 bg-purple-950 px-2 py-0.5 text-[10px] font-mono text-purple-400">
              Historical
            </span>
          </div>

          <div className="mt-3 flex items-baseline gap-2">
            <span className="font-mono text-3xl font-extrabold text-purple-300">
              {formatNumber(rain30Day)}
            </span>

            <span className="text-xs font-medium text-slate-400">mm</span>
          </div>

          <p className="mt-2 text-xs text-slate-400">
            {rainfallError ??
              (rainfall?.rainfall_30d_start && rainfall?.rainfall_30d_end
                ? `Observed rainfall, ${rainfall.rainfall_30d_start} to ${rainfall.rainfall_30d_end}.`
                : "Total observed rainfall over the previous 30 days.")}
          </p>
        </div>
      </section>

      {/* Hourly Rain Forecast: amount (bars) + chance (line) for every hour */}
      <section className="mt-6 rounded-xl border border-navy-800 bg-navy-900/60 p-5 shadow-lg backdrop-blur-md">
        <HourlyRainChart data={hourlyForecasts} height={320} />

        {hourlyForecasts.length > 0 && hourlyRainTotal === 0 && (
          <p className="mt-3 text-center text-xs text-slate-400">
            No measurable rain is forecast for the next 48 hours. The line still
            shows the chance of rain for every hour.
          </p>
        )}
      </section>

      {/* Soil Moisture */}
      <section className="mt-6 rounded-xl border border-navy-800 bg-navy-900/60 p-5 shadow-lg backdrop-blur-md">
        <div className="mb-4 flex items-center gap-2">
          <Droplets className="h-4 w-4 text-cyan-400" />
          <h3 className="text-sm font-semibold uppercase tracking-wider text-white">
            Soil Moisture by Depth
          </h3>
        </div>

        {soil &&
        (soil.topsoil_moisture_0_7cm !== null ||
          soil.root_zone_moisture_7_28cm !== null ||
          soil.deep_moisture_28_100cm !== null) ? (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              {[
                {
                  label: "Topsoil (0–7 cm)",
                  value: soil.topsoil_moisture_0_7cm,
                },
                {
                  label: "Root zone (7–28 cm)",
                  value: soil.root_zone_moisture_7_28cm,
                },
                {
                  label: "Deep soil (28–100 cm)",
                  value: soil.deep_moisture_28_100cm,
                },
              ].map((layer) => (
                <div
                  key={layer.label}
                  className="rounded-lg border border-navy-800 bg-navy-950/80 p-3.5"
                >
                  <div className="text-xs text-slate-400">{layer.label}</div>

                  <div className="mt-1 font-mono text-2xl font-bold text-cyan-300">
                    {layer.value === null
                      ? "—"
                      : formatNumber(layer.value * 100, 1)}
                    <span className="ml-1 text-xs text-slate-400">%</span>
                  </div>

                  <div className="mt-2 h-1.5 w-full overflow-hidden rounded bg-navy-800">
                    <div
                      className="h-full rounded bg-cyan-400"
                      style={{
                        width: `${Math.min(
                          100,
                          Math.max(0, (layer.value ?? 0) * 100),
                        )}%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>

            <p className="mt-3 text-[11px] text-slate-500">
              Volumetric water content (m³/m³ × 100) from {soil.data_source}
              {soil.timestamp ? `, ${soil.timestamp}` : ""}. Modelled values,
              not a calibrated saturation percentage.
            </p>
          </>
        ) : (
          <div className="rounded-lg border border-dashed border-navy-700 p-8 text-center">
            <Droplets className="mx-auto h-8 w-8 text-slate-500" />
            <p className="mt-3 text-sm text-slate-300">
              {soilError ?? "Soil moisture data is unavailable."}
            </p>
          </div>
        )}
      </section>

      {/* Seven-Day Forecast Table */}
      <section className="mt-6 rounded-xl border border-navy-800 bg-navy-900/60 p-5 shadow-lg backdrop-blur-md">
        <div className="mb-4 flex items-center justify-between border-b border-navy-800 pb-3">
          <div className="flex items-center gap-2">
            <Calendar className="h-4 w-4 text-cyan-400" />

            <h3 className="text-sm font-semibold uppercase tracking-wider text-white">
              7-Day Daily Meteorological Outlook
            </h3>
          </div>

          <span className="text-xs text-slate-400">Forecast</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="border-b border-navy-800 bg-navy-950/80 font-mono text-[11px] uppercase tracking-wider text-slate-400">
              <tr>
                <th className="px-3 py-2.5">Date</th>
                <th className="px-3 py-2.5">Conditions</th>
                <th className="px-3 py-2.5">Temp (Min / Max)</th>
                <th className="px-3 py-2.5">Rainfall Sum</th>
                <th className="px-3 py-2.5">Rain Probability</th>
                <th className="px-3 py-2.5">Max Wind</th>
                <th className="px-3 py-2.5">Status</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-navy-800/60">
              {dailyForecasts.map((day) => (
                <tr
                  key={day.date}
                  className="transition-colors hover:bg-navy-800/40"
                >
                  <td className="px-3 py-3 font-medium text-white">
                    {formatDate(day.date)}
                  </td>

                  <td className="px-3 py-3">
                    <span className="inline-flex items-center gap-1.5 text-slate-200">
                      {day.precipitation_sum_mm !== null &&
                      day.precipitation_sum_mm > 15 ? (
                        <CloudLightning className="h-3.5 w-3.5 text-amber-400" />
                      ) : day.precipitation_sum_mm !== null &&
                        day.precipitation_sum_mm > 0 ? (
                        <CloudRain className="h-3.5 w-3.5 text-cyan-400" />
                      ) : (
                        <Sun className="h-3.5 w-3.5 text-amber-300" />
                      )}

                      {day.weather_description || "—"}
                    </span>
                  </td>

                  <td className="px-3 py-3 font-mono">
                    <span className="text-cyan-300">
                      {formatNumber(day.temperature_min, 0)}°
                    </span>

                    <span className="mx-1 text-slate-500">/</span>

                    <span className="font-bold text-rose-300">
                      {formatNumber(day.temperature_max, 0)}°C
                    </span>
                  </td>

                  <td className="px-3 py-3 font-mono font-semibold text-cyan-400">
                    {formatNumber(day.precipitation_sum_mm)} mm
                  </td>

                  <td className="px-3 py-3 font-mono">
                    <span
                      className={`inline-block rounded px-1.5 py-0.5 text-[11px] ${
                        day.precipitation_probability_max === null
                          ? "bg-navy-800 text-slate-400"
                          : day.precipitation_probability_max > 60
                            ? "border border-rose-500/30 bg-rose-500/20 text-rose-300"
                            : day.precipitation_probability_max > 30
                              ? "border border-amber-500/30 bg-amber-500/20 text-amber-300"
                              : "bg-navy-800 text-slate-400"
                      }`}
                    >
                      {formatNumber(day.precipitation_probability_max, 0)}%
                    </span>
                  </td>

                  <td className="px-3 py-3 font-mono text-slate-300">
                    {formatNumber(day.wind_speed_max_kmh)} km/h
                  </td>

                  <td className="px-3 py-3">
                    <span className="font-mono text-[10px] text-emerald-400">
                      Forecast
                    </span>
                  </td>
                </tr>
              ))}

              {dailyForecasts.length === 0 && (
                <tr>
                  <td
                    colSpan={7}
                    className="px-3 py-8 text-center text-slate-400"
                  >
                    No daily forecast records are available.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </DashboardLayout>
  );
}
