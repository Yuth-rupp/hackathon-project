"use client";

import React from "react";
import clsx from "clsx";
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  Building2,
  Droplets,
  Gauge,
  HeartPulse,
  Home,
  Radio,
  Satellite,
  ShieldAlert,
  Waves,
  WifiOff,
} from "lucide-react";
import { RiskBadge } from "@/components/common/RiskBadge";
import { DataFreshness } from "@/components/common/DataFreshness";
import type { StreamConnection } from "@/hooks/useHydrologyStream";
import type {
  CommunityBasinSummary,
  CommunityGauge,
  CommunityProvinceRisk,
  CommunityRiskTrend,
  RiskLevel,
} from "@/types";

// ============================================================
// SHARED HELPERS
// ============================================================

export interface RiskChange {
  id: string;
  province: string;
  fromLabel: string;
  toLabel: string;
  direction: "up" | "down";
  at: number;
}

const LEVEL_STYLES: Record<
  RiskLevel,
  { text: string; border: string; bg: string; bar: string }
> = {
  low: {
    text: "text-emerald-300",
    border: "border-emerald-500/40",
    bg: "bg-emerald-500/10",
    bar: "bg-emerald-400",
  },
  moderate: {
    text: "text-amber-300",
    border: "border-amber-500/40",
    bg: "bg-amber-500/10",
    bar: "bg-amber-400",
  },
  high: {
    text: "text-orange-300",
    border: "border-orange-500/40",
    bg: "bg-orange-500/10",
    bar: "bg-orange-400",
  },
  very_high: {
    text: "text-rose-300",
    border: "border-rose-500/50",
    bg: "bg-rose-500/15",
    bar: "bg-rose-400",
  },
};

export function levelStyle(level: RiskLevel | null | undefined) {
  return LEVEL_STYLES[level ?? "low"] ?? LEVEL_STYLES.low;
}

