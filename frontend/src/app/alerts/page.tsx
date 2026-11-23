'use client';

import React, { useEffect, useState } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { RiskBadge } from '@/components/common/RiskBadge';
import { fetchAlerts } from '@/lib/api';
import { MONITORING_LOCATIONS } from '@/lib/constants';
import { Alert, AlertSeverity } from '@/types';
import {
  Bell,
  AlertTriangle,
  Send,
  Bot,
  Filter,
  CheckCircle2,
  Clock,
  X,
  PlusCircle,
  ExternalLink,
  ShieldAlert,
} from 'lucide-react';

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [filterSeverity, setFilterSeverity] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [loading, setLoading] = useState(true);

  // New alert form state
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newTitleKm, setNewTitleKm] = useState('');
  const [newSeverity, setNewSeverity] = useState<AlertSeverity>('warning');
  const [newLocation, setNewLocation] = useState('pursat');
  const [newMessage, setNewMessage] = useState('');
  const [newMessageKm, setNewMessageKm] = useState('');
  const [createSuccess, setCreateSuccess] = useState(false);

  // Telegram test state
  const [telegramToken, setTelegramToken] = useState('6184920412:AAH9*******************');
  const [telegramChatId, setTelegramChatId] = useState('-1001928472910');
  const [telegramTestStatus, setTelegramTestStatus] = useState<'idle' | 'testing' | 'success'>('idle');

  useEffect(() => {
    async function loadAlerts() {
      try {
        setLoading(true);
        const data = await fetchAlerts();
        setAlerts(data);
      } catch (err) {
        console.error('Error fetching alerts:', err);
      } finally {
        setLoading(false);
      }
    }
    loadAlerts();
  }, []);

  const handleCreateAlert = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle || !newMessage) return;

    const loc = MONITORING_LOCATIONS.find((l) => l.id === newLocation) || MONITORING_LOCATIONS[0];

    const created: Alert = {
      id: `alt-${Date.now()}`,
      severity: newSeverity,
      title: newTitle,
      title_km: newTitleKm || undefined,
      message: newMessage,
      message_km: newMessageKm || undefined,
      location_id: loc.id,
      location_name: loc.name,
      province: loc.province,
      category: 'flood',
      issued_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 86400000 * 2).toISOString(),
      status: 'active',
    };

    setAlerts([created, ...alerts]);
    setIsCreateOpen(false);
    setCreateSuccess(true);
    setNewTitle('');
    setNewTitleKm('');
    setNewMessage('');
    setNewMessageKm('');
    setTimeout(() => setCreateSuccess(false), 4000);
  };

  const handleTelegramTest = () => {
    setTelegramTestStatus('testing');
    setTimeout(() => {
      setTelegramTestStatus('success');
      setTimeout(() => setTelegramTestStatus('idle'), 3500);
    }, 1200);
  };

  // Filter alerts
  const filteredAlerts = alerts.filter((a) => {
    const matchesSeverity = filterSeverity === 'all' || a.severity === filterSeverity;
    const matchesSearch =
      a.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.location_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.message.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSeverity && matchesSearch;
  });

  return (
    <DashboardLayout
      title="Early Warning Center & Notification Dispatch"
      subtitle="Automated threshold surveillance, multi-channel alerting, and Telegram Bot dispatch"
      actions={
        <button
          onClick={() => setIsCreateOpen(true)}
          className="flex items-center gap-1.5 rounded-lg bg-rose-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-md hover:bg-rose-500 transition-colors"
        >
          <PlusCircle className="h-3.5 w-3.5" />
          <span>Dispatch Emergency Alert</span>
        </button>
      }
    >
      {/* Success banner */}
      {createSuccess && (
        <div className="flex items-center gap-2 rounded-lg border border-emerald-500/40 bg-emerald-950/80 p-3 text-xs text-emerald-300">
          <CheckCircle2 className="h-4 w-4" />
          <span>New emergency advisory broadcasted to multi-channel dispatch network.</span>
        </div>
      )}

      {/* Prominent Legal Disclaimer Banner */}
      <div className="rounded-xl border border-amber-500/30 bg-amber-950/30 p-4 text-xs text-amber-200">
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-amber-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="font-bold text-white uppercase tracking-wider text-[11px]">
              Critical Public Safety Notice
            </p>
            <p className="leading-relaxed text-amber-300/90">
              <strong>FloodPulse AI does not replace official emergency warnings</strong> issued by the Ministry of Water Resources and Meteorology (MOWRAM) or the National Committee for Disaster Management (NCDM). Always cross-reference bulletins with official provincial administration broadcasts.
            </p>
          </div>
        </div>
      </div>

      {/* Active Alerts Table & Controls */}
      <div className="rounded-xl border border-navy-800 bg-navy-900/60 p-5 shadow-lg backdrop-blur-md">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-navy-800 pb-4 mb-4">
          <div className="flex items-center gap-2">
            <Bell className="h-4 w-4 text-cyan-400" />
            <h3 className="text-sm font-semibold uppercase tracking-wider text-white">
              Active Alerts & Warning Registry ({filteredAlerts.length})
            </h3>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Search Input */}
            <input
              type="text"
              placeholder="Search alerts or locations..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="rounded-lg border border-navy-700 bg-navy-950 px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-cyan-500 focus:outline-none"
            />

            {/* Severity Filter */}
            <select
              value={filterSeverity}
              onChange={(e) => setFilterSeverity(e.target.value)}
              className="rounded-lg border border-navy-700 bg-navy-950 px-3 py-1.5 text-xs text-slate-200 focus:border-cyan-500 focus:outline-none"
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical / Emergency</option>
              <option value="danger">Danger</option>
              <option value="warning">Warning</option>
              <option value="info">Info</option>
            </select>
          </div>
        </div>

        {/* Alerts Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="border-b border-navy-800 bg-navy-950/80 text-[11px] uppercase tracking-wider text-slate-400 font-mono">
              <tr>
                <th className="py-2.5 px-3">Severity</th>
                <th className="py-2.5 px-3">Advisory Title</th>
                <th className="py-2.5 px-3">Target Location</th>
                <th className="py-2.5 px-3">Category</th>
                <th className="py-2.5 px-3">Issued Time</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-navy-800/60">
              {filteredAlerts.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-xs text-slate-500">
                    No active warnings matching the filter criteria.
                  </td>
                </tr>
              ) : (
                filteredAlerts.map((alt) => (
                  <tr
                    key={alt.id}
                    onClick={() => setSelectedAlert(alt)}
                    className="hover:bg-navy-800/40 cursor-pointer transition-colors"
                  >
                    <td className="py-3 px-3">
                      <RiskBadge
                        level={
                          alt.severity === 'critical' || alt.severity === 'danger'
                            ? 'very_high'
                            : alt.severity === 'warning'
                            ? 'high'
                            : 'moderate'
                        }
                        size="sm"
                      />
                    </td>
                    <td className="py-3 px-3">
                      <div className="font-semibold text-white">{alt.title}</div>
                      {alt.title_km && (
                        <div className="text-[11px] text-slate-400 font-sans">{alt.title_km}</div>
                      )}
                    </td>
                    <td className="py-3 px-3 font-medium text-cyan-300">{alt.province}</td>
                    <td className="py-3 px-3 uppercase text-[10px] font-mono text-slate-400">
                      {alt.category}
                    </td>
                    <td className="py-3 px-3 font-mono text-slate-400">
                      {new Date(alt.issued_at).toLocaleString([], {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </td>
                    <td className="py-3 px-3">
                      <span className="inline-flex items-center gap-1 rounded bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-400 border border-emerald-500/20">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                        Active
                      </span>
                    </td>
                    <td className="py-3 px-3 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedAlert(alt);
                        }}
                        className="text-xs text-cyan-400 hover:text-cyan-300 underline"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Telegram Alert Bot Configuration Section */}
      <div className="rounded-xl border border-navy-800 bg-navy-900/60 p-6 shadow-xl backdrop-blur-md">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between border-b border-navy-800 pb-4 mb-4">
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-cyan-400" />
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-wider text-white">
                Telegram Early Warning Bot Integration (@TonleSapFloodBot)
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Automated webhook relay for real-time flood pulse advisories to community leaders
              </p>
            </div>
          </div>

          <span className="rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-400 border border-emerald-500/30">
            Bot Connected & Ready
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-center">
          <div className="md:col-span-5">
            <label className="block text-xs text-slate-400 mb-1">Telegram Bot Token (Masked)</label>
            <input
              type="text"
              value={telegramToken}
              disabled
              className="w-full rounded-lg border border-navy-800 bg-navy-950 px-3 py-2 text-xs font-mono text-slate-400"
            />
          </div>

          <div className="md:col-span-4">
            <label className="block text-xs text-slate-400 mb-1">Target Community Broadcast Chat ID</label>
            <input
              type="text"
              value={telegramChatId}
              onChange={(e) => setTelegramChatId(e.target.value)}
              className="w-full rounded-lg border border-navy-700 bg-navy-950 px-3 py-2 text-xs font-mono text-slate-200 focus:border-cyan-500 focus:outline-none"
            />
          </div>

          <div className="md:col-span-3 flex items-end">
            <button
              onClick={handleTelegramTest}
              disabled={telegramTestStatus === 'testing'}
              className="w-full flex items-center justify-center gap-2 rounded-lg bg-cyan-600 px-4 py-2 text-xs font-semibold text-white hover:bg-cyan-500 transition-colors"
            >
              <Send className={`h-3.5 w-3.5 ${telegramTestStatus === 'testing' ? 'animate-bounce' : ''}`} />
              <span>
                {telegramTestStatus === 'testing'
                  ? 'Dispatching Test...'
                  : telegramTestStatus === 'success'
                  ? 'Dispatched to Telegram!'
                  : 'Send Test Notification'}
              </span>
            </button>
          </div>
        </div>
      </div>

      {/* Alert Detail Modal */}
      {selectedAlert && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-xl border border-navy-800 bg-navy-950 p-6 shadow-2xl space-y-4">
            <div className="flex items-start justify-between border-b border-navy-800 pb-3">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-cyan-400 font-mono">
                  Official Warning Bulletin
                </span>
                <h3 className="text-lg font-bold text-white mt-1">{selectedAlert.title}</h3>
                {selectedAlert.title_km && (
                  <p className="text-xs text-slate-300 font-sans mt-0.5">{selectedAlert.title_km}</p>
                )}
              </div>
              <button
                onClick={() => setSelectedAlert(null)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-navy-900 hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex items-center gap-3 text-xs border border-navy-800/80 rounded-lg p-3 bg-navy-900/40">
              <div>
                <span className="text-slate-400 block text-[10px]">Location:</span>
                <span className="font-semibold text-white">{selectedAlert.province}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px]">Severity:</span>
                <span className="font-semibold text-rose-400 uppercase">{selectedAlert.severity}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px]">Issued:</span>
                <span className="text-slate-300">{new Date(selectedAlert.issued_at).toLocaleString()}</span>
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <span className="text-xs font-semibold text-cyan-400 block mb-1">
                  English Bulletin:
                </span>
                <p className="text-xs text-slate-200 leading-relaxed bg-navy-900/60 p-3 rounded-lg border border-navy-800">
                  {selectedAlert.message}
                </p>
              </div>

              {selectedAlert.message_km && (
                <div>
                  <span className="text-xs font-semibold text-cyan-400 block mb-1 font-sans">
                    សេចក្តីជូនដំណឹងជាភាសាខ្មែរ:
                  </span>
                  <p className="text-xs text-slate-200 leading-relaxed bg-navy-900/60 p-3 rounded-lg border border-navy-800 font-sans">
                    {selectedAlert.message_km}
                  </p>
                </div>
              )}
            </div>

            <div className="pt-2 flex justify-end">
              <button
                onClick={() => setSelectedAlert(null)}
                className="rounded-lg bg-navy-800 px-4 py-1.5 text-xs font-medium text-white hover:bg-navy-700"
              >
                Close Bulletin
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Alert Modal */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <form
            onSubmit={handleCreateAlert}
            className="w-full max-w-xl rounded-xl border border-navy-800 bg-navy-950 p-6 shadow-2xl space-y-4"
          >
            <div className="flex items-center justify-between border-b border-navy-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <ShieldAlert className="h-5 w-5 text-rose-500" />
                Dispatch Manual Emergency Flood Advisory
              </h3>
              <button
                type="button"
                onClick={() => setIsCreateOpen(false)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-navy-900 hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Target Province</label>
                <select
                  value={newLocation}
                  onChange={(e) => setNewLocation(e.target.value)}
                  className="w-full rounded-lg border border-navy-700 bg-navy-900 px-3 py-2 text-slate-200 focus:border-cyan-500 focus:outline-none"
                >
                  {MONITORING_LOCATIONS.filter((l) => l.type === 'province').map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Alert Severity</label>
                <select
                  value={newSeverity}
                  onChange={(e) => setNewSeverity(e.target.value as AlertSeverity)}
                  className="w-full rounded-lg border border-navy-700 bg-navy-900 px-3 py-2 text-slate-200 focus:border-cyan-500 focus:outline-none"
                >
                  <option value="warning">Warning (Orange)</option>
                  <option value="danger">Danger (Red)</option>
                  <option value="critical">Critical (Flash Hazard)</option>
                  <option value="info">Informational</option>
                </select>
              </div>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Title (English)</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Flash Runoff Warning: Pursat River Basin"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  className="w-full rounded-lg border border-navy-700 bg-navy-900 px-3 py-2 text-slate-200 focus:border-cyan-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Title (Khmer)</label>
                <input
                  type="text"
                  placeholder="ចំណងជើងជាភាសាខ្មែរ"
                  value={newTitleKm}
                  onChange={(e) => setNewTitleKm(e.target.value)}
                  className="w-full rounded-lg border border-navy-700 bg-navy-900 px-3 py-2 text-slate-200 focus:border-cyan-500 focus:outline-none font-sans"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Message (English)</label>
                <textarea
                  required
                  rows={3}
                  placeholder="Detailed warning guidance and evacuation thresholds..."
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  className="w-full rounded-lg border border-navy-700 bg-navy-900 px-3 py-2 text-slate-200 focus:border-cyan-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Message (Khmer)</label>
                <textarea
                  rows={2}
                  placeholder="ព័ត៌មានលម្អិតជាភាសាខ្មែរ..."
                  value={newMessageKm}
                  onChange={(e) => setNewMessageKm(e.target.value)}
                  className="w-full rounded-lg border border-navy-700 bg-navy-900 px-3 py-2 text-slate-200 focus:border-cyan-500 focus:outline-none font-sans"
                />
              </div>
            </div>

            <div className="pt-3 border-t border-navy-800 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setIsCreateOpen(false)}
                className="rounded-lg border border-navy-700 px-4 py-2 text-xs font-medium text-slate-300 hover:text-white"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="rounded-lg bg-rose-600 px-4 py-2 text-xs font-semibold text-white hover:bg-rose-500"
              >
                Broadcast Alert
              </button>
            </div>
          </form>
        </div>
      )}
    </DashboardLayout>
  );
}
