"use client";

import React, { useEffect, useState, useCallback } from "react";
import dynamic from "next/dynamic";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { KPICard } from "@/components/common/KPICard";
import { RiskBadge } from "@/components/common/RiskBadge";
import { useLanguage } from "@/context/LanguageContext";
import {
  fetchDashboardKPIs,
  fetchAlerts,
  fetchWeatherCurrent,
  fetchHydrologyStations,
  fetchRiskAssessments,
} from "@/lib/api";
import { MONITORING_LOCATIONS } from "@/lib/constants";
import {
  DashboardKPIs,
  Alert,
  WeatherData,
  Station,
  RiskAssessment,
  MonitoringLocation,
} from "@/types";
import {
  Waves,
  Maximize2,
  TrendingUp,
  AlertTriangle,
  CloudRain,
  ShieldAlert,
  ArrowRight,
  X,
  Compass,
  Gauge,
  Droplets,
  Wind,
  RefreshCw,
} from "lucide-react";

// SSR-safe dynamic map import
const TonleSapMap = dynamic(() => import("@/components/maps/TonleSapMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[540px] w-full items-center justify-center rounded-xl border border-navy-800 bg-navy-950 text-slate-400">
      <div className="flex flex-col items-center gap-2">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
        <span className="text-xs">Loading Tonle Sap Geospatial Canvas...</span>
      </div>
    </div>
  ),
});

