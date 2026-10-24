import type { SeedResponse, Stats, WireTap } from "@/lib/types";

export const AEGIS_URL = (
  process.env.NEXT_PUBLIC_AEGIS_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${AEGIS_URL}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Aegis ${path} returned ${response.status}`);
  }
  return (await response.json()) as T;
}

export function fetchStats(): Promise<Stats> {
  return getJson<Stats>("/v1/aegis/stats");
}

export function fetchWireTap(requestId: string): Promise<WireTap> {
  return getJson<WireTap>(
    `/v1/aegis/wiretap/${encodeURIComponent(requestId)}`,
  );
}

export async function seedDemoData(): Promise<SeedResponse> {
  const response = await fetch(`${AEGIS_URL}/v1/aegis/_seed`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Aegis seed returned ${response.status}`);
  }
  return (await response.json()) as SeedResponse;
}
