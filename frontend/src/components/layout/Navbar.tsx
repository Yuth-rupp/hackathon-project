"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import {
  Bell,
  Menu,
  X,
  Sun,
  Moon,
  Globe,
  Activity,
  CloudRain,
  Eye,
  ShieldAlert,
  Users,
  Droplets,
} from "lucide-react";
import { useLanguage } from "@/context/LanguageContext";
import { fetchAlerts } from "@/lib/api";

export const NAV_LINKS = [
  {
    key: "navigation.dashboard",
    fallback: "Dashboard",
    href: "/dashboard",
    icon: Activity,
  },
  {
    key: "navigation.hydrology",
    fallback: "Hydrology",
    href: "/hydrology",
    icon: Droplets,
  },
  {
    key: "navigation.weather",
    fallback: "Weather",
    href: "/weather",
    icon: CloudRain,
  },
  {
    key: "navigation.satellite",
    fallback: "Satellite",
    href: "/satellite",
    icon: Eye,
  },
  {
    key: "navigation.risk",
    fallback: "AI Risk",
    href: "/risk",
    icon: ShieldAlert,
  },
  {
    key: "navigation.community",
    fallback: "Community",
    href: "/community",
    icon: Users,
  },
  {
    key: "navigation.alerts",
    fallback: "Alerts",
    href: "/alerts",
    icon: Bell,
  },
];

