"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE_URL } from "@/lib/constants";

export type StreamConnection = "connecting" | "live" | "polling" | "offline";

export interface HydrologyStreamEvent {
  type: "hello" | "heartbeat" | "station_reading" | "discharge_updated";
  server_time?: string;
  station_code?: string;
  [key: string]: unknown;
}

interface Options {
  /** Called when the server pushes new data (station_reading / discharge_updated). */
  onData: (event: HydrologyStreamEvent) => void;
  /** Called on the fallback timer when the live stream is down. */
  onPoll: () => void;
  /** Fallback polling interval while the stream is down. Default 30 s. */
  pollIntervalMs?: number;
}

/**
 * Real-time connection to GET /hydrology/stream (Server-Sent Events).
 *
 * - Connected      -> state "live": the server pushes updates instantly.
 * - Stream failing -> state "polling": the page re-fetches on a timer instead.
 * - Browser offline-> state "offline".
 * EventSource reconnects by itself, so "polling" flips back to "live" as soon
 * as the server is reachable again.
 */
export function useHydrologyStream({
  onData,
  onPoll,
  pollIntervalMs = 30_000,
}: Options) {
  const [connection, setConnection] = useState<StreamConnection>("connecting");
  const [lastEventAt, setLastEventAt] = useState<Date | null>(null);

  const onDataRef = useRef(onData);
  const onPollRef = useRef(onPoll);

  useEffect(() => {
    onDataRef.current = onData;
    onPollRef.current = onPoll;
  });

  // ---- Server-Sent Events ----
  useEffect(() => {
    if (typeof window === "undefined" || typeof EventSource === "undefined") {
      setConnection("polling");
      return;
    }

    const source = new EventSource(`${API_BASE_URL}/hydrology/stream`);

    const handleEvent = (message: MessageEvent) => {
      try {
        const event = JSON.parse(message.data) as HydrologyStreamEvent;
        setLastEventAt(new Date());

        if (
          event.type === "station_reading" ||
          event.type === "discharge_updated"
        ) {
          onDataRef.current(event);
        }
      } catch (error) {
        console.error("Invalid stream event:", error);
      }
    };

    source.onopen = () => setConnection("live");
    source.onerror = () =>
      setConnection(navigator.onLine ? "polling" : "offline");

    (
      ["hello", "heartbeat", "station_reading", "discharge_updated"] as const
    ).forEach((name) =>
      source.addEventListener(name, handleEvent as EventListener),
    );

    return () => source.close();
  }, []);

  // ---- Browser online/offline awareness ----
  useEffect(() => {
    const goOffline = () => setConnection("offline");
    const goOnline = () => {
      setConnection("polling");
      onPollRef.current();
    };

    window.addEventListener("offline", goOffline);
    window.addEventListener("online", goOnline);

    return () => {
      window.removeEventListener("offline", goOffline);
      window.removeEventListener("online", goOnline);
    };
  }, []);

  // ---- Fallback polling (only while the stream is not live) ----
  useEffect(() => {
    if (connection === "live" || connection === "connecting") return;

    const timer = setInterval(() => {
      if (document.visibilityState === "visible") onPollRef.current();
    }, pollIntervalMs);

    return () => clearInterval(timer);
  }, [connection, pollIntervalMs]);

  // ---- Catch up when the tab becomes visible again ----
  useEffect(() => {
    const handleVisibility = () => {
      if (document.visibilityState === "visible") onPollRef.current();
    };

    document.addEventListener("visibilitychange", handleVisibility);
    return () =>
      document.removeEventListener("visibilitychange", handleVisibility);
  }, []);

  return { connection, lastEventAt };
}
