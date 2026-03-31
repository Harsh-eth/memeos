import type { FeedItemApi, GenerateResponse } from "../api";
import { MEME_PREVIEW_H, MEME_PREVIEW_W, LANDING_MATRIX_SEED } from "../constants/memeCanvas";
import { layoutText } from "../lib/textLayout";
import { MatrixPreview } from "./MatrixPreview";

type OutputPanelProps = {
  visible: boolean;
  imageSrc: string | null;
  metaLine: string;
  /** Meme quality score 1–10 from API; shows praise line when ≥ 8 */
  memeScore?: number | null;
  detailsMeta?: GenerateResponse["metadata"] | FeedItemApi["metadata"] | null;
  onRegenerate: () => void;
  onDownload: () => void;
  loading?: boolean;
  showDetails?: boolean;
  onToggleDetails?: () => void;
};

function CaptionLines({
  text,
  width,
}: {
  text: string;
  width: number;
}) {
  const t = (text || "").trim();
  if (!t) return null;

  const maxWidth = Math.max(120, width - 40);
  const fontSizes = [32, 28, 24] as const;

  let chosen = layoutText(t, `bold ${fontSizes[0]}px Impact`, maxWidth, 36);
  for (const px of fontSizes) {
    const r = layoutText(t, `bold ${px}px Impact`, maxWidth, 36);
    // Prefer fewer lines when possible; keep first that is <= 2 lines.
    if (Array.isArray(r?.lines) && r.lines.length <= 2) {
      chosen = r;
      break;
    }
    chosen = r;
  }

  return (
    <div className="ws-cap">
      {(Array.isArray(chosen?.lines) ? chosen.lines : []).map(
        (line: { text: string }, i: number) => (
          <div key={i} className="ws-cap__line">
            {line.text}
          </div>
        ),
      )}
    </div>
  );
}

export function OutputPanel({
  visible,
  imageSrc,
  metaLine,
  memeScore,
  detailsMeta,
  onRegenerate,
  onDownload,
  loading,
  showDetails,
  onToggleDetails,
}: OutputPanelProps) {
  if (!visible) return null;

  const showHit =
    typeof memeScore === "number" && memeScore >= 8 && Boolean(imageSrc);

  const captions = (detailsMeta as any)?.captions as
    | { top_text?: string; bottom_text?: string }
    | undefined;
  const top = captions?.top_text ?? "";
  const bottom = captions?.bottom_text ?? "";

  return (
    <div className="ws-output">
      {showHit ? (
        <p className="ws-hit-badge" role="status">
          this one hits 😬
        </p>
      ) : null}
      <div className="ws-frame">
        {imageSrc ? (
          <div className="ws-frame__stack">
            <img
              src={imageSrc}
              alt="Generated meme"
              className="ws-meme-img ws-meme-img--in"
            />
            <div className="ws-frame__overlay" aria-hidden="true">
              <div className="ws-frame__top">
                <CaptionLines text={top} width={MEME_PREVIEW_W} />
              </div>
              <div className="ws-frame__bottom">
                <CaptionLines text={bottom} width={MEME_PREVIEW_W} />
              </div>
            </div>
          </div>
        ) : (
          <div className="ws-preview-wrap">
            {loading ? (
              <div className="ws-skeleton" aria-busy="true" aria-live="polite" />
            ) : (
              <div className="ws-meme-matrix-wrap">
                <MatrixPreview
                  width={MEME_PREVIEW_W}
                  height={MEME_PREVIEW_H}
                  seed={LANDING_MATRIX_SEED}
                  className="ref-meme-matrix-canvas"
                />
              </div>
            )}
          </div>
        )}
      </div>

      <p className="ws-meta">{metaLine}</p>

      {onToggleDetails ? (
        <button type="button" className="ws-details-toggle" onClick={onToggleDetails}>
          {showDetails ? "Hide details" : "Show details"}
        </button>
      ) : null}

      {showDetails && detailsMeta ? (
        <pre className="ws-details">{JSON.stringify(detailsMeta, null, 2)}</pre>
      ) : null}

      <div className="ws-actions">
        <button type="button" className="ws-action" onClick={onRegenerate} disabled={loading}>
          Regenerate
        </button>
        <button type="button" className="ws-action" onClick={onDownload} disabled={!imageSrc}>
          Download .png
        </button>
      </div>
    </div>
  );
}
