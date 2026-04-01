import { useEffect, useState } from "react";
import {
  fetchFeed,
  feedItemImageSrc,
  feedItemTitle,
  formatTimeAgo,
  type FeedItemApi,
} from "../api";
import { useMemeUi } from "../context/MemeUiContext";

type RecentSidebarProps = {
  tick: number;
};

export function RecentSidebar({ tick }: RecentSidebarProps) {
  const { applyFeedItem } = useMemeUi();
  const [items, setItems] = useState<FeedItemApi[]>([]);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    setFailed(false);
    fetchFeed(25)
      .then((list) => {
        if (alive) setItems(list);
      })
      .catch(() => {
        if (alive) {
          setItems([]);
          setFailed(true);
        }
      });
    return () => {
      alive = false;
    };
  }, [tick]);

  return (
    <aside className="ref-sidebar">
      <h2 className="ref-sidebar__title">Recent</h2>
      {failed ? (
        <p className="ref-sidebar__err">api unreachable — start backend :8000</p>
      ) : null}
      <ul className="ref-sidebar__list">
        {items.map((item) => (
          <li key={item.id} className="ref-sidebar__item">
            <button
              type="button"
              className="ref-sidebar__btn"
              onClick={() => applyFeedItem(item)}
            >
              <span className="ref-sidebar__thumb">
                <img
                  src={feedItemImageSrc(item)}
                  alt=""
                  width={40}
                  height={40}
                  className="ref-sidebar__thumb-img"
                  loading="lazy"
                />
              </span>
              <span className="ref-sidebar__body">
                <span className="ref-sidebar__label">{feedItemTitle(item)}</span>
                <span className="ref-sidebar__time">{formatTimeAgo(item.created_at)}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
      {!failed && items.length === 0 ? (
        <p className="ref-sidebar__empty">no memes yet</p>
      ) : null}
    </aside>
  );
}
