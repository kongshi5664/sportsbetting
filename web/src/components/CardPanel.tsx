import { useEffect, useRef, useState, type ReactNode } from "react";
import { money, odds, pct, pick, tipTime } from "../format";
import { Check, Cross, Lock } from "../icons";
import type { Card, Leg, Note } from "../types";
import { Progress, useLive } from "./Live";
import { NoteLine } from "./Suggest";
import { Term } from "./Term";

const STAT: Record<string, string> = {
  player_points: "Points",
  player_rebounds: "Rebounds",
  player_assists: "Assists",
  player_threes: "Threes",
  player_blocks: "Blocks",
};
const matchup = (l: Leg) =>
  l.away_team ? `${l.away_team} @ ${l.home_team}${l.commence_time ? " " + tipTime(l.commence_time) : ""}` : "";
const legLabel = (l: Leg) => `${l.player} ${STAT[l.market]?.toLowerCase()} ${pick(l.side, l.point)}`;
const fairAmerican = (p: number) => (p >= 0.5 ? -Math.round((100 * p) / (1 - p)) : Math.round((100 * (1 - p)) / p));

/** After the games: beating the market leads, the record follows. */
function NightClv({ legs }: { legs: Leg[] }) {
  const priced = legs.filter((l) => l.clv != null);
  const avg = priced.length ? priced.reduce((s, l) => s + l.clv!, 0) / priced.length : null;
  const beat = priced.filter((l) => l.clv! > 0).length;
  const w = legs.filter((l) => l.result === "win").length;
  const lo = legs.filter((l) => l.result === "loss").length;
  return (
    <div className="risk">
      <div className="risk-line">
        <span>
          <Term k="clv">Beat the market</Term>
        </span>
        <b className={avg == null ? "" : avg >= 0 ? "pos" : "neg"}>{pct(avg)}</b>
      </div>
      <p>
        {beat} of {priced.length} beat the market · record {w}–{lo} (wins and losses are mostly luck; beating the
        market is the score)
      </p>
    </div>
  );
}

/** The board's market id for a leg, which is how Claude's notes are keyed. */
export const legMarketId = (l: Leg) => `${l.event_id}|${l.market}|${l.name_key}|${l.point}|${l.side}`;

