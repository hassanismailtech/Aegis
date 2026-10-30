"use client";

import { Bar, BarChart, CartesianGrid, Cell, XAxis, YAxis } from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { ENTITY_TYPES, type Stats } from "@/lib/types";

const chartConfig = {
  count: { label: "Entities", color: "var(--color-cyan-400)" },
} satisfies ChartConfig;

const colors = ["#22d3ee", "#a78bfa", "#34d399", "#fbbf24", "#fb7185", "#60a5fa"];

export function EntityChart({ stats }: { stats: Stats }) {
  const data = ENTITY_TYPES.map((type) => ({ type, count: stats.entities[type] }));
  return (
    <Card className="panel-surface">
      <CardHeader>
        <CardTitle className="flex items-center justify-between text-sm">Entities by type <span className="text-xs font-normal text-muted-foreground">all observed</span></CardTitle>
      </CardHeader>
      <CardContent>
        <ChartContainer config={chartConfig} className="h-[250px] w-full">
          <BarChart data={data} margin={{ left: -20, right: 8, top: 8 }}>
            <CartesianGrid vertical={false} strokeDasharray="3 3" />
            <XAxis dataKey="type" tickLine={false} axisLine={false} tickMargin={8} />
            <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
            <ChartTooltip cursor={false} content={<ChartTooltipContent />} />
            <Bar dataKey="count" radius={4}>
              {data.map((entry, index) => <Cell key={entry.type} fill={colors[index]} />)}
            </Bar>
          </BarChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
