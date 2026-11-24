"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import {
  BasinStrip,
  ChangeFeed,
  LiveIndicator,
  ProvinceLiveChip,
  ProvinceLivePanel,
  RiskChange,
} from "@/components/community/LiveCommunityRisk";
import {
  fetchCommunityProfile,
  fetchCommunityRiskLive,
  fetchFloodHistory,
} from "@/lib/api";
import { MONITORING_LOCATIONS } from "@/lib/constants";
import { useLiveStream } from "@/hooks/useLiveStream";
import { CommunityProfile, CommunityRiskLive, FloodEvent } from "@/types";
import {
  Users,
  Anchor,
  ShieldCheck,
  AlertTriangle,
  Phone,
  Compass,
  Calendar,
  Home,
} from "lucide-react";

// Events that change what this page shows. The server announces them on
// GET /community/stream; the page then re-fetches /community/risk-live.
const LIVE_EVENTS = [
  "risk_updated",
  "alert_created",
  "alert_changed",
  "station_reading",
  "discharge_updated",
  "alerts_updated",
];

// A preparedness card turns into "Do now" once the community action level
// (0 routine, 1 prepare, 2 alert, 3 evacuate) reaches this number.
const PREPARED_CARDS = [
  {
    key: "mooring",
    title: "Floating Village Mooring",
    urgentFrom: 1,
    icon: Anchor,
    iconClass: "text-cyan-400",
    text: "Inspect bamboo raft anchors, nylon cables, and pontoon floats. Prepare to reposition floating homes to designated secondary sheltered bays as lake water accelerates reverse influx.",
  },
  {
    key: "stilt",
    title: "Stilt House Elevation",
    urgentFrom: 2,
    icon: Home,
    iconClass: "text-amber-400",
    text: "Relocate grain reserves, electrical equipment, drinking water barrels, and solar batteries above the +9.5m stage threshold mark. Prepare bamboo emergency walkways.",
  },
  {
    key: "evac",
    title: "Evacuation Corridor Drills",
    urgentFrom: 2,
    icon: Compass,
    iconClass: "text-emerald-400",
    text: "Confirm motorized boat fuel reserves. Keep emergency kits ready: clean water purification tablets, dry provisions, torches, whistles, and family medical records.",
  },
  {
    key: "livestock",
    title: "Livestock & Agricultural Safe Havens",
    urgentFrom: 2,
    icon: Users,
    iconClass: "text-purple-400",
    text: "Herds of cattle and pigs must be evacuated 48 hours prior to anticipated cresting to elevated earthen mounds (Phteah Kandal safe mounds) and pagoda grounds.",
  },
];

