"use client";

import { Activity, Clock3 } from "lucide-react";

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
    <Card className="min-h-[480px]">
      <CardHeader className="border-b border-white/10">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Activity className="size-4 text-cyan-300" /> Live feed
          <span className="ml-auto font-mono text-xs text-muted-foreground">{events.length} events</span>
        </CardTitle>
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
                  className={`w-full px-4 py-3 text-left transition-colors hover:bg-white/5 ${selectedId === event.request_id ? "bg-cyan-400/10" : ""}`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="truncate font-mono text-xs text-cyan-200">{event.request_id}</span>
                    <Badge variant={event.status === "ok" ? "default" : "destructive"}>{event.status}</Badge>
                  </div>
                  <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
                    <span>{event.entities_total} entities</span>
                    <span>{event.overhead_ms.toFixed(1)} ms overhead</span>
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
