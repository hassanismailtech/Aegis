"use client";

import { useEffect, useRef, useState } from "react";

import { AEGIS_TOKEN, AEGIS_URL } from "@/lib/api";
import type { TelemetryEvent } from "@/lib/types";

export type ConnectionStatus = "connecting" | "live" | "retrying";

/**
 * SSE subscription to GET /v1/aegis/events. Reconnects with exponential
 * backoff (1s → 15s); EventSource heartbeats are ignored by the browser.
 */
export function useEventSource(
  onEvent: (event: TelemetryEvent) => void,
): ConnectionStatus {
  const handler = useRef(onEvent);
  const [status, setStatus] = useState<ConnectionStatus>("connecting");

  useEffect(() => {
    handler.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    let source: EventSource | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let disposed = false;
    let attempt = 0;

    const connect = () => {
      if (disposed) return;
      setStatus(attempt === 0 ? "connecting" : "retrying");
      const token = AEGIS_TOKEN ? `?access_token=${encodeURIComponent(AEGIS_TOKEN)}` : "";
      source = new EventSource(`${AEGIS_URL}/v1/aegis/events${token}`);
      source.onopen = () => {
        attempt = 0;
        setStatus("live");
      };
      source.addEventListener("telemetry", (event) => {
        try {
          handler.current(
            JSON.parse((event as MessageEvent<string>).data) as TelemetryEvent,
          );
        } catch {
          // Malformed frame: ignore; the next event still renders.
        }
      });
      source.onerror = () => {
        source?.close();
        source = null;
        if (disposed) return;
        setStatus("retrying");
        const delay = Math.min(1000 * 2 ** attempt, 15000);
        attempt += 1;
        timer = setTimeout(connect, delay);
      };
    };

    connect();
    return () => {
      disposed = true;
      if (timer) clearTimeout(timer);
      source?.close();
    };
  }, []);

  return status;
}
