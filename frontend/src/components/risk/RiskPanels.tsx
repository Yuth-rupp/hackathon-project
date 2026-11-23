"use client";

import React, { useMemo } from "react";
import {
  Activity,
  AlertTriangle,
  CalendarDays,
  CheckCircle2,
  CloudRain,
  Info,
  Sprout,
  Waves,
  XCircle,
} from "lucide-react";
import {
  Bar,
  BarChart,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { RiskBadge } from "@/components/common/RiskBadge";
import type { RiskAssessment } from "@/types";
import {
  FACTOR_COLORS,
  LEVEL_COLORS,
  RISK_FACTOR_KEYS,
  clampPercent,
  fill,
  formatAge,
  formatDetailValue,
  getRiskText,
  toNumber,
  type RiskLang,
} from "@/lib/riskText";

const card =
  "rounded-xl border border-navy-800 bg-navy-900/60 shadow-lg backdrop-blur-md";

const FACTOR_ICONS: Record<string, React.ReactNode> = {
  rainfall: <CloudRain className="h-4 w-4" />,
  hydrology: <Waves className="h-4 w-4" />,
  soil: <Sprout className="h-4 w-4" />,
  seasonal: <CalendarDays className="h-4 w-4" />,
  historical: <Activity className="h-4 w-4" />,
};

function locationLabel(item: RiskAssessment, lang: RiskLang): string {
  return lang === "KM"
    ? item.location_name_km || item.location_name
    : item.location_name;
}

// ---------------------------------------------------------
// Summary strip
// ---------------------------------------------------------

export function RiskSummaryStrip({
  assessments,
  lang,
}: {
  assessments: RiskAssessment[];
  lang: RiskLang;
}) {
  const text = getRiskText(lang);

  const stats = useMemo(() => {
    const highest = [...assessments].sort(
      (a, b) => b.risk_score - a.risk_score,
    )[0];

    const average =
      assessments.reduce((sum, item) => sum + item.risk_score, 0) /
      Math.max(assessments.length, 1);

    const elevated = assessments.filter(
      (item) => item.risk_level === "high" || item.risk_level === "very_high",
    ).length;

    const coverageValues = assessments
      .map((item) => item.data_coverage_percent)
      .filter((value): value is number => typeof value === "number");

    const coverage =
      coverageValues.length > 0
        ? coverageValues.reduce((sum, value) => sum + value, 0) /
          coverageValues.length
        : null;

    return { highest, average, elevated, coverage };
  }, [assessments]);

  if (!stats.highest) return null;

  const tiles = [
    {
      label: text.summary.highest,
      value: locationLabel(stats.highest, lang),
      sub: `${stats.highest.risk_score.toFixed(1)}/100`,
      color: LEVEL_COLORS[stats.highest.risk_level],
    },
    {
      label: text.summary.average,
      value: stats.average.toFixed(1),
      sub: "/100",
      color: "#38bdf8",
    },
    {
      label: text.summary.elevated,
      value: String(stats.elevated),
      sub: fill(text.summary.of, { n: assessments.length }),
      color: stats.elevated > 0 ? "#f97316" : "#22c55e",
    },
    {
      label: text.summary.coverage,
      value: stats.coverage === null ? "-" : `${stats.coverage.toFixed(0)}%`,
      sub: "",
      color: "#a855f7",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {tiles.map((tile) => (
        <div
          key={tile.label}
          className={`${card} border-l-4 p-4`}
          style={{ borderLeftColor: tile.color }}
        >
          <p className="text-[11px] uppercase tracking-wider text-slate-400">
            {tile.label}
          </p>
          <p className="mt-1 truncate text-xl font-bold text-white">
            {tile.value}
          </p>
          {tile.sub && <p className="text-xs text-slate-500">{tile.sub}</p>}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------
// Location cards
// ---------------------------------------------------------

export function LocationCards({
  assessments,
  selectedId,
  onSelect,
  lang,
}: {
  assessments: RiskAssessment[];
  selectedId: string;
  onSelect: (id: string) => void;
  lang: RiskLang;
}) {
  const text = getRiskText(lang);

  const rankById = useMemo(() => {
    const ranked = [...assessments].sort((a, b) => b.risk_score - a.risk_score);
    return new Map(ranked.map((item, index) => [item.location_id, index + 1]));
  }, [assessments]);

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
      {assessments.map((item) => {
        const selected = item.location_id === selectedId;
        const color = LEVEL_COLORS[item.risk_level];
        const driver = text.factors.names[item.primary_driver];

        return (
          <button
            key={item.location_id}
            type="button"
            onClick={() => onSelect(item.location_id)}
            aria-pressed={selected}
            className={`rounded-xl border p-4 text-left transition-all ${
              selected
                ? "border-cyan-500 bg-navy-900/90 shadow-xl ring-1 ring-cyan-500"
                : "border-navy-800 bg-navy-900/50 hover:border-navy-700"
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <h3 className="truncate text-sm font-bold text-white">
                  {locationLabel(item, lang)}
                </h3>
                <p className="text-[10px] text-slate-500">
                  {text.cards.rank} #{rankById.get(item.location_id)}
                </p>
              </div>
              <RiskBadge level={item.risk_level} size="sm" showIcon={false} />
            </div>

            <div className="mt-3 flex items-baseline justify-between">
              <span className="text-xs text-slate-400">{text.cards.score}</span>
              <span className="font-mono text-2xl font-extrabold text-white">
                {item.risk_score.toFixed(1)}
              </span>
            </div>

            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-navy-950">
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{
                  width: `${clampPercent(item.risk_score)}%`,
                  backgroundColor: color,
                }}
              />
            </div>

            <p className="mt-2 truncate text-[11px] text-slate-400">
              {text.cards.driver}:{" "}
              <span className="text-slate-200">
                {driver || item.primary_driver || "-"}
              </span>
            </p>
          </button>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------
// Province comparison chart
// ---------------------------------------------------------

export function ProvinceComparisonChart({
  assessments,
  selectedId,
  onSelect,
  lang,
}: {
  assessments: RiskAssessment[];
  selectedId: string;
  onSelect: (id: string) => void;
  lang: RiskLang;
}) {
  const text = getRiskText(lang);

  const data = useMemo(
    () =>
      [...assessments]
        .sort((a, b) => b.risk_score - a.risk_score)
        .map((item) => ({
          id: item.location_id,
          name: locationLabel(item, lang),
          score: Number(item.risk_score.toFixed(1)),
          level: item.risk_level,
        })),
    [assessments, lang],
  );

  return (
    <div className={`${card} p-5`}>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-white">
          {text.compare.title}
        </h3>
        <span className="text-[10px] text-slate-400">{text.compare.hint}</span>
      </div>

      <div style={{ width: "100%", height: 230 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
          >
            <XAxis
              type="number"
              domain={[0, 100]}
              ticks={[0, 25, 50, 75, 100]}
              stroke="#64748b"
              tick={{ fill: "#94a3b8", fontSize: 10 }}
            />
            <YAxis
              type="category"
              dataKey="name"
              width={110}
              stroke="#64748b"
              tick={{ fill: "#cbd5e1", fontSize: 11 }}
            />
            <ReferenceLine x={25} stroke="#334155" strokeDasharray="3 3" />
            <ReferenceLine x={50} stroke="#334155" strokeDasharray="3 3" />
            <ReferenceLine x={75} stroke="#334155" strokeDasharray="3 3" />
            <Tooltip
              cursor={{ fill: "rgba(148,163,184,0.08)" }}
              content={({ active, payload }) => {
                if (!active || !payload || payload.length === 0) return null;
                const row = payload[0].payload as (typeof data)[number];

                return (
                  <div className="rounded border border-navy-800 bg-navy-950 p-2 text-xs text-white shadow-xl">
                    <p className="font-semibold">{row.name}</p>
                    <p style={{ color: LEVEL_COLORS[row.level] }}>
                      {row.score}/100 · {text.levels[row.level]}
                    </p>
                  </div>
                );
              }}
            />
            <Bar
              dataKey="score"
              radius={[0, 4, 4, 0]}
              cursor="pointer"
              onClick={(entry: { id?: string }) => {
                if (entry?.id) onSelect(entry.id);
              }}
            >
              {data.map((row) => (
                <Cell
                  key={row.id}
                  fill={LEVEL_COLORS[row.level]}
                  fillOpacity={row.id === selectedId ? 1 : 0.55}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-slate-400">
        {(["low", "moderate", "high", "very_high"] as const).map((level) => (
          <span key={level} className="flex items-center gap-1.5">
            <span
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: LEVEL_COLORS[level] }}
            />
            {text.levels[level]} ({text.scale[level]})
          </span>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------
// Explanation + recommended actions
// ---------------------------------------------------------

export function ExplanationAndActions({
  assessment,
  lang,
}: {
  assessment: RiskAssessment;
  lang: RiskLang;
}) {
  const text = getRiskText(lang);

  // Khmer explanation is not generated by the backend yet, so fall back to English.
  const explanation =
    (lang === "KM" ? assessment.explanation_km : "") ||
    assessment.explanation_en ||
    "";

  const actions =
    assessment.recommended_actions.length > 0
      ? assessment.recommended_actions
      : text.actions[assessment.risk_level];

  return (
    <div className={`${card} space-y-4 p-5`}>
      {explanation && (
        <div>
          <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-white">
            {text.detail.whyTitle}
          </h3>
          <p className="text-sm leading-relaxed text-slate-300">
            {explanation}
          </p>
        </div>
      )}

      <div className={explanation ? "border-t border-navy-800 pt-4" : ""}>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-white">
          {text.detail.actionsTitle}
        </h3>
        <ul className="space-y-1.5 text-sm text-slate-300">
          {actions.map((action) => (
            <li key={action} className="flex items-start gap-2">
              <span
                className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full"
                style={{ backgroundColor: LEVEL_COLORS[assessment.risk_level] }}
              />
              <span>{action}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

// ---------------------------------------------------------
// Factor breakdown
// ---------------------------------------------------------

export function FactorBreakdown({
  assessment,
  lang,
}: {
  assessment: RiskAssessment;
  lang: RiskLang;
}) {
  const text = getRiskText(lang);

  const rows = useMemo(() => {
    const factors = assessment.contributing_factors ?? {};

    const list = Object.entries(factors).map(([key, value]) => {
      const rawWeight = Number(value.weight ?? 0);
      const weight =
        rawWeight > 0 && rawWeight <= 1 ? rawWeight * 100 : rawWeight;

      return {
        key,
        name: text.factors.names[key] ?? key,
        score: value.score === null ? null : clampPercent(value.score),
        weight: clampPercent(weight),
        contribution: value.weighted_contribution,
        details: value.details ?? {},
        color: FACTOR_COLORS[key] ?? "#94a3b8",
      };
    });

    const totalContribution = list.reduce(
      (sum, row) => sum + (row.contribution ?? 0),
      0,
    );

    return list.map((row) => ({
      ...row,
      share:
        totalContribution > 0 && row.contribution !== null
          ? (row.contribution / totalContribution) * 100
          : 0,
    }));
  }, [assessment, text]);

  const isPrimary = (key: string) => key === assessment.primary_driver;

  return (
    <div className={`${card} p-5`}>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-white">
          {text.factors.title}
        </h3>
        <span className="text-[10px] text-slate-400">
          {text.factors.scoreHint}
        </span>
      </div>

      {rows.length === 0 ? (
        <div className="flex min-h-[140px] flex-col items-center justify-center text-center">
          <Info className="h-7 w-7 text-slate-500" />
          <p className="mt-3 text-sm text-slate-300">{text.factors.none}</p>
          <p className="mt-1 text-xs text-slate-500">{text.factors.noneBody}</p>
        </div>
      ) : (
        <>
          {/* Share of total score */}
          <p className="mb-1 text-[10px] uppercase tracking-wider text-slate-500">
            {text.factors.share}
          </p>
          <div className="flex h-3 w-full overflow-hidden rounded-full bg-navy-950">
            {rows.map((row) => (
              <div
                key={row.key}
                title={`${row.name}: ${row.share.toFixed(0)}%`}
                style={{ width: `${row.share}%`, backgroundColor: row.color }}
              />
            ))}
          </div>

          <div className="mt-4 space-y-4">
            {rows.map((row) => {
              const detailEntries = Object.entries(row.details)
                .map(([key, value]) => [key, toNumber(value)] as const)
                .filter(
                  (entry): entry is readonly [string, number] =>
                    entry[1] !== null && key_has_label(entry[0], text),
                );

              return (
                <div key={row.key}>
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex min-w-0 items-center gap-2">
                      <span
                        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md"
                        style={{
                          color: row.color,
                          backgroundColor: `${row.color}22`,
                        }}
                      >
                        {FACTOR_ICONS[row.key] ?? (
                          <Activity className="h-4 w-4" />
                        )}
                      </span>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-slate-100">
                          {row.name}
                          {isPrimary(row.key) && (
                            <span className="ml-2 rounded-full bg-cyan-500/15 px-1.5 py-0.5 text-[9px] font-bold uppercase text-cyan-300">
                              {text.cards.driver}
                            </span>
                          )}
                        </p>
                        <p className="truncate text-[10px] text-slate-500">
                          {text.factors.help[row.key] ?? ""}
                        </p>
                      </div>
                    </div>

                    <div className="shrink-0 text-right">
                      <p className="font-mono text-sm font-bold text-white">
                        {row.score === null ? "N/A" : row.score.toFixed(1)}
                        <span className="text-[10px] font-normal text-slate-500">
                          /100
                        </span>
                      </p>
                      <p className="text-[10px] text-slate-500">
                        {text.factors.weight} {row.weight.toFixed(0)}% ·{" "}
                        {text.factors.contribution}{" "}
                        {row.contribution === null
                          ? "N/A"
                          : row.contribution.toFixed(1)}
                      </p>
                    </div>
                  </div>

                  <div className="mt-2 h-2 overflow-hidden rounded-full bg-navy-950">
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{
                        width: `${row.score ?? 0}%`,
                        backgroundColor: row.color,
                      }}
                    />
                  </div>

                  {detailEntries.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {detailEntries.map(([key, value]) => (
                        <span
                          key={key}
                          className="rounded-md border border-navy-800 bg-navy-950/70 px-2 py-0.5 text-[10px] text-slate-300"
                        >
                          <span className="text-slate-500">
                            {text.factors.details[key]}:
                          </span>{" "}
                          {formatDetailValue(key, value)}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

function key_has_label(
  key: string,
  text: ReturnType<typeof getRiskText>,
): boolean {
  return key in text.factors.details;
}

// ---------------------------------------------------------
// Data quality
// ---------------------------------------------------------

type FreshnessState = "fresh" | "stale" | "none";

export function DataQualityPanel({
  assessment,
  lang,
}: {
  assessment: RiskAssessment;
  lang: RiskLang;
}) {
  const text = getRiskText(lang);
  const freshness = assessment.data_freshness ?? {};
  const coverage = clampPercent(assessment.data_coverage_percent);

  const statusLabel: Record<string, string> = {
    good: text.quality.good,
    partial: text.quality.partial,
    limited: text.quality.limited,
  };

  const statusColor: Record<string, string> = {
    good: "#22c55e",
    partial: "#f59e0b",
    limited: "#ef4444",
  };

  const status = assessment.data_status;
  const color = statusColor[status] ?? "#94a3b8";

  const sources = [
    { key: "weather", label: text.quality.weather },
    { key: "discharge", label: text.quality.discharge },
    { key: "water_level", label: text.quality.waterLevel },
  ].map((source) => {
    const timestamp = freshness[`${source.key}_timestamp`];
    const age = toNumber(freshness[`${source.key}_age_minutes`]);
    const fresh = freshness[`${source.key}_fresh`] === true;

    const state: FreshnessState =
      !timestamp || age === null ? "none" : fresh ? "fresh" : "stale";

    return { ...source, state, age };
  });

  const missing = RISK_FACTOR_KEYS.filter(
    (key) => !(assessment.contributing_factors ?? {})[key],
  );

  return (
    <div className={`${card} space-y-4 p-5`}>
      <h3 className="text-xs font-semibold uppercase tracking-wider text-white">
        {text.quality.title}
      </h3>

      <div>
        <div className="mb-1 flex justify-between text-xs">
          <span className="text-slate-400">{text.quality.coverage}</span>
          <span className="flex items-center gap-2">
            <span
              className="rounded-full px-2 py-0.5 text-[10px] font-bold uppercase"
              style={{ color, backgroundColor: `${color}22` }}
            >
              {statusLabel[status] ?? text.quality.unknown}
            </span>
            <span className="font-mono font-bold text-cyan-300">
              {coverage.toFixed(0)}%
            </span>
          </span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-navy-950">
          <div
            className="h-full rounded-full bg-cyan-400 transition-all duration-700"
            style={{ width: `${coverage}%` }}
          />
        </div>
        <p className="mt-1.5 text-[10px] leading-relaxed text-slate-500">
          {text.quality.coverageHelp}
        </p>
      </div>

      <div className="border-t border-navy-800 pt-3">
        <p className="mb-2 text-[11px] font-semibold uppercase text-slate-400">
          {text.quality.freshness}
        </p>
        <ul className="space-y-2">
          {sources.map((source) => (
            <li
              key={source.key}
              className="flex items-center justify-between text-xs"
            >
              <span className="text-slate-300">{source.label}</span>
              <span className="flex items-center gap-2">
                {source.state !== "none" && source.age !== null && (
                  <span className="text-[10px] text-slate-500">
                    {fill(text.quality.ago, {
                      age: formatAge(source.age, lang),
                    })}
                  </span>
                )}
                {source.state === "fresh" && (
                  <span className="flex items-center gap-1 text-emerald-400">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    {text.quality.fresh}
                  </span>
                )}
                {source.state === "stale" && (
                  <span className="flex items-center gap-1 text-amber-400">
                    <AlertTriangle className="h-3.5 w-3.5" />
                    {text.quality.stale}
                  </span>
                )}
                {source.state === "none" && (
                  <span className="flex items-center gap-1 text-slate-500">
                    <XCircle className="h-3.5 w-3.5" />
                    {text.quality.noData}
                  </span>
                )}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {missing.length > 0 && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3">
          <p className="flex items-center gap-1.5 text-xs font-semibold text-amber-300">
            <AlertTriangle className="h-3.5 w-3.5" />
            {text.quality.excludedTitle}
          </p>
          <p className="mt-1 text-[11px] leading-relaxed text-amber-100/80">
            {fill(text.quality.excludedBody, {
              names: missing.map((key) => text.factors.names[key]).join(", "),
            })}
          </p>
        </div>
      )}
    </div>
  );
}
