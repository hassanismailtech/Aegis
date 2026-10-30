"use client";

import { Activity, AlertTriangle, CheckCircle2, Clock3, ShieldAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { TelemetryEvent } from "@/lib/types";

export function LiveFeed({
  events,
  selectedId,
  onSelect,
}: {
  events: TelemetryEvent[];
  selectedId: string | null;
  onSelect: (event: TelemetryEvent) => void;
}) {
  return (
    <Card className="panel-surface min-h-[480px]">
      <CardHeader className="border-b border-white/10">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Activity className="size-4 text-cyan-300" /> Live feed
          <span className="ml-auto font-mono text-xs font-normal text-muted-foreground">{events.length} shown</span>
        </CardTitle>
        <p className="text-xs text-muted-foreground">Select a request to inspect its post-scrub outbound messages.</p>
      </CardHeader>
      <CardContent className="p-0">
        {events.length === 0 ? (
          <div className="flex min-h-[400px] items-center justify-center px-6 text-center text-sm text-muted-foreground">
            Waiting for traffic
          </div>
        ) : (
          <ScrollArea className="h-[430px]">
            <div className="divide-y divide-white/5">
              {events.map((event) => (
                <button
                  key={event.request_id}
                  type="button"
                  onClick={() => onSelect(event)}
                  className={`w-full border-l-2 px-4 py-3 text-left transition-colors duration-150 ease-in-out hover:bg-white/[0.04] ${selectedId === event.request_id ? "border-cyan-300 bg-cyan-300/[0.07]" : "border-transparent"}`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="flex min-w-0 items-center gap-2 font-mono text-xs text-cyan-200"><StatusIcon status={event.status} /><span className="truncate">{event.request_id}</span></span>
                    <Badge variant={event.status === "ok" ? "outline" : "destructive"} className="capitalize">{event.status.replace("_", " ")}</Badge>
                  </div>
                  <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
                    <span className="font-medium text-zinc-300">{event.model}</span>
                    <span>{event.entities_total} entities</span>
                    <span>{event.overhead_ms.toFixed(1)} ms</span>
                    <span className="ml-auto flex items-center gap-1"><Clock3 className="size-3" />{event.ts.slice(11, 19)}</span>
                  </div>
                </button>
              ))}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  );
}

function StatusIcon({ status }: { status: TelemetryEvent["status"] }) {
  if (status === "ok") return <CheckCircle2 className="size-3.5 text-emerald-300" />;
  if (status === "state_loss") return <ShieldAlert className="size-3.5 text-amber-300" />;
  return <AlertTriangle className="size-3.5 text-rose-300" />;
}
