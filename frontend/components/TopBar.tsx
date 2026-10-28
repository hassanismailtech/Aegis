"use client";

import { Activity, ArrowLeft, ShieldCheck, Wifi, WifiOff } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { Stats } from "@/lib/types";
import type { ConnectionStatus } from "@/lib/useEventSource";

type TopBarProps = {
  stats: Stats;
  connection: ConnectionStatus;
};

export function TopBar({ stats, connection }: TopBarProps) {
  const marketingUrl = process.env.NEXT_PUBLIC_MARKETING_URL;
  const leakLabel = stats.leaks
    ? `${stats.leaks.leaks} / ${stats.leaks.planted}`
    : "not run";

  return (
    <header className="border-b border-white/10 bg-zinc-950/75 px-4 py-4 backdrop-blur-xl md:px-8">
      <div className="mx-auto flex max-w-[1440px] flex-col gap-5">
        <div className="flex items-center gap-3">
          <div className="flex size-9 items-center justify-center rounded-lg bg-cyan-300 text-zinc-950 ring-1 ring-cyan-200/40">
            <ShieldCheck className="size-5" />
          </div>
          <div>
            <p className="text-base font-semibold tracking-tight">Aegis</p>
            <p className="text-[11px] text-muted-foreground">Data boundary control plane</p>
          </div>
          <Badge variant="outline" className="ml-2 gap-1.5 border-emerald-400/30 bg-emerald-400/5 text-emerald-300">
            {connection === "live" ? <Wifi className="size-3" /> : <WifiOff className="size-3" />}
            {connection === "live" ? "Telemetry live" : connection === "connecting" ? "Connecting" : "Reconnecting"}
          </Badge>
          <span className="hidden items-center gap-1.5 text-xs text-muted-foreground lg:flex"><Activity className="size-3.5" /> OpenAI-compatible proxy</span>
          {marketingUrl && <a href={marketingUrl} className="ml-auto hidden items-center gap-1.5 text-xs text-cyan-300 transition-colors duration-150 ease-in-out hover:text-cyan-200 md:inline-flex"><ArrowLeft className="size-3.5" /> Aegis site</a>}
        </div>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          <Metric label="Entities scrubbed" value={stats.entities_total.toLocaleString()} hint="all types" />
          <Metric label="Requests observed" value={stats.requests.toLocaleString()} hint="this instance" />
          <Metric label="Pipeline overhead" value={`${stats.overhead_ms_p50} ms`} hint={`p50 · ${stats.overhead_ms_p95} ms p95`} />
          <Metric label="Leak test" value={leakLabel} hint={stats.leaks ? `last run · ${stats.leaks.ts.slice(0, 10)}` : "not run · run it"} neutral={!stats.leaks} danger={Boolean(stats.leaks?.leaks)} />
        </div>
      </div>
    </header>
  );
}

function Metric({ label, value, hint, danger = false, neutral = false }: { label: string; value: string; hint: string; danger?: boolean; neutral?: boolean }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.025] px-3 py-2.5">
      <p className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">{label}</p>
      <p className={`mt-1 font-mono text-lg font-semibold tabular-nums ${danger ? "text-rose-300" : neutral ? "text-amber-200" : "text-foreground"}`}>{value}</p>
      <p className="mt-0.5 text-[11px] text-muted-foreground">{hint}</p>
    </div>
  );
}
