import { NavLink } from "react-router-dom";
import { MEME_PREVIEW_H, MEME_PREVIEW_W, LANDING_MATRIX_SEED } from "../constants/memeCanvas";
import { MatrixPreview } from "../components/MatrixPreview";

const MEMEOS_BUY_URL = "https://jup.ag/tokens/FzoyNVEaSavbTHzidJgmBa3EQZ4AFvARhr3rPm9vBAGS";

export function LandingPage() {
  return (
    <main className="ref-main ref-landing">
      <p className="ref-landing__kicker">memeos</p>
      <p className="ref-landing__tagline">agent-driven meme generation</p>
      <div className="ref-meme-frame ref-landing__frame">
        <div className="ref-meme-matrix-wrap ref-meme-matrix-wrap--landing">
          <MatrixPreview
            width={MEME_PREVIEW_W}
            height={MEME_PREVIEW_H}
            seed={LANDING_MATRIX_SEED}
            className="ref-meme-matrix-canvas"
          />
        </div>
      </div>
      <p className="ref-meta ref-landing__meta">tone: intense • template: matrix code • preview</p>
      <div className="ref-actions">
        <NavLink to="/workspace" className="ref-action-btn ref-landing__cta">
          open workspace
        </NavLink>
      </div>

      <p className="ref-landing__buy">
        <a className="ref-buy__mono" href={MEMEOS_BUY_URL} target="_blank" rel="noopener noreferrer">
          buy memEOS
        </a>
      </p>
    </main>
  );
}
