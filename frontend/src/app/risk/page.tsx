"use client";

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import dynamic from "next/dynamic";
import {
  Activity,
  AlertTriangle,
  BrainCircuit,
  Clock,
  Database,
  RefreshCw,
  Zap,
} from "lucide-react";

import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { RiskGauge } from "@/components/charts/RiskGauge";
import { RiskBadge } from "@/components/common/RiskBadge";
import {
  DataQualityPanel,
  ExplanationAndActions,
  FactorBreakdown,
  LocationCards,
  ProvinceComparisonChart,
  RiskSummaryStrip,
} from "@/components/risk/RiskPanels";

import { fetchRiskAssessments, triggerRiskAssessment } from "@/lib/api";
import { LEVEL_COLORS, fill, formatAge, getRiskText } from "@/lib/riskText";
import { useLanguage } from "@/context/LanguageContext";
import type { RiskAssessment } from "@/types";

const AUTO_REFRESH_MS = 5 * 60 * 1000;
const STALE_AFTER_MINUTES = 6 * 60;

const TonleSapMap = dynamic(() => import("@/components/maps/TonleSapMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center rounded-xl border border-navy-800 bg-navy-950 text-slate-400">
      <div className="flex flex-col items-center gap-2">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
        <span className="text-xs">Loading map...</span>
      </div>
    </div>
  ),
});

const panel =
  "rounded-xl border border-navy-800 bg-navy-900/60 shadow-lg backdrop-blur-md";

