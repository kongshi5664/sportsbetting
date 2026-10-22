import { useEffect, useState } from "react";
import { api } from "../api";
import { pct } from "../format";
import { Warn } from "../icons";
import type { Rule, Rules } from "../types";

const MIN_BETS = 30;
const GROUPS: { title: string; sub: string; test: (r: Rule) => boolean }[] = [
  { title: "Always on", sub: "Gates every bet passes", test: (r) => r.kind === "gate" },
  { title: "Confirmed", sub: "Enforced on the card", test: (r) => r.kind !== "gate" && r.status === "confirmed" },
  { title: "Testing", sub: "Measured, not enforced", test: (r) => r.status === "testing" },
  { title: "Retired", sub: "Tried and dropped", test: (r) => r.kind !== "gate" && r.status === "retired" },
];

export function Rulebook({ onError, say }: { onError: (e: unknown) => void; say: (t: string) => void }) {
  const [data, setData] = useState<Rules | null>(null);
  const [ask, setAsk] = useState<{ id: string; status: string } | null>(null);

  useEffect(() => {
    api.rules().then(setData).catch(onError);
  }, [onError]);

  const change = async (id: string, status: string, name: string) => {
    try {
      setData(await api.setStatus(id, status));
      setAsk(null);
      say(`“${name}” is now ${status}.`);
    } catch (e) {
      onError(e);
    }
  };

  const sample = data?.report?.db.includes("sample");

  return (
    <section aria-labelledby="rules-h">
      <div className="head">
        <h1 id="rules-h">Rulebook</h1>
        {data?.report && (
          <p>
            Verdicts from the backtest of {new Date(data.report.generated).toLocaleDateString()} on {data.report.db},
            held-out season {data.report.holdout}
          </p>
        )}
      </div>
      {sample && (
        <div className="notice">
          <Warn />
          <p>
            These verdicts come from sample data, a fake world with planted edges. They prove the harness works; don't
            promote rules on them.
          </p>
        </div>
      )}
      {!data ? (
        <p className="dim">Loading rules…</p>
      ) : (
        GROUPS.map((g) => {
          const rules = data.rules.filter(g.test);
          if (!rules.length) return null;
          return (
            <div key={g.title} className="rulegroup">
              <h2>
                {g.title} <span>{g.sub}</span>
              </h2>
              {rules.map((r) => (
                <RuleRow key={r.id} r={r} ask={ask} setAsk={setAsk} change={change} />
              ))}
            </div>
          );
        })
      )}
    </section>
  );
}

function RuleRow({
  r,
  ask,
  setAsk,
  change,
}: {
  r: Rule;
  ask: { id: string; status: string } | null;
  setAsk: (a: { id: string; status: string } | null) => void;
  change: (id: string, status: string, name: string) => void;
}) {
  const bt = r.backtest;
  const n = bt?.results.all.matched.n ?? 0;
  const few = bt && n < MIN_BETS;
  const verdict = few ? "too few bets" : bt?.verdict;
  const cls = verdict === "promote" ? "ok" : verdict === "retire" ? "no" : "test";
  const gap = (k: "train" | "holdout") => {
    const m = bt?.results[k];
    return m && m.matched.avg_clv != null && m.rest.avg_clv != null ? m.matched.avg_clv - m.rest.avg_clv : null;
  };
  const moves: { status: string; label: string; text: string }[] =
    r.kind === "gate"
      ? []
      : r.status === "testing"
        ? [
            { status: "confirmed", label: "Promote", text: "It will start shaping tonight's card." },
            { status: "retired", label: "Retire", text: "It stops being measured." },
          ]
        : [{ status: "testing", label: "Back to testing", text: "It stops affecting the card." }];

  return (
    <div className="rule">
      <div>
        <h3>{r.name}</h3>
        {r.note && <p className="note">{r.note}</p>}
        {r.kind === "gate" && r.params && (
          <p className="note">
            {Object.entries(r.params)
              .map(([k, v]) => `${k} ${v}`)
              .join(" · ")}{" "}
            · change in rules.json
          </p>
        )}
      </div>
      <div className="ev">
        {bt ? (
          <>
            <table>
              <thead>
                <tr>
                  <th className="l">Sample</th>
                  <th>Bets</th>
                  <th>Matched CLV</th>
                  <th>Gap</th>
                </tr>
              </thead>
              <tbody>
                {(["train", "holdout"] as const).map((k) => (
                  <tr key={k}>
                    <td className="l">{k === "train" ? "Earlier" : "Holdout"}</td>
                    <td>{bt.results[k].matched.n}</td>
                    <td>{pct(bt.results[k].matched.avg_clv)}</td>
                    <td>{pct(gap(k))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="why">
              <span className={"pill " + cls}>{verdict}</span> {few ? `Only ${n} matched bets; want ${MIN_BETS}+.` : bt.why}
            </p>
          </>
        ) : (
          <p className="dim">{r.status === "testing" ? "Not in the latest backtest yet." : ""}</p>
        )}
      </div>
      <div className="acts">
        {moves.map((m) => (
          <button key={m.status} className="btn" onClick={() => setAsk({ id: r.id, status: m.status })}>
            {m.label}
          </button>
        ))}
      </div>
      {ask?.id === r.id && (
        <div className="confirm">
          <p>
            {moves.find((m) => m.status === ask.status)?.label} “{r.name}”?{" "}
            {moves.find((m) => m.status === ask.status)?.text}
          </p>
          <button className="btn" onClick={() => change(r.id, ask.status, r.name)}>
            Yes, {moves.find((m) => m.status === ask.status)?.label.toLowerCase()}
          </button>
          <button className="btn link" onClick={() => setAsk(null)}>
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}
