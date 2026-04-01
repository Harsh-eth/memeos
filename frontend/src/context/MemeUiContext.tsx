import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useNavigate } from "react-router-dom";
import {
  dataUrlFromBase64,
  feedItemImageSrc,
  generateMeme,
  type FeedItemApi,
  type GenerateResponse,
  type MemeMode,
} from "../api";

export type { MemeMode };

export const MEME_MODES: MemeMode[] = ["personal", "roast", "decision"];

type MemeUiContextValue = {
  imageDataUrl: string | null;
  metaLine: string;
  lastMetadata: GenerateResponse["metadata"] | null;
  prompt: string;
  setPrompt: (v: string) => void;
  mode: MemeMode;
  setMode: (m: MemeMode) => void;
  captionEnabled: boolean;
  setCaptionEnabled: (v: boolean) => void;
  loading: boolean;
  error: string | null;
  generate: () => Promise<void>;
  regenerate: () => Promise<void>;
  applyFeedItem: (item: FeedItemApi) => void;
  feedTick: number;
  bumpFeed: () => void;
  clearError: () => void;
  toast: string | null;
  showToast: (msg: string) => void;
  totalGenerated: number;
};

const Ctx = createContext<MemeUiContextValue | null>(null);

const DEFAULT_PROMPT = "";

function buildMetaLine(data: GenerateResponse, seconds: string): string {
  const tone = data.metadata?.reasoning?.tone ?? data.metadata?.plan?.tone ?? "—";
  const tpl =
    data.metadata?.reasoning?.chosen_template ??
    data.metadata?.template?.name ??
    "—";
  const m = data.metadata?.mode ?? data.metadata?.reasoning?.mode ?? "—";
  const sc = data.metadata?.score ?? data.metadata?.reasoning?.score;
  const scoreBit = typeof sc === "number" ? `score: ${sc} • ` : "";
  return `mode: ${m} • ${scoreBit}tone: ${tone} • template: ${tpl} • ${seconds}s`;
}

export function MemeUiProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [mode, setMode] = useState<MemeMode>("personal");
  const [captionEnabled, setCaptionEnabled] = useState<boolean>(() => {
    const raw = window.localStorage.getItem("memeos_caption_enabled");
    if (raw === "0") return false;
    if (raw === "1") return true;
    return true;
  });
  const [imageDataUrl, setImageDataUrl] = useState<string | null>(null);
  const [metaLine, setMetaLine] = useState("mode: personal • tone: — • template: — • —");
  const [lastMetadata, setLastMetadata] = useState<GenerateResponse["metadata"] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feedTick, setFeedTick] = useState(0);
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<number | null>(null);
  const [totalGenerated, setTotalGenerated] = useState<number>(() => {
    const raw = window.localStorage.getItem("memeos_total_generated");
    const n = raw ? Number(raw) : 0;
    return Number.isFinite(n) && n >= 0 ? Math.floor(n) : 0;
  });
  const sessionGeneratedRef = useRef<number>(0);

  const bumpFeed = useCallback(() => setFeedTick((n) => n + 1), []);

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    if (toastTimer.current) window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 1200);
  }, []);

  const runPipeline = useCallback(
    async (text: string, memeMode: MemeMode) => {
      const t0 = performance.now();
      const data = await generateMeme(text, memeMode, captionEnabled);
      const secs = ((performance.now() - t0) / 1000).toFixed(1);
      setImageDataUrl(dataUrlFromBase64(data.image_base64, data.mime));
      setMetaLine(buildMetaLine(data, secs));
      setLastMetadata(data.metadata ?? null);
      bumpFeed();
      window.localStorage.setItem("memeos_last_mode", memeMode);
      window.localStorage.setItem("memeos_caption_enabled", captionEnabled ? "1" : "0");

      // Counts + achievements
      const nextTotal = totalGenerated + 1;
      window.localStorage.setItem("memeos_total_generated", String(nextTotal));
      setTotalGenerated(nextTotal);
      sessionGeneratedRef.current += 1;

      if (nextTotal === 1) showToast("you started");
      else if (nextTotal === 5) showToast("you’re cooking");
      else if (nextTotal === 20) showToast("certified memer");

      // Session nudge (2–3 memes)
      if (sessionGeneratedRef.current === 2) {
        showToast(memeMode === "roast" ? "try decision version" : "try a roast version");
      } else if (sessionGeneratedRef.current === 3) {
        showToast("this would hit harder as roast");
      }

      const variants = ["that one hit", "post-worthy", "this is good", "saved in your brain"] as const;
      showToast(variants[Math.floor(Math.random() * variants.length)]);
    },
    [bumpFeed, captionEnabled, showToast, totalGenerated],
  );

  const generate = useCallback(async () => {
    const p = prompt.trim();
    if (!p) return;
    setLoading(true);
    setError(null);
    try {
      await runPipeline(p, mode);
    } catch (e) {
      setError(e instanceof Error ? e.message : "generate failed");
    } finally {
      setLoading(false);
    }
  }, [prompt, mode, runPipeline]);

  const regenerate = useCallback(async () => {
    const p = prompt.trim();
    if (!p) return;
    setLoading(true);
    setError(null);
    try {
      await runPipeline(p, mode);
    } catch (e) {
      setError(e instanceof Error ? e.message : "regenerate failed");
    } finally {
      setLoading(false);
    }
  }, [prompt, mode, runPipeline]);

  const applyFeedItem = useCallback(
    (item: FeedItemApi) => {
      const src = feedItemImageSrc(item);
      if (src) setImageDataUrl(src);
      const tone = item.metadata?.plan?.tone ?? "—";
      const tpl = item.metadata?.template?.name ?? "—";
      const m = item.mode ?? item.metadata?.mode ?? "personal";
      setMetaLine(`mode: ${m} • tone: ${tone} • template: ${tpl} • feed`);
      const up = item.metadata?.user_prompt;
      if (up) setPrompt(up);
      navigate("/workspace");
    },
    [navigate],
  );

  const clearError = useCallback(() => setError(null), []);

  const value = useMemo(
    () => ({
      imageDataUrl,
      metaLine,
      lastMetadata,
      prompt,
      setPrompt,
      mode,
      setMode,
      captionEnabled,
      setCaptionEnabled,
      loading,
      error,
      generate,
      regenerate,
      applyFeedItem,
      feedTick,
      bumpFeed,
      clearError,
      toast,
      showToast,
      totalGenerated,
    }),
    [
      imageDataUrl,
      metaLine,
      lastMetadata,
      prompt,
      mode,
      captionEnabled,
      loading,
      error,
      generate,
      regenerate,
      applyFeedItem,
      feedTick,
      bumpFeed,
      clearError,
      toast,
      showToast,
      totalGenerated,
    ],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useMemeUi() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useMemeUi outside MemeUiProvider");
  return v;
}
