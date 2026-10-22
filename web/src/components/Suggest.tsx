import { useState } from "react";
import { money, odds, pct, pick, tipTime } from "../format";
import { Check, Plus, Warn } from "../icons";
import type { Note, Suggested } from "../types";
import { label } from "./EdgeBoard";

const VERDICT: Record<Note["verdict"], { cls: string; text: string }> = {
  clear: { cls: "ok", text: "Claude: clear" },
  caution: { cls: "warn", text: "Claude: caution" },
  skip: { cls: "no", text: "Claude: skip" },
};

const host = (url: string) => {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "source";
  }
};

/** Claude's note on one leg: advice shown beside the bet, never a rule. */
export function NoteLine({ note }: { note?: Note }) {
  if (!note) return null;
  const v = VERDICT[note.verdict];
  return (
    <p className={"note-line " + note.verdict}>
      <span className={"pill " + v.cls}>
        {note.verdict === "clear" ? <Check /> : <Warn />} {v.text}
      </span>
      <span>
        {note.note}
        {note.sources.slice(0, 2).map((u) => (
          <a key={u} href={u} target="_blank" rel="noreferrer">
            {host(u)}
          </a>
        ))}
      </span>
    </p>
  );
}

/** Tonight's suggested additions, and the one place to ask Claude about them. */
export function SuggestBlock(props: {
  suggested: Suggested | null;
  notes: Record<string, Note>;
  claudeKey: boolean;
  checkedAt: string | null;
  onAddAll: (exclude: string[]) => Promise<unknown>;
  onAdd: (id: string, label: string) => Promise<unknown> | unknown;
  onAsk: () => Promise<unknown>;
  hasLegs: boolean;
}) {
  const { suggested, notes, claudeKey, checkedAt, onAddAll, onAdd, onAsk, hasLegs } = props;
  const [busy, setBusy] = useState<"add" | "ask" | null>(null);
  const run = async (what: "add" | "ask", f: () => Promise<unknown>) => {
    setBusy(what);
    await f();
    setBusy(null);
  };
  const legs = suggested?.legs ?? [];
  // One tap never adds a leg Claude flagged "skip"; it stays listed so it can be added by hand.
  const skipped = legs.filter((m) => notes[m.id]?.verdict === "skip").map((m) => m.id);
  const taking = legs.length - skipped.length;

  return (
    <section className="suggest" aria-label="Suggested for tonight">
      {legs.length > 0 && (
        <>
          <div className="suggest-head">
            <div>
              <h3>Suggested</h3>
              <p>
                {legs.length} more {legs.length === 1 ? "leg" : "legs"} · {money(suggested!.risk)} · best edges that fit
                every rule
                {skipped.length > 0 && ` · Add leaves out the ${skipped.length} Claude flagged skip`}
              </p>
            </div>
            <button
              className="btn primary"
              disabled={busy !== null || taking === 0}
              onClick={() => run("add", () => onAddAll(skipped))}
            >
              {busy === "add" ? "Adding…" : skipped.length ? `Add ${taking}` : "Add all"}
            </button>
          </div>
          <ul className="legs">
            {legs.map((m) => (
              <li key={m.id} className="leg">
                <div className="what">
                  <b>
                    {m.player} · {m.stat_label} {pick(m.side, m.point)}
                  </b>
                  <small>
                    {m.matchup} {tipTime(m.commence_time)} · fair {odds(m.fair_american)}
                  </small>
                </div>
                <div className="price">
                  <b>{odds(m.price)}</b>
                  <small>
                    {money(m.stake)} · <span className="pos">{pct(m.edge)}</span>
                  </small>
                </div>
                <button className="x add-one" onClick={() => onAdd(m.id, label(m))} aria-label={`Add ${label(m)}`}>
                  <Plus />
                </button>
                <NoteLine note={notes[m.id]} />
              </li>
            ))}
          </ul>
        </>
      )}
      {(legs.length > 0 || hasLegs) && (
        <div className="ask">
          {claudeKey ? (
            <>
              <button className="btn" disabled={busy !== null} onClick={() => run("ask", onAsk)}>
                {busy === "ask" ? "Claude is checking the news…" : checkedAt ? "Check news again" : "Check news with Claude"}
              </button>
              <small>
                {checkedAt
                  ? `Checked ${tipTime(checkedAt)} ET. Notes are advice; the price and the rules still decide.`
                  : "Looks for injury and lineup news on every leg here. A few cents per check."}
              </small>
            </>
          ) : (
            <small>Add ANTHROPIC_API_KEY to .env and restart the desk to get Claude's news check on each leg.</small>
          )}
        </div>
      )}
    </section>
  );
}
