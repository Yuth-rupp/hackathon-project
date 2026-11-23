"use client";

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";
import enMessages from "@/messages/en.json";
import kmMessages from "@/messages/km.json";

export type Language = "EN" | "KM";

interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  toggleLanguage: () => void;
  t: (key: string, fallback?: string) => string;
  messages: typeof enMessages;
}

const LanguageContext = createContext<LanguageContextType | undefined>(
  undefined,
);

function getNestedValue(
  obj: Record<string, any>,
  path: string,
): string | undefined {
  const value = path.split(".").reduce<unknown>(
    (acc, part) => {
      if (acc !== null && typeof acc === "object" && part in acc) {
        return (acc as Record<string, unknown>)[part];
      }
      return undefined;
    },
    obj,
  );

  return typeof value === "string" ? value : undefined;
}

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = useState<Language>("EN");

  // Load saved preference on mount
  useEffect(() => {
    const saved = localStorage.getItem("floodpulse_lang");
    if (saved === "EN" || saved === "KM") {
      setLanguageState(saved);
    }
  }, []);

  // Update <html lang="..."> attribute for Khmer font rendering & accessibility
  useEffect(() => {
    document.documentElement.lang = language === "KM" ? "km" : "en";
  }, [language]);

  const setLanguage = useCallback((lang: Language) => {
    setLanguageState(lang);
    localStorage.setItem("floodpulse_lang", lang);
  }, []);

  const toggleLanguage = useCallback(() => {
    setLanguageState((prev) => {
      const next: Language = prev === "EN" ? "KM" : "EN";
      localStorage.setItem("floodpulse_lang", next);
      return next;
    });
  }, []);

  const messages =
    language === "KM" ? (kmMessages as typeof enMessages) : enMessages;

  const t = useCallback(
    (key: string, fallback?: string): string => {
      const value = getNestedValue(messages, key);
      if (typeof value === "string") return value;

      const enValue = getNestedValue(enMessages, key);
      if (typeof enValue === "string") return enValue;

      return fallback ?? key;
    },
    [messages],
  );

  return (
    <LanguageContext.Provider
      value={{ language, setLanguage, toggleLanguage, t, messages }}
    >
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useLanguage must be used within a LanguageProvider");
  }
  return context;
}