export default function CommunityPage() {
  const [selectedProvince, setSelectedProvince] = useState<string>("pursat");
  const [profile, setProfile] = useState<CommunityProfile | null>(null);
  const [floodHistory, setFloodHistory] = useState<FloodEvent[]>([]);

  // ---- live risk state ----
  const [live, setLive] = useState<CommunityRiskLive | null>(null);
  const [liveError, setLiveError] = useState<string | null>(null);
  const [changes, setChanges] = useState<RiskChange[]>([]);
  const [now, setNow] = useState<number>(() => Date.now());

  const previousIndex = useRef<
    Record<string, { index: number; label: string }>
  >({});
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const provinces = MONITORING_LOCATIONS.filter((l) => l.type === "province");

  // ---- static profile + history (changes with the selected province) ----
  useEffect(() => {
    async function loadCommunityData() {
      try {
        const [prof, history] = await Promise.all([
          fetchCommunityProfile(selectedProvince),
          fetchFloodHistory(selectedProvince),
        ]);
        setProfile(prof);
        setFloodHistory(history);
      } catch (err) {
        console.error("Error fetching community data:", err);
      }
    }
    loadCommunityData();
  }, [selectedProvince]);

  // ---- live risk loader ----
  const loadLive = useCallback(async () => {
    try {
      const data = await fetchCommunityRiskLive();

      const nextIndex: Record<string, { index: number; label: string }> = {};
      const found: RiskChange[] = [];

      for (const p of data.provinces) {
        nextIndex[p.key] = { index: p.action.index, label: p.action.label_en };
        const before = previousIndex.current[p.key];

        if (before && before.index !== p.action.index) {
          found.push({
            id: `${p.key}-${data.generated_at}`,
            province: p.name,
            fromLabel: before.label,
            toLabel: p.action.label_en,
            direction: p.action.index > before.index ? "up" : "down",
            at: Date.now(),
          });
        }
      }

      previousIndex.current = nextIndex;

      if (found.length > 0) {
        setChanges((current) => [...found, ...current].slice(0, 6));
      }

      setLive(data);
      setLiveError(null);
    } catch (err) {
      setLiveError(
        err instanceof Error
          ? err.message
          : "Live community risk is unavailable.",
      );
    }
  }, []);

  // Several events often arrive together (one risk_updated per province), so
  // wait a moment and fetch once.
  const scheduleRefresh = useCallback(() => {
    if (refreshTimer.current) return;
    refreshTimer.current = setTimeout(() => {
      refreshTimer.current = null;
      loadLive();
    }, 800);
  }, [loadLive]);

  useEffect(() => {
    loadLive();
    return () => {
      if (refreshTimer.current) clearTimeout(refreshTimer.current);
    };
  }, [loadLive]);

  const { connection, lastEventAt } = useLiveStream({
    path: "/community/stream",
    events: LIVE_EVENTS,
    onEvent: scheduleRefresh,
    onPoll: loadLive,
  });

  // Keep "x min ago" labels current.
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(timer);
  }, []);

  const liveByKey = new Map((live?.provinces ?? []).map((p) => [p.key, p]));
  const selectedLive = liveByKey.get(selectedProvince);
  const actionIndex = selectedLive?.action.index ?? null;

  return (
    <DashboardLayout
      title="Community Hazard Profiles & Disaster Preparedness"
      subtitle="Live community risk from the flood model, gauges, alerts and satellite, plus commune resilience, historical benchmarks and safe evacuation sites"
      lastUpdated={live?.generated_at}
      actions={
        <LiveIndicator
          connection={connection}
          lastEventAt={lastEventAt}
          now={now}
        />
      }
    >
      {/* Live basin summary */}
      {live && <BasinStrip basin={live.basin} now={now} />}

      {liveError && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 text-xs text-amber-200">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span>
              {live
                ? "Live refresh failed, showing the last data received. "
                : "Live community risk could not be loaded. "}
              {liveError}
            </span>
            <button
              type="button"
              onClick={loadLive}
              className="rounded-lg border border-amber-500/50 px-3 py-1 font-semibold hover:bg-amber-500/20"
            >
              Retry
            </button>
          </div>
        </div>
      )}

      <ChangeFeed changes={changes} now={now} />

      {/* Province Selector Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {provinces.map((p) => {
          const isSelected = p.id === selectedProvince;
          return (
            <div
              key={p.id}
              role="button"
              tabIndex={0}
              aria-pressed={isSelected}
              onClick={() => setSelectedProvince(p.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setSelectedProvince(p.id);
                }
              }}
              className={`cursor-pointer rounded-xl border p-4 transition-all duration-200 ${
                isSelected
                  ? "border-cyan-500 bg-navy-900/90 ring-1 ring-cyan-500 shadow-xl"
                  : "border-navy-800 bg-navy-900/50 hover:border-navy-700"
              }`}
            >
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-base font-bold text-white">{p.name}</h3>
                  <p className="text-xs text-slate-400 font-sans">
                    {p.name_km}
                  </p>
                </div>
                <div
                  className={`flex h-8 w-8 items-center justify-center rounded-lg border ${
                    isSelected
                      ? "border-cyan-500/50 bg-cyan-500/20 text-cyan-300"
                      : "border-navy-700 bg-navy-800 text-slate-400"
                  }`}
                >
                  <Users className="h-4 w-4" />
                </div>
              </div>

              <ProvinceLiveChip province={liveByKey.get(p.id)} />

              <div className="mt-4 border-t border-navy-800 pt-2 text-[11px] text-slate-400 flex justify-between">
                <span>Elevation:</span>
                <span className="font-mono text-cyan-400">
                  {p.elevation_m} m AMSL
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Live panel for the selected province */}
      {selectedLive ? (
        <ProvinceLivePanel province={selectedLive} now={now} />
      ) : (
        !liveError && (
          <div className="rounded-xl border border-navy-800 bg-navy-900/60 p-6 text-sm text-slate-400">
            Loading live community risk…
          </div>
        )
      )}

      {/* Selected Province Reference Profile */}
      {profile && (
        <div className="rounded-xl border border-navy-800 bg-navy-900/60 p-6 shadow-xl backdrop-blur-md">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-navy-800 pb-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="rounded bg-cyan-500/20 px-2 py-0.5 text-[10px] font-bold text-cyan-300 border border-cyan-500/30">
                  Commune Hazard Profile (reference data)
                </span>
                <h2 className="text-2xl font-bold text-white">
                  {profile.province}
                </h2>
              </div>
              <p className="text-sm text-slate-400 font-sans mt-0.5">
                {profile.province_km}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">Emergency Hotline:</span>
              <a
                href={`tel:${profile.contact_hotline.split(" ")[0]}`}
                className="flex items-center gap-1.5 rounded-lg border border-rose-500/40 bg-rose-950/60 px-3 py-1.5 text-xs font-bold text-rose-300 hover:bg-rose-900 transition-colors"
              >
                <Phone className="h-3.5 w-3.5" />
                <span>{profile.contact_hotline}</span>
              </a>
            </div>
          </div>

          <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-5">
            <div className="rounded-lg border border-navy-800 bg-navy-950/80 p-3.5">
              <span className="text-[11px] text-slate-400 block">
                Total Population
              </span>
              <span className="text-2xl font-bold text-white font-mono">
                {profile.population.toLocaleString()}
              </span>
              <span className="text-[10px] text-slate-400 mt-1 block">
                Commune census
              </span>
            </div>

            <div className="rounded-lg border border-navy-800 bg-navy-950/80 p-3.5">
              <span className="text-[11px] text-slate-400 block">
                Floating Villages
              </span>
              <span className="text-2xl font-bold text-cyan-300 font-mono">
                {profile.floating_villages_count}
              </span>
              <span className="text-[10px] text-slate-400 mt-1 block">
                Floating commune clusters
              </span>
            </div>

            <div className="rounded-lg border border-navy-800 bg-navy-950/80 p-3.5">
              <span className="text-[11px] text-slate-400 block">
                Vulnerable Households
              </span>
              <span className="text-2xl font-bold text-amber-300 font-mono">
                {profile.vulnerable_households.toLocaleString()}
              </span>
              <span className="text-[10px] text-slate-400 mt-1 block">
                In direct flood zone
              </span>
            </div>

            <div className="rounded-lg border border-navy-800 bg-navy-950/80 p-3.5">
              <span className="text-[11px] text-slate-400 block">
                Evacuation Shelters
              </span>
              <span className="text-2xl font-bold text-emerald-300 font-mono">
                {profile.evacuation_shelters_count}
              </span>
              <span className="text-[10px] text-slate-400 mt-1 block">
                High ground pagodas/schools
              </span>
            </div>

            <div className="rounded-lg border border-navy-800 bg-navy-950/80 p-3.5 col-span-2 sm:col-span-1">
              <span className="text-[11px] text-slate-400 block">
                Safe Zone Elevation
              </span>
              <span className="text-2xl font-bold text-purple-300 font-mono">
                {profile.safe_zone_elevation_m} m
              </span>
              <span className="text-[10px] text-slate-400 mt-1 block">
                Above mean sea level
              </span>
            </div>
          </div>

          <div className="mt-4 border-t border-navy-800 pt-3 flex flex-wrap items-center gap-2 text-xs">
            <span className="text-slate-400">Main Economic Livelihoods:</span>
            {profile.main_livelihoods.map((l, idx) => (
              <span
                key={idx}
                className="rounded-full bg-navy-800 px-2.5 py-0.5 text-slate-300"
              >
                {l}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Grid: Preparedness Guidance Cards + Historical Flood Timeline */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Preparedness Guidance Cards */}
        <div className="lg:col-span-7 space-y-4">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-cyan-400" />
            <h3 className="text-sm font-semibold uppercase tracking-wider text-white">
              Community Flood Preparedness Protocols
            </h3>
          </div>

          {selectedLive && (
            <p className="text-xs text-slate-400">
              Priorities for {selectedLive.name} follow the live action level:{" "}
              <span className="font-semibold text-slate-200">
                {selectedLive.action.label_en}
              </span>
              .
            </p>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {PREPARED_CARDS.map((card) => {
              const Icon = card.icon;
              const urgent =
                actionIndex !== null && actionIndex >= card.urgentFrom;

              return (
                <div
                  key={card.key}
                  className={`rounded-xl border bg-navy-900/60 p-4 shadow-lg backdrop-blur-md ${
                    urgent ? "border-orange-500/60" : "border-navy-800"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <Icon className={`h-4 w-4 ${card.iconClass}`} />
                      <h4 className="text-xs font-bold text-white uppercase">
                        {card.title}
                      </h4>
                    </div>
                    {actionIndex !== null && (
                      <span
                        className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-bold ${
                          urgent
                            ? "border-orange-500/50 bg-orange-500/15 text-orange-300"
                            : "border-navy-700 text-slate-400"
                        }`}
                      >
                        {urgent ? "Do now" : "Be ready"}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    {card.text}
                  </p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Historical Flood Timeline */}
        <div className="lg:col-span-5 flex flex-col">
          <div className="flex items-center gap-2 mb-4">
            <Calendar className="h-5 w-5 text-amber-400" />
            <h3 className="text-sm font-semibold uppercase tracking-wider text-white">
              Historical Flood Disasters Benchmark
            </h3>
          </div>

          <div className="flex-1 rounded-xl border border-navy-800 bg-navy-900/60 p-5 shadow-lg backdrop-blur-md space-y-6">
            {floodHistory.map((ev, idx) => (
              <div
                key={ev.id}
                className="relative pl-6 pb-2 border-l-2 border-cyan-800/80 last:border-0"
              >
                <span className="absolute -left-[9px] top-0 flex h-4 w-4 items-center justify-center rounded-full bg-cyan-500 text-white text-[9px] font-bold">
                  {idx + 1}
                </span>

                <div className="flex items-baseline justify-between mb-1">
                  <h4 className="text-xs font-bold text-white">{ev.title}</h4>
                  <span className="font-mono text-xs font-extrabold text-amber-400">
                    {ev.year}
                  </span>
                </div>

                <p className="text-[11px] text-slate-300 leading-relaxed mb-2">
                  {ev.summary}
                </p>

                <div className="grid grid-cols-3 gap-2 bg-navy-950/80 p-2 rounded border border-navy-800 text-[10px]">
                  <div>
                    <span className="text-slate-400 block">Peak Stage</span>
                    <span className="font-mono font-bold text-cyan-300">
                      {ev.peak_water_level_m} m
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block">Duration</span>
                    <span className="font-mono text-slate-200">
                      {ev.duration_days} days
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block">Damages</span>
                    <span className="font-mono text-rose-300">
                      ${(ev.estimated_damage_usd / 1e6).toFixed(0)}M
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Prominent Disclaimer */}
      <div className="rounded-xl border border-navy-800 bg-navy-900/40 p-4 text-xs text-slate-400">
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-amber-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="font-semibold text-slate-200">
              National Early Warning Coordination & Limitation Disclaimer
            </p>
            <p className="leading-relaxed">
              FloodPulse AI simulations are designed for open scientific
              research, community risk education, and preparedness decision
              support. All emergency evacuations, dam releases, and red alerts
              are governed by the National Committee for Disaster Management
              (NCDM) and the Ministry of Water Resources and Meteorology
              (MOWRAM). Dial <strong>1294</strong> (NCDM Toll-Free Emergency
              Hotline) for official emergency response services.
            </p>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
