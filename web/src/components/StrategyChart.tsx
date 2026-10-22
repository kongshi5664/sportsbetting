import { useEffect, useState } from "react";
import { api } from "../api";
import { dayLabel, pct, signedMoney } from "../format";
import type { StrategyHistory } from "../types";

const W = 640;
const H = 220;
const PAD = { l: 52, r: 12, t: 12, b: 26 };

/** Each paper strategy night by night: running profit, or running average CLV with the control line.
 *  One measure at a time (no second axis); colors follow the strategy, never its rank. */
export function StrategyChart() {
  const [data, setData] = useState<StrategyHistory[] | null>(null);
  const [measure, setMeasure] = useState<"clv" | "pnl">("clv");
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    api.paperHistory().then((r) => setData(r.strategies)).catch(() => setData([]));
  }, []);

  if (!data) return null;
  const series = data.filter((s) => (measure === "clv" || s.id !== "_all") && s.nights.length > 0);
  const dates = [...new Set(series.flatMap((s) => s.nights.map((n) => n.date)))].sort();

  const head = (
    <div className="chart-head">
      <h2 className="journal-h">Strategies over time</h2>
      <div className="seg small" role="group" aria-label="Measure">
        <button aria-pressed={measure === "clv"} onClick={() => setMeasure("clv")}>
          Vs. the close
        </button>
        <button aria-pressed={measure === "pnl"} onClick={() => setMeasure("pnl")}>
          Profit
        </button>
      </div>
    </div>
  );
  if (dates.length === 0)
    return (
      <div className="strategy-chart">
        {head}
        <p className="dim">The chart starts after the first graded night (tomorrow morning).</p>
      </div>
    );

  const val = (n: StrategyHistory["nights"][number]) => (measure === "clv" ? n.clv : n.pnl);
  const vals = series.flatMap((s) => s.nights.map(val)).filter((v): v is number => v != null);
  let lo = Math.min(0, ...vals);
  let hi = Math.max(0, ...vals);
  if (hi - lo < 1e-9) (hi += measure === "clv" ? 0.01 : 10), (lo -= measure === "clv" ? 0.01 : 10);
  const x = (i: number) => PAD.l + (dates.length === 1 ? (W - PAD.l - PAD.r) / 2 : (i * (W - PAD.l - PAD.r)) / (dates.length - 1));
  const y = (v: number) => PAD.t + ((hi - v) * (H - PAD.t - PAD.b)) / (hi - lo);
  const fmt = (v: number | null) => (v == null ? "—" : measure === "clv" ? pct(v) : signedMoney(v));
  const ticks = [hi, (hi + lo) / 2, lo];

  return (
    <div className="strategy-chart">
      {head}
      <ul className="legend">
        {series.map((s) => (
          <li key={s.id} className={"s-" + s.id}>
            <i aria-hidden="true" />
            {s.name}
          </li>
        ))}
      </ul>
      <div className="chart-wrap" onMouseLeave={() => setHover(null)}>
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Strategies, ${measure === "clv" ? "average vs. the close" : "profit"} by night`}>
          {ticks.map((t, i) => (
            <g key={i} className="grid">
              <line x1={PAD.l} x2={W - PAD.r} y1={y(t)} y2={y(t)} />
              <text x={PAD.l - 6} y={y(t) + 4} textAnchor="end">
                {fmt(t)}
              </text>
            </g>
          ))}
          <line className="zero" x1={PAD.l} x2={W - PAD.r} y1={y(0)} y2={y(0)} />
          {dates.map((d, i) =>
            i === 0 || i === dates.length - 1 || dates.length <= 7 ? (
              <text key={d} className="xlab" x={x(i)} y={H - 6} textAnchor="middle">
                {dayLabel(d)}
              </text>
            ) : null,
          )}
          {series.map((s) => {
            const pts = s.nights
              .map((n) => [dates.indexOf(n.date), val(n)] as const)
              .filter((p): p is readonly [number, number] => p[1] != null);
            return (
              <g key={s.id} className={"line s-" + s.id}>
                <polyline points={pts.map(([i, v]) => `${x(i)},${y(v)}`).join(" ")} />
                {pts.map(([i, v]) => (
                  <circle key={i} cx={x(i)} cy={y(v)} r={hover === i ? 5 : 3.5} />
                ))}
              </g>
            );
          })}
          {hover != null && <line className="cross" x1={x(hover)} x2={x(hover)} y1={PAD.t} y2={H - PAD.b} />}
          {dates.map((d, i) => (
            <rect
              key={d}
              className="hit"
              x={x(i) - (W - PAD.l - PAD.r) / Math.max(2, dates.length) / 2}
              width={(W - PAD.l - PAD.r) / Math.max(2, dates.length)}
              y={0}
              height={H}
              onMouseEnter={() => setHover(i)}
            />
          ))}
        </svg>
        {hover != null && (
          <div className="chart-tip" style={{ left: `${(x(hover) / W) * 100}%` }}>
            <b>{dayLabel(dates[hover])}</b>
            {series.map((s) => {
              const n = s.nights.find((n) => n.date === dates[hover]);
              return (
                <span key={s.id} className={"s-" + s.id}>
                  <i aria-hidden="true" />
                  {s.name}: {fmt(n ? val(n) : null)}
                </span>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
