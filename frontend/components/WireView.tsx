"use client";

import { useEffect, useState } from "react";
import { Cable, Check, Clipboard, LoaderCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { fetchWireTap } from "@/lib/api";
import type { TelemetryEvent, WireTap } from "@/lib/types";

export function WireView({ event }: { event: TelemetryEvent | null }) {
  const [wire, setWire] = useState<WireTap | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let active = true;
    if (!event) return () => { active = false; };
    fetchWireTap(event.request_id)
      .then((result) => { if (active) setWire(result); })
      .catch(() => { if (active) setError("Wire Tap unavailable for this request."); });
    return () => { active = false; };
  }, [event]);

  async function copyWire() {
    if (!wire) return;
    await navigator.clipboard.writeText(JSON.stringify(wire, null, 2));
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }

  return (
    <Card className="panel-surface">
      <CardHeader className="border-b border-white/10">
        <CardTitle className="flex items-center gap-2 text-sm"><Cable className="size-4 text-cyan-300" /> Wire View <span className="ml-auto text-xs font-normal text-muted-foreground">post-scrub only</span></CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {!event ? (
          <div className="flex h-[260px] items-center justify-center text-sm text-muted-foreground">Select an event to inspect its Wire Tap.</div>
        ) : error ? (
          <div className="p-5 text-sm text-red-300">{error}</div>
        ) : !wire ? (
          <div className="flex h-[260px] items-center justify-center text-muted-foreground"><LoaderCircle className="mr-2 size-4 animate-spin" />Loading Wire Tap</div>
        ) : (
          <ScrollArea className="h-[260px]">
            <div className="space-y-3 p-4">
              <div className="flex items-center gap-2"><Badge variant="outline">{wire.model}</Badge><span className="text-xs text-muted-foreground">exact outbound payload</span><Button className="ml-auto" variant="outline" size="sm" onClick={copyWire}>{copied ? <Check className="size-3.5" /> : <Clipboard className="size-3.5" />}{copied ? "Copied" : "Copy JSON"}</Button></div>
              {wire.messages.map((message, index) => (
                <div key={`${message.role}-${index}`} className="rounded-lg border border-white/10 bg-black/20 p-3">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">{message.role}</p>
                  <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed text-cyan-100">{JSON.stringify(message.content ?? message.tool_calls ?? null, null, 2)}</pre>
                </div>
              ))}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  );
}
