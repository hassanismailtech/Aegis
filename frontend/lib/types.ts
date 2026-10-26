/** Wire contracts mirrored from backend/app/schemas.py (PRD 7.3). */

export const ENTITY_TYPES = [
  "PERSON",
  "PHONE",
  "BVN",
  "NIN",
  "ACCOUNT_NO",
  "EMAIL",
] as const;

export type EntityType = (typeof ENTITY_TYPES)[number];

export type TelemetryStatus =
  | "ok"
  | "state_loss"
  | "scrub_blocked"
  | "upstream_error";

/** Exactly the Telemetry Event in PRD 7.3: counts, ids and timings only. */
export interface TelemetryEvent {
  request_id: string;
  ts: string;
  session: string;
  model: string;
  stream_requested: boolean;
  entities: Record<EntityType, number>;
  entities_total: number;
  scrub_ms: number;
  reinject_ms: number;
  upstream_ms: number;
  overhead_ms: number;
  unresolved: number;
  status: TelemetryStatus;
  fee_usd: number;
}

/** GET /v1/aegis/stats (backend/app/telemetry.py). */
export interface Stats {
  requests: number;
  entities_total: number;
  entities: Record<EntityType, number>;
  state_loss: number;
  overhead_ms_p50: number;
  overhead_ms_p95: number;
  fee_usd: number;
  leaks: LeakTestResult | null;
}

/** Redis key aegis:leaktest, written by `pytest --report`. */
export interface LeakTestResult {
  leaks: number;
  planted: number;
  ts: string;
}

export interface WireTapToolCall {
  id?: string;
  type?: string;
  function?: {
    name?: string;
    arguments?: string;
  };
}

export interface WireTapMessage {
  role: string;
  content?: string | Array<{ type?: string; text?: string }> | null;
  tool_calls?: WireTapToolCall[];
  tool_call_id?: string;
}

/** GET /v1/aegis/wiretap/{request_id}: exact post-scrub outbound body. */
export interface WireTap {
  model: string;
  messages: WireTapMessage[];
  stream?: boolean;
  [key: string]: unknown;
}

export interface SeedResponse {
  seeded: number;
  events: TelemetryEvent[];
}

/** POST /v1/aegis/ticket: short-lived signed ticket for the SSE feed. */
export interface TicketResponse {
  ticket: string;
  expires_in: number;
}
