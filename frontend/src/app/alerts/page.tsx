"use client";

import React, { useEffect, useState, useCallback } from "react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { RiskBadge } from "@/components/common/RiskBadge";
import { fetchAlerts } from "@/lib/api";
import { MONITORING_LOCATIONS } from "@/lib/constants";
import { Alert, AlertSeverity } from "@/types";
import {
  Bell,
  AlertTriangle,
  Send,
  Bot,
  CheckCircle2,
  X,
  PlusCircle,
  ShieldAlert,
  RefreshCw,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

const toBackendSeverity = (sev: AlertSeverity): string => {
  const map: Record<string, string> = {
    critical: "Very High",
    danger: "High",
    warning: "Moderate",
    info: "Low",
  };
  return map[sev] || "Moderate";
};

const normalizeSeverity = (sev: string): AlertSeverity => {
  const s = (sev || "").toLowerCase();
  if (s === "very high" || s === "critical") return "critical";
  if (s === "high" || s === "danger") return "danger";
  if (s === "moderate" || s === "warning") return "warning";
  return "info";
};

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [filterSeverity, setFilterSeverity] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);

  // Feedback banners
  const [banner, setBanner] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  // New alert form state
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newTitleKm, setNewTitleKm] = useState("");
  const [newSeverity, setNewSeverity] = useState<AlertSeverity>("warning");
  const [newLocation, setNewLocation] = useState("pursat");
  const [newMessage, setNewMessage] = useState("");
  const [newMessageKm, setNewMessageKm] = useState("");
  const [broadcastTelegram, setBroadcastTelegram] = useState(true);

  // Telegram live state
  const [telegramConnected, setTelegramConnected] = useState<boolean>(false);
  const [telegramToken, setTelegramToken] = useState("Loading...");
  const [telegramChatId, setTelegramChatId] = useState("");
  const [telegramTestStatus, setTelegramTestStatus] = useState<
    "idle" | "testing" | "success"
  >("idle");

  const showBanner = (type: "success" | "error", text: string) => {
    setBanner({ type, text });
    setTimeout(() => setBanner(null), 5000);
  };

  const loadAlerts = useCallback(async () => {
    try {
      const data = await fetchAlerts();
      setAlerts(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Error fetching alerts:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadTelegramStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/alerts/telegram-status`);
      if (!res.ok) return;
      const data = await res.json();
      setTelegramConnected(Boolean(data.connected));
      setTelegramToken(data.masked_token || "Not Configured");
      if (data.default_chat_id) {
        setTelegramChatId(data.default_chat_id);
      }
    } catch (err) {
      console.error("Error fetching Telegram status:", err);
      setTelegramToken("Unavailable");
    }
  }, []);

  useEffect(() => {
    loadAlerts();
    loadTelegramStatus();
    const interval = setInterval(loadAlerts, 30000);
    return () => clearInterval(interval);
  }, [loadAlerts, loadTelegramStatus]);

  const handleRunLiveScan = async () => {
    setScanning(true);
    try {
      const res = await fetch(`${API_BASE}/alerts/evaluate`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(`Scan failed (${res.status})`);
      const data = await res.json();
      await loadAlerts();
      showBanner(
        "success",
        `Live threshold scan completed. ${data.new_alerts_generated || 0} new alert(s) triggered.`,
      );
    } catch (err) {
      console.error("Live scan failed:", err);
      showBanner(
        "error",
        "Failed to run live threshold scan. Verify the backend is running.",
      );
    } finally {
      setScanning(false);
    }
  };

  const handleCreateAlert = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle || !newMessage) return;

    const loc =
      MONITORING_LOCATIONS.find((l) => l.id === newLocation) ||
      MONITORING_LOCATIONS[0];
    setSubmitting(true);

    try {
      const res = await fetch(`${API_BASE}/alerts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          severity: toBackendSeverity(newSeverity),
          title: newTitle,
          title_km: newTitleKm || null,
          message: newMessage,
          message_km: newMessageKm || null,
          province: loc.province,
          broadcast_telegram: broadcastTelegram,
        }),
      });

      if (!res.ok) throw new Error(`Failed to dispatch alert (${res.status})`);

      const created = await res.json();
      await loadAlerts();
      setIsCreateOpen(false);
      setNewTitle("");
      setNewTitleKm("");
      setNewMessage("");
      setNewMessageKm("");
      showBanner(
        "success",
        created.telegram_sent
          ? "Emergency advisory saved and broadcasted to Telegram."
          : "Emergency advisory saved to registry.",
      );
    } catch (err) {
      console.error("Dispatch failed:", err);
      showBanner(
        "error",
        "Failed to dispatch alert. Check backend connection and logs.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleUpdateStatus = async (
    alertId: string | number,
    action: "acknowledge" | "resolve",
  ) => {
    try {
      const body =
        action === "acknowledge"
          ? { responder_name: "Provincial Disaster Management Committee" }
          : {
              resolution_notes: "Resolved from Early Warning Console",
              resolved_by: "Disaster Coordinator",
            };

      const res = await fetch(`${API_BASE}/alerts/${alertId}/${action}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) throw new Error(`Failed to ${action} alert (${res.status})`);
      await loadAlerts();
      setSelectedAlert(null);
      showBanner(
        "success",
        action === "acknowledge"
          ? "Alert acknowledged."
          : "Alert marked as resolved.",
      );
    } catch (err) {
      console.error(err);
      showBanner("error", `Could not ${action} alert.`);
    }
  };

  const handleTelegramTest = async () => {
    setTelegramTestStatus("testing");
    try {
      const url = telegramChatId.trim()
        ? `${API_BASE}/alerts/test-telegram?chat_id=${encodeURIComponent(telegramChatId.trim())}`
        : `${API_BASE}/alerts/test-telegram`;

      const res = await fetch(url, { method: "POST" });
      const data = await res.json();

      if (res.ok && data.success !== false) {
        setTelegramTestStatus("success");
        showBanner("success", "Test notification delivered to Telegram.");
        setTimeout(() => setTelegramTestStatus("idle"), 3500);
      } else {
        throw new Error(data.error || data.detail || "Telegram test failed");
      }
    } catch (err: any) {
      console.error("Telegram test error:", err);
      setTelegramTestStatus("idle");
      showBanner(
        "error",
        `Telegram test failed: ${err?.message || "Check TELEGRAM_BOT_TOKEN and Chat ID."}`,
      );
    }
  };

  // Filter alerts safely across both frontend & backend schemas
  const filteredAlerts = alerts.filter((a) => {
    const normSev = normalizeSeverity(a.severity);
    const matchesSeverity =
      filterSeverity === "all" || normSev === filterSeverity;
    const locText = (a.location_name || a.province || "").toLowerCase();
    const q = searchQuery.toLowerCase();
    const matchesSearch =
      (a.title || "").toLowerCase().includes(q) ||
      locText.includes(q) ||
      (a.message || "").toLowerCase().includes(q);
    return matchesSeverity && matchesSearch;
  });

  const renderStatusBadge = (status: string) => {
    const s = (status || "active").toLowerCase();
    if (s === "resolved") {
      return (
        <span className="inline-flex items-center gap-1 rounded bg-slate-500/10 px-2 py-0.5 text-[10px] font-medium text-slate-400 border border-slate-500/20">
          Resolved
        </span>
      );
    }
    if (s === "acknowledged") {
      return (
        <span className="inline-flex items-center gap-1 rounded bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-400 border border-amber-500/20">
          Acknowledged
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 rounded bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-400 border border-emerald-500/20">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
        Active
      </span>
    );
  };

  return (
    <DashboardLayout
      title="Early Warning Center & Notification Dispatch"
      subtitle="Automated threshold surveillance, multi-channel alerting, and Telegram Bot dispatch"
      actions={
        <div className="flex items-center gap-2">
          <button
            onClick={handleRunLiveScan}
            disabled={scanning}
            className="flex items-center gap-1.5 rounded-lg border border-cyan-500/40 bg-cyan-950/60 px-3 py-1.5 text-xs font-semibold text-cyan-300 hover:bg-cyan-900/60 transition-colors disabled:opacity-50"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 ${scanning ? "animate-spin" : ""}`}
            />
            <span>{scanning ? "Scanning..." : "Run Live Scan"}</span>
          </button>

          <button
            onClick={() => setIsCreateOpen(true)}
            className="flex items-center gap-1.5 rounded-lg bg-rose-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-md hover:bg-rose-500 transition-colors"
          >
            <PlusCircle className="h-3.5 w-3.5" />
            <span>Dispatch Emergency Alert</span>
          </button>
        </div>
      }
    >
      {/* Status Banner */}
      {banner && (
        <div
          className={`flex items-center gap-2 rounded-lg border p-3 text-xs ${
            banner.type === "success"
              ? "border-emerald-500/40 bg-emerald-950/80 text-emerald-300"
              : "border-rose-500/40 bg-rose-950/80 text-rose-300"
          }`}
        >
          {banner.type === "success" ? (
            <CheckCircle2 className="h-4 w-4 shrink-0" />
          ) : (
            <AlertTriangle className="h-4 w-4 shrink-0" />
          )}
          <span>{banner.text}</span>
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
              <strong>
                FloodPulse AI does not replace official emergency warnings
              </strong>{" "}
              issued by the Ministry of Water Resources and Meteorology (MOWRAM)
              or the National Committee for Disaster Management (NCDM). Always
              cross-reference bulletins with official provincial administration
              broadcasts.
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
            <input
              type="text"
              placeholder="Search alerts or locations..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="rounded-lg border border-navy-700 bg-navy-950 px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-cyan-500 focus:outline-none"
            />

            <select
              value={filterSeverity}
              onChange={(e) => setFilterSeverity(e.target.value)}
              className="rounded-lg border border-navy-700 bg-navy-950 px-3 py-1.5 text-xs text-slate-200 focus:border-cyan-500 focus:outline-none"
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical / Very High</option>
              <option value="danger">Danger / High</option>
              <option value="warning">Warning / Moderate</option>
              <option value="info">Info / Low</option>
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
              {loading ? (
                <tr>
                  <td
                    colSpan={7}
                    className="py-8 text-center text-xs text-slate-500"
                  >
                    Loading live warnings...
                  </td>
                </tr>
              ) : filteredAlerts.length === 0 ? (
                <tr>
                  <td
                    colSpan={7}
                    className="py-8 text-center text-xs text-slate-500"
                  >
                    No active warnings matching the filter criteria.
                  </td>
                </tr>
              ) : (
                filteredAlerts.map((alt) => {
                  const normSev = normalizeSeverity(alt.severity);
                  const issuedAt = alt.issued_at || (alt as any).created_at;
                  const category =
                    alt.category || (alt as any).alert_type || "flood";

                  return (
                    <tr
                      key={alt.id}
                      onClick={() => setSelectedAlert(alt)}
                      className="hover:bg-navy-800/40 cursor-pointer transition-colors"
                    >
                      <td className="py-3 px-3">
                        <RiskBadge
                          level={
                            normSev === "critical"
                              ? "very_high"
                              : normSev === "danger"
                                ? "high"
                                : normSev === "warning"
                                  ? "moderate"
                                  : "low"
                          }
                          size="sm"
                        />
                      </td>
                      <td className="py-3 px-3">
                        <div className="font-semibold text-white">
                          {alt.title}
                        </div>
                        {alt.title_km && (
                          <div className="text-[11px] text-slate-400 font-sans">
                            {alt.title_km}
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-3 font-medium text-cyan-300">
                        {alt.province || alt.location_name || "Tonle Sap Basin"}
                      </td>
                      <td className="py-3 px-3 uppercase text-[10px] font-mono text-slate-400">
                        {category}
                      </td>
                      <td className="py-3 px-3 font-mono text-slate-400">
                        {issuedAt
                          ? new Date(issuedAt).toLocaleString([], {
                              month: "short",
                              day: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            })
                          : "—"}
                      </td>
                      <td className="py-3 px-3">
                        {renderStatusBadge(alt.status)}
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
                  );
                })
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
                Automated webhook relay for real-time flood pulse advisories to
                community leaders
              </p>
            </div>
          </div>

          <span
            className={`rounded-full px-3 py-1 text-xs font-semibold border ${
              telegramConnected
                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                : "bg-amber-500/10 text-amber-400 border-amber-500/30"
            }`}
          >
            {telegramConnected ? "Bot Connected & Ready" : "Bot Not Configured"}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-center">
          <div className="md:col-span-5">
            <label className="block text-xs text-slate-400 mb-1">
              Telegram Bot Token (Masked)
            </label>
            <input
              type="text"
              value={telegramToken}
              disabled
              className="w-full rounded-lg border border-navy-800 bg-navy-950 px-3 py-2 text-xs font-mono text-slate-400"
            />
          </div>

          <div className="md:col-span-4">
            <label className="block text-xs text-slate-400 mb-1">
              Target Community Broadcast Chat ID
            </label>
            <input
              type="text"
              value={telegramChatId}
              placeholder="Uses backend .env default if empty"
              onChange={(e) => setTelegramChatId(e.target.value)}
              className="w-full rounded-lg border border-navy-700 bg-navy-950 px-3 py-2 text-xs font-mono text-slate-200 focus:border-cyan-500 focus:outline-none"
            />
          </div>

          <div className="md:col-span-3 flex items-end">
            <button
              onClick={handleTelegramTest}
              disabled={telegramTestStatus === "testing"}
              className="w-full flex items-center justify-center gap-2 rounded-lg bg-cyan-600 px-4 py-2 text-xs font-semibold text-white hover:bg-cyan-500 transition-colors disabled:opacity-50"
            >
              <Send
                className={`h-3.5 w-3.5 ${telegramTestStatus === "testing" ? "animate-bounce" : ""}`}
              />
              <span>
                {telegramTestStatus === "testing"
                  ? "Dispatching Test..."
                  : telegramTestStatus === "success"
                    ? "Dispatched to Telegram!"
                    : "Send Test Notification"}
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
                <h3 className="text-lg font-bold text-white mt-1">
                  {selectedAlert.title}
                </h3>
                {selectedAlert.title_km && (
                  <p className="text-xs text-slate-300 font-sans mt-0.5">
                    {selectedAlert.title_km}
                  </p>
                )}
              </div>
              <button
                onClick={() => setSelectedAlert(null)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-navy-900 hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex items-center justify-between gap-3 text-xs border border-navy-800/80 rounded-lg p-3 bg-navy-900/40">
              <div>
                <span className="text-slate-400 block text-[10px]">
                  Location:
                </span>
                <span className="font-semibold text-white">
                  {selectedAlert.province || selectedAlert.location_name}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px]">
                  Severity:
                </span>
                <span className="font-semibold text-rose-400 uppercase">
                  {selectedAlert.severity}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px]">
                  Issued:
                </span>
                <span className="text-slate-300">
                  {new Date(
                    selectedAlert.issued_at ||
                      (selectedAlert as any).created_at,
                  ).toLocaleString()}
                </span>
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

            <div className="pt-2 flex justify-end gap-2">
              {selectedAlert.status === "active" && (
                <button
                  onClick={() =>
                    handleUpdateStatus(selectedAlert.id, "acknowledge")
                  }
                  className="rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-500"
                >
                  Acknowledge
                </button>
              )}
              {selectedAlert.status !== "resolved" && (
                <button
                  onClick={() =>
                    handleUpdateStatus(selectedAlert.id, "resolve")
                  }
                  className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-500"
                >
                  Mark Resolved
                </button>
              )}
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
                <label className="block text-slate-400 mb-1">
                  Target Province
                </label>
                <select
                  value={newLocation}
                  onChange={(e) => setNewLocation(e.target.value)}
                  className="w-full rounded-lg border border-navy-700 bg-navy-900 px-3 py-2 text-slate-200 focus:border-cyan-500 focus:outline-none"
                >
                  {MONITORING_LOCATIONS.filter(
                    (l) => l.type === "province",
                  ).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-slate-400 mb-1">
                  Alert Severity
                </label>
                <select
                  value={newSeverity}
                  onChange={(e) =>
                    setNewSeverity(e.target.value as AlertSeverity)
                  }
                  className="w-full rounded-lg border border-navy-700 bg-navy-900 px-3 py-2 text-slate-200 focus:border-cyan-500 focus:outline-none"
                >
                  <option value="warning">Warning / Moderate (Orange)</option>
                  <option value="danger">Danger / High (Red)</option>
                  <option value="critical">
                    Critical / Very High (Flash Hazard)
                  </option>
                  <option value="info">Informational / Low</option>
                </select>
              </div>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">
                  Title (English)
                </label>
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
                <label className="block text-slate-400 mb-1">
                  Title (Khmer)
                </label>
                <input
                  type="text"
                  placeholder="ចំណងជើងជាភាសាខ្មែរ"
                  value={newTitleKm}
                  onChange={(e) => setNewTitleKm(e.target.value)}
                  className="w-full rounded-lg border border-navy-700 bg-navy-900 px-3 py-2 text-slate-200 focus:border-cyan-500 focus:outline-none font-sans"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">
                  Message (English)
                </label>
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
                <label className="block text-slate-400 mb-1">
                  Message (Khmer)
                </label>
                <textarea
                  rows={2}
                  placeholder="ព័ត៌មានលម្អិតជាភាសាខ្មែរ..."
                  value={newMessageKm}
                  onChange={(e) => setNewMessageKm(e.target.value)}
                  className="w-full rounded-lg border border-navy-700 bg-navy-900 px-3 py-2 text-slate-200 focus:border-cyan-500 focus:outline-none font-sans"
                />
              </div>

              <label className="flex items-center gap-2 text-slate-300 pt-1 cursor-pointer">
                <input
                  type="checkbox"
                  checked={broadcastTelegram}
                  onChange={(e) => setBroadcastTelegram(e.target.checked)}
                  className="rounded border-navy-700 bg-navy-900 text-cyan-500 focus:ring-cyan-500"
                />
                <span>
                  Also broadcast this advisory to Telegram (@TonleSapFloodBot)
                </span>
              </label>
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
                disabled={submitting}
                className="rounded-lg bg-rose-600 px-4 py-2 text-xs font-semibold text-white hover:bg-rose-500 disabled:opacity-50"
              >
                {submitting ? "Broadcasting..." : "Broadcast Alert"}
              </button>
            </div>
          </form>
        </div>
      )}
    </DashboardLayout>
  );
}
