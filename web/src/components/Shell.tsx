import { useEffect, useState, type ReactNode } from "react";
import { dayLabel, money, pct } from "../format";
import { ChevronLeft, ChevronRight, Mark, Moon, Sun } from "../icons";
import type { Meta } from "../types";
import type { Toast } from "../App";

export type Tab = "tonight" | "board" | "out" | "ledger" | "rules";

const NAV: { id: Tab; label: string; short: string }[] = [
  { id: "tonight", label: "Tonight", short: "Tonight" },
  { id: "board", label: "All markets", short: "Markets" },
  { id: "out", label: "Player out", short: "Player out" },
  { id: "ledger", label: "Ledger", short: "Ledger" },
  { id: "rules", label: "Rulebook", short: "Rules" },
];

type Theme = "light" | "dark";
const readTheme = (): Theme => {
  const forced = new URLSearchParams(location.search).get("theme");
  if (forced === "light" || forced === "dark") return forced;
  try {
    const t = localStorage.getItem("tod-theme");
    if (t === "light" || t === "dark") return t;
  } catch {
    /* storage unavailable: follow the system */
  }
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
};

export function Shell(props: {
  meta: Meta | null;
  league: string;
  onLeague: (id: string) => void;
  date: string | null;
  onDate: (d: string) => void;
  tab: Tab;
  cardCount: number;
  cardLocked: boolean;
  toast: Toast;
  onSignOut?: () => void;
  children: ReactNode;
}) {
  const { meta, league: leagueId, onLeague, date, onDate, tab, cardCount, cardLocked, toast, onSignOut, children } = props;
  const [theme, setTheme] = useState<Theme>(readTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  // The mood accent: green while the desk beats the closing line (or has no record yet), coral below it.
  // League colour comes from data: the selected league's own token drives every league dot.
  useEffect(() => {
    document.documentElement.style.setProperty("--league", `var(--${leagueId})`);
  }, [leagueId]);

  const clv = meta?.live_clv;
  useEffect(() => {
    document.documentElement.dataset.mood = clv && clv.n > 0 && (clv.avg ?? 0) < 0 ? "down" : "up";
  }, [clv?.n, clv?.avg]);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    try {
      localStorage.setItem("tod-theme", next);
    } catch {
      /* fine: it just won't be remembered */
    }
  };

  // 1–5 switch screens when you're not typing.
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (e.ctrlKey || e.metaKey || e.altKey || el.closest("input, select, textarea")) return;
      const i = Number(e.key) - 1;
      if (i >= 0 && i < NAV.length) location.hash = "#/" + NAV[i].id;
    };
    addEventListener("keydown", on);
    return () => removeEventListener("keydown", on);
  }, []);

  const dates = meta?.dates ?? [];
  const league = meta?.leagues.find((l) => l.id === leagueId)?.label ?? "";
  const di = date ? dates.indexOf(date) : -1;
  const s = meta?.settings;
  const count = (id: Tab) =>
    id === "tonight" && cardCount > 0 ? (
      <span className="count" aria-label={`${cardCount} ${cardCount === 1 ? "bet" : "bets"} on the card${cardLocked ? ", locked" : ""}`}>
        {cardCount}
      </span>
    ) : null;

  return (
    <div className="app">
      <header className="top">
        <div className="top-row">
          <a className="brand" href="#/tonight" aria-label="HKX, the Hasan–Kong Exchange: Tonight">
            <Mark />
            <b>HKX</b>
          </a>
          <nav
            className="leagues"
            aria-label="Leagues"
            data-single={(meta?.leagues ?? []).filter((l) => l.live).length < 2 || undefined}
          >
            {(meta?.leagues ?? []).map((l) => (
              <button
                key={l.id}
                className="league"
                style={{ ["--c" as string]: `var(--${l.id})` }}
                aria-pressed={l.id === leagueId}
                disabled={!l.live}
                onClick={() => l.id !== leagueId && onLeague(l.id)}
                title={l.live ? (l.id === leagueId ? `Showing ${l.label}` : `Switch to ${l.label}`) : `${l.label} is coming later`}
              >
                <i aria-hidden="true" />
                {l.label}
                {!l.live && <small>soon</small>}
              </button>
            ))}
          </nav>
          <div className="top-right">
            <div className="slate">
              <button aria-label="Previous slate" disabled={di < 0 || di >= dates.length - 1} onClick={() => onDate(dates[di + 1])}>
                <ChevronLeft />
              </button>
              <label className="sr" htmlFor="slate">
                Slate date
              </label>
              <select id="slate" value={date ?? ""} onChange={(e) => onDate(e.target.value)}>
                {dates.map((d) => (
                  <option key={d} value={d}>
                    {league} · {dayLabel(d)}
                  </option>
                ))}
              </select>
              <button aria-label="Next slate" disabled={di <= 0} onClick={() => onDate(dates[di - 1])}>
                <ChevronRight />
              </button>
              {meta?.sample && <span className="tag">Sample</span>}
            </div>
            {s && (
              <div className="stats">
                <div className="stat">
                  <span>Bankroll</span>
                  <b>{money(s.bankroll)}</b>
                </div>
                <div className="stat">
                  <span>Unit</span>
                  <b>{money(s.bankroll / 100)}</b>
                </div>
                <div className="stat mood-chip" title="How much the market moved your way after you bet, on average (closing-line value)">
                  <span>Beat the market</span>
                  <b>
                    {meta.live_clv.n ? pct(meta.live_clv.avg) : "—"}
                    <small>n={meta.live_clv.n}</small>
                  </b>
                </div>
              </div>
            )}
            <button className="theme" onClick={toggleTheme} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}>
              {theme === "dark" ? <Sun /> : <Moon />}
            </button>
          </div>
        </div>
        <nav className="tabs" aria-label="Screens">
          {NAV.map((n) => (
            <a key={n.id} href={"#/" + n.id} aria-current={tab === n.id ? "page" : undefined}>
              {n.label}
              {count(n.id)}
            </a>
          ))}
        </nav>
      </header>

      <main>{children}</main>

      <footer className="foot">
        <span>
          Gambling problem? Call <b>1-800-GAMBLER</b>
        </span>
        <span>21+ · Florida · HKX never places bets</span>
        <span>Other books are price references only; Hard Rock is the one you bet</span>
        {onSignOut && (
          <button className="btn link" onClick={onSignOut}>
            Sign out
          </button>
        )}
        {meta?.sample && <span className="tag">Sample data</span>}
      </footer>

      <nav className="tabbar" aria-label="Screens">
        {NAV.map((n) => (
          <a key={n.id} href={"#/" + n.id} aria-current={tab === n.id ? "page" : undefined}>
            {n.short}
            {count(n.id)}
          </a>
        ))}
      </nav>

      <div role="status" aria-live="polite" className="sr">
        {toast?.text}
      </div>
      {toast && (
        <div className={"toast" + (toast.err ? " err" : "")} aria-hidden>
          {toast.text}
        </div>
      )}
    </div>
  );
}
