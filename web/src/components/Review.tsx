import { useEffect, useState } from "react";
import { api } from "../api";
import { pct } from "../format";
import { Check, Warn } from "../icons";
import type { Finding, Review, Stat } from "../types";
import { Term } from "./Term";

const describe = (p: NonNullable<Finding["proposal"]>) =>
  p.type === "strategy"
    ? `Use this strategy for the real card: ${Object.entries(p.overrides ?? {})
        .map(([k, v]) => (k === "min_edge" ? `minimum value ${Math.round(v * 100)}%` : `${k.replace("_", " ")} ${v}`))
        .join(", ")}.`
    : p.type === "rule_status"
    ? p.value === "confirmed"
      ? "Promote it: it starts shaping tonight's card."
      : p.value === "retired"
        ? "Retire it: it stops being measured."
        : "Move it back to testing: it stops shaping the card."
    : p.key === "min"
      ? `Raise the minimum value to ${Math.round(Number(p.value) * 100)}%.`
      : `Set the Pinnacle weighting to ${Math.round(Number(p.value) * 100)}%.`;

const side = (label: string, s?: Stat) =>
  s && s.n > 0 ? `${label}: ${s.n} bets, ${pct(s.avg)} vs. the close` : `${label}: no bets yet`;

function Row({ f, onApply, onDismiss }: { f: Finding; onApply: () => void; onDismiss: () => void }) {
  const [ask, setAsk] = useState(false);
  return (
    <li className={"finding" + (f.proposal && !f.decided ? " has-proposal" : "")}>
      <h3>{f.title}</h3>
      <p className="verdict">{f.verdict}.</p>
      {f.matched && (
        <p className="numbers">
          {side(f.area === "setting" ? "Priced with Pinnacle" : "Bets it matches", f.matched)} ·{" "}
          {side(f.area === "setting" ? "Without" : "Other bets", f.rest)}
        </p>
      )}
      {f.groups && (
        <p className="numbers">
          {f.groups.map(([name, s]) => `${name}: ${s.n ? `${s.n} bets, ${pct(s.avg)}` : "none"}`).join(" · ")}
        </p>
      )}
      {f.proposal &&
        (f.decided ? (
          <p className="decided">
            <Check /> {f.decided === "applied" ? "Applied this week" : "Set aside this week"}
          </p>
        ) : ask ? (
          <div className="confirm">
            <p>{describe(f.proposal)} Apply it?</p>
            <button className="btn" onClick={onApply}>
              Yes, apply
            </button>
            <button className="btn link" onClick={() => setAsk(false)}>
              Cancel
            </button>
          </div>
        ) : (
          <div className="proposal">
            <p>
              <b>Proposal:</b> {describe(f.proposal)}
            </p>
            <button className="btn primary" onClick={() => setAsk(true)}>
              Apply
            </button>
            <button className="btn link" onClick={onDismiss}>
              Not now
            </button>
          </div>
        ))}
    </li>
  );
}

/** The weekly review: what the graded bets say. Proposals change nothing until applied here. */
export function ReviewPanel({ onError, say, onChanged }: { onError: (e: unknown) => void; say: (t: string) => void; onChanged: () => void }) {
  const [rep, setRep] = useState<Review | null>(null);

  useEffect(() => {
    api.review().then(setRep).catch(onError);
  }, [onError]);

  const act = async (p: Promise<Review>, msg: string) => {
    try {
      setRep(await p);
      say(msg);
      onChanged();
    } catch (e) {
      onError(e);
    }
  };

  if (!rep) return <p className="dim">Reading the graded bets…</p>;
  const b = rep.bets;
  const open = rep.findings.filter((f) => f.proposal && !f.decided).length;

  return (
    <section className="review rulegroup" aria-labelledby="review-h">
      <h2 id="review-h">
        This week's review{" "}
        <span>
          {b.n} graded {b.n === 1 ? "bet" : "bets"}
          {b.n > 0 && ` · ${pct(b.avg)} vs. the close on average`}
          {open > 0 && ` · ${open} ${open === 1 ? "proposal" : "proposals"}`}
        </span>
      </h2>
      <p className="review-lede">
        Judged by whether you <Term k="clv">beat the market</Term>, never by wins and losses. A proposal needs {rep.min_n}+
        graded bets on each side of a comparison and a gap clear of the noise. Nothing changes until you apply it.
      </p>
      {b.n < rep.min_n && (
        <div className="notice">
          <Warn />
          <p>
            Still collecting: {b.n} of the {rep.min_n}+ graded bets the first comparisons need. At about 4 bets a night,
            the first real proposals arrive in a few weeks.
          </p>
        </div>
      )}
      <ul className="findings">
        {rep.findings.map((f) => (
          <Row
            key={f.id}
            f={f}
            onApply={() => act(api.applyProposal(f.id), `Applied: ${f.title}`)}
            onDismiss={() => act(api.dismissProposal(f.id), `Set aside for this week: ${f.title}`)}
          />
        ))}
      </ul>
    </section>
  );
}
