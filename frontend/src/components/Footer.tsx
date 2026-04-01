import { useEffect, useState } from "react";
import { fetchStats } from "../api";

const TWITTER_URL = "https://x.com/0xharsh";

type FooterProps = {
  className?: string;
  /** Bumps when feed/workspace generates so we refetch server total */
  feedTick: number;
};

export function Footer({ className, feedTick }: FooterProps) {
  const [totalMemes, setTotalMemes] = useState<number | null>(null);

  useEffect(() => {
    let alive = true;
    fetchStats()
      .then((s) => {
        if (alive) setTotalMemes(s.total_memes_generated);
      })
      .catch(() => {
        if (alive) setTotalMemes(null);
      });
    return () => {
      alive = false;
    };
  }, [feedTick]);

  return (
    <footer className={className ? `ref-footer ${className}` : "ref-footer"}>
      <div className="ref-footer__left" role="status" aria-live="polite">
        {totalMemes !== null ? (
          <>
            <span className="ref-footer__stat-num">{totalMemes.toLocaleString()}</span>
            <span className="ref-footer__stat-copy"> memes generated</span>
          </>
        ) : (
          <span className="ref-footer__stat-unavail">count unavailable</span>
        )}
      </div>
      <div className="ref-footer__center" aria-hidden="true">
        ♥
      </div>
      <p className="ref-footer__right">
        built by {" "}
        <a
          href={TWITTER_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="ref-footer__mono"
        >
          0xharsh
        </a>
      </p>
    </footer>
  );
}
