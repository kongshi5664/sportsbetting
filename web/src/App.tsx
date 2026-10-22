import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError, SignInError } from "./api";
import { SignIn } from "./components/SignIn";
import { CardPanel } from "./components/CardPanel";
import { EdgeBoard } from "./components/EdgeBoard";
import { LedgerView } from "./components/LedgerView";
import { PlayerOut } from "./components/PlayerOut";
import { Rulebook } from "./components/Rulebook";
import { Shell, type Tab } from "./components/Shell";
import { SuggestBlock } from "./components/Suggest";
import { Tonight } from "./components/Tonight";
import type { Card, Game, Meta, Note, Suggested } from "./types";

const TABS: Tab[] = ["tonight", "board", "out", "ledger", "rules"];
const tabFromHash = (): Tab => {
  if (location.hash === "#/card") return "tonight"; // the card now lives on Tonight
  const t = location.hash.replace("#/", "") as Tab;
  return TABS.includes(t) ? t : "tonight";
};

export type Toast = { text: string; err?: boolean } | null;

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [date, setDate] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>(tabFromHash);
  const [games, setGames] = useState<Game[] | null>(null);
  const [card, setCard] = useState<Card | null>(null);
  const [suggested, setSuggested] = useState<Suggested | null>(null);
  const [notes, setNotes] = useState<Record<string, Note>>({});
  const [claudeKey, setClaudeKey] = useState(false);
  const [toast, setToast] = useState<Toast>(null);
  const [fatal, setFatal] = useState<string | null>(null);
  const [needSignIn, setNeedSignIn] = useState(false);
  const [passwordSet, setPasswordSet] = useState(false);

  const say = useCallback((text: string, err = false) => setToast({ text, err }), []);
  const fail = useCallback(
    (e: unknown) => {
      if (e instanceof SignInError) setNeedSignIn(true);
      else say(e instanceof ApiError ? e.message : String(e), true);
    },
    [say],
  );

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), toast.err ? 6000 : 3200);
    return () => clearTimeout(t);
  }, [toast]);

  useEffect(() => {
    const on = () => setTab(tabFromHash());
    addEventListener("hashchange", on);
    return () => removeEventListener("hashchange", on);
  }, []);

  useEffect(() => {
    api
      .session()
      .then((s) => {
        setPasswordSet(s.required);
        if (s.required && !s.signed_in) {
          setNeedSignIn(true);
          return;
        }
        return api.meta().then((m) => {
          setMeta(m);
          const asked = new URLSearchParams(location.search).get("date");
          setDate(asked && m.dates.includes(asked) ? asked : m.default_date);
        });
      })
      .catch((e) =>
        e instanceof SignInError ? setNeedSignIn(true) : setFatal(e instanceof ApiError ? e.message : String(e)),
      );
  }, []);

  const refresh = useCallback(
    async (d: string) => {
      try {
        const [s, c, sg, n] = await Promise.all([api.slate(d), api.card(d), api.suggest(d), api.notes(d)]);
        setGames(s.games);
        setCard(c);
        setSuggested(sg);
        setNotes(n.notes);
        setClaudeKey(n.claude_key);
      } catch (e) {
        fail(e);
      }
    },
    [fail],
  );

  useEffect(() => {
    if (!date) return;
    setGames(null);
    refresh(date);
  }, [date, refresh]);

  // Every card change can move a cap, so the board is re-priced after it.
  const act = useCallback(
    async (p: Promise<Card>, ok?: string) => {
      try {
        const c = await p;
        setCard(c);
        if (ok) say(ok);
        if (date) {
          const [s, sg] = await Promise.all([api.slate(date), api.suggest(date)]);
          setGames(s.games);
          setSuggested(sg);
        }
        return c;
      } catch (e) {
        fail(e);
        return null;
      }
    },
    [date, say, fail],
  );

  const legIdFor = useMemo(() => {
    const m = new Map<string, number>();
    for (const l of card?.legs ?? []) m.set(`${l.event_id}|${l.market}|${l.name_key}|${l.point}|${l.side}`, l.id);
    return m;
  }, [card]);

  const handlers = {
    add: (marketId: string, label: string) => date && act(api.addLeg(date, marketId), `Added ${label}`),
    removeMarket: (marketId: string, label: string) => {
      const id = legIdFor.get(marketId);
      return id != null && act(api.removeLeg(id), `Removed ${label}`);
    },
    removeLeg: (id: number, label: string) => act(api.removeLeg(id), `Removed ${label}`),
    clear: () => date && act(api.clear(date), "Card cleared"),
    lock: () => date && act(api.lock(date), "Card locked. Place each leg at Hard Rock and tick it off."),
    unlock: () => date && act(api.unlock(date), "Card unlocked"),
    placed: (id: number, placed: boolean) => act(api.placed(id, placed)),
    refreshOdds: async () => {
      if (!date) return;
      try {
        const r = await api.refresh(date);
        const left = r.credits_remaining != null ? `, ${r.credits_remaining.toLocaleString()} left` : "";
        say(`Odds refreshed for ${r.games} games · ${r.credits_used} credits used${left}`);
        setMeta(await api.meta());
        await refresh(date);
      } catch (e) {
        fail(e);
      }
    },
  };

  if (needSignIn) return <SignIn />;

  if (fatal) {
    return (
      <div className="empty" style={{ margin: 40 }}>
        <h2>The desk can't load</h2>
        <p>{fatal}</p>
      </div>
    );
  }

  const checkedAt = Object.values(notes).reduce<string | null>(
    (latest, n) => (latest && latest > n.created_at ? latest : n.created_at),
    null,
  );
  const askClaude = async () => {
    if (!date) return;
    try {
      const r = await api.askClaude(date);
      setNotes(r.notes);
      const flagged = Object.values(r.notes).filter((n) => n.verdict !== "clear").length;
      say(`Claude checked ${r.checked} legs${flagged ? ` · ${flagged} flagged` : " · nothing flagged"}`);
    } catch (e) {
      fail(e);
    }
  };

  const cardPanel = (variant: "dock" | "page", withSuggest = true) =>
    card && (
      <CardPanel
        card={card}
        variant={variant}
        notes={notes}
        suggest={
          withSuggest &&
          !card.locked && (
            <SuggestBlock
              suggested={suggested}
              notes={notes}
              claudeKey={claudeKey}
              checkedAt={checkedAt}
              hasLegs={card.legs.length > 0}
              onAdd={handlers.add}
              onAddAll={(exclude) =>
                date ? act(api.addSuggested(date, exclude), "Added the suggested legs") : Promise.resolve()
              }
              onAsk={askClaude}
            />
          )
        }
        onRemove={handlers.removeLeg}
        onClear={handlers.clear}
        onLock={handlers.lock}
        onUnlock={handlers.unlock}
        onPlaced={handlers.placed}
      />
    );

  return (
    <Shell
      meta={meta}
      date={date}
      onDate={setDate}
      tab={tab}
      cardCount={card?.legs.length ?? 0}
      cardLocked={card?.locked ?? false}
      toast={toast}
      onSignOut={passwordSet ? () => api.logout().finally(() => location.reload()) : undefined}
    >
      {tab === "board" && (
        <div className="desk">
          <EdgeBoard
            games={games}
            sample={meta?.sample ?? false}
            live={!!meta && meta.odds_key && date === meta.today}
            today={!!meta && date === meta.today}
            costPerGame={meta?.markets ?? 5}
            creditsLeft={meta?.credits_remaining ?? null}
            onRefresh={handlers.refreshOdds}
            onAdd={handlers.add}
            onRemove={handlers.removeMarket}
            locked={card?.locked ?? false}
            onLock={handlers.lock}
            canLock={card?.can_lock ?? false}
          />
          {cardPanel("dock")}
        </div>
      )}
      {tab === "tonight" && (
        <Tonight
          date={date}
          games={games}
          suggested={suggested}
          card={card}
          notes={notes}
          sample={meta?.sample ?? false}
          live={!!meta && meta.odds_key && date === meta.today}
          today={!!meta && date === meta.today}
          costPerGame={meta?.markets ?? 5}
          claudeKey={claudeKey}
          checkedAt={checkedAt}
          cardPanel={cardPanel("page", false)}
          onRefresh={handlers.refreshOdds}
          onAsk={askClaude}
          onAdd={handlers.add}
          onAddAll={(exclude) =>
            date ? act(api.addSuggested(date, exclude), "Added to tonight's card") : Promise.resolve()
          }
          onLock={handlers.lock}
        />
      )}
      {tab === "out" && date && <PlayerOut date={date} games={games} onAdd={handlers.add} onError={fail} />}
      {tab === "ledger" && <LedgerView onError={fail} />}
      {tab === "rules" && <Rulebook onError={fail} say={say} />}
    </Shell>
  );
}
