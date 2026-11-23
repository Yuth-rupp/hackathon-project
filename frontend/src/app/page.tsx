"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowRight,
  Droplets,
  CloudRain,
  Eye,
  ShieldAlert,
  Users,
  CheckCircle2,
  AlertTriangle,
  MapPin,
  Radio,
  ExternalLink,
  ChevronRight,
  Info,
} from "lucide-react";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { MONITORING_LOCATIONS, DATA_SOURCES } from "@/lib/constants";
import { RiskBadge } from "@/components/common/RiskBadge";
import { useLanguage } from "@/context/LanguageContext";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

interface LiveAlert {
  id: number;
  severity: string;
  province?: string;
  status: string;
  title: string;
}

export default function LandingPage() {
  const { language, t } = useLanguage();
  const [selectedProvinceId, setSelectedProvinceId] =
    useState<string>("pursat");
  const [activeAlerts, setActiveAlerts] = useState<LiveAlert[]>([]);

  useEffect(() => {
    let isMounted = true;
    async function loadLiveAlerts() {
      try {
        const res = await fetch(`${API_BASE}/alerts?status=active`);
        if (!res.ok) return;
        const data = await res.json();
        if (isMounted && Array.isArray(data)) {
          setActiveAlerts(data);
        }
      } catch (err) {
        console.error("Failed to fetch live alerts for homepage:", err);
      }
    }

    loadLiveAlerts();
    const interval = setInterval(loadLiveAlerts, 60000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const provinces = MONITORING_LOCATIONS.filter((l) => l.type === "province");
  const stations = MONITORING_LOCATIONS.filter((l) => l.type === "station");
  const currentProvince =
    provinces.find((p) => p.id === selectedProvinceId) || provinces[0];

  // Live alerts matching the currently selected province
  const provinceAlerts = activeAlerts.filter((a) =>
    (a.province || "")
      .toLowerCase()
      .includes(currentProvince.name.toLowerCase()),
  );

  const hasCriticalAlert = provinceAlerts.some(
    (a) =>
      a.severity.toLowerCase() === "very high" ||
      a.severity.toLowerCase() === "critical",
  );
  const hasHighAlert = provinceAlerts.some(
    (a) =>
      a.severity.toLowerCase() === "high" ||
      a.severity.toLowerCase() === "danger",
  );

  const currentRiskLevel = hasCriticalAlert
    ? "very_high"
    : hasHighAlert || currentProvince.id === "kampong-chhnang"
      ? "high"
      : "moderate";

  const features = [
    {
      icon: Droplets,
      href: "/hydrology",
      title: t(
        "landing.features.f1Title",
        "Hydrological Telemetry & Flow Inversion",
      ),
      desc: t(
        "landing.features.f1Desc",
        "Real-time monitoring of the Mekong–Tonle Sap reverse flow mechanism, lake stage heights, and GloFAS discharge forecasts.",
      ),
      tag: "GloFAS & MRC",
      color: "from-cyan-500/20 to-blue-500/10 text-cyan-400 border-cyan-500/30",
    },
    {
      icon: CloudRain,
      href: "/weather",
      title: t(
        "landing.features.f2Title",
        "High-Res Meteorological Intelligence",
      ),
      desc: t(
        "landing.features.f2Desc",
        "Sub-catchment precipitation forecast, convective storm cell tracking, and soil saturation indices across Cambodia.",
      ),
      tag: "Open-Meteo IFS",
      color:
        "from-blue-500/20 to-indigo-500/10 text-blue-400 border-blue-500/30",
    },
    {
      icon: Eye,
      href: "/satellite",
      title: t(
        "landing.features.f3Title",
        "Copernicus SAR Satellite Delineation",
      ),
      desc: t(
        "landing.features.f3Desc",
        "Cloud-penetrating Sentinel-1 C-band SAR radar imagery for automated inundation mapping during heavy tropical overcast.",
      ),
      tag: "Sentinel-1 & 2",
      color:
        "from-emerald-500/20 to-teal-500/10 text-emerald-400 border-emerald-500/30",
    },
    {
      icon: ShieldAlert,
      href: "/risk",
      title: t("landing.features.f4Title", "AI Multi-Hazard Risk Scoring"),
      desc: t(
        "landing.features.f4Desc",
        "Machine learning calibrated model distinguishing beneficial seasonal flood pulse from life-threatening catastrophic inundation.",
      ),
      tag: "ML Hazard Engine",
      color:
        "from-amber-500/20 to-orange-500/10 text-amber-400 border-amber-500/30",
    },
    {
      icon: Users,
      href: "/community",
      title: t(
        "landing.features.f5Title",
        "Community Vulnerability & Shelters",
      ),
      desc: t(
        "landing.features.f5Desc",
        "Localized vulnerability profiles for floating villages, high-ground evacuation shelters, and commune disaster committees.",
      ),
      tag: "NCDM 1294",
      color: "from-rose-500/20 to-pink-500/10 text-rose-400 border-rose-500/30",
    },
  ];

  return (
    <div className="min-h-screen bg-navy-950 text-slate-100 flex flex-col selection:bg-cyan-500 selection:text-white">
      {/* Stable Sticky Navbar */}
      <div className="sticky top-0 z-50 w-full bg-navy-950/95 backdrop-blur-md border-b border-navy-800/80">
        <Navbar />
      </div>

      {/* Hero Section */}
      <section className="relative overflow-hidden pt-12 pb-20 md:pt-20 md:pb-28">
        <div className="pointer-events-none absolute inset-0 -z-10">
          <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 h-[550px] w-[900px] rounded-full bg-cyan-600/15 blur-[120px]" />
          <div className="absolute top-1/2 left-1/4 h-[350px] w-[500px] rounded-full bg-blue-600/10 blur-[100px]" />
          <div className="absolute bottom-0 inset-x-0 h-40 bg-gradient-to-t from-navy-950 to-transparent" />
        </div>

        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-4xl mx-auto">
            {/* Pill Badge */}
            <Link
              href="/alerts"
              className="inline-flex items-center gap-2 rounded-full border border-cyan-500/30 bg-navy-900/80 px-4 py-1.5 text-xs font-semibold text-cyan-300 shadow-lg shadow-cyan-500/10 backdrop-blur-md mb-6 hover:border-cyan-400 transition-colors"
            >
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-cyan-400" />
              </span>
              <span>
                {activeAlerts.length > 0
                  ? `${activeAlerts.length} Live Flood Advisory Active — View Early Warning Center`
                  : t(
                      "landing.badge",
                      "Next-Gen Tonle Sap Early Warning Intelligence",
                    )}
              </span>
            </Link>

            {/* Headline */}
            <h1 className="text-4xl font-extrabold tracking-tight text-white sm:text-6xl lg:text-7xl">
              {t("landing.heroTitle1", "Understand the Water.")}{" "}
              <span className="bg-gradient-to-r from-cyan-400 via-teal-300 to-blue-500 bg-clip-text text-transparent">
                {t("landing.heroTitleHighlight", "Anticipate the Risk.")}
              </span>{" "}
              {t("landing.heroTitle2", "Protect Communities.")}
            </h1>

            {/* Subtitle */}
            <p className="mt-6 text-base text-slate-300 sm:text-lg lg:text-xl leading-relaxed max-w-3xl mx-auto">
              {t(
                "landing.heroSubtitle",
                "An AI-powered flood monitoring and early-warning platform for the Tonle Sap Lake Basin, Cambodia — integrating satellite radar, GloFAS hydrological discharge forecasts, and machine learning hazard models to transform raw Earth observation data into actionable disaster resilience.",
              )}
            </p>

            {/* Call To Action Buttons */}
            <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
              <Link
                href="/dashboard"
                className="group flex items-center gap-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-6 py-3.5 text-sm font-bold text-white shadow-lg shadow-cyan-500/25 transition-all duration-300 hover:scale-105 hover:shadow-cyan-500/40"
              >
                <span>
                  {t("landing.exploreDashboard", "Explore Live Dashboard")}
                </span>
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </Link>

              <a
                href="#why-floodpulse"
                className="flex items-center gap-2 rounded-xl border border-navy-700 bg-navy-900/80 px-6 py-3.5 text-sm font-semibold text-slate-200 backdrop-blur-md transition-all duration-300 hover:border-cyan-500/50 hover:bg-navy-800"
              >
                <span>{t("landing.whyFloodPulse", "Why FloodPulse AI?")}</span>
                <ChevronRight className="h-4 w-4 text-cyan-400" />
              </a>
            </div>
          </div>

          {/* Clickable Live Stats Bar */}
          <div className="mt-16 grid grid-cols-2 gap-4 rounded-2xl border border-navy-800 bg-navy-900/60 p-6 shadow-2xl backdrop-blur-xl md:grid-cols-4 md:p-8">
            <Link
              href="/community"
              className="flex flex-col items-center border-b border-navy-800/80 pb-4 md:border-b-0 md:border-r md:pb-0 hover:opacity-80 transition-opacity"
            >
              <span className="text-3xl font-extrabold text-white md:text-4xl">
                {provinces.length}
              </span>
              <span className="mt-1 text-xs font-semibold text-cyan-400 uppercase tracking-wider">
                {t("landing.stats.provinces", "Provinces Monitored")}
              </span>
              <span className="text-[11px] text-slate-400 mt-0.5">
                {t(
                  "landing.stats.provincesSub",
                  "Siem Reap, Pursat, K. Chhnang...",
                )}
              </span>
            </Link>

            <Link
              href="/hydrology"
              className="flex flex-col items-center border-b border-navy-800/80 pb-4 md:border-b-0 md:border-r md:pb-0 hover:opacity-80 transition-opacity"
            >
              <span className="text-3xl font-extrabold text-white md:text-4xl">
                {stations.length}
              </span>
              <span className="mt-1 text-xs font-semibold text-cyan-400 uppercase tracking-wider">
                {t("landing.stats.stations", "Key Hydro Stations")}
              </span>
              <span className="text-[11px] text-slate-400 mt-0.5">
                {t("landing.stats.stationsSub", "Prek Kdam, K. Luong, K. Thom")}
              </span>
            </Link>

            <Link
              href="/alerts"
              className="flex flex-col items-center border-b border-navy-800/80 pb-4 md:border-b-0 md:border-r md:pb-0 hover:opacity-80 transition-opacity"
            >
              <span className="text-3xl font-extrabold text-white md:text-4xl">
                {activeAlerts.length}
              </span>
              <span className="mt-1 text-xs font-semibold text-cyan-400 uppercase tracking-wider">
                Active Warnings
              </span>
              <span className="text-[11px] text-slate-400 mt-0.5">
                Live Early Warning Registry
              </span>
            </Link>

            <Link
              href="/risk"
              className="flex flex-col items-center hover:opacity-80 transition-opacity"
            >
              <span className="text-3xl font-extrabold text-emerald-400 md:text-4xl">
                {t("landing.stats.aiEngine", "AI Engine")}
              </span>
              <span className="mt-1 text-xs font-semibold text-cyan-400 uppercase tracking-wider">
                {t("landing.stats.aiSub", "Predictive Risk Model")}
              </span>
              <span className="text-[11px] text-slate-400 mt-0.5">
                {t(
                  "landing.stats.aiDetail",
                  "Flood Pulse vs Hazard Classification",
                )}
              </span>
            </Link>
          </div>
        </div>
      </section>

      {/* Why FloodPulse AI Section */}
      <section
        id="why-floodpulse"
        className="py-20 border-t border-navy-800/80 bg-navy-900/30 scroll-mt-20"
      >
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            <div>
              <div className="inline-flex items-center gap-1.5 rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs font-semibold text-cyan-300 mb-4">
                <Info className="h-3.5 w-3.5" />
                <span>
                  {t(
                    "landing.paradox.badge",
                    "The Tonle Sap Hydrological Paradox",
                  )}
                </span>
              </div>
              <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
                {t(
                  "landing.paradox.title",
                  "The Natural Pulse vs. The Destructive Deluge",
                )}
              </h2>
              <p className="mt-4 text-sm text-slate-300 leading-relaxed sm:text-base">
                {t(
                  "landing.paradox.p1",
                  "Tonle Sap is Southeast Asia’s largest freshwater lake and the biological heart of Cambodia, providing over 70% of the country’s inland protein. Every monsoon season, the Mekong River forces the Tonle Sap River to reverse its flow backward into the lake, expanding its surface area from 2,500 km² to over 16,000 km².",
                )}
              </p>
              <p className="mt-3 text-sm text-slate-300 leading-relaxed sm:text-base">
                {t(
                  "landing.paradox.p2",
                  "This seasonal flood pulse is not a natural disaster — it is an ecological necessity for breeding fish and fertile sediment. However, when typhoon squalls, upstream dam discharges, and catchment saturation coincide, the lake surpasses critical emergency thresholds, submerging floating schools, drowning rice granaries, and stranding tens of thousands of households.",
                )}
              </p>

              <div className="mt-6 space-y-3">
                <div className="flex items-start gap-3 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3.5">
                  <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
                  <div>
                    <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                      {t(
                        "landing.paradox.beneficialTitle",
                        "Ecological Seasonal Expansion (Beneficial)",
                      )}
                    </h4>
                    <p className="text-xs text-slate-300 mt-1">
                      {t(
                        "landing.paradox.beneficialDesc",
                        "Predictable water rise supporting inundated forest nurseries, sediment replenishment, and sustainable floating commune migrations.",
                      )}
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3 rounded-xl border border-rose-500/20 bg-rose-500/5 p-3.5">
                  <AlertTriangle className="h-5 w-5 text-rose-400 shrink-0 mt-0.5" />
                  <div>
                    <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                      {t(
                        "landing.paradox.hazardTitle",
                        "Hazardous Flood Surge (Catastrophic)",
                      )}
                    </h4>
                    <p className="text-xs text-slate-300 mt-1">
                      {t(
                        "landing.paradox.hazardDesc",
                        "Anomalous velocities > 1.8 m/s, sudden backwater surges, and bank-breaching stage heights exceeding safe village mooring thresholds.",
                      )}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Visual Basin Hydro Diagram Card */}
            <div className="relative rounded-2xl border border-navy-700 bg-navy-900/80 p-6 shadow-2xl backdrop-blur-xl">
              <div className="flex items-center justify-between border-b border-navy-800 pb-4">
                <div className="flex items-center gap-2">
                  <Activity className="h-5 w-5 text-cyan-400" />
                  <span className="text-sm font-bold text-white">
                    {t(
                      "landing.paradox.diagramTitle",
                      "Tonle Sap Reverse Flow Dynamics",
                    )}
                  </span>
                </div>
                <Link
                  href="/hydrology"
                  className="text-xs font-mono text-cyan-400 hover:underline"
                >
                  Prek Kdam & Kampong Luong
                </Link>
              </div>

              <div className="mt-5 space-y-4">
                <div className="rounded-xl border border-navy-800 bg-navy-950/70 p-4">
                  <div className="flex justify-between text-xs text-slate-300">
                    <span>
                      {t(
                        "landing.paradox.drySeason",
                        "Dry Season Lake Volume (April)",
                      )}
                    </span>
                    <span className="font-mono text-cyan-400">
                      ~1.5 - 2.0 BCM
                    </span>
                  </div>
                  <div className="mt-2 h-2.5 w-full rounded-full bg-navy-800 overflow-hidden">
                    <div
                      className="h-full bg-cyan-600 rounded-full"
                      style={{ width: "15%" }}
                    />
                  </div>
                </div>

                <div className="rounded-xl border border-navy-800 bg-navy-950/70 p-4">
                  <div className="flex justify-between text-xs text-slate-300">
                    <span>
                      {t(
                        "landing.paradox.wetSeason",
                        "Peak Wet Season Lake Volume (October)",
                      )}
                    </span>
                    <span className="font-mono text-cyan-400">
                      ~40.0 - 45.0 BCM
                    </span>
                  </div>
                  <div className="mt-2 h-2.5 w-full rounded-full bg-navy-800 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-cyan-400 to-blue-500 rounded-full"
                      style={{ width: "92%" }}
                    />
                  </div>
                </div>

                <div className="rounded-xl border border-navy-800 bg-navy-950/70 p-4">
                  <div className="flex justify-between text-xs text-slate-300">
                    <span>
                      {t(
                        "landing.paradox.surfaceExpansion",
                        "Seasonal Surface Area Expansion",
                      )}
                    </span>
                    <span className="font-mono text-emerald-400">6.4x</span>
                  </div>
                  <div className="mt-2 text-xs text-slate-400 leading-relaxed">
                    {t(
                      "landing.paradox.surfaceNote",
                      "Surface expands from 2,500 km² to 16,000 km², requiring intelligent spatial discrimination of harmless inundation versus vulnerable settlement risk.",
                    )}
                  </div>
                </div>
              </div>

              <div className="mt-6 border-t border-navy-800/90 pt-4 flex items-center justify-between">
                <span className="text-xs text-slate-400">
                  {t(
                    "landing.paradox.discriminator",
                    "FloodPulse AI Discriminator",
                  )}
                </span>
                <Link
                  href="/risk"
                  className="text-xs font-semibold text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
                >
                  {t(
                    "landing.paradox.activeClassifier",
                    "Active ML Classifier",
                  )}{" "}
                  <CheckCircle2 className="h-3.5 w-3.5" />
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Core Features Section (All Clickable Links, JRC GSW & ODC Removed) */}
      <section className="py-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <span className="text-xs font-bold tracking-wider text-cyan-400 uppercase">
              {t("landing.features.eyebrow", "Full-Spectrum Intelligence")}
            </span>
            <h2 className="mt-2 text-3xl font-extrabold text-white sm:text-4xl">
              {t(
                "landing.features.title",
                "Engineered for Real-World Flood Risk Mitigation",
              )}
            </h2>
            <p className="mt-3 text-sm text-slate-300 sm:text-base">
              {t(
                "landing.features.subtitle",
                "A synthesis of European Space Agency satellite constellations, European Centre for Medium-Range Weather Forecasts (ECMWF), and local ground truth telemetry.",
              )}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((f, idx) => {
              const Icon = f.icon;
              return (
                <Link
                  key={idx}
                  href={f.href}
                  className="group relative flex flex-col justify-between rounded-2xl border border-navy-800 bg-navy-900/60 p-6 shadow-xl backdrop-blur-md transition-all duration-300 hover:-translate-y-1 hover:border-cyan-500/40 hover:shadow-cyan-950/40"
                >
                  <div>
                    <div className="flex items-center justify-between mb-4">
                      <div
                        className={`flex h-12 w-12 items-center justify-center rounded-xl border bg-gradient-to-br ${f.color}`}
                      >
                        <Icon className="h-6 w-6" />
                      </div>
                      <span className="rounded-md border border-navy-700 bg-navy-800/80 px-2 py-0.5 text-[10px] font-semibold text-slate-300">
                        {f.tag}
                      </span>
                    </div>

                    <h3 className="text-lg font-bold text-white group-hover:text-cyan-300 transition-colors">
                      {f.title}
                    </h3>

                    <p className="mt-2.5 text-xs text-slate-300 leading-relaxed">
                      {f.desc}
                    </p>
                  </div>

                  <div className="mt-5 flex items-center gap-1 text-xs font-semibold text-cyan-400 group-hover:translate-x-1 transition-transform">
                    <span>{t("landing.features.learnMore", "Learn More")}</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      </section>

      {/* Coverage Section: 5 Provinces & 3 Hydro Stations */}
      <section className="py-20 border-t border-navy-800/80 bg-navy-900/40">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row md:items-end justify-between mb-12">
            <div>
              <span className="text-xs font-bold tracking-wider text-cyan-400 uppercase">
                {t("landing.coverage.eyebrow", "Geographic Coverage")}
              </span>
              <h2 className="mt-2 text-3xl font-extrabold text-white sm:text-4xl">
                {t(
                  "landing.coverage.title",
                  "Tonle Sap Riparian Basin Network",
                )}
              </h2>
              <p className="mt-2 text-sm text-slate-300 max-w-2xl">
                {t(
                  "landing.coverage.subtitle",
                  "Continuous spatial surveillance across 5 critical provinces and real-time telemetry from primary hydrological gauges.",
                )}
              </p>
            </div>
            <Link
              href="/hydrology"
              className="mt-4 md:mt-0 inline-flex items-center gap-1.5 text-xs font-semibold text-cyan-400 hover:text-cyan-300 transition-colors"
            >
              <span>
                {t(
                  "landing.coverage.viewTelemetry",
                  "View River Discharge Station Telemetry",
                )}
              </span>
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
            {/* Province Selection Tabs */}
            <div className="space-y-3">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                {t(
                  "landing.coverage.monitoredProvinces",
                  "Monitored Provinces",
                )}
              </h3>
              {provinces.map((prov) => {
                const isSelected = prov.id === selectedProvinceId;
                return (
                  <button
                    key={prov.id}
                    onClick={() => setSelectedProvinceId(prov.id)}
                    className={`w-full text-left rounded-xl p-4 border transition-all duration-200 flex items-center justify-between ${
                      isSelected
                        ? "border-cyan-500/50 bg-cyan-500/15 shadow-md shadow-cyan-500/10"
                        : "border-navy-800 bg-navy-900/60 hover:border-navy-700 hover:bg-navy-900"
                    }`}
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <MapPin
                          className={`h-4 w-4 ${isSelected ? "text-cyan-400" : "text-slate-400"}`}
                        />
                        <span className="text-sm font-bold text-white">
                          {language === "KM" ? prov.name_km : prov.name}
                        </span>
                        <span className="text-xs text-slate-400 font-normal">
                          ({language === "KM" ? prov.name : prov.name_km})
                        </span>
                      </div>
                      <div className="mt-1 text-[11px] text-slate-400 ml-6">
                        {prov.lat.toFixed(2)}°N, {prov.lon.toFixed(2)}°E &bull;{" "}
                        {prov.elevation_m}m
                      </div>
                    </div>
                    <ChevronRight
                      className={`h-4 w-4 ${isSelected ? "text-cyan-400" : "text-slate-500"}`}
                    />
                  </button>
                );
              })}
            </div>

            {/* Selected Province Details Card */}
            <div className="lg:col-span-2 rounded-2xl border border-navy-800 bg-navy-900/80 p-6 shadow-xl backdrop-blur-md">
              <div className="flex flex-wrap items-center justify-between gap-4 border-b border-navy-800 pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-2xl font-bold text-white">
                      {language === "KM"
                        ? currentProvince.name_km
                        : currentProvince.name}
                    </h3>
                    <span className="text-lg text-slate-400 font-medium">
                      {language === "KM"
                        ? currentProvince.name
                        : currentProvince.name_km}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {t("common.tonleSap", "Tonle Sap Lake Basin")} &bull;{" "}
                    {currentProvince.lat}, {currentProvince.lon}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <RiskBadge level={currentRiskLevel} />
                  <Link
                    href="/community"
                    className="rounded-lg border border-navy-700 bg-navy-800 px-3 py-1.5 text-xs font-semibold text-slate-200 hover:border-cyan-500 hover:text-white transition-colors"
                  >
                    {t(
                      "landing.coverage.viewCommunity",
                      "View Community Details",
                    )}
                  </Link>
                </div>
              </div>

              {/* Province Hydrological Parameters Grid */}
              <div className="mt-6 grid grid-cols-2 sm:grid-cols-3 gap-4">
                <div className="rounded-xl border border-navy-800 bg-navy-950/60 p-4">
                  <span className="text-[11px] uppercase tracking-wider text-slate-400">
                    {t("landing.coverage.baseElevation", "Base Elevation")}
                  </span>
                  <p className="mt-1 text-xl font-bold text-white">
                    {currentProvince.elevation_m} m
                  </p>
                  <span className="text-[10px] text-slate-400">
                    {t(
                      "landing.coverage.aboveSeaLevel",
                      "Above mean sea level",
                    )}
                  </span>
                </div>

                <Link
                  href="/risk"
                  className="rounded-xl border border-navy-800 bg-navy-950/60 p-4 hover:border-cyan-500/40 transition-colors"
                >
                  <span className="text-[11px] uppercase tracking-wider text-slate-400">
                    {t(
                      "landing.coverage.inundationRisk",
                      "Flood Inundation Risk",
                    )}
                  </span>
                  <p
                    className={`mt-1 text-xl font-bold ${
                      currentRiskLevel === "very_high"
                        ? "text-rose-400"
                        : currentRiskLevel === "high"
                          ? "text-orange-400"
                          : "text-amber-400"
                    }`}
                  >
                    {currentRiskLevel === "very_high"
                      ? "Critical Risk"
                      : currentRiskLevel === "high"
                        ? t("risk.high", "High Risk")
                        : t("risk.moderate", "Moderate Risk")}
                  </p>
                  <span className="text-[10px] text-slate-400">
                    {t(
                      "landing.coverage.basedOnGlofas",
                      "Based on GloFAS discharge",
                    )}
                  </span>
                </Link>

                <Link
                  href="/alerts"
                  className="rounded-xl border border-navy-800 bg-navy-950/60 p-4 hover:border-cyan-500/40 transition-colors"
                >
                  <span className="text-[11px] uppercase tracking-wider text-slate-400">
                    {t(
                      "landing.coverage.earlyWarningStatus",
                      "Early Warning Status",
                    )}
                  </span>
                  <p
                    className={`mt-1 text-xl font-bold ${
                      provinceAlerts.length > 0
                        ? "text-rose-400"
                        : "text-emerald-400"
                    }`}
                  >
                    {provinceAlerts.length > 0
                      ? `${provinceAlerts.length} Active Alert${provinceAlerts.length > 1 ? "s" : ""}`
                      : t(
                          "landing.coverage.activeAlertDesk",
                          "Active Alert Desk",
                        )}
                  </p>
                  <span className="text-[10px] text-slate-400">NCDM 1294</span>
                </Link>
              </div>

              {/* Clickable Hydro Stations Connected to this Province */}
              <div className="mt-6">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300 mb-3">
                  {t(
                    "landing.coverage.gaugeStations",
                    "Telemetry Gauge Stations",
                  )}
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {stations.map((st) => (
                    <Link
                      key={st.id}
                      href="/hydrology"
                      className="rounded-xl border border-navy-800 bg-navy-950/40 p-3 hover:border-cyan-500/40 hover:bg-navy-900/60 transition-colors block"
                    >
                      <div className="flex items-center gap-1.5 text-xs font-semibold text-cyan-300">
                        <Radio className="h-3 w-3 text-cyan-400 animate-pulse" />
                        <span className="truncate">
                          {language === "KM"
                            ? st.name_km
                            : st.name.replace(
                                "Hydrological Station",
                                "Station",
                              )}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400 mt-1 truncate">
                        {st.province}
                      </p>
                      <p className="text-[10px] font-mono text-slate-400 mt-0.5">
                        {st.lat.toFixed(4)}°N, {st.lon.toFixed(4)}°E
                      </p>
                    </Link>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Data Sources Attribution Section */}
      <section className="py-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-14">
            <span className="text-xs font-bold tracking-wider text-cyan-400 uppercase">
              {t("landing.sources.eyebrow", "Scientific Rigor & Open Data")}
            </span>
            <h2 className="mt-2 text-3xl font-extrabold text-white sm:text-4xl">
              {t(
                "landing.sources.title",
                "Powered by Real Earth Observation Data Feeds",
              )}
            </h2>
            <p className="mt-3 text-sm text-slate-300 sm:text-base">
              {t(
                "landing.sources.subtitle",
                "Zero simulated datasets. Every prediction, forecast curve, and flood boundary is computed directly from operational scientific APIs and official Cambodian repositories.",
              )}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {DATA_SOURCES.map((ds) => (
              <div
                key={ds.id}
                className="rounded-xl border border-navy-800 bg-navy-900/60 p-5 shadow-lg backdrop-blur-md flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold uppercase tracking-wider rounded bg-navy-800 px-2 py-0.5 text-cyan-300 border border-navy-700">
                      {ds.type}
                    </span>
                    <span className="flex items-center gap-1 text-[11px] text-emerald-400 font-medium">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                      {ds.status}
                    </span>
                  </div>

                  <h3 className="mt-3 text-sm font-bold text-white">
                    {ds.name}
                  </h3>
                  <p className="text-[11px] font-medium text-cyan-400">
                    {ds.provider}
                  </p>

                  <p className="mt-2 text-xs text-slate-300 leading-relaxed">
                    {ds.description}
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-navy-800/80 flex items-center justify-between text-[11px] text-slate-400">
                  <span>{ds.updateFrequency}</span>
                  <a
                    href={ds.endpoint}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 text-cyan-400 hover:text-cyan-300 transition-colors font-medium"
                  >
                    <span>{t("landing.sources.apiDocs", "API Docs")}</span>
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </div>
            ))}
          </div>

          {/* Call to Action Banner */}
          <div className="mt-16 rounded-2xl border border-cyan-500/30 bg-gradient-to-r from-navy-900 via-navy-900 to-cyan-950/60 p-8 text-center shadow-2xl">
            <h3 className="text-2xl font-bold text-white sm:text-3xl">
              {t(
                "landing.sources.ctaTitle",
                "Ready to explore Tonle Sap Basin in real time?",
              )}
            </h3>
            <p className="mt-2 text-sm text-slate-300 max-w-xl mx-auto">
              {t(
                "landing.sources.ctaSubtitle",
                "Access the live hydrological console, interactive Copernicus SAR flood map, and 7-day GloFAS river discharge forecasts now.",
              )}
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-4">
              <Link
                href="/dashboard"
                className="rounded-xl bg-cyan-500 px-6 py-3 text-sm font-bold text-navy-950 shadow-lg shadow-cyan-500/30 hover:bg-cyan-400 transition-all hover:scale-105"
              >
                {t("landing.sources.launchDashboard", "Launch Dashboard")}
              </Link>
              <Link
                href="/alerts"
                className="rounded-xl border border-navy-700 bg-navy-800/90 px-6 py-3 text-sm font-semibold text-white hover:border-cyan-500 transition-colors"
              >
                {t(
                  "landing.sources.activeAdvisories",
                  "Active Flood Advisories",
                )}
              </Link>
            </div>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
}
