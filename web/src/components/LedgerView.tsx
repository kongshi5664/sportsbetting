import { useEffect, useState } from "react";
import { api } from "../api";
import { dayLabel, odds, pct, share, signedMoney } from "../format";
import { Warn } from "../icons";
import type { Ledger, LedgerBet } from "../types";

const MIN_BETS = 30;

export function LedgerView({ onError }: { onError: (e: unknown) => void }) {
  const [source, setSource] = useState<"live" | "backtest">("live");
  const [data, setData] = useState<Ledger | null>(null);

  useEffect(() => {
    setData(null);
    api.ledger(source).then(setData).catch(onError);
  }, [source, onError]);

  const s = data?.summary;
  const few = s && s.n < MIN_BETS;

  return (
    <section aria-labelledby="ledger-h">
      <div className="head">
        <h1 id="ledger-h">Ledger &amp; CLV</h1>
        <div className="seg" role="group" aria-label="Which bets">
          <button aria-pressed={source === "live"} onClick={() => setSource("live")}>
            Live bets
          </button>
          <button aria-pressed={source === "backtest"} onClick={() => setSource("backtest")}>
            Backtest · simulated
          </button>
        </div>
      </div>

      {!data || !s ? (
        <p className="dim">Loading the ledger…</p>
      ) : (
        <>
          {source === "backtest" && (
            <div className="notice">
              <Warn />
              <p>
                Simulated bets from the latest backtest report, not money you placed. Judge rules by these, judge yourselves
                by the live ledger.
              </p>
            </div>
          )}
          {s.n === 0 ? (
            <div className="empty">
              <h2>No graded bets yet</h2>
              <p>Lock a card on the Edge Board. Bets are graded here once the game is final and the closing price is in.</p>
            </div>
          ) : (
            <>
              {few && (
                <div className="notice">
                  <Warn />
                  <p>
                    Too few bets to judge (n={s.n}). CLV needs a few hundred bets before it means much; results need even
                    more.
                  </p>
                </div>
              )}
              <div className="lead">
                <div>
                  <span>Average CLV</span>
                  <div className={"big " + ((s.avg_clv ?? 0) >= 0 ? "pos" : "neg")}>{pct(s.avg_clv)}</div>
                  <small>
                    {s.clv_ci95 ? `95% range ${pct(s.clv_ci95[0])} to ${pct(s.clv_ci95[1])}` : "range needs 2+ bets"}
                  </small>
                </div>
                <div>
                  <span>Beat the close</span>
                  <div className="mid">{share(s.beat_close)}</div>
                  <small>of {s.n.toLocaleString()} bets</small>
                </div>
                <div className="secondary">
                  <span>Record</span>
                  <span>Units</span>
                  <span>Est. edge</span>
                  <b>
                    {s.wins}–{s.losses}
                  </b>
                  <b>{s.units >= 0 ? "+" : "−"}{Math.abs(s.units).toFixed(1)}</b>
                  <b>{pct(s.avg_edge)}</b>
                  <small style={{ gridColumn: "1 / -1" }}>
                    Results are mostly luck at this sample size. Estimated edge runs above realized CLV; the gap is the
                    haircut.
                  </small>
                </div>
              </div>
              <Chart bets={data.bets} />
              <div className="split">
                <div>
                  <h2>By night</h2>
                  <div className="table-scroll">
                    <table className="plain">
                      <thead>
                        <tr>
                          <th className="l">Night</th>
                          <th>Bets</th>
                          <th>Avg CLV</th>
                          <th>Result</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[...data.nights]
                          .reverse()
                          .slice(0, 14)
                          .map((n) => (
                            <tr key={n.date}>
                              <td className="l">{dayLabel(n.date)}</td>
                              <td>{n.bets}</td>
                              <td className={(n.avg_clv ?? 0) >= 0 ? "pos" : "neg"}>{pct(n.avg_clv)}</td>
                              <td>{signedMoney(n.pnl)}</td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                </div>
                <div>
                  <h2>Recent bets</h2>
                  <div className="table-scroll">
                    <table className="plain">
                      <thead>
                        <tr>
                          <th className="l">Bet</th>
                          <th className="wide">Took</th>
                          <th className="wide">Closed</th>
                          <th>CLV</th>
                          <th className="l">Result</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[...data.bets]
                          .reverse()
                          .slice(0, 14)
                          .map((b, i) => (
                            <tr key={i}>
                              <td className="l">
                                {b.bet}
                                <span className="dim"> · {dayLabel(b.date)}</span>
                              </td>
                              <td className="wide">{odds(b.price)}</td>
                              <td className="wide">{odds(b.close_price)}</td>
                              <td className={(b.clv ?? 0) >= 0 ? "pos" : "neg"}>{pct(b.clv)}</td>
                              <td className="l">
                                <span className={"result " + b.result}>{b.result}</span>
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </>
          )}
        </>
      )}
    </section>
  );
}

/** Cumulative result against what CLV says you should have made, on one shared scale. */
function Chart({ bets }: { bets: LedgerBet[] }) {
  if (bets.length < 2) return null;
  // One point per night, so the line reads against the By night table.
  let a = 0,
    e = 0;
  const nights: string[] = [];
  const pts: number[][] = [];
  for (const b of bets) {
    a += b.pnl;
    e += b.stake * (b.clv ?? 0);
    if (nights.at(-1) === b.date) pts[pts.length - 1] = [a, e];
    else {
      nights.push(b.date);
      pts.push([a, e]);
    }
  }
  if (pts.length < 2) return null;
  // Drawn narrower on phones so the axis labels stay readable.
  const W = matchMedia("(max-width: 860px)").matches ? 400 : 1280,
    H = 236,
    P = 44;
  const lo = Math.min(0, ...pts.flat()),
    hi = Math.max(0, ...pts.flat());
  const pad = (hi - lo) * 0.08 || 1;
  const y = (v: number) => H - 36 - ((v - (lo - pad)) / (hi + pad - (lo - pad))) * (H - 56);
  const x = (i: number) => P + (i / (pts.length - 1)) * (W - P - 12);
  const line = (k: 0 | 1) => pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(p[k]).toFixed(1)}`).join("");
  // Zero always gets a label; the extremes only when they sit clear of it.
  const ticks = [0, lo, hi].filter((v, i, arr) => arr.indexOf(v) === i && (v === 0 || Math.abs(y(v) - y(0)) > 18));
  return (
    <figure className="chart" aria-label={`Cumulative result ${signedMoney(a)} against CLV-expected ${signedMoney(e)}`}>
      <div className="legend">
        <span>
          <i />
          Actual result ({signedMoney(a)})
        </span>
        <span>
          <i className="e" />
          What CLV says you earned ({signedMoney(e)})
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} role="img">
        {ticks.map((t) => (
          <g key={t}>
            <line className={t === 0 ? "axis" : "grid"} x1={P} x2={W - 12} y1={y(t)} y2={y(t)} />
            <text x={P - 8} y={y(t) + 4} textAnchor="end">
              {signedMoney(t).replace(".00", "")}
            </text>
          </g>
        ))}
        {[...new Set([0, Math.floor((pts.length - 1) / 2), pts.length - 1])].map((i, k, arr) => (
          <text key={i} x={x(i)} y={H - 2} textAnchor={k === 0 ? "start" : k === arr.length - 1 ? "end" : "middle"}>
            {dayLabel(nights[i])}
          </text>
        ))}
        <path className="expected" d={line(1)} />
        <path className="actual" d={line(0)} />
        <circle cx={x(pts.length - 1)} cy={y(a)} r={4.5} fill="var(--zone)" />
      </svg>
    </figure>
  );
}
