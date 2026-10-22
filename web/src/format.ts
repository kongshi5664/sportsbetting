const MINUS = "−";

/** American odds with a true minus sign: +105, −110. */
export const odds = (p: number | null | undefined) =>
  p == null ? "—" : p > 0 ? `+${p}` : `${MINUS}${Math.abs(p)}`;

/** Signed percent: +4.6%, −1.9%. */
export const pct = (x: number | null | undefined, digits = 1) =>
  x == null ? "—" : `${x >= 0 ? "+" : MINUS}${Math.abs(x * 100).toFixed(digits)}%`;

/** Unsigned percent: 77%. */
export const share = (x: number | null | undefined) => (x == null ? "—" : `${Math.round(x * 100)}%`);

export const money = (x: number, cents = false) =>
  `${x < 0 ? MINUS : ""}$${Math.abs(x).toLocaleString("en-US", {
    minimumFractionDigits: cents ? 2 : 0,
    maximumFractionDigits: cents ? 2 : 0,
  })}`;

export const signedMoney = (x: number) => `${x >= 0 ? "+" : MINUS}$${Math.abs(x).toFixed(2)}`;

export const units = (x: number) => `${x >= 0 ? "+" : MINUS}${Math.abs(x).toFixed(1)}u`;

const ET = "America/New_York";

/** 7:30p (Eastern). */
export const tipTime = (iso: string) =>
  new Date(iso)
    .toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZone: ET })
    .replace(" AM", "a")
    .replace(" PM", "p");

export const dayLabel = (date: string, long = false) =>
  new Date(date + "T12:00:00").toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    ...(long ? { year: "numeric" } : {}),
  });

export const pick = (side: string, point: number) => `${side === "Over" ? "O" : "U"} ${point}`;

export const BOOK_SHORT: Record<string, string> = {
  hardrockbet: "Hard Rock",
  draftkings: "DK",
  fanduel: "FD",
  betmgm: "MGM",
  caesars: "CZR",
  espnbet: "ESPN",
  betrivers: "BR",
  pinnacle: "Pinnacle",
  betonlineag: "BetOnline",
};