export default function DashboardPage() {
  const { language, t } = useLanguage();
  const [kpis, setKpis] = useState<DashboardKPIs | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [weather, setWeather] = useState<WeatherData | null>(null);
  const [stations, setStations] = useState<Station[]>([]);
  const [riskList, setRiskList] = useState<RiskAssessment[]>([]);
  const [selectedProvince, setSelectedProvince] = useState<string>("all");
  const [selectedStation, setSelectedStation] = useState<Station | null>(null);
  const [isSlideOverOpen, setIsSlideOverOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());

  // Load all dashboard data
  const loadData = useCallback(async () => {
    try {
      setRefreshing(true);
      const [kpiRes, alertsRes, stationsRes, riskRes, weatherRes] =
        await Promise.all([
          fetchDashboardKPIs(),
          fetchAlerts(),
          fetchHydrologyStations(),
          fetchRiskAssessments(),
          fetchWeatherCurrent(
            selectedProvince === "all" ? "pursat" : selectedProvince,
          ),
        ]);

      setKpis(kpiRes);
      setAlerts(alertsRes);
      setStations(stationsRes);
      setRiskList(riskRes);
      setWeather(weatherRes);
      setLastRefreshed(new Date());
    } catch (err) {
      console.error("Failed to load dashboard data:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [selectedProvince]);

  // Initial load
  useEffect(() => {
    loadData();
  }, [loadData]);

  // Auto-refresh every 5 minutes (300,000 ms)
  useEffect(() => {
    const interval = setInterval(
      () => {
        loadData();
      },
      5 * 60 * 1000,
    );
    return () => clearInterval(interval);
  }, [loadData]);

  const handleSelectStation = (station: Station) => {
    setSelectedStation(station);
    setIsSlideOverOpen(true);
  };

  const handleSelectLocation = (loc: MonitoringLocation) => {
    const matched = riskList.find((r) => r.location_id === loc.id);
    if (matched) {
      setSelectedProvince(loc.id);
    }
  };

  return (
    <DashboardLayout
      title={t("dashboard.title", "Tonle Sap Flood Intelligence Dashboard")}
      subtitle={t(
        "dashboard.subtitle",
        "Real-time multi-sensor hydrological pulse surveillance, satellite water extent & AI flood hazard predictions",
      )}
      lastUpdated={lastRefreshed}
      actions={
        <div className="flex items-center gap-2">
          <button
            onClick={() => loadData()}
            disabled={refreshing}
            className="flex items-center gap-1.5 rounded-lg border border-navy-800 bg-navy-900 px-3 py-1.5 text-xs font-medium text-slate-300 shadow-sm transition-colors hover:bg-navy-800 hover:text-white"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 text-cyan-400 ${refreshing ? "animate-spin" : ""}`}
            />
            <span>
              {refreshing
                ? t("dashboard.syncing", "Syncing...")
                : t("dashboard.refresh", "Refresh")}
            </span>
          </button>
        </div>
      }
    >
      {/* 6 Responsive KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <div
              key={`skel-${i}`}
              className="h-28 animate-pulse rounded-xl border border-navy-800 bg-navy-900/60 p-4"
            />
          ))
        ) : (
          <>
            <KPICard
              title={t("dashboard.kpi.waterLevel", "Lake Water Level")}
              value={kpis?.water_level_m?.toFixed(2) ?? "7.82"}
              unit="m"
              trend={
                kpis?.water_level_anomaly_m && kpis.water_level_anomaly_m > 0
                  ? "up"
                  : "stable"
              }
              trendValue={`+${kpis?.water_level_anomaly_m ?? 0.45}m ${t("dashboard.kpi.anomaly", "anomaly")}`}
              icon={Waves}
              color="cyan"
              description={t(
                "dashboard.kpi.waterLevelDesc",
                "Kampong Luong telemetric datum",
              )}
            />

            <KPICard
              title={t("dashboard.kpi.inundationExtent", "Inundation Extent")}
              value={kpis?.inundation_area_km2?.toLocaleString() ?? "8,420"}
              unit="km²"
              trend="up"
              trendValue={`+${kpis?.inundation_change_pct ?? 3.4}% ${t("dashboard.kpi.sevenDay", "7-day")}`}
              icon={Maximize2}
              color="navy"
              description={t(
                "dashboard.kpi.inundationDesc",
                "Copernicus SAR & JRC fusion",
              )}
            />

            <KPICard
              title={t("dashboard.kpi.storageVolume", "Lake Storage Volume")}
              value={kpis?.lake_volume_bcm?.toFixed(1) ?? "38.6"}
              unit="BCM"
              trend="up"
              trendValue={t(
                "dashboard.kpi.monsoonPhase",
                "Monsoon expansion phase",
              )}
              icon={TrendingUp}
              color="emerald"
              description={t(
                "dashboard.kpi.storageDesc",
                "Billion Cubic Meters",
              )}
            />

            <KPICard
              title={t("dashboard.kpi.pulseFlow", "Pulse Flow Dynamics")}
              value={
                kpis?.flow_direction === "reverse_inflow"
                  ? t("dashboard.kpi.reverseInflow", "Reverse Inflow")
                  : t("dashboard.kpi.outflow", "Outflow")
              }
              unit=""
              trend="up"
              trendValue={`${kpis?.flow_rate_m3s?.toLocaleString() ?? "3,420"} m³/s`}
              icon={Compass}
              color="amber"
              description={t(
                "dashboard.kpi.pulseDesc",
                "Tonle Sap River pulse into lake",
              )}
            />

            <KPICard
              title={t("dashboard.kpi.activeAlerts", "Active Flood Alerts")}
              value={alerts.length}
              unit={t("dashboard.kpi.alertsUnit", "Alerts")}
              trend={alerts.length > 0 ? "up" : "stable"}
              trendValue={
                alerts.length > 0
                  ? t("dashboard.kpi.surveillanceActive", "Surveillance Active")
                  : t("dashboard.kpi.allClear", "All Clear")
              }
              icon={AlertTriangle}
              color="rose"
              description={t(
                "dashboard.kpi.alertsDesc",
                "Automated threshold warnings",
              )}
            />

            <KPICard
              title={t("dashboard.kpi.highestRisk", "Highest Risk Sector")}
              value={kpis?.highest_risk_province ?? "Kampong Chhnang"}
              unit=""
              trend="up"
              trendValue={kpis?.highest_risk_level?.toUpperCase() ?? "MODERATE"}
              icon={ShieldAlert}
              color="purple"
              description={t(
                "dashboard.kpi.highestRiskDesc",
                "Bottleneck confluence sector",
              )}
            />
          </>
        )}
      </div>

      {/* Main Grid: Interactive Map (~60-65%) + Side Intelligence Panel (~35-40%) */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Large Geospatial Map */}
        <div className="lg:col-span-8 flex flex-col space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="flex h-2.5 w-2.5 rounded-full bg-cyan-400 animate-pulse" />
              <h2 className="text-sm font-semibold uppercase tracking-wider text-white">
                {t(
                  "dashboard.mapHeading",
                  "Tonle Sap Basin Geospatial Intelligence",
                )}
              </h2>
            </div>
            <span className="text-xs text-slate-400 hidden sm:inline">
              {t(
                "dashboard.mapHint",
                "Click any station or province pin to inspect telemetry",
              )}
            </span>
          </div>

          <TonleSapMap
            height="560px"
            selectedStationId={selectedStation?.id}
            selectedLocationId={
              selectedProvince !== "all" ? selectedProvince : undefined
            }
            onSelectStation={handleSelectStation}
            onSelectLocation={handleSelectLocation}
            stations={stations}
            riskAssessments={riskList}
            showJRCWater={true}
          />

          {/* Quick Basin Status Strip */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 rounded-xl border border-navy-800 bg-navy-900/60 p-3 text-xs">
            <div className="border-r border-navy-800/80 pr-2">
              <span className="text-slate-400 block text-[11px]">
                {t("dashboard.status.hydrologicalLabel", "Hydrological Status")}
              </span>
              <span className="font-semibold text-cyan-300">
                {t(
                  "dashboard.status.hydrologicalValue",
                  "Monsoon Reverse Flow Active",
                )}
              </span>
            </div>
            <div className="border-r border-navy-800/80 pr-2">
              <span className="text-slate-400 block text-[11px]">
                {t("dashboard.status.velocityLabel", "Prek Kdam Velocity")}
              </span>
              <span className="font-semibold text-slate-200">
                {t("dashboard.status.velocityValue", "1.82 m/s (Inflow)")}
              </span>
            </div>
            <div className="border-r border-navy-800/80 pr-2">
              <span className="text-slate-400 block text-[11px]">
                {t("dashboard.status.satelliteLabel", "Satellite Coverage")}
              </span>
              <span className="font-semibold text-emerald-400">
                {t(
                  "dashboard.status.satelliteValue",
                  "Sentinel-1 SAR Orbit #018",
                )}
              </span>
            </div>
            <div>
              <span className="text-slate-400 block text-[11px]">
                {t("dashboard.status.modelLabel", "Next Model Run")}
              </span>
              <span className="font-semibold text-slate-300">
                {t("dashboard.status.modelValue", "GloFAS Cycle 12:00 UTC")}
              </span>
            </div>
          </div>
        </div>

        {/* Side Panel: Province Filter, Active Alerts, Live Weather Summary */}
        <div className="lg:col-span-4 flex flex-col space-y-5">
          {/* Province Filter Dropdown */}
          <div className="rounded-xl border border-navy-800 bg-navy-900/60 p-4 shadow-lg backdrop-blur-md">
            <div className="flex items-center justify-between mb-2">
              <label
                htmlFor="province-filter"
                className="text-xs font-semibold uppercase tracking-wider text-slate-400"
              >
                {t("dashboard.filterProvince", "Filter Basin Province")}
              </label>
              <span className="text-[11px] font-mono text-cyan-400">
                {t("dashboard.fiveProvinces", "5 Provinces")}
              </span>
            </div>
            <select
              id="province-filter"
              value={selectedProvince}
              onChange={(e) => setSelectedProvince(e.target.value)}
              className="w-full rounded-lg border border-navy-700 bg-navy-950 px-3 py-2 text-sm text-slate-100 focus:border-cyan-500 focus:outline-none"
            >
              <option value="all">
                {t(
                  "dashboard.allProvinces",
                  "All Basin Provinces (Tonle Sap Overview)",
                )}
              </option>
              {MONITORING_LOCATIONS.filter((l) => l.type === "province").map(
                (p) => (
                  <option key={p.id} value={p.id}>
                    {language === "KM"
                      ? `${p.name_km} (${p.name})`
                      : `${p.name} (${p.name_km})`}
                  </option>
                ),
              )}
            </select>
          </div>

          {/* Live Convective Weather Card */}
          <div className="rounded-xl border border-navy-800 bg-navy-900/60 p-4 shadow-lg backdrop-blur-md">
            <div className="flex items-center justify-between border-b border-navy-800 pb-2 mb-3">
              <div className="flex items-center gap-1.5">
                <CloudRain className="h-4 w-4 text-cyan-400" />
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                  {t("dashboard.liveWeather", "Live Weather")} (
                  {weather?.location_name || "Pursat"})
                </span>
              </div>
              <span className="text-[10px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-1.5 py-0.5 rounded">
                Open-Meteo
              </span>
            </div>

            {weather ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-3xl font-bold tracking-tight text-white font-mono">
                      {weather.temperature_c !== null
                        ? `${weather.temperature_c.toFixed(1)}°C`
                        : "N/A"}
                    </div>
                    <div className="text-xs text-slate-400 capitalize">
                      {weather.weather_description}
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="text-xs text-slate-400 block">
                      {t("dashboard.precipitation", "Precipitation")}
                    </span>
                    <span className="text-lg font-bold text-cyan-300 font-mono">
                      {weather.precipitation_mm !== null
                        ? weather.precipitation_mm.toFixed(1)
                        : "—"}{" "}
                      mm
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2 border-t border-navy-800/80 pt-2.5 text-xs">
                  <div>
                    <span className="text-slate-400 block text-[10px] flex items-center gap-1">
                      <Droplets className="h-3 w-3 text-cyan-400" />{" "}
                      {t("dashboard.humidity", "Humidity")}
                    </span>
                    <span className="font-semibold text-slate-200">
                      {weather.humidity_pct}%
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px] flex items-center gap-1">
                      <Wind className="h-3 w-3 text-cyan-400" />{" "}
                      {t("dashboard.wind", "Wind")}
                    </span>
                    <span className="font-semibold text-slate-200">
                      {weather.wind_speed_kmh} km/h
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px] flex items-center gap-1">
                      <Gauge className="h-3 w-3 text-cyan-400" />{" "}
                      {t("dashboard.cloud", "Cloud")}
                    </span>
                    <span className="font-semibold text-slate-200">
                      {weather.cloud_cover_pct}%
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="py-6 text-center text-xs text-slate-500">
                {t("dashboard.loadingWeather", "Loading atmospheric data...")}
              </div>
            )}
          </div>

          {/* Active Alerts List */}
          <div className="flex-1 rounded-xl border border-navy-800 bg-navy-900/60 p-4 shadow-lg backdrop-blur-md">
            <div className="flex items-center justify-between border-b border-navy-800 pb-2 mb-3">
              <div className="flex items-center gap-1.5">
                <AlertTriangle className="h-4 w-4 text-amber-400" />
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                  {t("dashboard.activeAlertsTitle", "Active Alerts")} (
                  {alerts.length})
                </span>
              </div>
              <a
                href="/alerts"
                className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-0.5"
              >
                {t("dashboard.allAlerts", "All alerts")}{" "}
                <ArrowRight className="h-3 w-3" />
              </a>
            </div>

            <div className="space-y-3">
              {alerts.length === 0 ? (
                <div className="py-8 text-center text-xs text-slate-500">
                  {t(
                    "dashboard.noAlerts",
                    "No active flood advisories at this time",
                  )}
                </div>
              ) : (
                alerts.map((alt) => (
                  <div
                    key={alt.id}
                    className="rounded-lg border border-navy-800 bg-navy-950/70 p-3 transition-colors hover:border-navy-700"
                  >
                    <div className="flex items-start justify-between gap-2 mb-1.5">
                      <h4 className="text-xs font-semibold text-white line-clamp-1">
                        {alt.title}
                      </h4>
                      <RiskBadge
                        level={
                          alt.severity === "danger"
                            ? "very_high"
                            : alt.severity === "warning"
                              ? "high"
                              : "moderate"
                        }
                        size="sm"
                      />
                    </div>
                    <p className="text-[11px] text-slate-400 line-clamp-2 mb-2 leading-relaxed">
                      {alt.message}
                    </p>
                    <div className="flex items-center justify-between text-[10px] text-slate-500 border-t border-navy-900 pt-1.5">
                      <span>{alt.province}</span>
                      <span>
                        {new Date(alt.issued_at).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Station Slide-Over Detail Panel */}
      {isSlideOverOpen && selectedStation && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-black/60 backdrop-blur-sm transition-opacity">
          <div className="absolute inset-y-0 right-0 max-w-full flex pl-10">
            <div className="w-screen max-w-md border-l border-navy-800 bg-navy-950 p-6 shadow-2xl flex flex-col justify-between overflow-y-auto">
              <div>
                {/* Header */}
                <div className="flex items-center justify-between border-b border-navy-800 pb-4 mb-4">
                  <div>
                    <span className="text-[11px] uppercase font-bold text-cyan-400 tracking-wider">
                      {t(
                        "dashboard.station.inspection",
                        "Telemetric Station Inspection",
                      )}
                    </span>
                    <h3 className="text-xl font-bold text-white mt-1">
                      {language === "KM"
                        ? selectedStation.name_km
                        : selectedStation.name}
                    </h3>
                    <p className="text-xs text-slate-400 font-sans">
                      {language === "KM"
                        ? selectedStation.name
                        : selectedStation.name_km}
                    </p>
                  </div>
                  <button
                    onClick={() => setIsSlideOverOpen(false)}
                    className="rounded-lg p-2 text-slate-400 hover:bg-navy-900 hover:text-white"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>

                {/* Key Metrics */}
                <div className="grid grid-cols-2 gap-3 mb-6">
                  <div className="rounded-lg border border-navy-800 bg-navy-900/60 p-3">
                    <span className="text-[11px] text-slate-400 block">
                      {t("dashboard.station.waterLevel", "Water Level")}
                    </span>
                    <span className="text-2xl font-bold text-cyan-300 font-mono">
                      {selectedStation.water_level_m}{" "}
                      <span className="text-xs font-normal">m</span>
                    </span>
                  </div>
                  <div className="rounded-lg border border-navy-800 bg-navy-900/60 p-3">
                    <span className="text-[11px] text-slate-400 block">
                      {t("dashboard.station.dischargeRate", "Discharge Rate")}
                    </span>
                    <span className="text-2xl font-bold text-slate-100 font-mono">
                      {selectedStation.discharge_m3s?.toLocaleString()}{" "}
                      <span className="text-xs font-normal">m³/s</span>
                    </span>
                  </div>
                  <div className="rounded-lg border border-navy-800 bg-navy-900/60 p-3">
                    <span className="text-[11px] text-slate-400 block">
                      {t("dashboard.station.alarmThreshold", "Alarm Threshold")}
                    </span>
                    <span className="text-xl font-bold text-amber-400 font-mono">
                      {selectedStation.alarm_level_m} m
                    </span>
                  </div>
                  <div className="rounded-lg border border-navy-800 bg-navy-900/60 p-3">
                    <span className="text-[11px] text-slate-400 block">
                      {t(
                        "dashboard.station.floodCritical",
                        "Flood Critical Level",
                      )}
                    </span>
                    <span className="text-xl font-bold text-rose-400 font-mono">
                      {selectedStation.flood_level_m} m
                    </span>
                  </div>
                </div>

                {/* Metadata & Status */}
                <div className="space-y-3 text-xs border border-navy-800 rounded-lg p-3 bg-navy-900/40 mb-6">
                  <div className="flex justify-between">
                    <span className="text-slate-400">
                      {t("dashboard.station.riverBody", "River / Water Body:")}
                    </span>
                    <span className="text-white font-medium">
                      {selectedStation.river}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">
                      {t(
                        "dashboard.station.coordinates",
                        "Geographic Coordinates:",
                      )}
                    </span>
                    <span className="text-slate-300 font-mono">
                      {selectedStation.lat.toFixed(4)}°N,{" "}
                      {selectedStation.lon.toFixed(4)}°E
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">
                      {t("dashboard.station.trend", "Hydraulic Trend:")}
                    </span>
                    <span className="text-cyan-400 capitalize font-medium">
                      {selectedStation.trend}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">
                      {t(
                        "dashboard.station.telemetryStatus",
                        "Telemetry Status:",
                      )}
                    </span>
                    <span className="text-emerald-400 font-medium">
                      {t("dashboard.station.onlineNominal", "Online & Nominal")}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">
                      {t("dashboard.station.lastPoll", "Last Telemetric Poll:")}
                    </span>
                    <span className="text-slate-300">
                      {new Date(
                        selectedStation.last_reading_time || Date.now(),
                      ).toLocaleTimeString()}
                    </span>
                  </div>
                </div>

                <div className="rounded-lg border border-cyan-800/50 bg-cyan-950/30 p-3 text-xs text-cyan-200">
                  <p className="font-semibold mb-1">
                    {t(
                      "dashboard.station.glofasTitle",
                      "GloFAS Hydraulic Synthesis:",
                    )}
                  </p>
                  <p className="text-[11px] text-cyan-300/80 leading-relaxed">
                    {t(
                      "dashboard.station.glofasDesc",
                      "This gauging station is utilized in our CatBoost hydrological ensemble to model the Tonle Sap reverse flow pulse and backwater storage capacity.",
                    )}
                  </p>
                </div>
              </div>

              <div className="pt-6 border-t border-navy-800 flex items-center gap-3">
                <a
                  href={`/hydrology?station=${selectedStation.id}`}
                  className="flex-1 text-center rounded-lg bg-cyan-600 px-4 py-2 text-xs font-semibold text-white shadow-md hover:bg-cyan-500 transition-colors"
                >
                  {t(
                    "dashboard.station.fullAnalysis",
                    "Full Hydrology Analysis",
                  )}
                </a>
                <button
                  onClick={() => setIsSlideOverOpen(false)}
                  className="rounded-lg border border-navy-700 bg-navy-900 px-4 py-2 text-xs font-medium text-slate-300 hover:text-white"
                >
                  {t("dashboard.station.close", "Close")}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
