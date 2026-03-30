import type { FeedItemApi, GenerateResponse } from "../api";
import { MEME_PREVIEW_H, MEME_PREVIEW_W, LANDING_MATRIX_SEED } from "../constants/memeCanvas";
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

  return (
    <div className="ws-output">
      {showHit ? (
        <p className="ws-hit-badge" role="status">
          this one hits 😬
        </p>
      ) : null}
      <div className="ws-frame">
        {imageSrc ? (
          <img
            src={imageSrc}
            alt="Generated meme"
            className="ws-meme-img ws-meme-img--in"
          />
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
