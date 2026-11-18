import React from 'react';
import Link from 'next/link';
import { Droplets, ExternalLink, ShieldAlert, Award } from 'lucide-react';

export function Footer() {
  return (
    <footer className="border-t border-navy-800 bg-navy-950 text-slate-400">
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-8 md:grid-cols-2 lg:grid-cols-5">
          {/* Brand info */}
          <div className="lg:col-span-2 space-y-4">
            <div className="flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-400 to-navy-600 p-1.5 shadow-md shadow-cyan-500/20">
                <svg viewBox="0 0 24 24" className="h-5 w-5 text-navy-950 fill-cyan-300">
                  <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z" />
                </svg>
              </div>
              <span className="text-lg font-bold text-white tracking-tight">
                FloodPulse AI
              </span>
              <span className="rounded bg-cyan-500/20 px-1.5 py-0.5 text-[10px] font-semibold text-cyan-400 border border-cyan-500/30">
                CAMBODIA
              </span>
            </div>

            <p className="text-xs leading-relaxed text-slate-400 max-w-md">
              High-resolution hydrological risk modeling, Sentinel SAR flood inundation delineation,
              and AI-driven hazard forecasting engineered specifically for the ecological heart of the Lower Mekong Basin: the Tonle Sap Great Lake.
            </p>

            <div className="flex items-center gap-2 text-xs text-slate-300">
              <Award className="h-4 w-4 text-cyan-400" />
              <span>Built for Open Science & Disaster Risk Reduction</span>
            </div>
          </div>

          {/* Platform Navigation */}
          <div>
            <h3 className="text-xs font-semibold tracking-wider text-slate-200 uppercase">
              Platform
            </h3>
            <ul className="mt-3 space-y-2 text-xs">
              <li>
                <Link href="/dashboard" className="hover:text-cyan-400 transition-colors">
                  Basin Dashboard
                </Link>
              </li>
              <li>
                <Link href="/hydrology" className="hover:text-cyan-400 transition-colors">
                  GloFAS Hydrology
                </Link>
              </li>
              <li>
                <Link href="/weather" className="hover:text-cyan-400 transition-colors">
                  Meteorological Radar
                </Link>
              </li>
              <li>
                <Link href="/satellite" className="hover:text-cyan-400 transition-colors">
                  Copernicus Earth Observation
                </Link>
              </li>
              <li>
                <Link href="/risk" className="hover:text-cyan-400 transition-colors">
                  AI Hazard Engine
                </Link>
              </li>
            </ul>
          </div>

          {/* Data Sources */}
          <div>
            <h3 className="text-xs font-semibold tracking-wider text-slate-200 uppercase">
              Real Data Feeds
            </h3>
            <ul className="mt-3 space-y-2 text-xs">
              <li>
                <a
                  href="https://open-meteo.com"
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 hover:text-cyan-400 transition-colors"
                >
                  Open-Meteo GloFAS <ExternalLink className="h-3 w-3" />
                </a>
              </li>
              <li>
                <a
                  href="https://dataspace.copernicus.eu"
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 hover:text-cyan-400 transition-colors"
                >
                  Copernicus Sentinel STAC <ExternalLink className="h-3 w-3" />
                </a>
              </li>
              <li>
                <a
                  href="https://global-surface-water.appspot.com"
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 hover:text-cyan-400 transition-colors"
                >
                  EC JRC Surface Water <ExternalLink className="h-3 w-3" />
                </a>
              </li>
              <li>
                <a
                  href="https://data.opendevelopmentcambodia.net"
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 hover:text-cyan-400 transition-colors"
                >
                  Open Dev Cambodia <ExternalLink className="h-3 w-3" />
                </a>
              </li>
              <li>
                <a
                  href="https://portal.mrcmekong.org"
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 hover:text-cyan-400 transition-colors"
                >
                  Mekong River Commission <ExternalLink className="h-3 w-3" />
                </a>
              </li>
            </ul>
          </div>

          {/* Emergency & Hotlines */}
          <div>
            <h3 className="text-xs font-semibold tracking-wider text-slate-200 uppercase">
              Emergency Hotlines
            </h3>
            <ul className="mt-3 space-y-2 text-xs">
              <li className="flex items-center gap-1.5 text-rose-400 font-semibold">
                <ShieldAlert className="h-3.5 w-3.5" />
                <span>NCDM Cambodia: 1294</span>
              </li>
              <li>
                <span className="text-slate-400">Siem Reap Provincial Desk:</span>
                <p className="text-slate-200 font-mono">063 760 033</p>
              </li>
              <li>
                <span className="text-slate-400">Pursat Provincial Desk:</span>
                <p className="text-slate-200 font-mono">052 740 011</p>
              </li>
              <li>
                <span className="text-slate-400">Kampong Chhnang Desk:</span>
                <p className="text-slate-200 font-mono">026 770 012</p>
              </li>
            </ul>
          </div>
        </div>

        {/* Legal & Scientific Disclaimer */}
        <div className="mt-8 border-t border-navy-800/80 pt-6">
          <p className="text-[11px] leading-relaxed text-slate-400">
            <strong>Scientific & Operational Disclaimer:</strong> FloodPulse AI is an experimental decision-support
            and early hazard forecasting platform designed for research, disaster resilience planning, and community preparedness.
            Hydrological predictions rely on ensemble satellite observations and numerical weather models. Official evacuation orders,
            flood alerts, and public warnings must always be corroborated with the National Committee for Disaster Management (NCDM)
            and the Ministry of Water Resources and Meteorology (MOWRAM) of the Royal Government of Cambodia.
          </p>

          <div className="mt-4 flex flex-col sm:flex-row items-center justify-between text-[11px] text-slate-400 gap-2">
            <div>
              &copy; {new Date().getFullYear()} FloodPulse AI. All data rights belong to their respective scientific providers.
            </div>
            <div className="flex gap-4">
              <Link href="/data-sources" className="hover:text-cyan-400 transition-colors">
                Data Licenses
              </Link>
              <Link href="/alerts" className="hover:text-cyan-400 transition-colors">
                Alert Protocols
              </Link>
              <a
                href="https://github.com"
                target="_blank"
                rel="noreferrer"
                className="hover:text-cyan-400 transition-colors"
              >
                Open Source Repository
              </a>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}
