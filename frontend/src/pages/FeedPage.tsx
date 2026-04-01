import { useEffect, useMemo, useRef, useState } from "react";
import {
  fetchFeed,
  fetchTop,
  feedItemCaptions,
  feedItemImageSrc,
  formatTimeAgo,
  generateMeme,
  type FeedItemApi,
  type MemeMode,
} from "../api";
import { MEME_MODES } from "../context/MemeUiContext";
import { useMemeUi } from "../context/MemeUiContext";

export function FeedPage() {
  const { showToast, bumpFeed } = useMemeUi();
  const [items, setItems] = useState<FeedItemApi[]>([]);
  const [top, setTop] = useState<FeedItemApi[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingTop, setLoadingTop] = useState(false);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [mode, setMode] = useState<MemeMode | "all">("all");
  const [hookMode, setHookMode] = useState<MemeMode | null>(null);
  const [modal, setModal] = useState<FeedItemApi | null>(null);
  const [modalClosing, setModalClosing] = useState(false);
  const [likes, setLikes] = useState<Record<string, number>>({});
  const [heartId, setHeartId] = useState<string | null>(null);
  const [newIds, setNewIds] = useState<Record<string, true>>({});

  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const loadingRef = useRef(false);
  const debounceRef = useRef<number | null>(null);
  const modalCloseTimer = useRef<number | null>(null);
  const swipeStartY = useRef<number | null>(null);
  const swipeDeltaY = useRef<number>(0);
  const heartTimer = useRef<number | null>(null);

  useEffect(() => {
    const last = (window.localStorage.getItem("memeos_last_mode") || "").toLowerCase() as MemeMode;
    if (last === "personal" || last === "roast" || last === "decision") {
      setHookMode(last);
      setMode(last);
    }
    let alive = true;
    setLoadingTop(true);
    fetchTop(10)
      .then((list) => {
        if (!alive) return;
        setTop(list);
      })
      .catch(() => {
        if (!alive) return;
        setTop([]);
      })
      .finally(() => {
        if (!alive) return;
        setLoadingTop(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    let alive = true;
    setErr(null);
    setItems([]);
    setOffset(0);
    setHasMore(true);
    setLoading(true);
    loadingRef.current = true;

    fetchFeed(20, 0)
      .then((list) => {
        if (!alive) return;
        setItems(list);
        setOffset(list.length);
        setHasMore(list.length >= 20);
      })
      .catch((e) => {
        if (!alive) return;
        setErr(e instanceof Error ? e.message : "failed to load feed");
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
      const next = await fetchFeed(20, offset);
      const newOnes: Record<string, true> = {};
      for (const it of next) newOnes[it.id] = true;
      setNewIds((prev) => ({ ...prev, ...newOnes }));
      window.setTimeout(() => {
        setNewIds((prev) => {
          const copy = { ...prev };
          for (const it of next) delete copy[it.id];
          return copy;
        });
      }, 420);
      setItems((prev) => [...prev, ...next]);
      setOffset((n) => n + next.length);
      setHasMore(next.length >= 20);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "failed to load feed");
    } finally {
      setLoading(false);
      loadingRef.current = false;
    }
  }

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;

    const obs = new IntersectionObserver(
      (entries) => {
        const v = entries[0];
        if (!v?.isIntersecting) return;
        if (debounceRef.current) window.clearTimeout(debounceRef.current);
        debounceRef.current = window.setTimeout(() => {
          void loadMore();
        }, 180);
      },
      { root: null, rootMargin: "800px 0px", threshold: 0.01 },
    );

    obs.observe(el);
    return () => {
      obs.disconnect();
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
  }, [offset, hasMore]);

  const filteredTop = useMemo(() => {
    if (mode === "all") return top;
    return top.filter((x) => (x.mode ?? x.metadata?.mode) === mode);
  }, [top, mode]);

  const filtered = useMemo(() => {
    if (mode === "all") return items;
    return items.filter((x) => (x.mode ?? x.metadata?.mode) === mode);
  }, [items, mode]);

  function modeTagClass(m: string) {
    const s = (m || "").toLowerCase();
    if (s === "roast") return "sm-tag sm-tag--roast";
    if (s === "decision") return "sm-tag sm-tag--decision";
    return "sm-tag sm-tag--personal";
  }

  function ScoreBadge({ score }: { score?: number }) {
    const s = typeof score === "number" ? score : undefined;
    if (!s) return null;
    return <span className="sm-score">{s}</span>;
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

  function like(itemId: string) {
    setLikes((prev) => ({ ...prev, [itemId]: (prev[itemId] ?? 0) + 1 }));
    setHeartId(itemId);
    if (heartTimer.current) window.clearTimeout(heartTimer.current);
    heartTimer.current = window.setTimeout(() => setHeartId(null), 520);
  }

  async function generateSimilar(item: FeedItemApi) {
    const up = item.metadata?.user_prompt?.trim();
    const m = ((item.mode ?? item.metadata?.mode ?? "personal") as MemeMode) || "personal";
    if (!up) return;
    try {
      showToast("generating…");
      await generateMeme(up, m);
      bumpFeed();
      showToast(["that one hit", "post-worthy", "this is good"][Math.floor(Math.random() * 3)]);
      // refresh rails quickly
      setLoadingTop(true);
      fetchTop(10).then(setTop).finally(() => setLoadingTop(false));
      fetchFeed(20, 0).then((list) => {
        setItems(list);
        setOffset(list.length);
        setHasMore(list.length >= 20);
      });
    } catch {
      showToast("generate failed");
    }
  }

  async function makeItBetter(item: FeedItemApi) {
    const up = item.metadata?.user_prompt?.trim();
    const m = ((item.mode ?? item.metadata?.mode ?? "personal") as MemeMode) || "personal";
    const scenario =
      (item.metadata as any)?.reasoning?.scenario ??
      (item.metadata as any)?.reasoning?.scenario ??
      "";
    if (!up) return;
    const tweak = [
      "Make it punchier, more contrast between top and bottom, and end with a stronger punchline.",
      scenario ? `Keep the same core scenario: ${String(scenario).slice(0, 160)}` : "",
    ]
      .filter(Boolean)
      .join("\n");
    try {
      showToast("making it better…");
      await generateMeme(`${up}\n\n${tweak}`, m);
      bumpFeed();
      showToast("upgraded");
      setLoadingTop(true);
      fetchTop(10).then(setTop).finally(() => setLoadingTop(false));
      fetchFeed(20, 0).then((list) => {
        setItems(list);
        setOffset(list.length);
        setHasMore(list.length >= 20);
      });
    } catch {
      showToast("generate failed");
    }
  }

  function MemeImage({
    src,
    className,
  }: {
    src: string;
    className: string;
  }) {
    const [loaded, setLoaded] = useState(false);
    return (
      <img
        src={src}
        alt=""
        className={loaded ? `${className} sm-img--loaded` : `${className} sm-img--loading`}
        loading="lazy"
        onLoad={() => setLoaded(true)}
      />
    );
  }

  function closeModal() {
    if (!modal) return;
    setModalClosing(true);
    if (modalCloseTimer.current) window.clearTimeout(modalCloseTimer.current);
    modalCloseTimer.current = window.setTimeout(() => {
      setModal(null);
      setModalClosing(false);
    }, 140);
  }

  useEffect(() => {
    if (!modal) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") closeModal();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modal]);

  useEffect(() => {
    return () => {
      if (modalCloseTimer.current) window.clearTimeout(modalCloseTimer.current);
      if (heartTimer.current) window.clearTimeout(heartTimer.current);
    };
  }, []);

  return (
    <main className="sm-page">
      <div className="sm-shell">
        <div className="sm-head">
          <div>
            <h1 className="sm-title">Feed</h1>
            <p className="sm-subtitle">Newest first</p>
          </div>
          <div className="sm-filters" role="tablist" aria-label="Mode filter">
            <button
              type="button"
              className={mode === "all" ? "sm-pill sm-pill--on" : "sm-pill"}
              onClick={() => setMode("all")}
            >
              all
            </button>
            {MEME_MODES.map((m) => (
              <button
                key={m}
                type="button"
                className={mode === m ? "sm-pill sm-pill--on" : "sm-pill"}
                onClick={() => setMode(m)}
              >
                {m}
              </button>
            ))}
          </div>
        </div>

        {hookMode ? (
          <div className="sm-banner">
            <div className="sm-banner__title">Filter</div>
            <div className="sm-banner__sub">
              Showing <span className="sm-banner__mode">{hookMode}</span> only (from your last run).
            </div>
          </div>
        ) : null}

        {err ? <p className="sm-err">{err}</p> : null}

        <section className="sm-rail">
          <div className="sm-rail__head">
            <h2 className="sm-h2">Top</h2>
          </div>
          <div className="sm-rail__scroll" role="list">
            {loadingTop
              ? Array.from({ length: 6 }).map((_, idx) => (
                  <div key={idx} className="sm-skel sm-skel--top" />
                ))
              : filteredTop.map((item) => {
                  const caps = feedItemCaptions(item);
                  return (
                    <button
                      key={item.id}
                      type="button"
                      className="sm-topcard"
                      onClick={() => setModal(item)}
                      onDoubleClick={() => {
                        like(item.id);
                      }}
                    >
                      <div className="sm-topcard__imgwrap">
                        <MemeImage src={feedItemImageSrc(item)} className="sm-topcard__img" />
                        <ScoreBadge score={item.score ?? item.metadata?.score} />
                        {(item.score ?? item.metadata?.score ?? 0) >= 9 ? (
                          <span className="sm-trending">Hot</span>
                        ) : null}
                        {heartId === item.id ? <span className="sm-heart">+1</span> : null}
                      </div>
                      <div
                        className="sm-topcard__cap"
                        title={[caps.top, caps.bottom].filter(Boolean).join(" — ") || undefined}
                      >
                        {(caps.bottom || caps.top || "—").slice(0, 52)}
                      </div>
                    </button>
                  );
                })}
          </div>
        </section>

        <section className="sm-feed">
          <div className="sm-feed__head">
            <h2 className="sm-h2">Latest</h2>
          </div>

          <div className="sm-grid">
            {filtered.map((item) => {
              const caps = feedItemCaptions(item);
              const m = item.mode ?? item.metadata?.mode ?? "personal";
              return (
                <article
                  key={item.id}
                  className={
                    newIds[item.id]
                      ? "sm-card sm-card--hover sm-appear"
                      : "sm-card sm-card--hover"
                  }
                >
                  <button
                    type="button"
                    className="sm-imgbtn"
                    onClick={() => setModal(item)}
                    onDoubleClick={() => {
                      like(item.id);
                    }}
                  >
                    <MemeImage src={feedItemImageSrc(item)} className="sm-img" />
                    <ScoreBadge score={item.score ?? item.metadata?.score} />
                    {heartId === item.id ? <span className="sm-heart sm-heart--big">+1</span> : null}
                  </button>
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
                      <span className="sm-like">{likes[item.id] ?? 0} likes</span>
                    </div>
                    <div className="sm-foot">
                      <span className={modeTagClass(m)}>{m}</span>
                      <span className="sm-time">{formatTimeAgo(item.created_at)}</span>
                    </div>
                  </div>
                </article>
              );
            })}

            {loading ? (
              <>
                <div className="sm-skel sm-skel--card" />
                <div className="sm-skel sm-skel--card" />
                <div className="sm-skel sm-skel--card" />
              </>
            ) : null}
          </div>

          <div ref={sentinelRef} className="sm-sentinel" />
          {!loading && !hasMore && filtered.length ? <div className="sm-muted">end</div> : null}
          {!loading && !filtered.length && !err ? (
            <div className="sm-empty">
              <div className="sm-empty__title">No memes yet</div>
              <div className="sm-empty__sub">Be the first to create one in workspace.</div>
            </div>
          ) : null}
        </section>
      </div>

      {modal ? (
        <div
          className={modalClosing ? "sm-modal sm-modal--closing" : "sm-modal sm-modal--open"}
          role="dialog"
          aria-modal="true"
          onClick={() => closeModal()}
        >
          <div
            className={modalClosing ? "sm-modal__card sm-modal__card--closing" : "sm-modal__card"}
            onClick={(e) => e.stopPropagation()}
            onTouchStart={(e) => {
              swipeStartY.current = e.touches[0]?.clientY ?? null;
              swipeDeltaY.current = 0;
            }}
            onTouchMove={(e) => {
              if (swipeStartY.current == null) return;
              const y = e.touches[0]?.clientY ?? swipeStartY.current;
              swipeDeltaY.current = Math.max(0, y - swipeStartY.current);
              if (swipeDeltaY.current > 140) closeModal();
            }}
            onTouchEnd={() => {
              swipeStartY.current = null;
              swipeDeltaY.current = 0;
            }}
          >
            <button type="button" className="sm-modal__close" onClick={() => closeModal()}>
              close
            </button>
            <MemeImage src={feedItemImageSrc(modal)} className="sm-modal__img" />
            <div className="sm-modal__meta">
              <div className="sm-cap sm-cap--top">{feedItemCaptions(modal).top}</div>
              <div className="sm-cap sm-cap--bottom">{feedItemCaptions(modal).bottom}</div>
              <div className="sm-modal__actions">
                <button
                  type="button"
                  className="sm-btn sm-btn--primary"
                  disabled={!modal.metadata?.user_prompt}
                  onClick={() => void generateSimilar(modal)}
                >
                  Generate similar
                </button>
                <button
                  type="button"
                  className="sm-btn"
                  disabled={!modal.metadata?.user_prompt}
                  onClick={() => void makeItBetter(modal)}
                >
                  make it better
                </button>
                <button type="button" className="sm-btn" onClick={() => void copyCaption(modal)}>
                  copy caption
                </button>
                <button type="button" className="sm-btn" onClick={() => void downloadImage(modal)}>
                  download
                </button>
              </div>
              <div className="sm-foot">
                <span className={modeTagClass(modal.mode ?? modal.metadata?.mode ?? "personal")}>
                  {modal.mode ?? modal.metadata?.mode ?? "personal"}
                </span>
                <span className="sm-time">{formatTimeAgo(modal.created_at)}</span>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}
