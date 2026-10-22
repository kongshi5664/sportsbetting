import { useId, useState, type ReactNode } from "react";

/** Plain-language definitions for the desk's few technical words. */
export const GLOSSARY = {
  worth:
    "What the bet is really worth: the other sportsbooks' prices with their built-in cut removed, nudged slightly by our own projection.",
  value:
    "How much better Hard Rock pays than the bet is worth. +4% means about $4 profit per $100 bet, on average over many bets like it. Only bets at +2% or more are suggested.",
  clv: "Beat the market (closing-line value): whether the price moved your way after you bet. The best sign you're doing this right, long before wins and losses settle down.",
  stake:
    "How much to bet: a careful slice of the bankroll sized to the value, never more than 2% of it on one bet.",
  cap: "The most the card can risk in one night (8% of the bankroll), so one bad night stays small.",
} as const;

export type TermKey = keyof typeof GLOSSARY;

/** A word with a tap-to-explain definition: no hover needed, works on phones and keyboards. */
export function Term({ k, children }: { k: TermKey; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span className="term">
      <button type="button" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}>
        {children}
      </button>
      {open && (
        <span id={id} role="note" className="term-def">
          {GLOSSARY[k]}
        </span>
      )}
    </span>
  );
}
