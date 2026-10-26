"use client";

import { useEffect, useRef, useState } from "react";

import { AEGIS_URL, fetchTicket } from "@/lib/api";
import type { TelemetryEvent } from "@/lib/types";

export type ConnectionStatus = "connecting" | "live" | "retrying";

/**
 * SSE subscription to GET /v1/aegis/events. Every connection attempt exchanges
 * the demo token for a fresh 60 s ticket. Reconnects with exponential backoff
 * (1s → 15s); EventSource heartbeats are ignored by the browser.
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

    function retry() {
      if (disposed) return;
      setStatus("retrying");
      const delay = Math.min(1000 * 2 ** attempt, 15000);
      attempt += 1;
      timer = setTimeout(() => void connect(), delay);
    }

    async function connect() {
      if (disposed) return;
      setStatus(attempt === 0 ? "connecting" : "retrying");
      let ticket: string;
      try {
        ticket = await fetchTicket();
      } catch {
        retry();
        return;
      }
      if (disposed) return;
      source = new EventSource(
        `${AEGIS_URL}/v1/aegis/events?ticket=${encodeURIComponent(ticket)}`,
      );
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
        retry();
      };
    }

    void connect();
    return () => {
      disposed = true;
      if (timer) clearTimeout(timer);
      source?.close();
    };
  }, []);

  return status;
}
