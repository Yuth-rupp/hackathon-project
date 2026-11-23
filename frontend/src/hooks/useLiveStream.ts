"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE_URL } from "@/lib/constants";
import type { StreamConnection } from "@/hooks/useHydrologyStream";

export interface LiveStreamEvent {
  type: string;
  server_time?: string;
  [key: string]: unknown;
}

interface Options {
  /** Stream path below the API base, e.g. "/community/stream". */
  path: string;
  /** Event names to react to. Heartbeat and hello are always tracked. */
  events: string[];
  /** Called when the server pushes one of `events`. */
  onEvent: (event: LiveStreamEvent) => void;
  /** Called on the fallback timer while the stream is down. */
  onPoll: () => void;
  /** Fallback polling interval while the stream is down. Default 30 s. */
  pollIntervalMs?: number;
}

/**
 * Generic Server-Sent Events hook (same behaviour as useHydrologyStream).
 *
 * - Connected      -> "live": the server pushes updates instantly.
 * - Stream failing -> "polling": the page re-fetches on a timer instead.
 * - Browser offline-> "offline".
 * EventSource reconnects by itself, so "polling" returns to "live" as soon as
 * the server is reachable again.
 */
export function useLiveStream({
  path,
  events,
  onEvent,
  onPoll,
  pollIntervalMs = 30_000,
}: Options) {
  const [connection, setConnection] = useState<StreamConnection>("connecting");
  const [lastEventAt, setLastEventAt] = useState<Date | null>(null);

  const onEventRef = useRef(onEvent);
  const onPollRef = useRef(onPoll);

  useEffect(() => {
    onEventRef.current = onEvent;
    onPollRef.current = onPoll;
  });

  const eventsKey = events.join("|");

  // ---- Server-Sent Events ----
  useEffect(() => {
    if (typeof window === "undefined" || typeof EventSource === "undefined") {
      setConnection("polling");
      return;
    }

    const wanted = new Set(eventsKey.split("|").filter(Boolean));
    const source = new EventSource(`${API_BASE_URL}${path}`);

    const handleEvent = (message: MessageEvent) => {
      try {
        const event = JSON.parse(message.data) as LiveStreamEvent;
        setLastEventAt(new Date());

        if (wanted.has(event.type)) {
          onEventRef.current(event);
        }
      } catch (error) {
        console.error("Invalid stream event:", error);
      }
    };

    source.onopen = () => setConnection("live");
    source.onerror = () =>
      setConnection(navigator.onLine ? "polling" : "offline");

    ["hello", "heartbeat", ...Array.from(wanted)].forEach((name) =>
      source.addEventListener(name, handleEvent as EventListener),
    );

    return () => source.close();
  }, [path, eventsKey]);

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
