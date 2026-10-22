import { useState, type ReactNode } from "react";
import { dayLabel, money, odds, tipTime } from "../format";
import { Check, ChevronRight, Lock, Plus, Warn } from "../icons";
import type { Card, Game, Injury, JournalEntry, Market, Note, Suggested } from "../types";
import { Entry } from "./Journal";
import { Scoreboard, StatusStrip, useLive } from "./Live";
import { label, Proof, Ramp } from "./EdgeBoard";
import { NoteLine } from "./Suggest";
import { Term } from "./Term";

type Pick = Suggested["legs"][number];

/** Strength in words, from the same fixed ramp the board draws. */
export const strength = (edge: number) => (edge >= 0.06 ? "Strong" : edge >= 0.04 ? "Solid" : "Small");

const implied = (p: number) => (p > 0 ? 100 / (p + 100) : -p / (-p + 100));

/** How Hard Rock's price has moved since the day's first pull, in words; null when it hasn't. */
export const movement = (m: Market) => {
  if (m.open_price == null || m.open_price === m.price) return null;
  const from = `Hard Rock moved from ${odds(m.open_price)} to ${odds(m.price)} since the first prices today`;
  return implied(m.price) > implied(m.open_price)
    ? `${from}: the market is leaning your way, so the value has shrunk a little.`
    : `${from}: it pays more now. Worth checking the news before betting.`;
};

/** One sentence a non-bettor can follow: what Hard Rock pays, what it's worth, what that means. */
export const reason = (m: Market) =>
  `Hard Rock pays ${odds(m.price)}; the rest of the market makes it worth about ${odds(m.fair_american)}. ` +
  `That's about $${Math.round(m.edge * 100)} profit per $100 bet, on average over many bets like it.`;

function BetCard({ m, note, injury, onAdd }: { m: Pick; note?: Note; injury?: Injury; onAdd: () => void }) {
  const [math, setMath] = useState(false);
  const side = m.side === "Over" ? "OVER" : "UNDER";
  return (
    <article className="bet" aria-label={label(m)}>
      <header>
        <span>{m.matchup}</span>
        <span>{tipTime(m.commence_time)}</span>
      </header>
      <div className="bet-body">
        <h3>{m.player}</h3>
        <p className="bet-pick">
          <b>{side}</b> {m.point} {m.stat_label.toLowerCase()}
        </p>
        <div className="bet-quote">
          <div className="hr-quote">
            <small>Hard Rock pays</small>
            <b>{odds(m.price)}</b>
          </div>
          <div>
            <small>
              <Term k="worth">Worth</Term>
            </small>
            <b>{odds(m.fair_american)}</b>
          </div>
          <div>
            <small>Bet</small>
            <b>{money(m.stake)}</b>
          </div>
        </div>
        <p className="bet-strength">
          <Ramp edge={m.edge} />
          <span>
            {strength(m.edge)} <Term k="value">value</Term>
          </span>
        </p>
        <p className="bet-why">{reason(m)}</p>
        {movement(m) && <p className="bet-moved">{movement(m)}</p>}
        {injury && (
          <p className="bet-injury">
            <Warn /> <b>{injury.status}:</b> {injury.detail}
          </p>
        )}
        <NoteLine note={note} />
      </div>
      <footer>
        <button className="btn primary" onClick={onAdd}>
          <Plus /> Add to tonight's card
        </button>
        <button className="btn link" aria-expanded={math} onClick={() => setMath(!math)}>
          {math ? "Hide the math" : "Show the math"}
        </button>
      </footer>
      {math && (
        <div className="bet-math">
          <Proof m={m} />
        </div>
      )}
    </article>
  );
}