export function Navbar() {
  const pathname = usePathname();
  const { language, toggleLanguage, t } = useLanguage();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(true);
  const [alertsCount, setAlertsCount] = useState<number>(0);

  // Sync theme from localStorage on mount and every route change
  useEffect(() => {
    const savedTheme = localStorage.getItem("floodpulse_theme");
    const shouldBeDark = savedTheme !== "light";
    setIsDarkMode(shouldBeDark);

    const root = document.documentElement;
    if (shouldBeDark) {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
  }, [pathname]);

  // Fetch live active alerts count for the notification bell
  useEffect(() => {
    let isMounted = true;
    const loadAlertsCount = async () => {
      try {
        const data = await fetchAlerts();
        if (isMounted) {
          setAlertsCount(Array.isArray(data) ? data.length : 0);
        }
      } catch {
        // Keep previous count if backend is momentarily unreachable
      }
    };

    loadAlertsCount();
    const interval = setInterval(loadAlertsCount, 60_000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [pathname]);

  const toggleDarkMode = () => {
    setIsDarkMode((prev) => {
      const next = !prev;
      localStorage.setItem("floodpulse_theme", next ? "dark" : "light");

      const root = document.documentElement;
      if (next) {
        root.classList.add("dark");
      } else {
        root.classList.remove("dark");
      }
      return next;
    });
  };

  return (
    <nav className="sticky top-0 z-50 w-full border-b border-navy-800 bg-navy-950/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand / Logo */}
        <div className="flex items-center gap-3">
          <Link href="/" className="group flex items-center gap-2.5">
            <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-400 to-navy-600 p-2 shadow-lg shadow-cyan-500/20 ring-1 ring-cyan-400/40 transition-transform duration-300 group-hover:scale-105">
              <svg
                viewBox="0 0 24 24"
                className="h-6 w-6 text-navy-950 fill-cyan-300 drop-shadow"
              >
                <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z" />
              </svg>
              <div className="absolute inset-0 rounded-xl bg-cyan-400/30 blur-sm -z-10 animate-pulse" />
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-1.5">
                <span className="text-lg font-extrabold tracking-tight text-white">
                  FloodPulse
                </span>
                <span className="rounded bg-cyan-500/20 px-1.5 py-0.2 text-[10px] font-bold text-cyan-400 border border-cyan-500/30">
                  AI
                </span>
              </div>
              <span className="text-[10px] font-medium tracking-wider text-slate-400">
                {t("common.tonleSap", "TONLE SAP BASIN")}
              </span>
            </div>
          </Link>

          {/* Real-time Status Indicator Badge */}
          <div className="hidden lg:flex items-center gap-1.5 ml-3 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-medium text-emerald-400">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
            </span>
            <span>{t("common.live", "Live Telemetry")}</span>
          </div>
        </div>

        {/* Desktop Nav Links */}
        <div className="hidden xl:flex items-center gap-1">
          {NAV_LINKS.map((item) => {
            const isActive =
              pathname === item.href ||
              (item.href !== "/" && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={clsx(
                  "rounded-lg px-3 py-1.5 text-xs font-semibold transition-all duration-200",
                  isActive
                    ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 shadow-sm"
                    : "text-slate-300 hover:bg-navy-800/80 hover:text-white",
                )}
              >
                {t(item.key, item.fallback)}
              </Link>
            );
          })}
        </div>

        {/* Right Action Icons & Toggles */}
        <div className="flex items-center gap-2">
          {/* Language Toggle */}
          <button
            onClick={toggleLanguage}
            title={`Switch language (Current: ${language === "EN" ? "English" : "Khmer"})`}
            className="flex items-center gap-1 rounded-lg border border-navy-800 bg-navy-900/80 px-2.5 py-1.5 text-xs font-semibold text-slate-300 transition-colors hover:border-cyan-500/40 hover:text-white"
          >
            <Globe className="h-3.5 w-3.5 text-cyan-400" />
            <span>{language === "EN" ? "EN" : "ខ្មែរ"}</span>
          </button>

          {/* Dark / Light Toggle */}
          <button
            onClick={toggleDarkMode}
            title={isDarkMode ? "Switch to Light Mode" : "Switch to Dark Mode"}
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-navy-800 bg-navy-900/80 text-slate-300 transition-colors hover:border-cyan-500/40 hover:text-white"
          >
            {isDarkMode ? (
              <Sun className="h-4 w-4 text-amber-400" />
            ) : (
              <Moon className="h-4 w-4 text-cyan-400" />
            )}
          </button>

          {/* Alerts Notification Bell */}
          <Link
            href="/alerts"
            title={t("navigation.alerts", "Active Flood Alerts")}
            className="relative flex h-9 w-9 items-center justify-center rounded-lg border border-navy-800 bg-navy-900/80 text-slate-300 transition-colors hover:border-cyan-500/40 hover:text-white"
          >
            <Bell className="h-4 w-4" />
            {alertsCount > 0 && (
              <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-rose-500 text-[10px] font-bold text-white shadow-sm shadow-rose-500/50">
                {alertsCount}
              </span>
            )}
          </Link>

          {/* Mobile Menu Toggle Button */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-navy-800 bg-navy-900 text-slate-300 transition-colors hover:text-white xl:hidden"
            aria-label="Toggle navigation menu"
          >
            {mobileMenuOpen ? (
              <X className="h-5 w-5" />
            ) : (
              <Menu className="h-5 w-5" />
            )}
          </button>
        </div>
      </div>

      {/* Mobile Drawer Menu */}
      {mobileMenuOpen && (
        <div className="border-b border-navy-800 bg-navy-950 px-4 pt-2 pb-6 xl:hidden">
          <div className="space-y-1">
            {NAV_LINKS.map((item) => {
              const Icon = item.icon;
              const isActive =
                pathname === item.href ||
                (item.href !== "/" && pathname.startsWith(item.href));
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={clsx(
                    "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/30"
                      : "text-slate-300 hover:bg-navy-900 hover:text-white",
                  )}
                >
                  <Icon className="h-4 w-4 text-cyan-400" />
                  <span>{t(item.key, item.fallback)}</span>
                </Link>
              );
            })}
          </div>

          <div className="mt-4 border-t border-navy-800 pt-3 flex items-center justify-between text-xs text-slate-400">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              {t("common.live", "Live Telemetry Online")}
            </span>
            <span>v1.0.0</span>
          </div>
        </div>
      )}
    </nav>
  );
}
