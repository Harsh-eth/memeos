import { useEffect, useMemo, useRef, useState } from "react";
import {
  fetchHistory,
  feedItemCaptions,
  feedItemImageSrc,
  formatTimeAgo,
  type FeedItemApi,
} from "../api";
import { useMemeUi } from "../context/MemeUiContext";

export function HistoryPage() {
  const { showToast } = useMemeUi();
  const [items, setItems] = useState<FeedItemApi[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);

  const loadingRef = useRef(false);

  const view = useMemo(() => {
    return items;
  }, [items]);

  const best = useMemo(() => {
    const scored = items
      .map((x) => ({
        item: x,
        score: typeof x.score === "number" ? x.score : typeof x.metadata?.score === "number" ? x.metadata.score : 0,
      }))
      .filter((x) => x.score > 0)
      .sort((a, b) => b.score - a.score);
    return scored.slice(0, 3).map((x) => x.item);
  }, [items]);

  function modeTagClass(m: string) {
    const s = (m || "").toLowerCase();
    if (s === "roast") return "sm-tag sm-tag--roast";
    if (s === "decision") return "sm-tag sm-tag--decision";
    return "sm-tag sm-tag--personal";
  }

  async function copyCaption(item: FeedItemApi) {
    const caps = feedItemCaptions(item);
    const text = `${caps.top}\n${caps.bottom}`.trim();
    try {
      await navigator.clipboard.writeText(text);
      showToast("copied");
    } catch {
      showToast("copy failed");
    }
  }

  async function downloadImage(item: FeedItemApi) {
    try {
      const src = feedItemImageSrc(item);
      const res = await fetch(src);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `meme_${item.id}.png`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      showToast("saved");
    } catch {
      showToast("save failed");
    }
  }

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setErr(null);
    setItems([]);
    setOffset(0);
    setHasMore(true);
    loadingRef.current = true;

    fetchHistory(20, 0)
      .then((list) => {
        if (!alive) return;
        setItems(list);
        setOffset(list.length);
        setHasMore(list.length >= 20);
      })
      .catch((e) => {
        if (!alive) return;
        setErr(e instanceof Error ? e.message : "failed to load history");
      })
      .finally(() => {
        if (!alive) return;
        setLoading(false);
        loadingRef.current = false;
      });

    return () => {
      alive = false;
    };
  }, []);

  async function loadMore() {
    if (!hasMore || loadingRef.current) return;
    loadingRef.current = true;
    setLoading(true);
    try {
      const next = await fetchHistory(20, offset);
      setItems((prev) => [...prev, ...next]);
      setOffset((n) => n + next.length);
      setHasMore(next.length >= 20);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "failed to load history");
    } finally {
      setLoading(false);
      loadingRef.current = false;
    }
  }

  return (
    <main className="sm-page">
      <div className="sm-shell">
        <h1 className="sm-title">History</h1>
        <p className="sm-subtitle">Your memes (newest first)</p>
        {err ? <p className="sm-err">{err}</p> : null}

        {best.length ? (
          <section className="sm-best">
            <h2 className="sm-h2 sm-h2--section">Your best</h2>
            <div className="sm-best__row">
              {best.map((item) => (
                <article key={item.id} className="sm-best__card">
                  <img src={feedItemImageSrc(item)} alt="" className="sm-best__img" loading="lazy" />
                  <div className="sm-best__score">{item.score ?? item.metadata?.score}</div>
                </article>
              ))}
            </div>
          </section>
        ) : null}

        <div className="sm-grid sm-grid--history">
          {view.map((item) => {
            const caps = feedItemCaptions(item);
            const m = item.mode ?? item.metadata?.mode ?? "personal";
            return (
              <article key={item.id} className="sm-card">
                <img
                  src={feedItemImageSrc(item)}
                  alt=""
                  className="sm-img"
                  loading="lazy"
                />
                <div className="sm-card__body">
                  <div className="sm-cap sm-cap--top">{caps.top || "—"}</div>
                  <div className="sm-cap sm-cap--bottom">{caps.bottom || ""}</div>
                  <div className="sm-actions">
                    <button
                      type="button"
                      className="sm-ic"
                      title="Copy caption"
                      onClick={() => void copyCaption(item)}
                    >
                      ⧉
                    </button>
                    <button
                      type="button"
                      className="sm-ic"
                      title="Download"
                      onClick={() => void downloadImage(item)}
                    >
                      ⤓
                    </button>
                    <button type="button" className="sm-ic sm-ic--off" title="Share (soon)">
                      ↗
                    </button>
                  </div>
                  <div className="sm-foot">
                    <span className={modeTagClass(m)}>{m}</span>
                    <span className="sm-time">{formatTimeAgo(item.created_at)}</span>
                  </div>
                </div>
              </article>
            );
          })}
        </div>

        <div className="sm-more">
          {loading ? <div className="sm-muted">loading…</div> : null}
          {!loading && hasMore ? (
            <button type="button" className="sm-btn" onClick={() => void loadMore()}>
              load more
            </button>
          ) : null}
          {!loading && !hasMore && items.length ? (
            <div className="sm-muted">end</div>
          ) : null}
          {!loading && !items.length && !err ? (
            <div className="sm-empty">
              <div className="sm-empty__title">You haven’t generated anything yet</div>
              <div className="sm-empty__sub">Go to workspace and make your first meme.</div>
            </div>
          ) : null}
        </div>
      </div>
    </main>
  );
}
