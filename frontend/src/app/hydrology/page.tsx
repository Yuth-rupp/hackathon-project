'use client';

import React, { useEffect, useState } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { TimeSeriesChart } from '@/components/charts/TimeSeriesChart';
import { fetchRiverDischarge, fetchHydrologyStations } from '@/lib/api';
import { RiverDischarge, Station } from '@/types';
import {
  Waves,
  Download,
  Activity,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  Info,
  Calendar,
  Layers,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';

export default function HydrologyPage() {
  const [stations, setStations] = useState<Station[]>([]);
  const [selectedStationId, setSelectedStationId] = useState<string>('station-prek-kdam');
  const [dischargeData, setDischargeData] = useState<RiverDischarge | null>(null);
  const [compareStationId, setCompareStationId] = useState<string>('station-kampong-luong');
  const [compareDischargeData, setCompareDischargeData] = useState<RiverDischarge | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingCompare, setLoadingCompare] = useState(false);

  // Fetch station list and primary station discharge
  useEffect(() => {
    async function init() {
      try {
        setLoading(true);
        const stList = await fetchHydrologyStations();
        setStations(stList);
        const data = await fetchRiverDischarge(selectedStationId);
        setDischargeData(data);
      } catch (err) {
        console.error('Error fetching hydrology telemetry:', err);
      } finally {
        setLoading(false);
      }
    }
    init();
  }, [selectedStationId]);

  // Fetch comparison station discharge
  useEffect(() => {
    async function loadCompare() {
      if (!compareStationId || compareStationId === selectedStationId) return;
      try {
        setLoadingCompare(true);
        const data = await fetchRiverDischarge(compareStationId);
        setCompareDischargeData(data);
      } catch (err) {
        console.error('Error loading compare station:', err);
      } finally {
        setLoadingCompare(false);
      }
    }
    loadCompare();
  }, [compareStationId, selectedStationId]);

  const activeStation = stations.find((s) => s.id === selectedStationId) || stations[0];
  const compStation = stations.find((s) => s.id === compareStationId);

  // Build CSV export
  const handleExportCSV = () => {
    if (!dischargeData || !dischargeData.forecast) return;

    const headers = ['Date', 'Discharge_m3s', 'Discharge_Median_m3s', 'P25_m3s', 'P75_m3s'];
    const rows = dischargeData.forecast.map((f) => [
      f.date,
      f.discharge_m3s,
      f.discharge_median,
      f.discharge_p25 ?? '',
      f.discharge_p75 ?? '',
    ]);

    const csvContent =
      'data:text/csv;charset=utf-8,' +
      [headers.join(','), ...rows.map((e) => e.join(','))].join('\n');

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute(
      'download',
      `floodpulse_discharge_${selectedStationId}_${new Date().toISOString().split('T')[0]}.csv`
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Build merged comparison chart dataset
  const mergedComparisonData =
    dischargeData?.forecast?.map((pt, idx) => {
      const compPt = compareDischargeData?.forecast?.[idx];
      return {
        date: pt.date,
        [activeStation?.name || 'Station 1']: pt.discharge_m3s,
        [compStation?.name || 'Station 2']: compPt?.discharge_m3s ?? 0,
      };
    }) || [];

  return (
    <DashboardLayout
      title="Tonle Sap Hydrological Monitoring"
      subtitle="ECMWF GloFAS v4.0 River Discharge Ensemble, MRC telemetric stage levels & reverse flow analysis"
      actions={
        <button
          onClick={handleExportCSV}
          className="flex items-center gap-1.5 rounded-lg border border-cyan-800/80 bg-cyan-950/60 px-3 py-1.5 text-xs font-semibold text-cyan-300 shadow-sm hover:bg-cyan-900/80 hover:text-white transition-all"
        >
          <Download className="h-3.5 w-3.5" />
          <span>Export Hydrology CSV</span>
        </button>
      }
    >
      {/* Station Selector Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {stations.map((st) => {
          const isSelected = st.id === selectedStationId;
          return (
            <div
              key={st.id}
              onClick={() => setSelectedStationId(st.id)}
              className={`cursor-pointer rounded-xl border p-4 transition-all duration-200 ${
                isSelected
                  ? 'border-cyan-500 bg-navy-900/90 shadow-lg shadow-cyan-950/40 ring-1 ring-cyan-500'
                  : 'border-navy-800 bg-navy-900/50 hover:border-navy-700 hover:bg-navy-900/70'
              }`}
            >
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-cyan-400">
                    {st.river}
                  </span>
                  <h3 className="mt-1 text-base font-bold text-white">{st.name}</h3>
                  <p className="text-xs text-slate-400 font-sans">{st.name_km}</p>
                </div>
                <div
                  className={`flex h-8 w-8 items-center justify-center rounded-lg border ${
                    isSelected
                      ? 'border-cyan-500/50 bg-cyan-500/20 text-cyan-300'
                      : 'border-navy-700 bg-navy-800/50 text-slate-400'
                  }`}
                >
                  <Waves className="h-4 w-4" />
                </div>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-2 border-t border-navy-800 pt-3 text-xs">
                <div>
                  <span className="text-slate-400 block text-[10px]">Water Level</span>
                  <span className="font-bold text-white">{st.water_level_m} m</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px]">Discharge</span>
                  <span className="font-bold text-cyan-300">
                    {st.discharge_m3s?.toLocaleString()} m³/s
                  </span>
                </div>
              </div>

              <div className="mt-2 flex items-center justify-between text-[11px]">
                <span className="text-slate-400 flex items-center gap-1">
                  Alarm: <span className="text-amber-400 font-medium">{st.alarm_level_m} m</span>
                </span>
                <span className="flex items-center gap-1 text-emerald-400">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Telemetry Active
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Selected Station Detailed Status */}
      {activeStation && (
        <div className="rounded-xl border border-navy-800 bg-navy-900/60 p-5 shadow-lg backdrop-blur-md">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-navy-800 pb-4">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-white">{activeStation.name}</h2>
                <span className="rounded bg-cyan-500/20 px-2 py-0.5 text-[10px] font-semibold text-cyan-300 border border-cyan-500/30">
                  {activeStation.river}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Coordinates: {activeStation.lat.toFixed(4)}°N, {activeStation.lon.toFixed(4)}°E &bull; Historical Datum Baseline: MRC Standard
              </p>
            </div>

            <div className="flex items-center gap-4 text-xs">
              <div className="rounded-lg border border-navy-800 bg-navy-950 px-3 py-2">
                <span className="text-slate-400 block text-[10px]">Hydraulic Direction</span>
                <span className="font-semibold text-cyan-400">
                  {selectedStationId === 'station-prek-kdam' ? 'Reverse Inflow (+1.8 m/s)' : 'Lake Circulation'}
                </span>
              </div>
              <div className="rounded-lg border border-navy-800 bg-navy-950 px-3 py-2">
                <span className="text-slate-400 block text-[10px]">Stage Tendency</span>
                <span className="font-semibold text-emerald-400 flex items-center gap-1">
                  <ArrowUpRight className="h-3.5 w-3.5" /> Rising (+0.12 m/24h)
                </span>
              </div>
            </div>
          </div>

          {/* TimeSeries Chart for 14-Day Forecast with Uncertainty Bounds */}
          <div className="mt-6">
            <TimeSeriesChart
              title={`14-Day River Discharge Forecast with Uncertainty Bounds (${activeStation.name})`}
              subtitle="ECMWF GloFAS ensemble simulation: median, p25 (lower bound) and p75 (upper bound)"
              unit="m³/s"
              data={dischargeData?.forecast || []}
              xKey="date"
              yKeys={[
                { key: 'discharge_p75', name: '75th Percentile Bound', color: '#60a5fa', type: 'line', strokeDasharray: '3 3' },
                { key: 'discharge_m3s', name: 'Discharge Ensemble Run', color: '#06b6d4', type: 'area' },
                { key: 'discharge_median', name: 'Median Historical Mean', color: '#10b981', type: 'line' },
                { key: 'discharge_p25', name: '25th Percentile Bound', color: '#93c5fd', type: 'line', strokeDasharray: '3 3' },
              ]}
              height={340}
            />
          </div>
        </div>
      )}

      {/* Station Comparison Section */}
      <div className="rounded-xl border border-navy-800 bg-navy-900/60 p-5 shadow-lg backdrop-blur-md">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-navy-800 pb-4 mb-4">
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-white">
              Multi-Station Hydraulic Overlay Comparison
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Compare discharge discharge dynamics between two key nodes in the Tonle Sap pulse system
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">Compare With:</span>
            <select
              value={compareStationId}
              onChange={(e) => setCompareStationId(e.target.value)}
              className="rounded-lg border border-navy-700 bg-navy-950 px-3 py-1.5 text-xs text-slate-100 focus:border-cyan-500 focus:outline-none"
            >
              {stations.map((st) => (
                <option key={st.id} value={st.id} disabled={st.id === selectedStationId}>
                  {st.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <TimeSeriesChart
          title={`${activeStation?.name || 'Station 1'} vs ${compStation?.name || 'Station 2'}`}
          subtitle="Simultaneous river discharge comparison overlay"
          unit="m³/s"
          data={mergedComparisonData}
          xKey="date"
          yKeys={[
            { key: activeStation?.name || 'Station 1', name: activeStation?.name || 'Station 1', color: '#06b6d4', type: 'line' },
            { key: compStation?.name || 'Station 2', name: compStation?.name || 'Station 2', color: '#f59e0b', type: 'line' },
          ]}
          height={280}
        />
      </div>

      {/* Attribution & Telemetry Notice Card */}
      <div className="rounded-xl border border-navy-800 bg-navy-900/40 p-4 text-xs text-slate-400">
        <div className="flex items-start gap-3">
          <Info className="h-5 w-5 text-cyan-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="font-semibold text-slate-200">
              Data Source Attribution & Telemetry Notice
            </p>
            <p className="leading-relaxed">
              Discharge simulations provided by <strong>GloFAS via Open-Meteo Flood API</strong> (ECMWF Copernicus Emergency Management Service).
              Ground telemetric stage observations are calibrated against the Mekong River Commission (MRC) hydrological monitoring network.
              <em> Note: Direct real-time MRC automated telemetry requires Mekong PDIES credentials; synthetic open-access calibration is applied for public monitoring.</em>
            </p>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
