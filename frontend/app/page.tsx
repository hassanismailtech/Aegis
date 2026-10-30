"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowUpRight, Database, RefreshCw, ShieldCheck } from "lucide-react";

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
    <main className="telemetry-shell min-h-screen">
      <TopBar stats={displayedStats} connection={connection} />
      <div className="mx-auto max-w-[1440px] space-y-6 p-4 md:p-8">
        <section className="relative flex flex-col justify-between gap-5 overflow-hidden rounded-xl border border-white/10 bg-zinc-900/50 p-5 md:flex-row md:items-end md:p-6">
          <div aria-hidden="true" className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_88%_0%,rgba(6,182,212,0.12),transparent_28rem)]" />
          <div>
            <p className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.2em] text-cyan-300"><ShieldCheck className="size-3.5" /> Boundary activity</p>
            <h1 className="max-w-2xl text-3xl font-semibold tracking-tight text-white md:text-4xl">Know what your agent sends upstream.</h1>
            <p className="mt-3 max-w-xl text-sm leading-6 text-zinc-400">A live view of scrubbed traffic, entity detection and the exact post-scrub messages received by your Upstream.</p>
          </div>
          <a className="inline-flex items-center gap-1.5 text-sm text-cyan-300 transition-colors hover:text-cyan-200" href="https://github.com/hassanismailtech/Aegis" target="_blank" rel="noreferrer">View source <ArrowUpRight className="size-4" /></a>
        </section>
        {events.length === 0 && (
          <section className="flex flex-col items-start justify-between gap-5 rounded-xl border border-cyan-300/20 bg-cyan-300/[0.04] p-5 sm:flex-row sm:items-center">
            <div><p className="font-semibold">Waiting for traffic</p><p className="mt-1 max-w-xl text-sm text-muted-foreground">Connect an agent or seed synthetic telemetry to populate the control plane. Wire View never displays pre-scrub text.</p><code className="mt-3 block w-fit rounded-md border border-white/10 bg-black/30 px-2.5 py-1.5 font-mono text-xs text-cyan-200">python demo/agent.py</code></div>
            <Button onClick={seed} disabled={seeding}><Database className="size-4" />{seeding ? "Seeding..." : "Seed demo data"}</Button>
          </section>
        )}
        <div className="dashboard-grid grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)]">
          <LiveFeed events={events} selectedId={selected?.request_id ?? null} onSelect={setSelected} />
          <EntityChart stats={displayedStats} />
        </div>
        <WireView key={selected?.request_id ?? "empty"} event={selected} />
        <div className="flex items-center justify-between border-t border-white/10 pt-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5"><ShieldCheck className="size-3.5 text-emerald-300" />Post-scrub telemetry only</span>
          <Button variant="ghost" size="sm" onClick={refreshStats}><RefreshCw className="size-3" />Refresh</Button>
        </div>
      </div>
    </main>
  );
}