export function Tonight(props: {
  date: string | null;
  games: Game[] | null;
  suggested: Suggested | null;
  card: Card | null;
  notes: Record<string, Note>;
  sample: boolean;
  live: boolean;
  today: boolean;
  costPerGame: number;
  claudeKey: boolean;
  checkedAt: string | null;
  injuries: Injury[];
  recap: JournalEntry | null;
  cardPanel: ReactNode;
  onRefresh: () => Promise<void>;
  onAsk: () => Promise<unknown>;
  onAdd: (id: string, label: string) => Promise<unknown> | unknown;
  onAddAll: (exclude: string[]) => Promise<unknown>;
  onLock: () => void;
}) {
  const { date, games, suggested, card, notes, sample, live: oddsKey, today, costPerGame, claudeKey, checkedAt, cardPanel } =
    props;
  const [busy, setBusy] = useState<"odds" | "news" | "add" | null>(null);
  const live = useLive(today ? date : null);
  const run = async (what: "odds" | "news" | "add", f: () => Promise<unknown>) => {
    setBusy(what);
    await f();
    setBusy(null);
  };

  const legs = suggested?.legs ?? [];
  const skipped = legs.filter((m) => notes[m.id]?.verdict === "skip");
  const picks = legs.filter((m) => notes[m.id]?.verdict !== "skip");
  const total = picks.reduce((s, m) => s + m.stake, 0);
  const clearing = (games ?? []).flatMap((g) => g.markets).filter((m) => !m.blocked).length;
  const tips = (games ?? []).map((g) => g.commence_time).sort();
  const upcoming = (games ?? []).filter((g) => Date.parse(g.commence_time) > Date.now()).length;
  const onCard = card?.legs.length ?? 0;
  const hurt = new Map(props.injuries.map((i) => [i.name_key, i]));
  const graded = (card?.legs ?? []).filter((l) => l.status === "graded");
  const clvs = graded.filter((l) => l.clv != null).map((l) => l.clv!);
  const priced = clvs.length;
  const beat = clvs.filter((c) => c > 0).length;
  const avgClv = priced ? clvs.reduce((a, b) => a + b, 0) / priced : null;

  let state: ReactNode = null;
  if (!games) state = <p className="dim">Pricing tonight's games…</p>;
  else if (games.length === 0)
    state = (
      <div className="calm">
        <h2>No odds for this date yet</h2>
        <p>
          {today
            ? oddsKey
              ? "Pull tonight's odds once Hard Rock posts player props, usually by early afternoon."
              : "Add your ODDS_API_KEY to .env and restart the desk to pull tonight's odds."
            : "Nothing was priced on this date. Pick another night in the header."}
        </p>
      </div>
    );
  else if (card?.locked && graded.length === onCard)
    state = (
      <div className="calm results">
        <h2 className="results-figure">
          <span className={(avgClv ?? 0) >= 0 ? "pos" : "neg"}>
            {avgClv == null ? "—" : `${avgClv >= 0 ? "+" : "−"}${Math.abs(avgClv * 100).toFixed(1)}%`}
          </span>
          <small>
            <Term k="clv">beat the market</Term>, on average
          </small>
        </h2>
        <p>
          {beat} of {priced} {priced === 1 ? "bet" : "bets"} beat the market, and your prices beat the close by this
          much on average. That's the number to watch: over a night or two, wins and losses are mostly luck.
        </p>
      </div>
    );
  else if (card?.locked)
    state = (
      <div className="calm">
        <h2>Tonight's card is locked</h2>
        <p>Place each bet in the Hard Rock app at the price shown, then tick it off on your ticket.</p>
      </div>
    );
  else if (picks.length === 0)
    state = (
      <div className="calm">
        <h2>
          {onCard ? "Everything worth taking is on your card" : `Nothing worth betting ${today ? "tonight" : "that night"}`}
        </h2>
        <p>
          {onCard
            ? "Lock the card when you're ready, then place each bet at Hard Rock."
            : `Hard Rock's prices ${today ? "are" : "were"} fair. Passing is part of the plan: you only bet when the price is on your side.`}
        </p>
      </div>
    );

  return (
    <div className="tonight">
      <section className="tonight-main" aria-labelledby="tonight-h">
        <div className="head">
          <h1 id="tonight-h">{today || !date ? "Tonight" : dayLabel(date)}</h1>
          {games && games.length > 0 && date && (
            <p>
              {today ? `${dayLabel(date)} · ` : ""}
              {games.length} {games.length === 1 ? "game" : "games"}
              {today ? ` · first tip ${tipTime(tips[0])} ET` : ""}
              {sample && " · sample data"}
            </p>
          )}
        </div>

        {today && date && <StatusStrip date={date} />}
        <Scoreboard live={live} />

        {(oddsKey || (claudeKey && legs.length > 0)) && !card?.locked && (
          <div className="tonight-tools">
            {oddsKey && (
              <button className="btn" disabled={busy !== null || upcoming === 0} onClick={() => run("odds", props.onRefresh)}>
                {busy === "odds" ? "Pulling odds…" : `Refresh odds · ${upcoming * costPerGame} credits`}
              </button>
            )}
            {claudeKey && legs.length > 0 && (
              <button className="btn" disabled={busy !== null} onClick={() => run("news", props.onAsk)}>
                {busy === "news" ? "Claude is checking the news…" : checkedAt ? "Check news again" : "Check news with Claude"}
              </button>
            )}
            {checkedAt && <small>News checked {tipTime(checkedAt)} ET</small>}
          </div>
        )}

        {props.recap && today && (
          <div className="recap-card">
            <Entry e={props.recap} />
            <a href="#/ledger">Paper trading in the Ledger</a>
          </div>
        )}

        {state}

        {props.injuries.length > 0 && !card?.locked && (
          <section className="injury-report" aria-labelledby="inj-h">
            <h2 id="inj-h">
              <Warn /> Injury report for tonight's players
            </h2>
            <ul>
              {props.injuries.map((i) => (
                <li key={i.name_key}>
                  <span className={"pill " + (i.status === "Out" ? "no" : "warn")}>{i.status}</span>
                  <b>
                    {i.player} <small>{i.team}</small>
                  </b>
                  <span>{i.detail}</span>
                  {(i.status === "Out" || i.status === "Doubtful") && (
                    <a href="#/out">Teammates' props</a>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}

        {!card?.locked && picks.length > 0 && (
          <>
            <div className="picks-head">
              <h2>
                {picks.length} {picks.length === 1 ? "bet" : "bets"} worth taking
                <span>
                  {money(total)} total · Hard Rock pays more than each one is <Term k="worth">worth</Term>
                </span>
              </h2>
              <button
                className="btn primary"
                disabled={busy !== null}
                onClick={() => run("add", () => props.onAddAll(skipped.map((m) => m.id)))}
              >
                {busy === "add" ? "Adding…" : picks.length === 1 ? "Add it to tonight's card" : `Add all ${picks.length}`}
              </button>
            </div>
            <div className="bets">
              {picks.map((m) => (
                <BetCard
                  key={m.id}
                  m={m}
                  note={notes[m.id]}
                  injury={hurt.get(m.name_key)}
                  onAdd={() => props.onAdd(m.id, label(m))}
                />
              ))}
            </div>
          </>
        )}

        {!card?.locked && skipped.length > 0 && (
          <div className="skipped">
            <h2>
              <Warn /> Not taking {skipped.length === 1 ? "this one" : `these ${skipped.length}`}
            </h2>
            <ul>
              {skipped.map((m) => (
                <li key={m.id}>
                  <b>
                    {m.player} {m.side === "Over" ? "OVER" : "UNDER"} {m.point} {m.stat_label.toLowerCase()}
                  </b>
                  <span>{notes[m.id]?.note}</span>
                  <button className="btn link" onClick={() => props.onAdd(m.id, label(m))}>
                    Add anyway
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {games && games.length > 0 && (
          <a className="more" href="#/board">
            See every market ({clearing} clear the rules) <ChevronRight />
          </a>
        )}
      </section>

      <div className="tonight-card" id="your-card">
        {onCard > 0 && !card?.locked && (
          <p className="card-hint">
            <Check /> {onCard} on your card. Lock it when you're done, then place each bet at Hard Rock.
          </p>
        )}
        {cardPanel}
      </div>

      {/* Phones: the lock stays one tap away instead of below every bet card. */}
      {card && onCard > 0 && !card.locked && (
        <div className="lockbar" role="region" aria-label="Your card">
          <a href="#your-card" onClick={(e) => (e.preventDefault(), document.getElementById("your-card")?.scrollIntoView())}>
            <b>
              {onCard} on your card · {money(card.risk)}
            </b>
            <small>
              {card.can_lock ? "Review" : "Fix a check before locking"} <ChevronRight />
            </small>
          </a>
          <button className="btn primary" disabled={!card.can_lock} onClick={props.onLock}>
            <Lock /> Lock
          </button>
        </div>
      )}
    </div>
  );
}
