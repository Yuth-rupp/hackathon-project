"use client";

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { TimeSeriesChart } from "@/components/charts/TimeSeriesChart";
import { fetchRiverDischarge, fetchHydrologyStations } from "@/lib/api";
import { MONITORING_LOCATIONS, API_BASE_URL } from "@/lib/constants";
import { useLanguage } from "@/context/LanguageContext";
import { DataFreshnessLevel, RiverDischarge, Station } from "@/types";
import {
  StreamConnection,
  useHydrologyStream,
} from "@/hooks/useHydrologyStream";
import {
  Waves,
  Download,
  RefreshCw,
  Info,
  AlertCircle,
  Droplets,
  Activity,
  Radio,
  WifiOff,
} from "lucide-react";

// ============================================================
// HELPERS
// ============================================================

function formatNumber(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "Unavailable";
  }

  return value.toLocaleString(undefined, {
    maximumFractionDigits: digits,
  });
}

/**
 * Parse an API timestamp. Values without a timezone are UTC (the backend
 * stores UTC), so "Z" is added before parsing - otherwise the browser would
 * read them as local time and show the wrong hour.
 */
function toDate(value: string | null | undefined): Date | null {
  if (!value) return null;

  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/.test(value);
  const date = new Date(hasZone ? value : `${value}Z`);

  return Number.isNaN(date.getTime()) ? null : date;
}

function formatDate(value: string | null | undefined) {
  if (!value) return "Unavailable";

  const date = toDate(value);

  if (!date) return value;

  return date.toLocaleString();
}

function formatAge(value: string | null | undefined, now: number) {
  const date = toDate(value);

  if (!date) return "";

  const seconds = Math.max(0, Math.floor((now - date.getTime()) / 1000));

  if (seconds < 10) return "just now";
  if (seconds < 60) return `${seconds}s ago`;

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 48) return `${hours} h ago`;

  return `${Math.floor(hours / 24)} d ago`;
}

const FRESHNESS_BADGES: Record<
  DataFreshnessLevel,
  { label: string; className: string; hint: string }
> = {
  live: {
    label: "LIVE",
    className: "border-emerald-500/40 bg-emerald-500/10 text-emerald-400",
    hint: "Measured recently",
  },
  delayed: {
    label: "DELAYED",
    className: "border-amber-500/40 bg-amber-500/10 text-amber-400",
    hint: "Last measurement is older than the live window",
  },
  stale: {
    label: "STALE",
    className: "border-red-500/40 bg-red-500/10 text-red-400",
    hint: "No recent measurement",
  },
  baseline: {
    label: "BASELINE - NOT LIVE",
    className: "border-violet-500/40 bg-violet-500/10 text-violet-300",
    hint: "Stored placeholder value, not a real measurement",
  },
  no_data: {
    label: "NO DATA",
    className: "border-slate-600 bg-slate-800/50 text-slate-400",
    hint: "No readings stored",
  },
};

