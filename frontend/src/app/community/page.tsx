'use client';

import React, { useEffect, useState } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { fetchCommunityProfile, fetchFloodHistory } from '@/lib/api';
import { MONITORING_LOCATIONS } from '@/lib/constants';
import { CommunityProfile, FloodEvent } from '@/types';
import {
  Users,
  Anchor,
  ShieldCheck,
  AlertTriangle,
  Phone,
  Compass,
  Calendar,
  Home,
  CheckCircle,
  HelpCircle,
  Clock,
  ArrowRight,
  Shield,
} from 'lucide-react';

export default function CommunityPage() {
  const [selectedProvince, setSelectedProvince] = useState<string>('pursat');
  const [profile, setProfile] = useState<CommunityProfile | null>(null);
  const [floodHistory, setFloodHistory] = useState<FloodEvent[]>([]);
  const [loading, setLoading] = useState(true);

  const provinces = MONITORING_LOCATIONS.filter((l) => l.type === 'province');

  useEffect(() => {
    async function loadCommunityData() {
      try {
        setLoading(true);
        const [prof, history] = await Promise.all([
          fetchCommunityProfile(selectedProvince),
          fetchFloodHistory(selectedProvince),
        ]);
        setProfile(prof);
        setFloodHistory(history);
      } catch (err) {
        console.error('Error fetching community data:', err);
      } finally {
        setLoading(false);
      }
    }
    loadCommunityData();
  }, [selectedProvince]);

  return (
    <DashboardLayout
      title="Community Hazard Profiles & Disaster Preparedness"
      subtitle="Commune flood resilience, floating village demographics, historical disaster benchmarks, and safe evacuation corridors"
    >
      {/* Province Selector Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {provinces.map((p) => {
          const isSelected = p.id === selectedProvince;
          return (
            <div
              key={p.id}
              onClick={() => setSelectedProvince(p.id)}
              className={`cursor-pointer rounded-xl border p-4 transition-all duration-200 ${
                isSelected
                  ? 'border-cyan-500 bg-navy-900/90 ring-1 ring-cyan-500 shadow-xl'
                  : 'border-navy-800 bg-navy-900/50 hover:border-navy-700'
              }`}
            >
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-base font-bold text-white">{p.name}</h3>
                  <p className="text-xs text-slate-400 font-sans">{p.name_km}</p>
                </div>
                <div
                  className={`flex h-8 w-8 items-center justify-center rounded-lg border ${
                    isSelected
                      ? 'border-cyan-500/50 bg-cyan-500/20 text-cyan-300'
                      : 'border-navy-700 bg-navy-800 text-slate-400'
                  }`}
                >
                  <Users className="h-4 w-4" />
                </div>
              </div>

              <div className="mt-4 border-t border-navy-800 pt-2 text-[11px] text-slate-400 flex justify-between">
                <span>Elevation:</span>
                <span className="font-mono text-cyan-400">{p.elevation_m} m AMSL</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Selected Province Detailed Profile */}
      {profile && (
        <div className="rounded-xl border border-navy-800 bg-navy-900/60 p-6 shadow-xl backdrop-blur-md">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-navy-800 pb-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="rounded bg-cyan-500/20 px-2 py-0.5 text-[10px] font-bold text-cyan-300 border border-cyan-500/30">
                  Commune Hazard Profile
                </span>
                <h2 className="text-2xl font-bold text-white">{profile.province}</h2>
              </div>
              <p className="text-sm text-slate-400 font-sans mt-0.5">{profile.province_km}</p>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">Emergency Hotline:</span>
              <a
                href={`tel:${profile.contact_hotline.split(' ')[0]}`}
                className="flex items-center gap-1.5 rounded-lg border border-rose-500/40 bg-rose-950/60 px-3 py-1.5 text-xs font-bold text-rose-300 hover:bg-rose-900 transition-colors"
              >
                <Phone className="h-3.5 w-3.5" />
                <span>{profile.contact_hotline}</span>
              </a>
            </div>
          </div>

          <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-5">
            <div className="rounded-lg border border-navy-800 bg-navy-950/80 p-3.5">
              <span className="text-[11px] text-slate-400 block">Total Population</span>
              <span className="text-2xl font-bold text-white font-mono">
                {profile.population.toLocaleString()}
              </span>
              <span className="text-[10px] text-slate-400 mt-1 block">Commune census</span>
            </div>

            <div className="rounded-lg border border-navy-800 bg-navy-950/80 p-3.5">
              <span className="text-[11px] text-slate-400 block">Floating Villages</span>
              <span className="text-2xl font-bold text-cyan-300 font-mono">
                {profile.floating_villages_count}
              </span>
              <span className="text-[10px] text-slate-400 mt-1 block">Floating commune clusters</span>
            </div>

            <div className="rounded-lg border border-navy-800 bg-navy-950/80 p-3.5">
              <span className="text-[11px] text-slate-400 block">Vulnerable Households</span>
              <span className="text-2xl font-bold text-amber-300 font-mono">
                {profile.vulnerable_households.toLocaleString()}
              </span>
              <span className="text-[10px] text-slate-400 mt-1 block">In direct flood zone</span>
            </div>

            <div className="rounded-lg border border-navy-800 bg-navy-950/80 p-3.5">
              <span className="text-[11px] text-slate-400 block">Evacuation Shelters</span>
              <span className="text-2xl font-bold text-emerald-300 font-mono">
                {profile.evacuation_shelters_count}
              </span>
              <span className="text-[10px] text-slate-400 mt-1 block">High ground pagodas/schools</span>
            </div>

            <div className="rounded-lg border border-navy-800 bg-navy-950/80 p-3.5 col-span-2 sm:col-span-1">
              <span className="text-[11px] text-slate-400 block">Safe Zone Elevation</span>
              <span className="text-2xl font-bold text-purple-300 font-mono">
                {profile.safe_zone_elevation_m} m
              </span>
              <span className="text-[10px] text-slate-400 mt-1 block">Above mean sea level</span>
            </div>
          </div>

          <div className="mt-4 border-t border-navy-800 pt-3 flex flex-wrap items-center gap-2 text-xs">
            <span className="text-slate-400">Main Economic Livelihoods:</span>
            {profile.main_livelihoods.map((l, idx) => (
              <span key={idx} className="rounded-full bg-navy-800 px-2.5 py-0.5 text-slate-300">
                {l}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Grid: Preparedness Guidance Cards + Historical Flood Timeline */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Preparedness Guidance Cards (English) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-cyan-400" />
            <h3 className="text-sm font-semibold uppercase tracking-wider text-white">
              Standard Community Flood Preparedness Protocols
            </h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="rounded-xl border border-navy-800 bg-navy-900/60 p-4 shadow-lg backdrop-blur-md">
              <div className="flex items-center gap-2 mb-2">
                <Anchor className="h-4 w-4 text-cyan-400" />
                <h4 className="text-xs font-bold text-white uppercase">Floating Village Mooring</h4>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                Inspect bamboo raft anchors, nylon cables, and pontoon floats. Prepare to reposition floating homes to designated secondary sheltered bays as lake water accelerates reverse influx.
              </p>
            </div>

            <div className="rounded-xl border border-navy-800 bg-navy-900/60 p-4 shadow-lg backdrop-blur-md">
              <div className="flex items-center gap-2 mb-2">
                <Home className="h-4 w-4 text-amber-400" />
                <h4 className="text-xs font-bold text-white uppercase">Stilt House Elevation</h4>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                Relocate grain reserves, electrical equipment, drinking water barrels, and solar batteries above the +9.5m stage threshold mark. Prepare bamboo emergency walkways.
              </p>
            </div>

            <div className="rounded-xl border border-navy-800 bg-navy-900/60 p-4 shadow-lg backdrop-blur-md">
              <div className="flex items-center gap-2 mb-2">
                <Compass className="h-4 w-4 text-emerald-400" />
                <h4 className="text-xs font-bold text-white uppercase">Evacuation Corridor Drills</h4>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                Confirm motorized boat fuel reserves. Keep emergency kits ready: clean water purification tablets, dry provisions, torches, whistles, and family medical records.
              </p>
            </div>

            <div className="rounded-xl border border-navy-800 bg-navy-900/60 p-4 shadow-lg backdrop-blur-md">
              <div className="flex items-center gap-2 mb-2">
                <Users className="h-4 w-4 text-purple-400" />
                <h4 className="text-xs font-bold text-white uppercase">Livestock & Agricultural Safe Havens</h4>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                Herds of cattle and pigs must be evacuated 48 hours prior to anticipated cresting to elevated earthen mounds (Phteah Kandal safe mounds) and pagoda grounds.
              </p>
            </div>
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
              <div key={ev.id} className="relative pl-6 pb-2 border-l-2 border-cyan-800/80 last:border-0">
                <span className="absolute -left-[9px] top-0 flex h-4 w-4 items-center justify-center rounded-full bg-cyan-500 text-white text-[9px] font-bold">
                  {idx + 1}
                </span>

                <div className="flex items-baseline justify-between mb-1">
                  <h4 className="text-xs font-bold text-white">{ev.title}</h4>
                  <span className="font-mono text-xs font-extrabold text-amber-400">{ev.year}</span>
                </div>

                <p className="text-[11px] text-slate-300 leading-relaxed mb-2">{ev.summary}</p>

                <div className="grid grid-cols-3 gap-2 bg-navy-950/80 p-2 rounded border border-navy-800 text-[10px]">
                  <div>
                    <span className="text-slate-400 block">Peak Stage</span>
                    <span className="font-mono font-bold text-cyan-300">{ev.peak_water_level_m} m</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block">Duration</span>
                    <span className="font-mono text-slate-200">{ev.duration_days} days</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block">Damages</span>
                    <span className="font-mono text-rose-300">${(ev.estimated_damage_usd / 1e6).toFixed(0)}M</span>
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
              FloodPulse AI simulations are designed for open scientific research, community risk education, and preparedness decision support.
              All emergency evacuations, dam releases, and red alerts are governed by the National Committee for Disaster Management (NCDM) and the Ministry of Water Resources and Meteorology (MOWRAM).
              Dial <strong>1294</strong> (NCDM Toll-Free Emergency Hotline) for official emergency response services.
            </p>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
