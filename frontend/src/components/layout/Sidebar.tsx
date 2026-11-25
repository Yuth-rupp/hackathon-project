"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import {
  Activity,
  Droplets,
  CloudRain,
  Eye,
  ShieldAlert,
  Users,
  Bell,
  ChevronLeft,
  ChevronRight,
  LifeBuoy,
} from "lucide-react";
import { useLanguage } from "@/context/LanguageContext";
import { fetchAlerts } from "@/lib/api";

const SIDEBAR_ITEMS = [
  {
    key: "navigation.dashboard",
    fallback: "Dashboard",
    href: "/dashboard",
    icon: Activity,
    badge: null,
  },
  {
    key: "navigation.hydrology",
    fallback: "Hydrology",
    href: "/hydrology",
    icon: Droplets,
    badge: "GloFAS",
  },
  {
    key: "navigation.weather",
    fallback: "Weather",
    href: "/weather",
    icon: CloudRain,
    badge: "Live",
  },
  {
    key: "navigation.satellite",
    fallback: "Satellite EO",
    href: "/satellite",
    icon: Eye,
    badge: "SAR",
  },
  {
    key: "navigation.risk",
    fallback: "AI Risk Engine",
    href: "/risk",
    icon: ShieldAlert,
    badge: "ML",
  },
  {
    key: "navigation.community",
    fallback: "Community Profile",
    href: "/community",
    icon: Users,
    badge: null,
  },
  {
    key: "navigation.alerts",
    fallback: "Flood Alerts",
    href: "/alerts",
    icon: Bell,
    badge: null,
    isAlert: true,
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { language, t } = useLanguage();
  const [collapsed, setCollapsed] = useState(false);
  const [alertsCount, setAlertsCount] = useState<number>(0);

  useEffect(() => {
    let isMounted = true;
    const loadAlerts = async () => {
      try {
        const data = await fetchAlerts();
        if (isMounted) {
          setAlertsCount(Array.isArray(data) ? data.length : 0);
        }
      } catch {
        // Ignore transient network errors
      }
    };

    loadAlerts();
    const interval = setInterval(loadAlerts, 60_000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [pathname]);

  return (
    <aside
      className={clsx(
        "sticky top-16 h-[calc(100dvh-4rem)] self-start shrink-0 hidden md:flex flex-col border-r border-navy-800 bg-navy-950/80 backdrop-blur-md transition-all duration-300 ease-in-out",
        collapsed ? "w-20" : "w-64",
      )}
    >
      {/* Collapse Toggle Button */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="absolute -right-3.5 top-7 z-20 flex h-7 w-7 items-center justify-center rounded-full border border-navy-700 bg-navy-900 text-slate-300 shadow-md transition-colors hover:border-cyan-500 hover:text-white"
        title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed ? (
          <ChevronRight className="h-4 w-4" />
        ) : (
          <ChevronLeft className="h-4 w-4" />
        )}
      </button>

      {/* Basin Telemetry Header */}
      <div className="flex h-16 items-center px-4 border-b border-navy-800/80">
        {!collapsed ? (
          <div className="flex flex-col">
            <span className="text-xs font-semibold tracking-wider text-cyan-400 uppercase">
              {language === "KM"
                ? "ផ្ទាំងប្រតិបត្តិការ"
                : "Operational Console"}
            </span>
            <span className="text-sm font-bold text-white truncate">
              {t("common.tonleSap", "Tonle Sap Monitoring")}
            </span>
          </div>
        ) : (
          <div className="mx-auto flex h-9 w-9 items-center justify-center rounded-lg bg-navy-900 text-cyan-400 border border-navy-800">
            <Activity className="h-4 w-4" />
          </div>
        )}
      </div>

      {/* Nav List */}
      <div className="flex-1 space-y-1.5 p-3 overflow-y-auto">
        {SIDEBAR_ITEMS.map((item) => {
          const Icon = item.icon;
          const label = t(item.key, item.fallback);
          const isActive =
            pathname === item.href ||
            (item.href !== "/dashboard" && pathname.startsWith(item.href));

          const dynamicBadge = item.isAlert
            ? alertsCount > 0
              ? String(alertsCount)
              : null
            : item.badge;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "group flex items-center rounded-xl px-3 py-2.5 text-xs font-medium transition-all duration-200",
                isActive
                  ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 shadow-sm shadow-cyan-500/10"
                  : "text-slate-400 hover:bg-navy-900/90 hover:text-slate-100",
                collapsed ? "justify-center" : "justify-between",
              )}
              title={collapsed ? label : undefined}
            >
              <div className="flex items-center gap-3 min-w-0">
                <Icon
                  className={clsx(
                    "h-4 w-4 shrink-0 transition-colors",
                    isActive
                      ? "text-cyan-400"
                      : "text-slate-400 group-hover:text-cyan-300",
                  )}
                />
                {!collapsed && <span className="truncate">{label}</span>}
              </div>

              {!collapsed && dynamicBadge && (
                <span
                  className={clsx(
                    "ml-2 shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold tracking-wide",
                    item.isAlert
                      ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                      : "bg-navy-800 text-cyan-300 border border-navy-700",
                  )}
                >
                  {dynamicBadge === "Live"
                    ? t("common.live", "Live")
                    : dynamicBadge}
                </span>
              )}
            </Link>
          );
        })}
      </div>

      {/* Bottom Emergency Help Box */}
      {!collapsed && (
        <div className="p-3 m-3 rounded-xl border border-navy-800/90 bg-navy-900/70">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-200">
            <LifeBuoy className="h-4 w-4 text-rose-400" />
            <span>
              {language === "KM"
                ? "ប្រព័ន្ធព្រមានជាមុន NCDM"
                : "NCDM Early Warning"}
            </span>
          </div>
          <p className="mt-1 text-[11px] text-slate-400 leading-relaxed">
            {language === "KM" ? (
              <>
                ហៅទូរស័ព្ទទៅលេខ <strong className="text-rose-400">1294</strong>{" "}
                នៅកម្ពុជា សម្រាប់សេវាសង្គ្រោះបន្ទាន់ និងការជូនដំណឹង។
              </>
            ) : (
              <>
                Dial <strong className="text-rose-400">1294</strong> in Cambodia
                for emergency alerts &amp; rescue services.
              </>
            )}
          </p>
        </div>
      )}
    </aside>
  );
}
