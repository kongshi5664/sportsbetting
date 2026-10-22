import { useEffect, useState } from "react";
import { api } from "../api";
import { tipTime } from "../format";
import type { BetProgress, DeskStatus, Live } from "../types";

const ago = (iso: string | null) => {
  if (!iso) return null;
  const m = Math.max(0, Math.round((Date.now() - Date.parse(iso)) / 60000));
  return m < 1 ? "just now" : m < 60 ? `${m} min ago` : `${Math.floor(m / 60)} h ${m % 60} min ago`;
};

/** Polls a loader on an interval while the tab is visible; null until the first answer. `key` restarts it. */
function usePoll<T>(key: string | null, load: () => Promise<T>, every: number) {
  const [data, setData] = useState<T | null>(null);
  useEffect(() => {
    setData(null);
    if (!key) return;
    let alive = true;
    const tick = () => {
      if (document.visibilityState === "visible") load().then((d) => alive && setData(d)).catch(() => {});
    };
    tick();
    const t = setInterval(tick, every);
    document.addEventListener("visibilitychange", tick);
    return () => {
      alive = false;
      clearInterval(t);
      document.removeEventListener("visibilitychange", tick);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, every]);
  return data;
}

/** Scores and each open bet's progress, refreshed every 30 seconds. */
export function useLive(date: string | null) {
  return usePoll<Live>(date, () => api.live(date!), 30_000);
}

/** One line on whether tonight's machinery is working: the trader, the odds, the credits. */
export function StatusStrip({ date }: { date: string }) {
  const s = usePoll<DeskStatus>(date, () => api.status(date), 60_000);
  if (!s) return null;
  const low = s.credits_remaining != null && s.credits_remaining < 100;
  const left = s.games - s.decided;
  return (
    <div className="status-strip" role="status">
      <span className={"status-item " + (s.trader.running ? "ok" : left ? "bad" : "")}>
        <i aria-hidden="true" />
        {s.trader.running ? "Paper trader running" : left ? "Paper trader not running" : "Paper trader done for tonight"}
      </span>
      {s.next && (
        <span className="status-item">
          Next: {s.next.game} at {tipTime(s.next.decide_at)} ET
        </span>
      )}
      {!s.next && s.games > 0 && (
        <span className="status-item">
          {s.decided} of {s.games} games decided
        </span>
      )}
      {s.last_pull && <span className="status-item">Odds pulled {ago(s.last_pull)}</span>}
      {s.credits_remaining != null && (
        <span className={"status-item " + (low ? "bad" : "")}>{s.credits_remaining} credits left</span>
      )}
    </div>
  );
}

/** Tonight's games as a strip of score chips, once any has tipped. */
export function Scoreboard({ live }: { live: Live | null }) {
  if (!live || !live.games.some((g) => g.state !== "pre")) return null;
  return (
    <div className="scoreboard" aria-label="Scores">
      {live.games.map((g) => (
        <div key={g.espn_id} className={"score " + g.state}>
          <span className="score-row">
            <b>{g.away}</b>
            {g.state !== "pre" && <span>{g.away_score}</span>}
          </span>
          <span className="score-row">
            <b>{g.home}</b>
            {g.state !== "pre" && <span>{g.home_score}</span>}
          </span>
          <small>{g.state === "in" && <i className="live-dot" aria-hidden="true" />}{g.detail}</small>
        </div>
      ))}
    </div>
  );
}

/** A bet's live progress in words: "14 so far, on pace for 28" or "Hit". */
export function Progress({ p, point, side }: { p?: BetProgress; point: number; side: string }) {
  if (!p) return <span className="dim">—</span>;
  if (p.state === "pre") return <span className="dim">{p.detail || "Not started"}</span>;
  if (p.now == null) return <span className="dim">No stats yet</span>;
  if (p.status === "won") return <span className="prog won">✓ Hit · {p.now}</span>;
  if (p.status === "lost") return <span className="prog lost">✗ Missed · {p.now}</span>;
  if (p.status === "void") return <span className="dim">Didn't play</span>;
  const need = side === "Over" ? Math.max(0, Math.ceil(point - p.now)) : null;
  return (
    <span className={"prog " + (p.on_pace == null ? "" : p.on_pace ? "good" : "behind")}>
      {p.now} so far
      {need != null && need > 0 ? ` · needs ${need}` : ""}
      {p.pace != null && ` · pace ${Math.round(p.pace)}`}
    </span>
  );
}