export function CardPanel(props: {
  card: Card;
  variant: "dock" | "page";
  notes: Record<string, Note>;
  suggest: ReactNode;
  onRemove: (id: number, label: string) => void;
  onClear: () => void;
  onLock: () => void;
  onUnlock: () => void;
  onPlaced: (id: number, placed: boolean) => void;
}) {
  const { card, variant, notes, suggest, onRemove, onClear, onLock, onUnlock, onPlaced } = props;
  const [confirm, setConfirm] = useState<"clear" | "unlock" | null>(null);
  const [settle, setSettle] = useState(false);
  const wasLocked = useRef(card.locked);

  // The settle plays once, at the moment the card becomes a ticket.
  useEffect(() => {
    if (card.locked && !wasLocked.current) setSettle(true);
    wasLocked.current = card.locked;
    setConfirm(null);
  }, [card.locked]);

  const failing = new Map<number, string[]>();
  for (const ch of card.checks.filter((c) => !c.ok))
    for (const id of ch.legs) failing.set(id, [...(failing.get(id) ?? []), ch.fail]);

  const fill = Math.min(1, card.risk / card.cap);
  const over = card.risk > card.cap;
  const n = card.legs.length;
  const graded = card.legs.filter((l) => l.status === "graded");
  const placed = card.legs.filter((l) => l.placed).length;
  // Once locked, follow each open leg live from the box score until it is graded.
  const live = useLive(card.locked && graded.length < n ? card.date : null);

  const head = (
    <div className="card-head">
      <h2>{card.locked ? "Tonight's Ticket" : "Tonight's Card"}</h2>
      <span>
        {n} {n === 1 ? "bet" : "bets"} · Hard Rock prices
      </span>
    </div>
  );

  const risk = (
    <div className="risk">
      <div className="risk-line">
        <span>Risk</span>
        <b>
          {money(card.risk)}
          <small>of {money(card.cap)} cap</small>
        </b>
      </div>
      <div
        className={"capacity" + (over ? " over" : "")}
        role="meter"
        aria-label="Risk against the nightly cap"
        aria-valuemin={0}
        aria-valuemax={card.cap}
        aria-valuenow={card.risk}
      >
        <i style={{ width: `${fill * 100}%` }} />
      </div>
      <p>
        {over ? `${money(card.risk - card.cap)} over the cap` : `${money(card.cap - card.risk)} of room left tonight`}
      </p>
    </div>
  );

  if (card.locked) {
    return (
      <aside className={"card ticket " + variant} aria-label="Tonight's ticket">
        {head}
        <div className="stub">
          <span>
            <Lock style={{ width: 12, height: 12, verticalAlign: -1 }} /> Locked{" "}
            {card.locked_at ? tipTime(card.locked_at) : ""} ET
          </span>
          <span>
            {graded.length
              ? `${graded.length} of ${n} graded`
              : `${placed} of ${n} placed at Hard Rock`}
          </span>
        </div>
        <ul className="legs">
          {card.legs.map((l, i) => (
            <li
              key={l.id}
              className={"leg" + (settle ? " settle" : "") + (l.placed ? " placed" : "")}
              style={{ ["--i" as string]: i }}
            >
              {l.status === "graded" ? (
                <span className={"result " + l.result}>{l.result}</span>
              ) : (
                <input
                  type="checkbox"
                  checked={!!l.placed}
                  onChange={(e) => onPlaced(l.id, e.target.checked)}
                  aria-label={`Placed ${legLabel(l)} at Hard Rock`}
                />
              )}
              <div className="what">
                <b>
                  {l.player} · {STAT[l.market]} {pick(l.side, l.point)}
                </b>
                <small className="meta">
                  <span>{matchup(l)}</span>
                  {l.status === "graded" ? (
                    <>
                      <span>took {odds(l.price)}</span>
                      <span>closed {odds(l.close_price)}</span>
                      {l.actual != null && <span>finished {l.actual}</span>}
                    </>
                  ) : (
                    <>
                      <span>worth {odds(fairAmerican(l.fair))}</span>
                      <span>value {pct(l.edge)}</span>
                      {live?.bets[String(l.id)] && live.bets[String(l.id)].state !== "pre" && (
                        <span className="leg-live">
                          <Progress p={live.bets[String(l.id)]} point={l.point} side={l.side} />
                        </span>
                      )}
                    </>
                  )}
                </small>
              </div>
              {l.status === "graded" ? (
                <div className="price">
                  <b className={l.clv == null ? "" : l.clv >= 0 ? "pos" : "neg"}>{l.result === "void" ? "Void" : pct(l.clv)}</b>
                  <small>vs. market · {money(l.stake)}</small>
                </div>
              ) : (
                <div className="price">
                  <b>{odds(l.price)}</b>
                  <small>{money(l.stake)}</small>
                </div>
              )}
              {l.status !== "graded" && <NoteLine note={notes[legMarketId(l)]} />}
            </li>
          ))}
        </ul>
        {graded.length === n ? <NightClv legs={card.legs} /> : risk}
        {graded.length < n &&
          (confirm === "unlock" ? (
            <div className="confirm">
              <p>Unlock the card? Placed ticks are cleared.</p>
              <button className="btn" onClick={onUnlock}>
                Unlock
              </button>
              <button className="btn link" onClick={() => setConfirm(null)}>
                Keep locked
              </button>
            </div>
          ) : (
            <p className="reason">
              Closing prices are captured at tip to see whether you beat the market.{" "}
              <button className="btn link" onClick={() => setConfirm("unlock")}>
                Unlock card
              </button>
            </p>
          ))}
      </aside>
    );
  }

  return (
    <aside className={"card " + variant} aria-label="Tonight's card">
      {head}
      {n === 0 ? (
        <p className="none">No bets on the card yet.</p>
      ) : (
        <ul className="legs">
          {card.legs.map((l) => {
            const why = failing.get(l.id);
            return (
              <li key={l.id} className={"leg" + (why ? " fail" : "")}>
                <div className="what">
                  <b>
                    {l.player} · {STAT[l.market]} {pick(l.side, l.point)}
                  </b>
                  <small>
                    {matchup(l)} · worth {odds(fairAmerican(l.fair))}
                  </small>
                </div>
                <div className="price">
                  <b>{odds(l.price)}</b>
                  <small>
                    {money(l.stake)} · <span className={l.edge >= 0 ? "pos" : "neg"}>{pct(l.edge)}</span>
                  </small>
                </div>
                <button className="x" onClick={() => onRemove(l.id, legLabel(l))} aria-label={`Remove ${legLabel(l)}`}>
                  <Cross />
                </button>
                {why && (
                  <span className="why">
                    <Cross /> {why.join(" · ")}
                  </span>
                )}
                <NoteLine note={notes[legMarketId(l)]} />
              </li>
            );
          })}
        </ul>
      )}
      {suggest}
      {risk}
      <ul className="checks" aria-label="Checks before locking">
        {card.checks.map((c) => (
          <li key={c.text} className={c.ok ? "y" : "n"}>
            {c.ok ? <Check /> : <Cross />}
            <span>
              {c.text}
              {!c.ok && c.legs.length > 0 && (
                <small>
                  {c.legs
                    .map((id) => card.legs.find((l) => l.id === id))
                    .filter(Boolean)
                    .map((l) => legLabel(l!))
                    .join(", ")}
                </small>
              )}
            </span>
          </li>
        ))}
      </ul>
      {confirm === "clear" ? (
        <div className="confirm">
          <p>
            Clear all {n} {n === 1 ? "bet" : "bets"}?
          </p>
          <button className="btn danger" onClick={onClear}>
            Clear card
          </button>
          <button className="btn link" onClick={() => setConfirm(null)}>
            Keep them
          </button>
        </div>
      ) : (
        <div className="card-actions">
          <button className="lock" disabled={!card.can_lock} onClick={onLock} aria-describedby="lock-why">
            <Lock /> Lock card{n ? ` · ${money(card.risk)}` : ""}
          </button>
          <button className="clear" disabled={n === 0} onClick={() => setConfirm("clear")}>
            Clear
          </button>
        </div>
      )}
      <p className="reason" id="lock-why">
        {n === 0
          ? "The card can be locked once it has a bet."
          : card.can_lock
            ? "Locking freezes these prices. Then place each bet by hand in the Hard Rock app."
            : "Fix the failed checks above to lock. Use a bet's remove button to take it off."}
      </p>
    </aside>
  );
}
