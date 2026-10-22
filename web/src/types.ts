export type League = { id: string; label: string; live: boolean };

export type Settings = {
  target_books: string[];
  model_weight: number;
  bankroll: number;
  kelly_fraction: number;
  stake_cap_units: number;
  nightly_risk_cap: number;
};

export type Meta = {
  db: string;
  sample: boolean;
  dates: string[];
  default_date: string | null;
  settings: Settings;
  leagues: League[];
  league: string;
  stat_labels: Record<string, string>;
  live_clv: { n: number; avg: number | null };
  odds_key: boolean;
  today: string;
  credits_remaining: number | null;
  markets: number;
};

export type Flag = { rule: string; text: string; blocks: boolean; testing?: boolean };

export type BookQuote = { over: number; under: number; p_over: number };

export type Market = {
  id: string;
  event_id: string;
  market: string;
  stat: string;
  stat_label: string;
  player: string;
  name_key: string;
  team: string;
  side: "Over" | "Under";
  point: number;
  book: string;
  price: number;
  fair: number;
  fair_american: number;
  edge: number;
  stake: number;
  refs: Record<string, number | undefined>;
  open_price?: number | null;
  proof: {
    books: Record<string, BookQuote>;
    p_market: number;
    p_model: number;
    model_weight: number;
    projection: number;
  };
  on_card: boolean;
  flags: Flag[];
  blocked: boolean;
};

export type Game = {
  event_id: string;
  away: string;
  home: string;
  commence_time: string;
  snapshot_ts: string | null;
  snapshot: "live" | "bet";
  markets: Market[];
};

export type Leg = {
  id: number;
  slate_date: string;
  event_id: string;
  market: string;
  stat_label?: string;
  name_key: string;
  player: string;
  side: "Over" | "Under";
  point: number;
  book: string;
  price: number;
  fair: number;
  edge: number;
  stake: number;
  snapshot_ts: string | null;
  status: "card" | "locked" | "graded";
  locked_at: string | null;
  placed: number;
  close_price: number | null;
  clv: number | null;
  result: "win" | "loss" | "push" | "void" | null;
  actual: number | null;
  away_team: string | null;
  home_team: string | null;
  commence_time: string | null;
};

export type Check = { ok: boolean; text: string; fail: string; legs: number[] };

export type Card = {
  date: string;
  legs: Leg[];
  risk: number;
  cap: number;
  checks: Check[];
  locked: boolean;
  locked_at: string | null;
  can_lock: boolean;
};

export type Metrics = {
  n: number;
  wins: number;
  losses: number;
  units: number;
  roi: number | null;
  avg_clv: number | null;
  clv_ci95: [number, number] | null;
  beat_close: number | null;
  avg_edge: number | null;
};

export type WaitingBet = {
  id: number;
  date: string;
  game: string;
  bet: string;
  side: string;
  point: number;
  price: number;
  edge: number;
  stake: number;
  strategy: string;
  strategy_name: string;
  to_win: number;
  expected: number;
};

export type LedgerBet = {
  date: string;
  game: string;
  bet: string;
  price: number;
  close_price: number | null;
  clv: number | null;
  edge: number;
  result: string;
  stake: number;
  pnl: number;
};

export type JournalEntry = { id: number; day: string; at: string; kind: "decision" | "recap"; title: string; body: string };

export type PaperStrategy = {
  id: string;
  name: string;
  graded: number;
  pending: number;
  avg_clv: number | null;
  bankroll: number | null; // null for the "every prop" control row
  start: number | null;
};

export type Ledger = {
  source: "live" | "backtest" | "paper";
  paper: PaperStrategy[] | null;
  waiting?: WaitingBet[];
  summary: Metrics;
  nights: { date: string; bets: number; pnl: number; stake: number; avg_clv: number | null }[];
  bets: LedgerBet[];
};

export type RuleVerdict = {
  verdict: string;
  why: string;
  results: Record<"train" | "holdout" | "all", { matched: Metrics; rest: Metrics }>;
};

export type Rule = {
  id: string;
  name: string;
  status: "confirmed" | "testing" | "retired";
  kind: "gate" | "avoid" | "prefer";
  params?: Record<string, number>;
  note?: string;
  backtest: RuleVerdict | null;
};

export type Rules = {
  rules: Rule[];
  report: { generated: string; db: string; holdout: string; overall: Metrics } | null;
};

export type Note = {
  verdict: "clear" | "caution" | "skip";
  note: string;
  sources: string[];
  created_at: string;
};

export type Suggested = {
  date: string;
  legs: (Market & { matchup: string; commence_time: string })[];
  risk: number;
};

export type Stat = { n: number; avg: number | null; se: number | null; beat: number | null };

export type Finding = {
  id: string;
  area: "rule" | "setting" | "claude" | "paper" | "market";
  title: string;
  verdict: string;
  matched?: Stat;
  rest?: Stat;
  groups?: [string, Stat][];
  proposal: {
    type: "rule_status" | "setting" | "strategy";
    rule?: string;
    key?: string;
    value?: string | number;
    strategy?: string;
    overrides?: Record<string, number>;
  } | null;
  decided: "applied" | "dismissed" | null;
};

export type Review = { generated: string; bets: Stat; first: string | null; last: string | null; min_n: number; findings: Finding[] };

export type Injury = {
  name_key: string;
  player: string;
  team: string;
  status: string;
  detail: string;
  updated: string;
  matchup: string;
};

export type News = {
  player: string;
  team: string;
  teammates: (Market & { matchup: string; commence_time: string; snapshot_ts: string | null })[];
  own: (Market & { matchup: string })[];
};

export type DeskStatus = {
  trader: { running: boolean; seen: string | null };
  last_pull: string | null;
  credits_remaining: number | null;
  credits_at: string | null;
  games: number;
  decided: number;
  next: { game: string; tip: string; decide_at: string } | null;
};

export type LiveGame = {
  espn_id: string;
  away: string;
  home: string;
  away_score: number;
  home_score: number;
  state: "pre" | "in" | "post";
  period: number;
  clock: string;
  detail: string;
};

export type BetProgress = {
  state: "pre" | "in" | "post";
  detail: string;
  now?: number;
  min?: number;
  pace?: number | null;
  on_pace?: boolean | null;
  status?: "live" | "won" | "lost" | "void";
};

export type Live = { games: LiveGame[]; bets: Record<string, BetProgress> };

export type StrategyHistory = {
  id: string;
  name: string;
  nights: { date: string; pnl: number | null; clv: number | null; n: number }[];
};
