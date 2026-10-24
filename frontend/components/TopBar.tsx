"use client";

import { ShieldCheck, Wifi, WifiOff } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { Stats } from "@/lib/types";
import type { ConnectionStatus } from "@/lib/useEventSource";

type TopBarProps = {
  stats: Stats;
  connection: ConnectionStatus;
};

export function TopBar({ stats, connection }: TopBarProps) {
  const leakLabel = stats.leaks
    ? `${stats.leaks.leaks} / ${stats.leaks.planted}`
    : "not run";

  return (
    <header className="border-b border-white/10 bg-black/30 px-4 py-4 backdrop-blur md:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-xl bg-cyan-400/10 text-cyan-300 ring-1 ring-cyan-300/30">
            <ShieldCheck className="size-5" />
          </div>
          <div>
            <p className="text-lg font-semibold tracking-tight">Aegis</p>
            <p className="text-xs text-muted-foreground">PII proxy control plane</p>
          </div>
          <Badge variant={connection === "live" ? "default" : "outline"} className="ml-2 gap-1.5">
            {connection === "live" ? <Wifi className="size-3" /> : <WifiOff className="size-3" />}
            {connection === "live" ? "LIVE" : connection.toUpperCase()}
          </Badge>
        </div>
        <div className="grid grid-cols-2 gap-x-6 gap-y-3 text-xs sm:grid-cols-5">
          <Metric label="Entities scrubbed" value={stats.entities_total.toLocaleString()} />
          <Metric label="Requests" value={stats.requests.toLocaleString()} />
          <Metric label="Overhead p50 / p95" value={`${stats.overhead_ms_p50} / ${stats.overhead_ms_p95} ms`} />
          <Metric label="Metered fee" value={`$${stats.fee_usd.toFixed(6)}`} />
          <Metric label="Leaks" value={leakLabel} danger={Boolean(stats.leaks?.leaks)} />
        </div>
      </div>
    </header>
  );
}

function Metric({ label, value, danger = false }: { label: string; value: string; danger?: boolean }) {
  return (
    <div>
      <p className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">{label}</p>
      <p className={`mt-1 font-mono text-sm font-semibold ${danger ? "text-red-400" : "text-foreground"}`}>{value}</p>
    </div>
  );
}
