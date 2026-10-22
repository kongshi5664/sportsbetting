import { Fragment, useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { BOOK_SHORT, odds, pct, pick, tipTime } from "../format";
import { Check, ChevronDown, Cross, Search, Warn } from "../icons";
import { Term } from "./Term";
import type { Game, Market } from "../types";

const REFS = ["draftkings", "fanduel", "betmgm"];
type SortKey = "edge" | "player" | "price" | "stake";

/** Edge on one fixed ramp everywhere: segments at 2, 4, 6 and 10 percent. */
export function Ramp({ edge }: { edge: number }) {
  const steps = [0.02, 0.04, 0.06, 0.1];
  return (
    <span className={"ramp" + (edge < 0 ? " neg" : "")} aria-hidden>
      {steps.map((s) => (
        <i key={s} className={Math.abs(edge) >= s ? "on" : ""} />
      ))}
    </span>
  );
}

export function RulePills({ m }: { m: Market }) {
  const blocking = m.flags.filter((f) => f.blocks);
  const testing = m.flags.filter((f) => f.testing);
  return (
    <span className="chips">
      {blocking.length === 0 ? (
        <span className="pill ok">
          <Check /> Pass
        </span>
      ) : (
        blocking.map((f) => (
          <span key={f.rule} className="pill no">
            <Cross /> {f.text}
          </span>
        ))
      )}
      {testing.length > 0 && (
        <span className="pill test" title={"Testing, not enforced: " + testing.map((f) => f.text).join("; ")}>
          {testing.length} testing
        </span>
      )}
    </span>
  );
}

export const label = (m: Market) => `${m.player} ${m.stat_label.toLowerCase()} ${pick(m.side, m.point)}`;

export function EdgeBoard(props: {
  games: Game[] | null;
  sample: boolean;
  live: boolean;
  today: boolean;
  costPerGame: number;
  creditsLeft: number | null;
  onRefresh: () => Promise<void>;
  locked: boolean;
  canLock: boolean;
  onAdd: (id: string, label: string) => void;
  onRemove: (id: string, label: string) => void;
  onLock: () => void;
}) {
  const { games, sample, live, today, costPerGame, creditsLeft, onRefresh, locked, canLock, onAdd, onRemove, onLock } =
    props;
  const [pulling, setPulling] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(t);
  }, []);
  const [stat, setStat] = useState("all");
  const [showHeld, setShowHeld] = useState(false);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "edge", dir: -1 });
  const [open, setOpen] = useState<string | null>(null);
  const search = useRef<HTMLInputElement>(null);
  const body = useRef<HTMLTableSectionElement>(null);

  const all = useMemo(() => (games ?? []).flatMap((g) => g.markets), [games]);
  const stats = useMemo(() => [...new Set(all.map((m) => m.stat_label))], [all]);
  const clears = all.filter((m) => !m.blocked).length;

  // Near misses (held out, but still a positive edge) always show, dimmed, with the rule that holds them.
  const visible = (m: Market) =>
    (stat === "all" || m.stat_label === stat) &&
    (showHeld || !m.blocked || m.on_card || m.edge >= 0) &&
    (!query || `${m.player} ${m.team}`.toLowerCase().includes(query.toLowerCase()));

  const order = (a: Market, b: Market) => {
    const v = (m: Market) =>
      sort.key === "player" ? m.player : sort.key === "price" ? m.price : sort.key === "stake" ? m.stake : m.edge;
    const x = v(a),
      y = v(b);
    return (typeof x === "string" ? x.localeCompare(y as string) : (x as number) - (y as number)) * sort.dir;
  };

  const groups = (games ?? [])
    .map((g) => ({ g, rows: g.markets.filter(visible).sort(order) }))
    .filter((x) => x.rows.length);
  const shown = groups.reduce((n, x) => n + x.rows.length, 0);
  const closest = shown === 0 && !query ? [...all].sort((a, b) => b.edge - a.edge).slice(0, 5) : [];

  const snap = (games ?? []).map((g) => g.snapshot_ts).filter(Boolean).sort().at(-1);
  const upcoming = (games ?? []).filter((g) => Date.parse(g.commence_time) > now).length;
  const ageMin = snap ? Math.round((now - Date.parse(snap)) / 60000) : null;
  const stale = today && upcoming > 0 && ageMin != null && ageMin > 20;
  const pull = async () => {
    setPulling(true);
    await onRefresh();
    setPulling(false);
  };

  // Keys: "/" search, j/k or arrows move, Enter opens the proof, "a" adds or removes, Shift+L locks.
  useEffect(() => {
    const on = (e: globalThis.KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (el.closest("input, select, textarea") || e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === "/") {
        e.preventDefault();
        search.current?.focus();
      } else if (e.key === "L" && canLock) {
        onLock();
      } else if ((e.key === "j" || e.key === "ArrowDown") && !el.closest("tr.mk")) {
        e.preventDefault();
        body.current?.querySelector<HTMLElement>("tr.mk")?.focus();
      }
    };
    addEventListener("keydown", on);
    return () => removeEventListener("keydown", on);
  }, [canLock, onLock]);

  const rowKeys = (e: KeyboardEvent<HTMLTableRowElement>, m: Market) => {
    const rows = [...(body.current?.querySelectorAll<HTMLElement>("tr.mk") ?? [])];
    const i = rows.indexOf(e.currentTarget);
    if (e.key === "j" || e.key === "ArrowDown") {
      e.preventDefault();
      rows[i + 1]?.focus();
    } else if (e.key === "k" || e.key === "ArrowUp") {
      e.preventDefault();
      rows[i - 1]?.focus();
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      setOpen(open === m.id ? null : m.id);
    } else if (e.key === "a") {
      toggle(m);
    }
  };

  const toggle = (m: Market) => {
    if (locked) return;
    if (m.on_card) onRemove(m.id, label(m));
    else if (!m.blocked) onAdd(m.id, label(m));
  };

  const th = (key: SortKey, text: string, cls = "") => (
    <th className={cls} aria-sort={sort.key === key ? (sort.dir === 1 ? "ascending" : "descending") : undefined}>
      <button onClick={() => setSort({ key, dir: sort.key === key ? (-sort.dir as 1 | -1) : key === "player" ? 1 : -1 })}>
        {text}
        {sort.key === key && <ChevronDown style={{ rotate: sort.dir === 1 ? "180deg" : "0deg" }} />}
      </button>
    </th>
  );

  const row = (m: Market, held = false) => {
    const expanded = open === m.id;
    const addLabel = m.on_card ? "On card" : m.blocked ? "Held" : "Add";
    return (
      <Fragment key={m.id}>
        <tr
          className={"mk" + (m.blocked && !m.on_card ? " held" : "") + (m.on_card ? " oncard" : "")}
          tabIndex={0}
          aria-expanded={expanded}
          onClick={(e) => !(e.target as HTMLElement).closest("button") && setOpen(expanded ? null : m.id)}
          onKeyDown={(e) => rowKeys(e, m)}
        >
          <td className="l who">
            <b>{m.player}</b>
            <small>{m.team}</small>
          </td>
          <td className="l mkt">
            {m.stat_label} <b className="pk">{pick(m.side, m.point)}</b>
          </td>
          <td className="fair">{odds(m.fair_american)}</td>
          <td className="hr">
            {odds(m.price)}
            <small className="fair-m"> worth {odds(m.fair_american)}</small>
          </td>
          {REFS.map((b) => (
            <td key={b} className="ref">
              {odds(m.refs[b])}
            </td>
          ))}
          <td className="edgec">
            <span className={m.edge >= 0 ? "pos" : "neg"}>{pct(m.edge)}</span>
            <Ramp edge={m.edge} />
          </td>
          <td className="stakec">{m.blocked && !m.on_card ? "—" : `$${Math.round(m.stake)}`}</td>
          <td className="rules">{held ? <span className="pill test">Closest to clearing</span> : <RulePills m={m} />}</td>
          <td className="addc">
            <button
              className={"btn add" + (m.on_card ? " in" : "")}
              disabled={locked || (m.blocked && !m.on_card)}
              onClick={() => toggle(m)}
              aria-label={`${m.on_card ? "Remove" : "Add"} ${label(m)}`}
              title={
                locked
                  ? "Tonight's card is locked"
                  : m.blocked && !m.on_card
                    ? m.flags.find((f) => f.blocks)?.text
                    : m.on_card
                      ? "Remove from tonight's card"
                      : "Add to tonight's card"
              }
            >
              {m.on_card && <Check />}
              {addLabel}
              {(m.on_card || !m.blocked) && <span className="stk"> · ${Math.round(m.stake)}</span>}
            </button>
          </td>
        </tr>
        {expanded && (
          <tr className="proof">
            <td colSpan={11}>
              <Proof m={m} />
            </td>
          </tr>
        )}
      </Fragment>
    );
  };

  return (
    <section aria-labelledby="board-h">
      <div className="head">
        <h1 id="board-h">All markets</h1>
        {games && (
          <p>
            {games.length} games · {all.length} markets priced · <b>{clears} clear the rulebook</b> · bettable at Hard Rock
            only
          </p>
        )}
      </div>

      <div className="filters">
        <div className="seg" role="group" aria-label="Market">
          {["all", ...stats].map((s) => (
            <button key={s} aria-pressed={stat === s} onClick={() => setStat(s)}>
              {s === "all" ? "All" : s}
            </button>
          ))}
        </div>
        <label className="field">
          <input type="checkbox" checked={showHeld} onChange={(e) => setShowHeld(e.target.checked)} />
          Show every held-out market
        </label>
        <div className="search">
          <label className="field">
            <span className="sr">Search players or teams</span>
            <Search />
            <input
              ref={search}
              type="search"
              placeholder="Player or team"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
        </div>
        {live && (
          <button className="btn" onClick={pull} disabled={pulling || upcoming === 0}>
            {pulling ? "Pulling odds…" : `Refresh odds · ${upcoming * costPerGame} credits`}
          </button>
        )}
        <div className="meta">
          {snap ? (
            <>
              Odds as of {tipTime(snap)} ET{today && ageMin != null ? ` (${ageMin} min ago)` : ""}
              {sample ? " · sample snapshot" : ""}
              {live && creditsLeft != null ? ` · ${creditsLeft.toLocaleString()} credits left` : ""}
            </>
          ) : null}
          <br />
          What the words mean: <Term k="worth">Worth</Term> · <Term k="value">Value</Term> ·{" "}
          <Term k="stake">Stake</Term>
        </div>
      </div>

      {stale && (
        <div className="notice" style={{ marginTop: 12 }}>
          <Warn />
          <p>
            These prices are {ageMin} minutes old. Refresh before you bet: lines move, especially near tip and after injury
            news.
          </p>
        </div>
      )}

      {games && games.length === 0 ? (
        <div className="empty">
          <h2>No odds for this date yet</h2>
          <p>
            {!today
              ? "This date has no odds in the database. Pick another slate in the header."
              : live
                ? "Nothing pulled for tonight yet. Pull once the books post props, usually by early afternoon."
                : "Add your ODDS_API_KEY to .env and restart the server, or run: python -m tipoff.snapshot --estimate"}
          </p>
          {live && (
            <p style={{ marginTop: 12 }}>
              <button className="btn primary" onClick={pull} disabled={pulling}>
                {pulling ? "Pulling odds…" : "Pull tonight's odds"}
              </button>
            </p>
          )}
        </div>
      ) : !games ? (
        <p className="dim" style={{ padding: "24px 0" }}>
          Pricing tonight's slate…
        </p>
      ) : (
        <div className="board-wrap">
        <table className="board">
          <thead>
            <tr>
              {th("player", "Player", "l")}
              <th className="l">Market</th>
              <th>Worth</th>
              {th("price", "Hard Rock", "hr")}
              {REFS.map((b) => (
                <th key={b} className="ref">
                  {BOOK_SHORT[b]}
                </th>
              ))}
              {th("edge", "Value")}
              {th("stake", "Stake")}
              <th className="l">Rules</th>
              <th>
                <span className="sr">Add to card</span>
              </th>
            </tr>
          </thead>
          <tbody ref={body}>
            {groups.map(({ g, rows }) => (
              <Fragment key={g.event_id}>
                <tr className="game">
                  <td colSpan={11}>
                    {g.away} @ {g.home}
                    <span>{tipTime(g.commence_time)}</span>
                  </td>
                </tr>
                {rows.map((m) => row(m))}
              </Fragment>
            ))}
            {closest.length > 0 && (
              <>
                <tr className="game">
                  <td colSpan={11}>
                    Closest to clearing<span>held out, for reference</span>
                  </td>
                </tr>
                {closest.map((m) => row(m, true))}
              </>
            )}
          </tbody>
        </table>
        </div>
      )}

      {games && games.length > 0 && shown === 0 && (
        <div className="empty">
          {query ? (
            <>
              <h2>No markets match “{query}”</h2>
              <p>Search covers player names and team codes on this slate.</p>
            </>
          ) : (
            <>
              <h2>Nothing clears the rulebook on this slate</h2>
              <p>That's a normal night. The closest markets are listed above so you can see how far off they are.</p>
            </>
          )}
        </div>
      )}

      <p className="dim" style={{ fontSize: 12, marginTop: 12 }}>
        Keys: <kbd>/</kbd> search · <kbd>j</kbd> <kbd>k</kbd> move · <kbd>Enter</kbd> show the math · <kbd>a</kbd> add or
        remove · <kbd>Shift</kbd>+<kbd>L</kbd> lock · <kbd>1</kbd>–<kbd>5</kbd> screens
      </p>
    </section>
  );
}