function LiveIndicator({
  connection,
  lastChecked,
  now,
}: {
  connection: StreamConnection;
  lastChecked: Date | null;
  now: number;
}) {
  const styles: Record<
    StreamConnection,
    { label: string; className: string; dot: string }
  > = {
    live: {
      label: "Live stream",
      className: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
      dot: "bg-emerald-400 animate-pulse",
    },
    polling: {
      label: "Polling (stream down)",
      className: "border-amber-500/40 bg-amber-500/10 text-amber-300",
      dot: "bg-amber-400",
    },
    connecting: {
      label: "Connecting...",
      className: "border-slate-600 bg-slate-800/50 text-slate-300",
      dot: "bg-slate-400 animate-pulse",
    },
    offline: {
      label: "Offline",
      className: "border-red-500/40 bg-red-500/10 text-red-300",
      dot: "bg-red-400",
    },
  };

  const style = styles[connection];

  return (
    <div
      className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold ${style.className}`}
      title="Connection to the FloodPulse server"
    >
      {connection === "offline" ? (
        <WifiOff className="h-3.5 w-3.5" />
      ) : (
        <Radio className="h-3.5 w-3.5" />
      )}
      <span className={`h-2 w-2 rounded-full ${style.dot}`} />
      <span>{style.label}</span>
      {lastChecked && (
        <span className="hidden font-normal opacity-80 md:inline">
          · checked {formatAge(lastChecked.toISOString(), now)}
        </span>
      )}
    </div>
  );
}

function statusColor(status: string) {
  switch (status) {
    case "CRITICAL_FLOOD":
      return "border-red-500/40 bg-red-500/10 text-red-400";
    case "WARNING":
      return "border-amber-500/40 bg-amber-500/10 text-amber-400";
    case "NORMAL":
      return "border-emerald-500/40 bg-emerald-500/10 text-emerald-400";
    default:
      return "border-slate-600 bg-slate-800/50 text-slate-400";
  }
}

function dischargeStatusColor(status: string) {
  switch (status) {
    case "HIGH":
      return "text-red-400";
    case "LOW":
      return "text-amber-400";
    case "NORMAL":
      return "text-emerald-400";
    default:
      return "text-slate-400";
  }
}

function downloadCSV(data: RiverDischarge | null) {
  if (!data || data.forecast.length === 0) return;

  const headers = [
    "Date",
    "Discharge_m3s",
    "Discharge_Max",
    "Discharge_Mean",
    "Discharge_Median",
    "Data_Source",
  ];

  const rows = data.forecast.map((item) => [
    item.date,
    item.discharge_m3s ?? "",
    item.discharge_max ?? "",
    item.discharge_mean ?? "",
    item.discharge_median ?? "",
    item.data_source ?? "",
  ]);

  const csv = [
    headers.join(","),
    ...rows.map((row) =>
      row.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(","),
    ),
  ].join("\n");

  const blob = new Blob([csv], {
    type: "text/csv;charset=utf-8;",
  });

  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = `floodpulse_discharge_${data.location_name}_${new Date()
    .toISOString()
    .slice(0, 10)}.csv`;

  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  URL.revokeObjectURL(url);
}

// ============================================================
// PAGE
// ============================================================

export default function HydrologyPage() {
  const { language } = useLanguage();
  const isKm = language === "KM";

  // ----------------------------------------------------------
  // DISCHARGE MONITORING LOCATIONS
  // ----------------------------------------------------------

  const monitoringLocations = useMemo(
    () =>
      MONITORING_LOCATIONS.filter((location) => location.type === "province"),
    [],
  );

  const [selectedLocationId, setSelectedLocationId] = useState("siem-reap");

  const [dischargeData, setDischargeData] = useState<RiverDischarge | null>(
    null,
  );

  const [dischargeLoading, setDischargeLoading] = useState(true);
  const [dischargeError, setDischargeError] = useState<string | null>(null);

  // ----------------------------------------------------------
  // HYDROLOGICAL GAUGE STATIONS
  // ----------------------------------------------------------

  const [stations, setStations] = useState<Station[]>([]);
  const [stationsLoading, setStationsLoading] = useState(true);
  const [stationsError, setStationsError] = useState<string | null>(null);

  const [selectedStationId, setSelectedStationId] = useState("");
  const [compareStationId, setCompareStationId] = useState("");

  // ----------------------------------------------------------
  // STATION TIME SERIES
  // ----------------------------------------------------------

  const [primaryTimeseries, setPrimaryTimeseries] = useState<any[]>([]);
  const [compareTimeseries, setCompareTimeseries] = useState<any[]>([]);

  const [timeseriesLoading, setTimeseriesLoading] = useState(false);
  const [timeseriesError, setTimeseriesError] = useState<string | null>(null);

  // Refresh trigger
  const [refreshKey, setRefreshKey] = useState(0);
  const [refreshing, setRefreshing] = useState(false);

  // Real-time bookkeeping
  const [now, setNow] = useState(() => Date.now());
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  // Remember what is already on screen so background refreshes are silent
  // (no "Loading..." flicker) and a failed refresh keeps the last good data.
  const dischargeKeyRef = useRef("");
  const stationsLoadedRef = useRef(false);
  const timeseriesKeyRef = useRef("");

  // Re-render every 15 s so "x min ago" labels keep counting.
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 15_000);
    return () => clearInterval(timer);
  }, []);

  // ----------------------------------------------------------
  // FETCH DISCHARGE FORECAST
  // ----------------------------------------------------------

  const loadDischarge = useCallback(async () => {
    const key = selectedLocationId;
    const isBackgroundRefresh = dischargeKeyRef.current === key;

    if (!isBackgroundRefresh) {
      setDischargeLoading(true);
      setDischargeError(null);
    }

    try {
      const result = await fetchRiverDischarge(key);
      setDischargeData(result);
      setDischargeError(null);
      dischargeKeyRef.current = key;
      setLastChecked(new Date());
    } catch (error) {
      console.error("Discharge forecast error:", error);

      // A failed background refresh keeps the last good data on screen.
      if (!isBackgroundRefresh) {
        setDischargeData(null);
        setDischargeError(
          error instanceof Error
            ? error.message
            : "Unable to load discharge forecast.",
        );
      }
    } finally {
      setDischargeLoading(false);
    }
  }, [selectedLocationId]);

  useEffect(() => {
    loadDischarge();
  }, [loadDischarge, refreshKey]);

  // ----------------------------------------------------------
  // FETCH HYDROLOGICAL STATIONS
  // ----------------------------------------------------------

  useEffect(() => {
    let cancelled = false;

    async function loadStations() {
      const isBackgroundRefresh = stationsLoadedRef.current;

      if (!isBackgroundRefresh) {
        setStationsLoading(true);
        setStationsError(null);
      }

      try {
        const result = await fetchHydrologyStations();

        if (cancelled) return;

        stationsLoadedRef.current = true;
        setStationsError(null);
        setLastChecked(new Date());
        setStations(result);

        if (result.length > 0) {
          setSelectedStationId((current) => {
            if (current && result.some((s) => s.id === current)) {
              return current;
            }

            return result[0].id;
          });

          setCompareStationId((current) => {
            if (
              current &&
              result.some((s) => s.id === current) &&
              current !== result[0].id
            ) {
              return current;
            }

            return result.length > 1 ? result[1].id : "";
          });
        }
      } catch (error) {
        console.error("Hydrological station error:", error);

        if (!cancelled && !stationsLoadedRef.current) {
          setStations([]);
          setStationsError(
            error instanceof Error
              ? error.message
              : "Unable to load hydrological stations.",
          );
        }
      } finally {
        if (!cancelled) setStationsLoading(false);
      }
    }

    loadStations();

    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  // ----------------------------------------------------------
  // FETCH ACTUAL STATION TIME SERIES
  // ----------------------------------------------------------

  useEffect(() => {
    if (!selectedStationId) return;

    let cancelled = false;

    const seriesKey = `${selectedStationId}|${compareStationId}`;
    const isBackgroundRefresh = timeseriesKeyRef.current === seriesKey;

    async function loadStationComparison() {
      if (!isBackgroundRefresh) {
        setTimeseriesLoading(true);
        setTimeseriesError(null);
      }

      try {
        const requests = [
          fetch(
            `${API_BASE_URL}/hydrology/stations/${selectedStationId}/timeseries?limit=100`,
            { cache: "no-store" },
          ),
        ];

        if (compareStationId && compareStationId !== selectedStationId) {
          requests.push(
            fetch(
              `${API_BASE_URL}/hydrology/stations/${compareStationId}/timeseries?limit=100`,
              { cache: "no-store" },
            ),
          );
        }

        const responses = await Promise.all(requests);

        for (const response of responses) {
          if (!response.ok) {
            throw new Error(
              `Station time series request failed: HTTP ${response.status}`,
            );
          }
        }

        const primary = await responses[0].json();
        const comparison =
          responses.length > 1 ? await responses[1].json() : [];

        if (cancelled) return;

        timeseriesKeyRef.current = seriesKey;
        setTimeseriesError(null);
        setPrimaryTimeseries(Array.isArray(primary) ? primary : []);
        setCompareTimeseries(Array.isArray(comparison) ? comparison : []);
      } catch (error) {
        console.error("Station comparison error:", error);

        if (!cancelled && !isBackgroundRefresh) {
          setPrimaryTimeseries([]);
          setCompareTimeseries([]);
          setTimeseriesError(
            error instanceof Error
              ? error.message
              : "Unable to load station time series.",
          );
        }
      } finally {
        if (!cancelled) setTimeseriesLoading(false);
      }
    }

    loadStationComparison();

    return () => {
      cancelled = true;
    };
  }, [selectedStationId, compareStationId, refreshKey]);

  // ----------------------------------------------------------
  // SELECTED STATION
  // ----------------------------------------------------------

  const activeStation = stations.find(
    (station) => station.id === selectedStationId,
  );

  const comparisonStation = stations.find(
    (station) => station.id === compareStationId,
  );

  // ----------------------------------------------------------
  // DISCHARGE CHART DATA
  // ----------------------------------------------------------

  const dischargeChartData = useMemo(() => {
    if (!dischargeData?.forecast) return [];

    return dischargeData.forecast.map((point) => ({
      date: point.date,
      discharge_m3s: point.discharge_m3s,
      discharge_max: point.discharge_max,
      discharge_mean: point.discharge_mean,
      discharge_median: point.discharge_median,
    }));
  }, [dischargeData]);

  // ----------------------------------------------------------
  // STATION COMPARISON CHART DATA
  // ----------------------------------------------------------

  const comparisonChartData = useMemo(() => {
    const dataMap = new Map<string, any>();

    primaryTimeseries.forEach((point) => {
      const date = point.timestamp;

      dataMap.set(date, {
        timestamp: date,
        primary_level: point.water_level_m,
        compare_level: null,
      });
    });

    compareTimeseries.forEach((point) => {
      const date = point.timestamp;

      const existing = dataMap.get(date) ?? {
        timestamp: date,
        primary_level: null,
        compare_level: null,
      };

      existing.compare_level = point.water_level_m;
      dataMap.set(date, existing);
    });

    return Array.from(dataMap.values()).sort(
      (a, b) =>
        new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
    );
  }, [primaryTimeseries, compareTimeseries]);

  // ----------------------------------------------------------
  // REFRESH
  // ----------------------------------------------------------

  const handleRefresh = useCallback(() => {
    setRefreshKey((current) => current + 1);
  }, []);

  const handleManualRefresh = () => {
    handleRefresh();
    setRefreshing(true);
    setTimeout(() => setRefreshing(false), 800);
  };

  // ----------------------------------------------------------
  // REAL-TIME: server pushes events; polling is only a fallback
  // ----------------------------------------------------------

  const { connection } = useHydrologyStream({
    onData: handleRefresh,
    onPoll: handleRefresh,
    pollIntervalMs: 30_000,
  });

  // Newest timestamp we can honestly call "data updated":
  // real (non-baseline) gauge readings, or the discharge forecast run.
  const dataUpdatedAt = useMemo(() => {
    const candidates: Date[] = [];

    stations.forEach((station) => {
      if (station.freshness === "baseline") return;
      const date = toDate(station.last_reading_time);
      if (date) candidates.push(date);
    });

    const forecastDate = toDate(dischargeData?.updated_at);
    if (forecastDate) candidates.push(forecastDate);

    if (candidates.length === 0) return undefined;

    return new Date(
      Math.max(...candidates.map((date) => date.getTime())),
    ).toISOString();
  }, [stations, dischargeData]);

  // ----------------------------------------------------------
  // RENDER
  // ----------------------------------------------------------

  return (
    <DashboardLayout
      title={
        isKm
          ? "ការតាមដានជលសាស្ត្របឹងទន្លេសាប"
          : "Tonle Sap Hydrological Monitoring"
      }
      subtitle={
        isKm
          ? "ការត្រួតពិនិត្យកម្ពស់ទឹក និងការព្យាករណ៍លំហូរទឹក"
          : "River discharge forecasts, hydrological gauge readings and station comparison"
      }
      lastUpdated={dataUpdatedAt}
      actions={
        <div className="flex items-center gap-2">
          <LiveIndicator
            connection={connection}
            lastChecked={lastChecked}
            now={now}
          />

          <button
            onClick={handleManualRefresh}
            className="flex items-center gap-2 rounded-lg border border-navy-700 bg-navy-900 px-3 py-2 text-xs font-semibold text-slate-300 transition hover:border-cyan-500 hover:text-white"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`}
            />
            {isKm ? "ធ្វើបច្ចុប្បន្នភាព" : "Refresh"}
          </button>

          <button
            onClick={() => downloadCSV(dischargeData)}
            disabled={!dischargeData || dischargeData.forecast.length === 0}
            className="flex items-center gap-2 rounded-lg border border-cyan-800 bg-cyan-950/60 px-3 py-2 text-xs font-semibold text-cyan-300 transition hover:bg-cyan-900 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Download className="h-3.5 w-3.5" />
            {isKm ? "ទាញយក CSV" : "Export CSV"}
          </button>
        </div>
      }
    >
      {/* ================================================== */}
      {/* SECTION 1: DISCHARGE MONITORING LOCATION */}
      {/* ================================================== */}

      <section className="rounded-xl border border-navy-800 bg-navy-900/60 p-5">
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Waves className="h-5 w-5 text-cyan-400" />
              <h2 className="text-base font-bold text-white">
                {isKm
                  ? "ទីតាំងតាមដានលំហូរទឹក"
                  : "River Discharge Monitoring Locations"}
              </h2>
            </div>

            <p className="mt-1 text-xs text-slate-400">
              {isKm
                ? "ជ្រើសរើសខេត្តសម្រាប់មើលការព្យាករណ៍លំហូរទឹក"
                : "Select a monitoring location to view its stored discharge forecast."}
            </p>
          </div>

          <select
            value={selectedLocationId}
            onChange={(event) => setSelectedLocationId(event.target.value)}
            className="w-full rounded-lg border border-navy-700 bg-navy-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500 sm:w-64"
          >
            {monitoringLocations.map((location) => (
              <option key={location.id} value={location.id}>
                {isKm ? location.name_km : location.name}
              </option>
            ))}
          </select>
        </div>

        {dischargeLoading && (
          <div className="rounded-lg border border-navy-800 bg-navy-950/50 p-8 text-center text-sm text-slate-400">
            Loading discharge forecast...
          </div>
        )}

        {!dischargeLoading && dischargeError && (
          <div className="flex items-start gap-3 rounded-lg border border-red-500/30 bg-red-500/5 p-4">
            <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-400" />
            <div>
              <p className="text-sm font-semibold text-red-400">
                Discharge forecast unavailable
              </p>
              <p className="mt-1 text-xs text-slate-400">{dischargeError}</p>
            </div>
          </div>
        )}

        {!dischargeLoading && !dischargeError && dischargeData && (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-lg border border-navy-800 bg-navy-950/70 p-4">
                <p className="text-xs text-slate-400">
                  {isKm
                    ? "លំហូរទឹកដំបូងក្នុងការព្យាករណ៍"
                    : "First Forecast Discharge"}
                </p>
                <p className="mt-2 text-2xl font-bold text-cyan-300">
                  {formatNumber(dischargeData.current_discharge_m3s)}
                </p>
                <p className="mt-1 text-xs text-slate-500">m³/s</p>
              </div>

              <div className="rounded-lg border border-navy-800 bg-navy-950/70 p-4">
                <p className="text-xs text-slate-400">
                  {isKm
                    ? "មធ្យមយោងក្នុងការព្យាករណ៍"
                    : "Forecast Reference Mean"}
                </p>
                <p className="mt-2 text-2xl font-bold text-white">
                  {formatNumber(dischargeData.historical_mean_m3s)}
                </p>
                <p className="mt-1 text-xs text-slate-500">m³/s</p>
              </div>

              <div className="rounded-lg border border-navy-800 bg-navy-950/70 p-4">
                <p className="text-xs text-slate-400">
                  {isKm ? "ការប្រែប្រួល (%)" : "Difference from Reference"}
                </p>
                <p className="mt-2 text-2xl font-bold text-white">
                  {dischargeData.anomaly_pct == null
                    ? "Unavailable"
                    : `${dischargeData.anomaly_pct}%`}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {isKm
                    ? "ធៀបនឹងមធ្យមយោង"
                    : "Compared with forecast reference mean"}
                </p>
              </div>

              <div className="rounded-lg border border-navy-800 bg-navy-950/70 p-4">
                <p className="text-xs text-slate-400">
                  {isKm ? "ស្ថានភាពលំហូរ" : "Flow Classification"}
                </p>
                <p
                  className={`mt-2 text-xl font-bold ${dischargeStatusColor(dischargeData.flow_status)}`}
                >
                  {dischargeData.flow_status}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {dischargeData.forecast.length} forecast records
                </p>
              </div>
            </div>

            <div className="mt-4 rounded-lg border border-navy-800 bg-navy-950/50 p-3">
              <p className="text-xs text-slate-400">
                <strong className="text-slate-300">Location:</strong>{" "}
                {dischargeData.location_name}
                {" · "}
                <strong className="text-slate-300">Province:</strong>{" "}
                {dischargeData.province ?? "Unavailable"}
              </p>

              <p className="mt-1 text-xs text-slate-500">
                <strong className="text-slate-400">Sources:</strong>{" "}
                {dischargeData.data_sources.length > 0
                  ? dischargeData.data_sources.join(", ")
                  : "Unavailable"}
              </p>

              <p className="mt-1 text-xs text-slate-500">
                <strong className="text-slate-400">Retrieved:</strong>{" "}
                {formatDate(dischargeData.updated_at)}
                {dischargeData.updated_at &&
                  ` (${formatAge(dischargeData.updated_at, now)})`}
              </p>

              <p className="mt-1 text-xs text-slate-500">
                Modelled GloFAS forecast - refreshed by the server every few
                hours, not a live gauge measurement.
              </p>
            </div>
          </>
        )}
      </section>

      {/* ================================================== */}
      {/* SECTION 2: DISCHARGE FORECAST CHART */}
      {/* ================================================== */}

      <section className="rounded-xl border border-navy-800 bg-navy-900/60 p-5">
        <div className="mb-4">
          <h2 className="text-sm font-bold uppercase tracking-wider text-white">
            {isKm ? "ក្រាហ្វព្យាករណ៍លំហូរទឹក" : "River Discharge Forecast"}
          </h2>

          <p className="mt-1 text-xs text-slate-400">
            {isKm
              ? "ទិន្នន័យព្យាករណ៍ដែលបានរក្សាទុកក្នុងប្រព័ន្ធ"
              : "Stored forecast records. Missing values are left blank rather than estimated."}
          </p>
        </div>

        {dischargeLoading ? (
          <div className="flex h-72 items-center justify-center text-sm text-slate-400">
            Loading forecast chart...
          </div>
        ) : dischargeChartData.length > 0 ? (
          <TimeSeriesChart
            title={dischargeData?.location_name ?? "Discharge Forecast"}
            subtitle="Daily river discharge forecast"
            data={dischargeChartData}
            xKey="date"
            yKeys={[
              {
                key: "discharge_m3s",
                name: "Discharge",
                color: "#06b6d4",
                type: "area",
              },
              {
                key: "discharge_mean",
                name: "Forecast Mean",
                color: "#10b981",
                type: "line",
              },
              {
                key: "discharge_max",
                name: "Forecast Maximum",
                color: "#f59e0b",
                type: "line",
                strokeDasharray: "4 4",
              },
              {
                key: "discharge_median",
                name: "Forecast Median",
                color: "#a78bfa",
                type: "line",
              },
            ]}
            unit="m³/s"
            height={340}
          />
        ) : (
          <div className="flex h-64 items-center justify-center rounded-lg border border-dashed border-navy-700 text-center text-sm text-slate-400">
            No discharge forecast records available for this location.
          </div>
        )}
      </section>

      {/* ================================================== */}
      {/* SECTION 3: HYDROLOGICAL GAUGE STATIONS */}
      {/* ================================================== */}

      <section className="rounded-xl border border-navy-800 bg-navy-900/60 p-5">
        <div className="mb-4 flex items-center gap-2">
          <Droplets className="h-5 w-5 text-cyan-400" />
          <div>
            <h2 className="text-base font-bold text-white">
              {isKm ? "ស្ថានីយវាស់កម្ពស់ទឹក" : "Hydrological Gauge Stations"}
            </h2>
            <p className="mt-1 text-xs text-slate-400">
              {isKm
                ? "ជ្រើសរើសស្ថានីយវាស់កម្ពស់ទឹក"
                : "Actual gauge stations and their latest stored water-level readings."}
            </p>
          </div>
        </div>

        {stationsLoading && (
          <div className="p-8 text-center text-sm text-slate-400">
            Loading hydrological stations...
          </div>
        )}

        {!stationsLoading && stationsError && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-400">
            {stationsError}
          </div>
        )}

        {!stationsLoading && !stationsError && stations.length === 0 && (
          <div className="rounded-lg border border-dashed border-navy-700 p-8 text-center text-sm text-slate-400">
            No hydrological stations returned by the API.
          </div>
        )}

        {!stationsLoading && stations.length > 0 && (
          <>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
              {stations.map((station) => {
                const selected = station.id === selectedStationId;

                return (
                  <button
                    key={station.id}
                    type="button"
                    onClick={() => setSelectedStationId(station.id)}
                    className={`rounded-xl border p-4 text-left transition ${
                      selected
                        ? "border-cyan-500 bg-cyan-950/30 ring-1 ring-cyan-500/40"
                        : "border-navy-800 bg-navy-950/50 hover:border-navy-600"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-[10px] font-bold uppercase tracking-wider text-cyan-400">
                          {station.code}
                        </p>

                        <h3 className="mt-1 text-sm font-bold text-white">
                          {isKm
                            ? station.name_km || station.name
                            : station.name}
                        </h3>

                        <p className="mt-1 text-xs text-slate-400">
                          {station.water_body ?? "Water body unavailable"}
                        </p>
                      </div>

                      <Activity className="h-5 w-5 shrink-0 text-cyan-400" />
                    </div>

                    <div className="mt-4 grid grid-cols-2 gap-3 border-t border-navy-800 pt-3">
                      <div>
                        <p className="text-[10px] text-slate-400">
                          Water Level
                        </p>
                        <p className="mt-1 text-lg font-bold text-white">
                          {formatNumber(station.water_level_m)}{" "}
                          <span className="text-xs font-normal text-slate-400">
                            m
                          </span>
                        </p>
                      </div>

                      <div>
                        <p className="text-[10px] text-slate-400">
                          Alarm Level
                        </p>
                        <p className="mt-1 text-lg font-bold text-amber-400">
                          {formatNumber(station.alarm_level_m)}{" "}
                          <span className="text-xs font-normal text-slate-400">
                            m
                          </span>
                        </p>
                      </div>
                    </div>

                    <div className="mt-3 flex items-center justify-between gap-2">
                      <span
                        className={`rounded-md border px-2 py-1 text-[10px] font-semibold ${statusColor(station.status)}`}
                      >
                        {station.status}
                      </span>

                      <span
                        title={
                          FRESHNESS_BADGES[station.freshness ?? "no_data"].hint
                        }
                        className={`rounded-md border px-2 py-1 text-[10px] font-semibold ${
                          FRESHNESS_BADGES[station.freshness ?? "no_data"]
                            .className
                        }`}
                      >
                        {FRESHNESS_BADGES[station.freshness ?? "no_data"].label}
                      </span>
                    </div>

                    <p className="mt-2 text-[10px] text-slate-500">
                      Last reading: {formatDate(station.last_reading_time)}
                      {station.last_reading_time &&
                        ` (${formatAge(station.last_reading_time, now)})`}
                    </p>

                    <p className="mt-1 text-[10px] text-slate-600">
                      Source: {station.latest_data_source ?? "none"}
                      {" · "}
                      {station.is_active ? "Configured active" : "Inactive"}
                    </p>
                  </button>
                );
              })}
            </div>

            {/* SELECTED GAUGE DETAILS */}

            {activeStation && (
              <div className="mt-5 rounded-lg border border-navy-800 bg-navy-950/60 p-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h3 className="font-bold text-white">
                      {isKm
                        ? activeStation.name_km || activeStation.name
                        : activeStation.name}
                    </h3>
                    <p className="mt-1 text-xs text-slate-400">
                      {activeStation.province ?? "Province unavailable"}
                      {" · "}
                      {activeStation.data_source ?? "Source unavailable"}
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-400">
                      {isKm ? "ប្រៀបធៀបជាមួយ" : "Compare with"}
                    </span>

                    <select
                      value={compareStationId}
                      onChange={(event) =>
                        setCompareStationId(event.target.value)
                      }
                      className="max-w-56 rounded-lg border border-navy-700 bg-navy-950 px-3 py-2 text-xs text-white outline-none focus:border-cyan-500"
                    >
                      <option value="">Select comparison station</option>

                      {stations
                        .filter((station) => station.id !== selectedStationId)
                        .map((station) => (
                          <option key={station.id} value={station.id}>
                            {station.name}
                          </option>
                        ))}
                    </select>
                  </div>
                </div>

                <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
                  <div className="rounded-lg bg-navy-900 p-3">
                    <p className="text-xs text-slate-400">
                      Current Water Level
                    </p>
                    <p className="mt-1 text-xl font-bold text-cyan-300">
                      {formatNumber(activeStation.water_level_m)} m
                    </p>
                  </div>

                  <div className="rounded-lg bg-navy-900 p-3">
                    <p className="text-xs text-slate-400">Alarm Threshold</p>
                    <p className="mt-1 text-xl font-bold text-amber-400">
                      {formatNumber(activeStation.alarm_level_m)} m
                    </p>
                  </div>

                  <div className="rounded-lg bg-navy-900 p-3">
                    <p className="text-xs text-slate-400">Flood Threshold</p>
                    <p className="mt-1 text-xl font-bold text-red-400">
                      {formatNumber(activeStation.flood_level_m)} m
                    </p>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </section>

      {/* ================================================== */}
      {/* SECTION 4: MULTI-STATION WATER LEVEL COMPARISON */}
      {/* ================================================== */}

      <section className="rounded-xl border border-navy-800 bg-navy-900/60 p-5">
        <div className="mb-4">
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-cyan-400" />
            <h2 className="text-sm font-bold uppercase tracking-wider text-white">
              {isKm
                ? "ការប្រៀបធៀបកម្ពស់ទឹករវាងស្ថានីយ"
                : "Multi-Station Water-Level Comparison"}
            </h2>
          </div>

          <p className="mt-1 text-xs text-slate-400">
            {isKm
              ? "ប្រៀបធៀបទិន្នន័យវាស់កម្ពស់ទឹកជាក់ស្តែងដែលមានក្នុងប្រព័ន្ធ"
              : "Compare stored water-level measurements from two hydrological gauge stations."}
          </p>
        </div>

        {timeseriesLoading && (
          <div className="flex h-64 items-center justify-center text-sm text-slate-400">
            Loading station comparison...
          </div>
        )}

        {!timeseriesLoading && timeseriesError && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-400">
            {timeseriesError}
          </div>
        )}

        {!timeseriesLoading &&
          !timeseriesError &&
          comparisonChartData.length > 0 && (
            <TimeSeriesChart
              title={`${activeStation?.name ?? "Station"} vs ${comparisonStation?.name ?? "Comparison"}`}
              subtitle="Recorded water-level measurements"
              data={comparisonChartData}
              xKey="timestamp"
              yKeys={[
                {
                  key: "primary_level",
                  name: activeStation?.name ?? "Selected station",
                  color: "#06b6d4",
                  type: "line",
                },
                {
                  key: "compare_level",
                  name: comparisonStation?.name ?? "Comparison station",
                  color: "#f59e0b",
                  type: "line",
                },
              ]}
              unit="m"
              height={320}
            />
          )}

        {!timeseriesLoading &&
          !timeseriesError &&
          comparisonChartData.length === 0 && (
            <div className="flex h-64 flex-col items-center justify-center rounded-lg border border-dashed border-navy-700 text-center">
              <Droplets className="mb-3 h-8 w-8 text-slate-500" />
              <p className="text-sm text-slate-300">
                No recorded station time-series data available.
              </p>
              <p className="mt-1 text-xs text-slate-500">
                The chart will display when actual measurements are available.
              </p>
            </div>
          )}
      </section>

      {/* ================================================== */}
      {/* SECTION 5: DATA SOURCE NOTICE */}
      {/* ================================================== */}

      <section className="rounded-xl border border-navy-800 bg-navy-900/40 p-4">
        <div className="flex items-start gap-3">
          <Info className="mt-0.5 h-5 w-5 shrink-0 text-cyan-400" />

          <div>
            <h3 className="text-sm font-semibold text-slate-200">
              {isKm
                ? "ប្រភពទិន្នន័យ និងកំណត់សម្គាល់"
                : "Data Sources and Important Notes"}
            </h3>

            <p className="mt-2 text-xs leading-relaxed text-slate-400">
              Discharge forecasts are retrieved from the stored
              monitoring-location records. Hydrological gauge readings are
              retrieved separately from the station water-level records. The two
              datasets are not interchangeable. Stored baseline readings and
              model forecasts should not be interpreted as verified live MRC
              telemetry.
            </p>

            <p className="mt-2 text-xs text-slate-500">
              Missing readings are displayed as unavailable. No artificial
              station measurements or discharge values are generated by this
              dashboard.
            </p>
          </div>
        </div>
      </section>
    </DashboardLayout>
  );
}
