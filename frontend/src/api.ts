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
  created_at: string;
  source: string;
  image_base64: string;
  metadata: {
    user_prompt?: string;
    mode?: string;
    score?: number;
    plan?: { topic?: string; tone?: string; template_type?: string };
    template?: { name?: string };
  };
};

export type GenerateResponse = {
  request_id: string;
  id: string;
  image_base64: string;
  mime: string;
  metadata: FeedItemApi["metadata"] & {
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

export async function fetchFeed(limit = 30): Promise<FeedItemApi[]> {
  const res = await fetch(`${BASE}/feed?limit=${limit}`);
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

export async function generateMeme(prompt: string, mode: MemeMode): Promise<GenerateResponse> {
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
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<GenerateResponse>;
}

export function dataUrlFromBase64(b64: string, mime = "image/png"): string {
  return `data:${mime};base64,${b64}`;
}

export function formatTimeAgo(iso: string): string {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const sec = Math.floor((Date.now() - t) / 1000);
  if (sec < 45) return "just now";
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  return `${Math.floor(sec / 86400)}d ago`;
}

export function feedItemTitle(item: FeedItemApi): string {
  const p = item.metadata?.user_prompt?.trim();
  if (p) return p.length > 44 ? `${p.slice(0, 44)}…` : p;
  const topic = item.metadata?.plan?.topic;
  if (topic) return topic.length > 44 ? `${topic.slice(0, 44)}…` : topic;
  return "meme";
}
