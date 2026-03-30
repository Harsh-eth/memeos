import { useEffect, useState } from "react";
import { fetchFeed, feedItemTitle, formatTimeAgo, type FeedItemApi } from "../api";
import { useMemeUi } from "../context/MemeUiContext";

export function HistoryPage() {
  const { applyFeedItem, feedTick } = useMemeUi();
  const [items, setItems] = useState<FeedItemApi[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let ok = true;
    fetchFeed(100)
      .then((list) => {
        if (ok) {
          const userOnly = list.filter((i) => i.source === "user");
          setItems(userOnly.length ? userOnly : list);
          setErr(null);
        }
      })
      .catch((e) => {
        if (ok) setErr(e instanceof Error ? e.message : "failed to load history");
      });
    return () => {
      ok = false;
    };
  }, [feedTick]);

  return (
    <main className="ref-main ref-main--wide">
      <h1 className="ref-page-title">history</h1>
      <p className="ref-muted ref-history-hint">your generations (newest first)</p>
      {err ? <p className="ref-page-err">{err}</p> : null}
      <ul className="ref-history-list">
        {items.map((item) => (
          <li key={item.id} className="ref-history-row">
            <button
              type="button"
              className="ref-history-row__btn"
              onClick={() => applyFeedItem(item)}
            >
              <img
                src={`data:image/png;base64,${item.image_base64}`}
                alt=""
                width={48}
                height={48}
                className="ref-history-row__thumb"
              />
              <div className="ref-history-row__text">
                <span className="ref-history-row__title">{feedItemTitle(item)}</span>
                <span className="ref-history-row__sub">
                  {formatTimeAgo(item.created_at)} · {item.source}
                </span>
              </div>
            </button>
          </li>
        ))}
      </ul>
      {items.length === 0 && !err ? <p className="ref-muted">no history</p> : null}
    </main>
  );
}
