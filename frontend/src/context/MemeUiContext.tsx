import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useNavigate } from "react-router-dom";
import {
  dataUrlFromBase64,
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
  loading: boolean;
  error: string | null;
  generate: () => Promise<void>;
  regenerate: () => Promise<void>;
  applyFeedItem: (item: FeedItemApi) => void;
  feedTick: number;
  bumpFeed: () => void;
  clearError: () => void;
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
  const [imageDataUrl, setImageDataUrl] = useState<string | null>(null);
  const [metaLine, setMetaLine] = useState("mode: personal • tone: — • template: — • —");
  const [lastMetadata, setLastMetadata] = useState<GenerateResponse["metadata"] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feedTick, setFeedTick] = useState(0);

  const bumpFeed = useCallback(() => setFeedTick((n) => n + 1), []);

  const runPipeline = useCallback(
    async (text: string, memeMode: MemeMode) => {
      const t0 = performance.now();
      const data = await generateMeme(text, memeMode);
      const secs = ((performance.now() - t0) / 1000).toFixed(1);
      setImageDataUrl(dataUrlFromBase64(data.image_base64, data.mime));
      setMetaLine(buildMetaLine(data, secs));
      setLastMetadata(data.metadata ?? null);
      bumpFeed();
    },
    [bumpFeed],
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
      setImageDataUrl(dataUrlFromBase64(item.image_base64));
      const tone = item.metadata?.plan?.tone ?? "—";
      const tpl = item.metadata?.template?.name ?? "—";
      const m = item.metadata?.mode ?? "personal";
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
      loading,
      error,
      generate,
      regenerate,
      applyFeedItem,
      feedTick,
      bumpFeed,
      clearError,
    }),
    [
      imageDataUrl,
      metaLine,
      lastMetadata,
      prompt,
      mode,
      loading,
      error,
      generate,
      regenerate,
      applyFeedItem,
      feedTick,
      bumpFeed,
      clearError,
    ],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useMemeUi() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useMemeUi outside MemeUiProvider");
  return v;
}
