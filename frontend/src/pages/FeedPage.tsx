import { useEffect, useState } from "react";
import { fetchFeed, feedItemTitle, formatTimeAgo, type FeedItemApi } from "../api";
import { useMemeUi } from "../context/MemeUiContext";

export function FeedPage() {
  const { applyFeedItem, feedTick } = useMemeUi();
  const [items, setItems] = useState<FeedItemApi[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let ok = true;
    fetchFeed(50)
      .then((list) => {
        if (ok) {
          setItems(list);
          setErr(null);
        }
      })
      .catch((e) => {
        if (ok) setErr(e instanceof Error ? e.message : "failed to load feed");
      });
    return () => {
      ok = false;
    };
  }, [feedTick]);

  return (
    <main className="ref-main ref-main--wide">
      <h1 className="ref-page-title">feed</h1>
      {err ? <p className="ref-page-err">{err}</p> : null}
      <ul className="ref-feed-grid">
        {items.map((item) => (
          <li key={item.id} className="ref-feed-card">
            <button
              type="button"
              className="ref-feed-card__btn"
              onClick={() => applyFeedItem(item)}
            >
              <img
                src={`data:image/png;base64,${item.image_base64}`}
                alt=""
                className="ref-feed-card__img"
              />
              <div className="ref-feed-card__meta">
                <span className="ref-feed-card__title">{feedItemTitle(item)}</span>
                <span className="ref-feed-card__time">{formatTimeAgo(item.created_at)}</span>
              </div>
            </button>
          </li>
        ))}
      </ul>
      {items.length === 0 && !err ? <p className="ref-muted">no items</p> : null}
    </main>
  );
}
