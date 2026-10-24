"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Database, RefreshCw } from "lucide-react";

import { EntityChart } from "@/components/EntityChart";
import { LiveFeed } from "@/components/LiveFeed";
import { TopBar } from "@/components/TopBar";
import { WireView } from "@/components/WireView";
import { Button } from "@/components/ui/button";
import { fetchStats, seedDemoData } from "@/lib/api";
import { useEventSource } from "@/lib/useEventSource";
import type { Stats, TelemetryEvent } from "@/lib/types";

const emptyStats: Stats = {
  requests: 0,
  entities_total: 0,
  entities: { PERSON: 0, PHONE: 0, BVN: 0, NIN: 0, ACCOUNT_NO: 0, EMAIL: 0 },
  state_loss: 0,
  overhead_ms_p50: 0,
  overhead_ms_p95: 0,
  fee_usd: 0,
  leaks: null,
};

export default function Home() {
  const [stats, setStats] = useState<Stats>(emptyStats);
  const [events, setEvents] = useState<TelemetryEvent[]>([]);
  const [selected, setSelected] = useState<TelemetryEvent | null>(null);
  const [seeding, setSeeding] = useState(false);

  const refreshStats = useCallback(() => {
    fetchStats().then(setStats).catch(() => undefined);
  }, []);
  const onEvent = useCallback((event: TelemetryEvent) => {
    setEvents((current) => [event, ...current.filter((item) => item.request_id !== event.request_id)].slice(0, 100));
    setStats((current) => ({ ...current, requests: current.requests + 1, entities_total: current.entities_total + event.entities_total }));
  }, []);
  const connection = useEventSource(onEvent);

  useEffect(() => {
    refreshStats();
    const timer = window.setInterval(refreshStats, 5000);
    return () => window.clearInterval(timer);
  }, [refreshStats]);

  const displayedStats = useMemo(() => stats, [stats]);
  async function seed() {
    setSeeding(true);
    try {
      const result = await seedDemoData();
      setEvents((current) => [...result.events.reverse(), ...current].slice(0, 100));
      refreshStats();
    } finally {
      setSeeding(false);
    }
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_right,rgba(8,145,178,0.13),transparent_35%)]">
      <TopBar stats={displayedStats} connection={connection} />
      <div className="mx-auto max-w-7xl space-y-5 p-4 md:p-8">
        {events.length === 0 && (
          <section className="flex flex-col items-start justify-between gap-4 rounded-xl border border-dashed border-cyan-300/30 bg-cyan-300/5 p-5 sm:flex-row sm:items-center">
            <div><p className="font-semibold">Waiting for traffic</p><p className="mt-1 text-sm text-muted-foreground">Connect an agent or seed synthetic telemetry to populate the control plane.</p></div>
            <Button onClick={seed} disabled={seeding}><Database className="size-4" />{seeding ? "Seeding..." : "Seed demo data"}</Button>
          </section>
        )}
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)]">
          <LiveFeed events={events} selectedId={selected?.request_id ?? null} onSelect={setSelected} />
          <EntityChart stats={displayedStats} />
        </div>
        <WireView event={selected} />
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Redis-backed telemetry · no pre-scrub text displayed</span>
          <Button variant="ghost" size="sm" onClick={refreshStats}><RefreshCw className="size-3" />Refresh</Button>
        </div>
      </div>
    </main>
  );
}