export function Proof({ m }: { m: Market }) {
  const p = m.proof;
  const dec = m.price > 0 ? 1 + m.price / 100 : 1 + 100 / -m.price;
  const side = m.side === "Over" ? "over" : "under";
  const sideP = (po: number) => (m.side === "Over" ? po : 1 - po);
  return (
    <div className="proof-grid">
      <div>
        <h3>Other books, with their cut removed</h3>
        <table>
          <thead>
            <tr>
              <th className="l">Book</th>
              <th>Over</th>
              <th>Under</th>
              <th>No-vig {side}</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(p.books).map(([b, q]) => (
              <tr key={b}>
                <td className="l">{BOOK_SHORT[b] ?? b}</td>
                <td>{odds(q.over)}</td>
                <td>{odds(q.under)}</td>
                <td>{(sideP(q.p_over) * 100).toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="math">
        <h3>How the value is worked out</h3>
        The other books say it hits <b>{(p.p_market * 100).toFixed(1)}%</b> of the time
        {p.books.pinnacle ? " (Pinnacle, the sharpest book, counts for half)" : " (the middle of them)"}
        <br />
        Our projection ({p.projection}) says <b>{(p.p_model * 100).toFixed(1)}%</b>, counted at{" "}
        {Math.round(p.model_weight * 100)}%
        <br />
        Worth ({side}): <b>{(m.fair * 100).toFixed(1)}%</b> chance, a fair price of {odds(m.fair_american)}
        <br />
        Hard Rock {odds(m.price)} pays ${(dec * 100).toFixed(0)} back per $100 when it hits, so value ={" "}
        {(m.fair * 100).toFixed(1)}% × {dec.toFixed(3)} − 1 = <b className={m.edge >= 0 ? "pos" : "neg"}>{pct(m.edge)}</b>
        <br />
        Stake: a quarter of the "ideal" bet size for this value, capped at 2% of the bankroll ={" "}
        <b>${Math.round(m.stake)}</b>
        {m.flags.some((f) => f.testing) && (
          <>
            <h3>Testing rules that match (not enforced)</h3>
            {m.flags
              .filter((f) => f.testing)
              .map((f) => f.text)
              .join(" · ")}
          </>
        )}
      </div>
    </div>
  );
}