export default function RiskPage() {
  const { language } = useLanguage();
  const lang = language;
  const text = getRiskText(lang);

  const [assessments, setAssessments] = useState<RiskAssessment[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [recalculating, setRecalculating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());

  const mounted = useRef(true);

  // -------------------------------------------------------
  // Data loading
  // -------------------------------------------------------

  const load = useCallback(async (mode: "initial" | "manual" | "silent") => {
    try {
      if (mode === "initial") setLoading(true);
      if (mode === "manual") setRefreshing(true);
      if (mode !== "silent") setError(null);

      const data = await fetchRiskAssessments();

      if (!mounted.current) return;

      setAssessments(data);
      setNow(Date.now());

      // Keep the current selection when it still exists.
      setSelectedId((current) =>
        data.some((item) => item.location_id === current)
          ? current
          : (data[0]?.location_id ?? ""),
      );
    } catch (err) {
      console.error("Error loading risk assessments:", err);

      // A failed background refresh should not replace good data with an error.
      if (mounted.current && mode !== "silent") {
        setError(
          err instanceof Error
            ? err.message
            : "Unable to load risk assessments.",
        );
      }
    } finally {
      if (mounted.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    load("initial");

    const timer = window.setInterval(() => load("silent"), AUTO_REFRESH_MS);

    return () => {
      mounted.current = false;
      window.clearInterval(timer);
    };
  }, [load]);

  async function handleRecalculate() {
    try {
      setRecalculating(true);
      setError(null);

      await triggerRiskAssessment();
      await load("manual");
    } catch (err) {
      console.error("Risk recalculation failed:", err);

      if (mounted.current) {
        setError(
          err instanceof Error ? err.message : "Risk assessment failed.",
        );
      }
    } finally {
      if (mounted.current) setRecalculating(false);
    }
  }

  // -------------------------------------------------------
  // Derived values
  // -------------------------------------------------------

  const active = useMemo(
    () =>
      assessments.find((item) => item.location_id === selectedId) ??
      assessments[0],
    [assessments, selectedId],
  );

  const newestTimestamp = useMemo(() => {
    const times = assessments
      .map((item) => new Date(item.timestamp).getTime())
      .filter((value) => Number.isFinite(value));

    return times.length > 0 ? Math.max(...times) : null;
  }, [assessments]);

  const ageMinutes =
    newestTimestamp === null ? null : (now - newestTimestamp) / 60000;

  const isStale = ageMinutes !== null && ageMinutes > STALE_AFTER_MINUTES;

  const busy = loading || refreshing || recalculating;

  // -------------------------------------------------------
  // Render
  // -------------------------------------------------------

  return (
    <DashboardLayout
      title={text.title}
      subtitle={text.subtitle}
      lastUpdated={
        newestTimestamp === null ? undefined : new Date(newestTimestamp)
      }
      actions={
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => load("manual")}
            disabled={busy}
            className="flex items-center gap-2 rounded-lg border border-navy-800 bg-navy-900 px-3 py-2 text-xs text-cyan-300 transition hover:border-cyan-500 disabled:opacity-50"
          >
            <RefreshCw
              className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
            />
            {text.refresh}
          </button>

          <button
            type="button"
            onClick={handleRecalculate}
            disabled={busy}
            className="flex items-center gap-2 rounded-lg border border-cyan-500/40 bg-cyan-500/10 px-3 py-2 text-xs font-semibold text-cyan-200 transition hover:bg-cyan-500/20 disabled:opacity-50"
          >
            <Zap
              className={`h-4 w-4 ${recalculating ? "animate-pulse" : ""}`}
            />
            {recalculating ? text.running : text.runAssessment}
          </button>
        </div>
      }
    >
      {/* Loading */}
      {loading && (
        <div
          className={`${panel} flex min-h-[300px] flex-col items-center justify-center`}
        >
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
          <p className="mt-4 text-sm text-slate-300">{text.loading}</p>
          <p className="mt-1 text-xs text-slate-500">{text.loadingSub}</p>
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-6">
          <div className="flex items-center gap-3">
            <AlertTriangle className="h-6 w-6 text-red-400" />
            <div>
              <h3 className="font-semibold text-white">{text.errorTitle}</h3>
              <p className="mt-1 text-sm text-red-200">{error}</p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => load("initial")}
            className="mt-4 flex items-center gap-2 rounded-lg border border-red-400/30 px-4 py-2 text-xs font-semibold text-red-200 transition hover:bg-red-500/20"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            {text.tryAgain}
          </button>
        </div>
      )}

      {/* Empty */}
      {!loading && !error && assessments.length === 0 && (
        <div
          className={`${panel} flex min-h-[300px] flex-col items-center justify-center p-6 text-center`}
        >
          <Database className="h-10 w-10 text-slate-500" />
          <h3 className="mt-4 text-lg font-bold text-white">
            {text.emptyTitle}
          </h3>
          <p className="mt-2 max-w-md text-sm text-slate-400">
            {text.emptyBody}
          </p>
        </div>
      )}

      {/* Content */}
      {!loading && assessments.length > 0 && active && (
        <>
          {/* Error from a manual action while data is still shown */}
          {error && (
            <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2 text-xs text-red-200">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}

          {/* Stale assessment notice */}
          {isStale && ageMinutes !== null && (
            <div className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-xs text-amber-200">
              <Clock className="h-4 w-4 shrink-0" />
              {fill(text.staleNotice, { age: formatAge(ageMinutes, lang) })}
            </div>
          )}

          <RiskSummaryStrip assessments={assessments} lang={lang} />

          <LocationCards
            assessments={assessments}
            selectedId={active.location_id}
            onSelect={setSelectedId}
            lang={lang}
          />

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            {/* Left column: map + comparison */}
            <div className="space-y-6 lg:col-span-6">
              <div className={`${panel} p-4`}>
                <div className="mb-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-cyan-400" />
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-white">
                      {text.map.title}
                    </h3>
                  </div>
                  <span className="text-xs text-slate-400">
                    {text.map.hint}
                  </span>
                </div>

                <div className="h-[440px]">
                  <TonleSapMap
                    height="100%"
                    selectedLocationId={active.location_id}
                    onSelectLocation={(loc) => setSelectedId(loc.id)}
                    riskAssessments={assessments}
                  />
                </div>
              </div>

              <ProvinceComparisonChart
                assessments={assessments}
                selectedId={active.location_id}
                onSelect={setSelectedId}
                lang={lang}
              />
            </div>

            {/* Right column: selected location */}
            <div className="space-y-6 lg:col-span-6">
              <div className={`${panel} p-6`}>
                <div className="mb-4 flex items-start justify-between gap-3 border-b border-navy-800 pb-3">
                  <div className="min-w-0">
                    <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-cyan-400">
                      {text.detail.current}
                    </span>
                    <h2 className="mt-0.5 truncate text-xl font-bold text-white">
                      {lang === "KM"
                        ? active.location_name_km || active.location_name
                        : active.location_name}
                    </h2>
                    <p className="mt-1 text-xs text-slate-400">
                      {active.province}
                    </p>
                  </div>
                  <RiskBadge level={active.risk_level} size="md" />
                </div>

                <div className="grid grid-cols-1 items-center gap-4 sm:grid-cols-12">
                  <div className="flex justify-center sm:col-span-6">
                    <RiskGauge
                      score={active.risk_score}
                      level={active.risk_level}
                      size={210}
                      title={text.detail.overall}
                      className="border-0 bg-transparent p-0 shadow-none"
                    />
                  </div>

                  <div className="space-y-4 sm:col-span-6">
                    <div>
                      <p className="text-xs text-slate-400">
                        {text.detail.category.replace(
                          "{level}",
                          text.levels[active.risk_level],
                        )}
                      </p>
                      <p
                        className="font-mono text-3xl font-extrabold"
                        style={{ color: LEVEL_COLORS[active.risk_level] }}
                      >
                        {active.risk_score.toFixed(1)}
                        <span className="text-sm font-normal text-slate-500">
                          /100
                        </span>
                      </p>
                    </div>

                    <div>
                      <p className="mb-1 text-xs text-slate-400">
                        {text.detail.driver}
                      </p>
                      <p className="text-sm font-semibold text-white">
                        {text.factors.names[active.primary_driver] ||
                          active.primary_driver ||
                          text.detail.notAvailable}
                      </p>
                    </div>

                    <div>
                      <p className="mb-1 text-xs text-slate-400">
                        {text.detail.assessedAt}
                      </p>
                      <p className="text-xs text-white">
                        {active.timestamp
                          ? new Date(active.timestamp).toLocaleString()
                          : text.detail.notAvailable}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <ExplanationAndActions assessment={active} lang={lang} />
            </div>
          </div>

          {/* Factors and data quality */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            <div className="lg:col-span-7">
              <FactorBreakdown assessment={active} lang={lang} />
            </div>
            <div className="lg:col-span-5">
              <DataQualityPanel assessment={active} lang={lang} />
            </div>
          </div>

          {/* Methodology */}
          <div className={`${panel} p-6`}>
            <div className="mb-4 flex items-center gap-2 border-b border-navy-800 pb-3">
              <BrainCircuit className="h-5 w-5 text-cyan-400" />
              <h3 className="text-sm font-semibold uppercase tracking-wider text-white">
                {text.method.title}
              </h3>
            </div>

            <div className="grid grid-cols-1 gap-4 text-xs md:grid-cols-3">
              {[
                {
                  tag: text.method.c1Tag,
                  title: text.method.c1Title,
                  body: text.method.c1Body,
                  color: "text-cyan-400",
                },
                {
                  tag: text.method.c2Tag,
                  title: text.method.c2Title,
                  body: text.method.c2Body,
                  color: "text-amber-400",
                },
                {
                  tag: text.method.c3Tag,
                  title: text.method.c3Title,
                  body: text.method.c3Body,
                  color: "text-purple-400",
                },
              ].map((item) => (
                <div
                  key={item.tag}
                  className="rounded-lg border border-navy-800 bg-navy-950/70 p-4"
                >
                  <span
                    className={`mb-1 block text-[10px] font-bold uppercase tracking-wider ${item.color}`}
                  >
                    {item.tag}
                  </span>
                  <h4 className="mb-2 text-sm font-bold text-white">
                    {item.title}
                  </h4>
                  <p className="leading-relaxed text-slate-400">{item.body}</p>
                </div>
              ))}
            </div>

            <div className="mt-4 grid grid-cols-1 gap-3 border-t border-navy-800 pt-4 sm:grid-cols-2">
              <div>
                <p className="text-[10px] uppercase text-slate-500">
                  {text.method.version}
                </p>
                <p className="mt-1 text-xs font-semibold text-white">
                  {active.model_version || text.detail.notAvailable}
                </p>
              </div>
              <div>
                <p className="text-[10px] uppercase text-slate-500">
                  {text.method.type}
                </p>
                <p className="mt-1 text-xs font-semibold text-white">
                  {active.model_type || text.detail.notAvailable}
                </p>
              </div>
            </div>

            <div className="mt-4 flex items-center gap-2 border-t border-navy-800 pt-4 text-xs text-slate-400">
              <Activity className="h-4 w-4 shrink-0 text-cyan-400" />
              <span>{text.method.disclaimer}</span>
            </div>
          </div>
        </>
      )}
    </DashboardLayout>
  );
}
