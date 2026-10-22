import { dayLabel, tipTime } from "../format";
import type { JournalEntry } from "../types";

/** One journal entry: a title and its plain-English body (bullets kept as a list). */
export function Entry({ e }: { e: JournalEntry }) {
  const lines = e.body.split("\n").filter(Boolean);
  const items = lines.filter((l) => l.startsWith("- ")).map((l) => l.slice(2));
  const prose = lines.filter((l) => !l.startsWith("- "));
  return (
    <article className={"entry " + e.kind}>
      <header>
        <span>{e.kind === "recap" ? "Morning recap" : `Decided ${tipTime(e.at)} ET`}</span>
        <span>{dayLabel(e.day)}</span>
      </header>
      <h3>{e.title}</h3>
      {prose.map((l, i) => (
        <p key={i}>{l}</p>
      ))}
      {items.length > 0 && (
        <ul>
          {items.map((l, i) => (
            <li key={i}>{l}</li>
          ))}
        </ul>
      )}
    </article>
  );
}

/** The paper trader's journal, newest first. */
export function Journal({ entries }: { entries: JournalEntry[] }) {
  if (!entries.length)
    return (
      <p className="dim">
        No journal entries yet. The paper trader writes one as it decides each game, and a recap the next morning.
      </p>
    );
  return (
    <div className="journal">
      {entries.map((e) => (
        <Entry key={e.id} e={e} />
      ))}
    </div>
  );
}