/** Backend timestamps are UTC; add the zone when it is missing. */
function parseUtc(value: string | null | undefined): Date | null {
  if (!value) return null;
  const hasZone = /([zZ]|[+-]\d{2}:?\d{2})$/.test(value);
  const date = new Date(hasZone ? value : `${value}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatAge(
  value: string | number | null | undefined,
  now: number,
): string {
  const date =
    typeof value === "number" ? new Date(value) : parseUtc(value ?? null);
  if (!date) return "no time";

  const seconds = Math.max(0, Math.floor((now - date.getTime()) / 1000));
  if (seconds < 45) return "just now";

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${Math.max(1, minutes)} min ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 48) return `${hours} h ago`;

  return `${Math.floor(hours / 24)} d ago`;
}

function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

// ============================================================
// CONNECTION INDICATOR
// ============================================================

export function LiveIndicator({
  connection,
  lastEventAt,
  now,
}: {
  connection: StreamConnection;
  lastEventAt: Date | null;
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
      {lastEventAt && (
        <span className="hidden font-normal opacity-80 md:inline">
          · signal {formatAge(lastEventAt.getTime(), now)}
        </span>
      )}
    </div>
  );
}

// ============================================================
// BASIN SUMMARY STRIP
// ============================================================

export function BasinStrip({
  basin,
  now,
}: {
  basin: CommunityBasinSummary;
  now: number;
}) {
  const sat = basin.satellite;
  const cards = [
    {
      icon: ShieldAlert,
      label: "Provinces at Alert or above",
      value: `${basin.provinces_at_alert_or_above} / ${basin.provinces_total}`,
      hint: "Combined risk model, live gauges and official alerts",
      tone:
        basin.provinces_at_alert_or_above > 0
          ? "text-orange-300"
          : "text-emerald-300",
    },
    {
      icon: AlertTriangle,
      label: "Open alerts",
      value: formatNumber(basin.open_alerts),
      hint: "Active or acknowledged",
      tone: basin.open_alerts > 0 ? "text-amber-300" : "text-slate-200",
    },
    {
      icon: Gauge,
      label: "Live gauges",
      value: formatNumber(basin.live_gauges),
      hint:
        basin.live_gauges === 0
          ? "No live gauge feed. Baseline values are never used for risk."
          : `${basin.gauges_in_alarm} in alarm · ${basin.gauges_in_flood} in flood · newest ${formatAge(basin.newest_gauge_reading, now)}`,
      tone: basin.live_gauges === 0 ? "text-slate-400" : "text-cyan-300",
    },
    {
      icon: Satellite,
      label: "Satellite water extent",
      value:
        sat.last_water_extent_km2 !== null
          ? `${formatNumber(sat.last_water_extent_km2)} km²`
          : "—",
      hint: sat.last_processed_pass
        ? `Sentinel-1 pass ${formatAge(sat.last_processed_pass, now)}`
        : sat.last_pass
          ? `Last pass ${formatAge(sat.last_pass, now)} (not processed)`
          : "No satellite pass stored",
      tone: "text-cyan-300",
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {cards.map(({ icon: Icon, label, value, hint, tone }) => (
        <div
          key={label}
          className="rounded-xl border border-navy-800 bg-navy-900/60 p-4 backdrop-blur-md"
        >
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-slate-400">
            <Icon className="h-3.5 w-3.5" />
            <span>{label}</span>
          </div>
          <div className={`mt-1 font-mono text-2xl font-bold ${tone}`}>
            {value}
          </div>
          <div className="mt-1 text-[11px] leading-snug text-slate-400">
            {hint}
          </div>
        </div>
      ))}
    </div>
  );
}

// ============================================================
// RECENT CHANGES
// ============================================================

export function ChangeFeed({
  changes,
  now,
}: {
  changes: RiskChange[];
  now: number;
}) {
  if (changes.length === 0) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="rounded-xl border border-cyan-500/30 bg-cyan-500/5 p-4"
    >
      <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-cyan-300">
        <Activity className="h-4 w-4" />
        Community action level changes (this session)
      </div>
      <ul className="space-y-1.5 text-xs">
        {changes.map((change) => (
          <li key={change.id} className="flex flex-wrap items-center gap-2">
            {change.direction === "up" ? (
              <ArrowUpRight className="h-3.5 w-3.5 text-orange-400" />
            ) : (
              <ArrowDownRight className="h-3.5 w-3.5 text-emerald-400" />
            )}
            <span className="font-semibold text-white">{change.province}</span>
            <span className="text-slate-300">
              {change.fromLabel} → {change.toLabel}
            </span>
            <span className="text-slate-500">{formatAge(change.at, now)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ============================================================
// TREND
// ============================================================

function TrendLabel({ trend }: { trend: CommunityRiskTrend }) {
  if (trend.direction === "unknown") {
    return (
      <span className="text-slate-400">Trend: not enough history yet</span>
    );
  }

  const Icon =
    trend.direction === "rising"
      ? ArrowUpRight
      : trend.direction === "falling"
        ? ArrowDownRight
        : ArrowRight;

  const tone =
    trend.direction === "rising"
      ? "text-orange-300"
      : trend.direction === "falling"
        ? "text-emerald-300"
        : "text-slate-300";

  const delta =
    trend.delta !== null
      ? ` (${trend.delta > 0 ? "+" : ""}${trend.delta.toFixed(1)} pts / ${trend.window_hours} h)`
      : "";

  return (
    <span className={`inline-flex items-center gap-1 ${tone}`}>
      <Icon className="h-3.5 w-3.5" />
      <span className="capitalize">{trend.direction}</span>
      <span className="text-slate-400">{delta}</span>
    </span>
  );
}

function Sparkline({ trend }: { trend: CommunityRiskTrend }) {
  const points = trend.points;

  if (points.length < 2) {
    return (
      <p className="text-[11px] text-slate-500">
        The 48-hour history appears after a few assessments have been stored.
      </p>
    );
  }

  const width = 260;
  const height = 64;
  const pad = 4;
  const x = (i: number) => pad + (i * (width - pad * 2)) / (points.length - 1);
  const y = (score: number) =>
    height -
    pad -
    (Math.min(100, Math.max(0, score)) / 100) * (height - pad * 2);

  const line = points.map((p, i) => `${x(i)},${y(p.score)}`).join(" ");

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="h-16 w-full"
      role="img"
      aria-label={`Risk score over the last 48 hours, ${trend.direction}`}
    >
      {[25, 50, 75].map((threshold) => (
        <line
          key={threshold}
          x1={pad}
          x2={width - pad}
          y1={y(threshold)}
          y2={y(threshold)}
          stroke="currentColor"
          strokeDasharray="3 4"
          className="text-slate-700"
        />
      ))}
      <polyline
        points={line}
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinejoin="round"
        strokeLinecap="round"
        className="text-cyan-400"
      />
      <circle
        cx={x(points.length - 1)}
        cy={y(points[points.length - 1].score)}
        r={3}
        className="fill-cyan-300"
      />
    </svg>
  );
}

// ============================================================
// SMALL BLOCK INSIDE EACH PROVINCE SELECTOR CARD
// ============================================================

export function ProvinceLiveChip({
  province,
}: {
  province: CommunityProvinceRisk | undefined;
}) {
  if (!province) {
    return (
      <div className="mt-3 text-[11px] text-slate-500">Loading live risk…</div>
    );
  }

  if (!province.risk.available) {
    return (
      <div className="mt-3 text-[11px] text-slate-400">
        Awaiting first risk assessment
      </div>
    );
  }

  const style = levelStyle(province.action.level);

  return (
    <div className="mt-3 space-y-1.5">
      <RiskBadge
        level={province.risk.level ?? "low"}
        score={province.risk.score ?? undefined}
        size="sm"
      />
      <div className={`text-[11px] font-semibold ${style.text}`}>
        {province.action.label_en}
        {province.action.escalated && (
          <span className="ml-1 font-normal text-slate-400">(escalated)</span>
        )}
      </div>
      <div className="text-[11px]">
        <TrendLabel trend={province.trend} />
      </div>
    </div>
  );
}

// ============================================================
// GAUGE ROW
// ============================================================

const GAUGE_FRESHNESS: Record<
  CommunityGauge["freshness"],
  { label: string; className: string }
> = {
  live: { label: "LIVE", className: "border-emerald-500/40 text-emerald-300" },
  delayed: {
    label: "DELAYED",
    className: "border-amber-500/40 text-amber-300",
  },
  stale: { label: "STALE", className: "border-red-500/40 text-red-300" },
  baseline: {
    label: "BASELINE – NOT LIVE",
    className: "border-violet-500/40 text-violet-300",
  },
  no_data: { label: "NO DATA", className: "border-slate-600 text-slate-400" },
};

function GaugeRow({ gauge, now }: { gauge: CommunityGauge; now: number }) {
  const badge = GAUGE_FRESHNESS[gauge.freshness];
  const statusTone =
    gauge.status === "CRITICAL_FLOOD"
      ? "text-rose-300"
      : gauge.status === "WARNING"
        ? "text-orange-300"
        : "text-slate-200";

  return (
    <li className="rounded-lg border border-navy-800 bg-navy-950/70 p-3 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-semibold text-white">{gauge.name}</span>
        <span
          className={`rounded border px-1.5 py-0.5 text-[10px] font-bold ${badge.className}`}
        >
          {badge.label}
        </span>
      </div>
      <div className="mt-1.5 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <span className={`font-mono text-lg font-bold ${statusTone}`}>
          {gauge.water_level_m !== null
            ? `${gauge.water_level_m.toFixed(2)} m`
            : "—"}
        </span>
        <span className="text-slate-400">
          alarm {formatNumber(gauge.alarm_level_m, 1)} m · flood{" "}
          {formatNumber(gauge.flood_level_m, 1)} m
        </span>
        <span className="text-slate-500">
          {formatAge(gauge.timestamp, now)}
        </span>
      </div>
      {!gauge.counts_for_risk && (
        <p className="mt-1.5 text-[11px] text-slate-500">
          Not used for the community action level (no live measurement).
        </p>
      )}
    </li>
  );
}

// ============================================================
// SAFE SITE ICON
// ============================================================

function SiteIcon({ group }: { group: "shelter" | "health" | "structure" }) {
  if (group === "health")
    return <HeartPulse className="h-4 w-4 text-rose-300" />;
  if (group === "structure") return <Waves className="h-4 w-4 text-cyan-300" />;
  return <Home className="h-4 w-4 text-emerald-300" />;
}

// ============================================================
// MAIN PANEL FOR THE SELECTED PROVINCE
// ============================================================

export function ProvinceLivePanel({
  province,
  now,
}: {
  province: CommunityProvinceRisk;
  now: number;
}) {
  const { risk, action, discharge } = province;
  const style = levelStyle(action.level);

  const dischargeTone = (status: string) =>
    status === "alarm"
      ? "text-rose-300"
      : status === "warning"
        ? "text-orange-300"
        : status === "normal"
          ? "text-emerald-300"
          : "text-slate-400";

  const sourceLabel: Record<string, string> = {
    risk_model: "Risk model",
    gauge: "Live gauge",
    alert: "Official alert",
  };

  return (
    <section
      aria-label={`Live community risk for ${province.name}`}
      className="space-y-5 rounded-xl border border-navy-800 bg-navy-900/60 p-5 shadow-xl backdrop-blur-md"
    >
      <div className="flex flex-col gap-3 border-b border-navy-800 pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <span className="rounded border border-cyan-500/30 bg-cyan-500/20 px-2 py-0.5 text-[10px] font-bold text-cyan-300">
            LIVE COMMUNITY RISK
          </span>
          <h3 className="text-lg font-bold text-white">{province.name}</h3>
          <span className="font-sans text-xs text-slate-400">
            {province.name_km}
          </span>
        </div>
        {risk.assessment_date && (
          <DataFreshness timestamp={risk.assessment_date} label="Assessed" />
        )}
      </div>

      {(risk.freshness === "delayed" || risk.freshness === "stale") && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-200">
          The latest risk assessment is {formatAge(risk.assessment_date, now)}.
          Assessments normally refresh every 15 minutes, so check that the
          backend scheduler is running.
        </div>
      )}

      {!risk.available ? (
        <div className="rounded-lg border border-navy-700 bg-navy-950/70 p-4 text-sm text-slate-300">
          No risk assessment is stored for {province.name} yet. It will appear
          here the moment the first assessment finishes.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {/* ---- Action level ---- */}
          <div className={`rounded-xl border p-4 ${style.border} ${style.bg}`}>
            <div className="text-[11px] uppercase tracking-wider text-slate-400">
              Community action level
            </div>
            <div className={`mt-1 text-xl font-bold ${style.text}`}>
              {action.label_en}
            </div>
            <div className="font-sans text-xs text-slate-400">
              {action.label_km}
            </div>
            <p className="mt-3 text-xs leading-relaxed text-slate-200">
              {action.guidance_en}
            </p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {action.driven_by.map((d) => (
                <span
                  key={`${d.source}-${d.level}`}
                  className="rounded-full border border-navy-700 bg-navy-950/70 px-2 py-0.5 text-[10px] text-slate-300"
                >
                  {sourceLabel[d.source] ?? d.source}: {d.level}
                </span>
              ))}
            </div>
            {action.escalated && (
              <p className="mt-2 text-[11px] text-orange-300">
                Raised above the model score by a live gauge or an official
                alert.
              </p>
            )}
          </div>

          {/* ---- Drivers ---- */}
          <div className="rounded-xl border border-navy-800 bg-navy-950/70 p-4">
            <div className="flex items-baseline justify-between">
              <div className="text-[11px] uppercase tracking-wider text-slate-400">
                Risk score · what drives it
              </div>
              <div className={`font-mono text-2xl font-bold ${style.text}`}>
                {risk.score !== null ? `${risk.score.toFixed(1)}` : "—"}
                <span className="text-xs text-slate-500"> / 100</span>
              </div>
            </div>
            <ul className="mt-3 space-y-2">
              {risk.factors.map((factor) => (
                <li key={factor.name} className="text-[11px]">
                  <div className="flex justify-between text-slate-300">
                    <span>{factor.label}</span>
                    <span className="font-mono text-slate-400">
                      {factor.score !== null ? factor.score.toFixed(0) : "—"}
                      {factor.weight !== null &&
                        ` · ${Math.round(factor.weight * 100)}%`}
                    </span>
                  </div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded bg-navy-800">
                    <div
                      className="h-full rounded bg-cyan-400"
                      style={{
                        width: `${Math.min(100, Math.max(0, factor.score ?? 0))}%`,
                      }}
                    />
                  </div>
                </li>
              ))}
            </ul>
            {risk.data_coverage_percent !== null &&
              risk.data_coverage_percent !== undefined && (
                <p className="mt-3 text-[11px] text-slate-500">
                  Data coverage {risk.data_coverage_percent.toFixed(0)}% (
                  {risk.data_status ?? "unknown"}). Rule-based score, not a
                  calibrated probability.
                </p>
              )}
          </div>

          {/* ---- Trend + discharge ---- */}
          <div className="rounded-xl border border-navy-800 bg-navy-950/70 p-4">
            <div className="text-[11px] uppercase tracking-wider text-slate-400">
              48-hour risk trend
            </div>
            <div className="mt-1 text-xs">
              <TrendLabel trend={province.trend} />
            </div>
            <div className="mt-2">
              <Sparkline trend={province.trend} />
            </div>

            <div className="mt-3 border-t border-navy-800 pt-3">
              <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-slate-400">
                <Droplets className="h-3.5 w-3.5" />
                River discharge
              </div>
              <div className="mt-1 grid grid-cols-2 gap-2 text-xs">
                <div>
                  <div className="text-slate-500">Now</div>
                  <div
                    className={`font-mono text-base font-bold ${dischargeTone(discharge.current_status)}`}
                  >
                    {formatNumber(discharge.current_m3s, 1)} m³/s
                  </div>
                </div>
                <div>
                  <div className="text-slate-500">7-day forecast peak</div>
                  <div
                    className={`font-mono text-base font-bold ${dischargeTone(discharge.forecast_peak_status)}`}
                  >
                    {formatNumber(discharge.forecast_peak_m3s, 1)} m³/s
                  </div>
                </div>
              </div>
              <p className="mt-1.5 text-[10px] text-slate-500">
                Model forecast (not a gauge). Warning{" "}
                {formatNumber(discharge.warning_m3s)} · alarm{" "}
                {formatNumber(discharge.alarm_m3s)} m³/s.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ---- Gauges + alerts ---- */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div>
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-white">
            <Gauge className="h-4 w-4 text-cyan-400" />
            Gauges in this province
          </div>
          {province.gauges.length === 0 ? (
            <p className="rounded-lg border border-navy-800 bg-navy-950/70 p-3 text-xs text-slate-400">
              No hydrological gauge is registered in {province.name}. Its risk
              comes from rainfall, discharge, soil and history.
            </p>
          ) : (
            <ul className="space-y-2">
              {province.gauges.map((gauge) => (
                <GaugeRow key={gauge.code} gauge={gauge} now={now} />
              ))}
            </ul>
          )}
        </div>

        <div>
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-white">
            <AlertTriangle className="h-4 w-4 text-amber-400" />
            Open alerts
          </div>
          {province.alerts.length === 0 ? (
            <p className="rounded-lg border border-navy-800 bg-navy-950/70 p-3 text-xs text-slate-400">
              No open alert for {province.name}.
            </p>
          ) : (
            <ul className="space-y-2">
              {province.alerts.map((alert) => (
                <li
                  key={alert.id}
                  className="rounded-lg border border-navy-800 bg-navy-950/70 p-3 text-xs"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <RiskBadge level={alert.severity} size="sm" />
                    <span className="font-semibold text-white">
                      {alert.title}
                    </span>
                  </div>
                  <p className="mt-1.5 leading-relaxed text-slate-300">
                    {alert.message}
                  </p>
                  <div className="mt-1.5 text-[11px] text-slate-500">
                    {alert.status} · {formatAge(alert.created_at, now)}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* ---- Safe sites ---- */}
      <div>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-white">
            <Building2 className="h-4 w-4 text-emerald-400" />
            Safe sites and critical infrastructure
          </div>
          <span className="text-[11px] text-slate-400">
            Shelter capacity{" "}
            <span className="font-mono text-emerald-300">
              {formatNumber(province.shelter_capacity_people)}
            </span>{" "}
            people · {formatNumber(province.vulnerable_communes)} vulnerable
            communes
          </span>
        </div>
        <div className="overflow-x-auto rounded-lg border border-navy-800">
          <table className="w-full min-w-[560px] text-left text-xs">
            <thead className="bg-navy-950/80 text-[11px] uppercase tracking-wider text-slate-400">
              <tr>
                <th className="px-3 py-2">Site</th>
                <th className="px-3 py-2">Capacity</th>
                <th className="px-3 py-2">Elevation</th>
                <th className="px-3 py-2">Posture now</th>
              </tr>
            </thead>
            <tbody>
              {province.safe_sites.map((site) => (
                <tr key={site.name} className="border-t border-navy-800">
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <SiteIcon group={site.group} />
                      <div>
                        <div className="font-semibold text-white">
                          {site.name}
                        </div>
                        <div className="font-sans text-[11px] text-slate-500">
                          {site.name_km}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-3 py-2 font-mono text-slate-200">
                    {site.capacity_people !== null
                      ? formatNumber(site.capacity_people)
                      : "—"}
                  </td>
                  <td className="px-3 py-2 font-mono text-slate-300">
                    {formatNumber(site.elevation_m, 1)} m
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={clsx(
                        "inline-block rounded-full border px-2 py-0.5 text-[11px] font-medium",
                        style.border,
                        style.bg,
                        style.text,
                      )}
                    >
                      {site.posture.label_en}
                    </span>
                    <div className="mt-0.5 font-sans text-[10px] text-slate-500">
                      {site.posture.label_km}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-[11px] text-slate-500">
          Posture is guidance derived from the community action level.
          Evacuation orders and shelter openings are decided by NCDM and the
          provincial committee.
        </p>
      </div>
    </section>
  );
}
