export const MAX_CHARS = 2000;
export const ENTITY_TYPES = ["PERSON", "PHONE", "BVN", "NIN", "ACCOUNT_NO", "EMAIL"] as const;
export const EXAMPLES = [
  { label: "Transfer", text: "Transfer 50000 naira to Chinedu Okafor from the Ojota branch. Reach him on 0803 123 4567; his BVN is 22334455667." },
  { label: "Identifier check", text: "Customer support ticket: Tunde Ajayi says his BVN is 18938412234 and his NIN 18938412256 needs verification; transfer 30000 pending." },
  { label: "Email request", text: "Forward the statement of account for Ngozi Eze to femi.balogun@gtbank.ng before branch close." },
] as const;

export type PlaygroundResult = {
  scrubbed: string;
  simulated_reply: string;
  counts: Record<(typeof ENTITY_TYPES)[number], number>;
  overhead_ms: number;
  mode: "full" | "lite";
};
export type PlaygroundResponse = { ok: true; result: PlaygroundResult } | { ok: false; message: string };

const UNAVAILABLE = "The playground is unavailable. Please try again later.";

export function playgroundEndpoint(base: string | undefined): string | null {
  if (!base?.trim()) return null;
  try {
    const url = new URL(base.trim());
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.search || url.hash) return null;
    url.pathname = `${url.pathname.replace(/\/+$/, "")}/v1/playground/scrub`;
    return url.href;
  } catch {
    return null;
  }
}

export function splitPlaceholders(text: string) {
  return text.split(/(\[\[(?:PERSON|PHONE|BVN|NIN|ACCOUNT_NO|EMAIL)_\d+\]\])/g)
    .map((text, index) => ({ text, placeholder: index % 2 === 1 }));
}

function readResult(value: unknown): PlaygroundResult | null {
  if (!value || typeof value !== "object") return null;
  const data = value as Record<string, unknown>;
  if (typeof data.scrubbed !== "string" || typeof data.simulated_reply !== "string" ||
      (data.mode !== "full" && data.mode !== "lite") ||
      typeof data.overhead_ms !== "number" || !Number.isFinite(data.overhead_ms) || data.overhead_ms < 0 ||
      !data.counts || typeof data.counts !== "object") return null;
  const source = data.counts as Record<string, unknown>;
  const counts = {} as PlaygroundResult["counts"];
  for (const type of ENTITY_TYPES) {
    const count = source[type];
    if (typeof count !== "number" || !Number.isSafeInteger(count) || count < 0) return null;
    counts[type] = count;
  }
  return { scrubbed: data.scrubbed, simulated_reply: data.simulated_reply, counts,
    overhead_ms: data.overhead_ms, mode: data.mode };
}

export async function scrubPlayground(base: string | undefined, text: string, signal: AbortSignal): Promise<PlaygroundResponse> {
  const endpoint = playgroundEndpoint(base);
  if (!endpoint) return { ok: false, message: UNAVAILABLE };
  if (!text.trim() || text.length > MAX_CHARS) return { ok: false, message: `Enter synthetic text up to ${MAX_CHARS} characters.` };
  try {
    const response = await fetch(endpoint, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }),
      cache: "no-store", credentials: "omit", redirect: "error", signal,
    });
    if (response.status === 429) {
      const retry = response.headers.get("Retry-After");
      const seconds = retry && /^\d+$/.test(retry) ? Number(retry) : 0;
      return { ok: false, message: Number.isSafeInteger(seconds) && seconds > 0 && seconds <= 60
        ? `Too many requests. Try again in ${seconds} seconds.` : "Too many requests. Please wait before trying again." };
    }
    if (response.status === 422) return { ok: false, message: "The input was rejected. Use a shorter synthetic example." };
    if (!response.ok) return { ok: false, message: UNAVAILABLE };
    const result = readResult(await response.json());
    return result ? { ok: true, result } : { ok: false, message: UNAVAILABLE };
  } catch {
    return { ok: false, message: UNAVAILABLE };
  }
}
