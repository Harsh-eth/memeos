import { useEffect, useState } from "react";
import { MEME_MODES, useMemeUi, type MemeMode } from "../context/MemeUiContext";
import { OutputPanel } from "../components/OutputPanel";

const PLACEHOLDERS = [
  "i keep buying tops",
  "should i long btc now",
  "lost money again",
] as const;

function modeLabel(m: MemeMode): string {
  if (m === "personal") return "Personal";
  if (m === "roast") return "Roast";
  return "Decision";
}

export function WorkspacePage() {
  const {
    prompt,
    setPrompt,
    mode,
    setMode,
    captionEnabled,
    setCaptionEnabled,
    generate,
    regenerate,
    imageDataUrl,
    metaLine,
    lastMetadata,
    loading,
    error,
    clearError,
  } = useMemeUi();

  const [showDetails, setShowDetails] = useState(false);
  const [phIdx, setPhIdx] = useState(0);

  useEffect(() => {
    const id = window.setInterval(
      () => setPhIdx((i) => (i + 1) % PLACEHOLDERS.length),
      3500,
    );
    return () => window.clearInterval(id);
  }, []);

  const download = () => {
    if (!imageDataUrl) return;
    const a = document.createElement("a");
    a.href = imageDataUrl;
    a.download = "meme.png";
    a.click();
  };

  const memeScoreFromMeta =
    typeof lastMetadata?.score === "number"
      ? lastMetadata.score
      : typeof lastMetadata?.reasoning?.score === "number"
        ? lastMetadata.reasoning.score
        : null;

  return (
    <main className="ws-page">
      <div className="ws-inner">
        <div className="ws-card">
          <div className="ws-modes" role="group" aria-label="Meme mode">
            {MEME_MODES.map((m) => (
              <button
                key={m}
                type="button"
                className={`ws-mode-btn${mode === m ? " ws-mode-btn--active" : ""}`}
                onClick={() => {
                  clearError();
                  setMode(m);
                }}
              >
                {modeLabel(m)}
              </button>
            ))}
          </div>

          <label className="ws-label" htmlFor="meme-prompt">
            Prompt
          </label>
          <textarea
            id="meme-prompt"
            className="ws-textarea"
            value={prompt}
            onChange={(e) => {
              clearError();
              setPrompt(e.target.value);
            }}
            placeholder={PLACEHOLDERS[phIdx]}
            spellCheck={false}
            disabled={loading}
            rows={5}
          />

          <div className="ws-row" style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 10 }}>
            <span className="ws-label" style={{ margin: 0 }}>
              captions
            </span>
            <button
              type="button"
              className={`ws-mode-btn${captionEnabled ? " ws-mode-btn--active" : ""}`}
              onClick={() => setCaptionEnabled(true)}
              disabled={loading}
            >
              on
            </button>
            <button
              type="button"
              className={`ws-mode-btn${!captionEnabled ? " ws-mode-btn--active" : ""}`}
              onClick={() => setCaptionEnabled(false)}
              disabled={loading}
            >
              off
            </button>
          </div>

          <button
            type="button"
            className="ws-generate"
            onClick={() => void generate()}
            disabled={loading || !prompt.trim()}
          >
            {loading ? "Generating…" : "Generate"}
          </button>
        </div>

        {error ? <p className="ws-err">{error}</p> : null}

        <div className="ws-out">
          <OutputPanel
            visible
            imageSrc={imageDataUrl}
            metaLine={metaLine}
            memeScore={memeScoreFromMeta}
            detailsMeta={lastMetadata}
            onRegenerate={() => void regenerate()}
            onDownload={download}
            loading={loading}
            showDetails={showDetails}
            onToggleDetails={() => setShowDetails((v) => !v)}
          />
        </div>
      </div>
    </main>
  );
}
