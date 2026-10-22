import type { Card, Game, Injury, JournalEntry, Ledger, Meta, News, Note, Review, Rules, Suggested } from "./types";

export class ApiError extends Error {}
/** The desk has a password and this device isn't signed in (or its session expired). */
export class SignInError extends ApiError {}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: init?.body ? { "Content-Type": "application/json" } : undefined,
    });
  } catch {
    throw new ApiError("Can't reach the desk server. Start it with: python -m tipoff.api");
  }
  if (res.status === 401 && path !== "/api/login") throw new SignInError("Sign in to use the desk.");
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(body?.detail ?? `The server answered ${res.status}. Try again.`);
  }
  return res.json();
}

const q = (params: Record<string, string>) => "?" + new URLSearchParams(params).toString();
const post = (body: unknown) => ({ method: "POST", body: JSON.stringify(body) });

export const api = {
  session: () => call<{ required: boolean; signed_in: boolean }>("/api/session"),
  login: (password: string) => call<{ signed_in: boolean }>("/api/login", post({ password })),
  logout: () => call<{ signed_in: boolean }>("/api/logout", post({})),
  meta: () => call<Meta>("/api/meta"),
  slate: (date: string) => call<{ date: string; games: Game[] }>("/api/slate" + q({ date })),
  card: (date: string) => call<Card>("/api/card" + q({ date })),
  addLeg: (date: string, market_id: string) => call<Card>("/api/card/legs", post({ date, market_id })),
  removeLeg: (id: number) => call<Card>(`/api/card/legs/${id}`, { method: "DELETE" }),
  clear: (date: string) => call<Card>("/api/card/clear", post({ date })),
  lock: (date: string) => call<Card>("/api/card/lock", post({ date })),
  unlock: (date: string) => call<Card>("/api/card/unlock", post({ date })),
  placed: (id: number, placed: boolean) =>
    call<Card>(`/api/bets/${id}`, { method: "PATCH", body: JSON.stringify({ placed }) }),
  ledger: (source: "live" | "backtest" | "paper", strategy = "current") =>
    call<Ledger>("/api/ledger" + q({ source, strategy })),
  rules: () => call<Rules>("/api/rules"),
  review: () => call<Review>("/api/review"),
  journal: (limit = 30) => call<{ entries: JournalEntry[] }>("/api/journal" + q({ limit: String(limit) })),
  applyProposal: (id: string) => call<Review>("/api/review/apply", post({ id })),
  dismissProposal: (id: string) => call<Review>("/api/review/dismiss", post({ id })),
  setStatus: (id: string, status: string) => call<Rules>(`/api/rules/${id}/status`, post({ status })),
  news: (date: string, player: string) => call<News>("/api/news" + q({ date, player })),
  injuries: (date: string) => call<{ players: Injury[]; error?: string }>("/api/injuries" + q({ date })),
  suggest: (date: string) => call<Suggested>("/api/suggest" + q({ date })),
  addSuggested: (date: string, exclude: string[]) => call<Card>("/api/card/suggested", post({ date, exclude })),
  notes: (date: string) =>
    call<{ notes: Record<string, Note>; claude_key: boolean }>("/api/notes" + q({ date })),
  askClaude: (date: string) =>
    call<{ notes: Record<string, Note>; checked: number }>("/api/notes", post({ date })),
  refresh: (date: string) =>
    call<{ games: number; credits_used: number; credits_remaining: number | null }>("/api/refresh", post({ date })),
};
