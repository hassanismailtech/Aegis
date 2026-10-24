"use client";

import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { ENTITY_TYPES, type Stats } from "@/lib/types";

const chartConfig = {
  count: { label: "Entities", color: "var(--color-cyan-400)" },
} satisfies ChartConfig;

export function EntityChart({ stats }: { stats: Stats }) {
  const data = ENTITY_TYPES.map((type) => ({ type, count: stats.entities[type] }));
  return (
    <Card>
      <CardHeader><CardTitle className="text-sm">Entities by type</CardTitle></CardHeader>
      <CardContent>
        <ChartContainer config={chartConfig} className="h-[250px] w-full">
          <BarChart data={data} margin={{ left: -20, right: 8, top: 8 }}>
            <CartesianGrid vertical={false} strokeDasharray="3 3" />
            <XAxis dataKey="type" tickLine={false} axisLine={false} tickMargin={8} />
            <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
            <ChartTooltip cursor={false} content={<ChartTooltipContent />} />
            <Bar dataKey="count" fill="var(--color-count)" radius={4} />
          </BarChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
