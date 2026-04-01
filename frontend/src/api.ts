const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

const CLIENT_TOKEN = import.meta.env.VITE_MEMEOS_CLIENT_TOKEN ?? "";

const HMAC_SECRET = import.meta.env.VITE_MEMEOS_HMAC_SECRET ?? "";

export type MemeMode = "personal" | "roast" | "decision";

async function hmacSha256Hex(secret: string, message: string): Promise<string> {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    enc.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(message));
  return Array.from(new Uint8Array(sig))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export type FeedItemApi = {
  id: string;
  created_at: string | number;
  source: string;
  image_base64?: string;
  image_url?: string;
  mode?: string;
  score?: number;
  captions?: { top_text?: string; bottom_text?: string };
  metadata?: {
    user_prompt?: string;
    mode?: string;
    score?: number;
    plan?: { topic?: string; tone?: string; template_type?: string };
    template?: { name?: string };
    captions?: { top_text?: string; bottom_text?: string };
  };
};

export type GenerateResponse = {
  request_id: string;
  id: string;
  image_base64: string;
  mime: string;
  metadata: NonNullable<FeedItemApi["metadata"]> & {
    reasoning?: {
      tone?: string;
      chosen_template?: string;
      mode?: string;
      scenario?: string;
      emotion?: string;
      score?: number;
    };
  };
  cached: boolean;
};

export type StatsResponse = {
  total_memes_generated: number;
};

export async function fetchStats(): Promise<StatsResponse> {
  const res = await fetch(`${BASE}/stats`);
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<StatsResponse>;
}

export async function fetchFeed(limit = 20, offset = 0): Promise<FeedItemApi[]> {
  const res = await fetch(`${BASE}/feed?limit=${limit}&offset=${offset}`);
  if (!res.ok) throw new Error(await res.text());
  const data = (await res.json()) as { items: FeedItemApi[] };
  return data.items ?? [];
}

export async function fetchTop(limit = 10): Promise<FeedItemApi[]> {
  const res = await fetch(`${BASE}/top?limit=${limit}`);
  if (!res.ok) throw new Error(await res.text());
  const data = (await res.json()) as { items: FeedItemApi[] };
  return data.items ?? [];
}

export async function fetchHistory(limit = 20, offset = 0, userId?: string): Promise<FeedItemApi[]> {
  const qp = new URLSearchParams();
  qp.set("limit", String(limit));
  qp.set("offset", String(offset));
  if (userId) qp.set("user_id", userId);
  const res = await fetch(`${BASE}/history?${qp.toString()}`);
  if (!res.ok) throw new Error(await res.text());
  const data = (await res.json()) as { items: FeedItemApi[] };
  return data.items ?? [];
}

/** Headers only the SPA sets — required by API for POST /generate-meme */
function generateHeaders(): HeadersInit {
  const h: Record<string, string> = {
    "Content-Type": "application/json",
    "X-MemeOS-Intent": "generate",
  };
  if (CLIENT_TOKEN) {
    h["X-MemeOS-Client-Token"] = CLIENT_TOKEN;
  }
  return h;
}

export async function generateMeme(
  prompt: string,
  mode: MemeMode,
  captionEnabled: boolean = true,
): Promise<GenerateResponse> {
  const trimmedPrompt = prompt.trim();
  if (!HMAC_SECRET) {
    throw new Error("VITE_MEMEOS_HMAC_SECRET is not set (must match backend MEMEOS_HMAC_SECRET)");
  }
  const timestamp = Math.floor(Date.now() / 1000);
  const signingPayload = `${trimmedPrompt}\n${mode}\n${timestamp}`;
  const signature = await hmacSha256Hex(HMAC_SECRET, signingPayload);

  const res = await fetch(`${BASE}/generate-meme`, {
    method: "POST",
    headers: generateHeaders(),
    body: JSON.stringify({
      prompt: trimmedPrompt,
      timestamp,
      signature,
      mode,
      caption_enabled: captionEnabled,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<GenerateResponse>;
}

export function dataUrlFromBase64(b64: string, mime = "image/png"): string {
  return `data:${mime};base64,${b64}`;
}

export function formatTimeAgo(value: string | number): string {
  const t =
    typeof value === "number"
      ? value * 1000
      : Number.isNaN(Date.parse(value))
        ? 0
        : Date.parse(value);
  if (!t) return "";
  const sec = Math.floor((Date.now() - t) / 1000);
  if (sec < 45) return "just now";
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  return `${Math.floor(sec / 86400)}d ago`;
}

function truncateAtWord(s: string, max: number): string {
  const t = s.trim();
  if (t.length <= max) return t;
  const slice = t.slice(0, max);
  const i = slice.lastIndexOf(" ");
  const cut = i > max * 0.45 ? slice.slice(0, i) : slice;
  return `${cut.trimEnd()}…`;
}

/** Dev / smoke-test prompts we should not show as the human-visible title */
function isInternalPrompt(p: string): boolean {
  const s = p.trim().toLowerCase();
  if (/^ui\s+feed\b/.test(s) || /^feed\s+smoke\b/.test(s) || /^smoke\s+test\b/.test(s)) return true;
  if (/\bseed\s+(personal|roast|decision)\b/.test(s) && /\d{10}/.test(s)) return true;
  return false;
}

/** Sidebar / list label: caption first, never raw image-description prompts when captions exist */
export function feedItemTitle(item: FeedItemApi): string {
  const caps = feedItemCaptions(item);
  const line = (caps.top || caps.bottom || "").trim();
  if (line) return truncateAtWord(line, 52);

  const p = item.metadata?.user_prompt?.trim();
  if (p && !isInternalPrompt(p)) return truncateAtWord(p, 48);

  const topic = item.metadata?.plan?.topic?.trim();
  if (topic) return truncateAtWord(topic, 48);

  return "Untitled";
}

export function feedItemImageSrc(item: FeedItemApi): string {
  if (item.image_base64) return dataUrlFromBase64(item.image_base64, "image/png");
  if (item.image_url) return `${BASE}${item.image_url}`;
  return "";
}

export function feedItemCaptions(item: FeedItemApi): { top: string; bottom: string } {
  const caps = item.captions ?? item.metadata?.captions ?? {};
  return {
    top: (caps.top_text ?? "").trim(),
    bottom: (caps.bottom_text ?? "").trim(),
  };
}
