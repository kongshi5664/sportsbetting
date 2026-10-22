import { Fragment, useMemo, useState } from "react";
import { api } from "../api";
import { odds, pct, pick, tipTime } from "../format";
import { ChevronLeft, Search, Warn } from "../icons";
import type { Game, News } from "../types";
import { label, Ramp, RulePills } from "./EdgeBoard";

/** Breaking news: mark a player out and see the teammates' props that may not have moved yet. */
export function PlayerOut(props: {
  date: string;
  games: Game[] | null;
  onAdd: (id: string, label: string) => Promise<unknown> | unknown;
  onError: (e: unknown) => void;
}) {
  const { date, games, onAdd, onError } = props;
  const [query, setQuery] = useState("");
  const [news, setNews] = useState<News | null>(null);
  const [outKey, setOutKey] = useState<string | null>(null);

  const teams = useMemo(() => {
    const byTeam = new Map<string, Map<string, { name: string; key: string; n: number }>>();
    for (const g of games ?? [])
      for (const m of g.markets) {
        const t = byTeam.get(m.team) ?? new Map();
        const p = t.get(m.name_key) ?? { name: m.player, key: m.name_key, n: 0 };
        p.n += 1;
        t.set(m.name_key, p);
        byTeam.set(m.team, t);
      }
    return [...byTeam.entries()]
      .map(([team, ps]) => ({ team, players: [...ps.values()].sort((a, b) => a.name.localeCompare(b.name)) }))
      .sort((a, b) => a.team.localeCompare(b.team));
  }, [games]);

  const load = async (key: string) => {
    setOutKey(key);
    try {
      setNews(await api.news(date, key));
    } catch (e) {
      onError(e);
    }
  };

  if (outKey && news) {
    const snap = news.teammates[0]?.snapshot_ts;
    return (
      <section aria-labelledby="out-h">
        <button className="btn link" onClick={() => (setNews(null), setOutKey(null))}>
          <ChevronLeft /> Pick another player
        </button>
        <div className="out-head">
          <h2 id="out-h">{news.player} is out</h2>
          <span className="pill no">{news.team}</span>
          <p className="dim">
            {news.teammates.length} teammate markets, best edge first
            {snap ? ` · prices as of ${tipTime(snap)} ET` : ""}
          </p>
        </div>
        <div className="notice">
          <Warn />
          <p>
            Check each price in Hard Rock before you bet: these are the last captured prices and may already have moved.
            {news.own.length > 0 &&
              ` ${news.player}'s own ${news.own.length} markets are left off; Hard Rock voids them if the player sits.`}
          </p>
        </div>
        {news.teammates.length === 0 ? (
          <div className="empty">
            <h2>No teammate markets on this slate</h2>
            <p>Nobody else on {news.team} has a priced prop tonight.</p>
          </div>
        ) : (
          <div className="board-wrap out-list">
            <table className="board">
              <thead>
                <tr>
                  <th className="l">Player</th>
                  <th className="l">Market</th>
                  <th>Fair</th>
                  <th className="hr">Hard Rock</th>
                  <th>Edge</th>
                  <th>Stake</th>
                  <th className="l">Rules</th>
                  <th>
                    <span className="sr">Add to card</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {[...new Set(news.teammates.map((m) => m.matchup))].map((game) => {
                  const rows = news.teammates.filter((m) => m.matchup === game);
                  return (
                    <Fragment key={game}>
                      <tr className="game">
                        <td colSpan={8}>
                          {game}
                          <span>{tipTime(rows[0].commence_time)}</span>
                        </td>
                      </tr>
                      {rows.map((m) => (
                        <tr key={m.id} className={"mk" + (m.blocked && !m.on_card ? " held" : "") + (m.on_card ? " oncard" : "")}>
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
                            <small className="fair-m"> fair {odds(m.fair_american)}</small>
                          </td>
                          <td className="edgec">
                            <span className={m.edge >= 0 ? "pos" : "neg"}>{pct(m.edge)}</span>
                            <Ramp edge={m.edge} />
                          </td>
                          <td className="stakec">{m.blocked ? "—" : `$${Math.round(m.stake)}`}</td>
                          <td className="rules">
                            <RulePills m={m} />
                          </td>
                          <td className="addc">
                            <button
                              className={"btn add" + (m.on_card ? " in" : "")}
                              disabled={m.on_card || m.blocked}
                              aria-label={`Add ${label(m)}`}
                              title={m.blocked ? m.flags.find((f) => f.blocks)?.text : undefined}
                              onClick={async () => {
                                await onAdd(m.id, label(m));
                                load(outKey);
                              }}
                            >
                              {m.on_card ? "On card" : m.blocked ? "Held" : "Add"}
                              {!m.on_card && !m.blocked && <span className="stk"> · ${Math.round(m.stake)}</span>}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    );
  }

  const q = query.toLowerCase();
  return (
    <section aria-labelledby="out-h">
      <div className="head">
        <h1 id="out-h">Player out</h1>
        <p>Someone's ruled out? Tap them to see teammates' props that may not have moved yet.</p>
      </div>
      <div className="filters">
        <div className="search" style={{ flex: "1 1 260px" }}>
          <label className="field" style={{ width: "100%" }}>
            <span className="sr">Find a player</span>
            <Search />
            <input
              type="search"
              placeholder="Find a player or team"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              style={{ width: "100%" }}
            />
          </label>
        </div>
      </div>
      {!games ? (
        <p className="dim">Loading tonight's players…</p>
      ) : (
        <div className="teams">
          {teams.map(({ team, players }) => {
            const ps = players.filter((p) => !q || p.name.toLowerCase().includes(q) || team.toLowerCase().includes(q));
            if (!ps.length) return null;
            return (
              <div key={team} className="team">
                <h2>{team}</h2>
                <ul>
                  {ps.map((p) => (
                    <li key={p.key}>
                      <button onClick={() => load(p.key)}>
                        {p.name}
                        <small>
                          {p.n} {p.n === 1 ? "market" : "markets"}
                        </small>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
