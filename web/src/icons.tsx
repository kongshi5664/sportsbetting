import type { SVGProps } from "react";

// One icon family: 24px grid, 2px square-capped strokes, angles on 45/90 like the pictograms.
type P = SVGProps<SVGSVGElement>;
const base = (p: P) => ({
  width: 16,
  height: 16,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2.4,
  strokeLinecap: "square" as const,
  strokeLinejoin: "miter" as const,
  "aria-hidden": true,
  ...p,
});

export const Check = (p: P) => (
  <svg {...base(p)}>
    <path d="M5 12.5l4.5 4.5L19 7.5" />
  </svg>
);
export const Cross = (p: P) => (
  <svg {...base(p)}>
    <path d="M6 6l12 12M18 6L6 18" />
  </svg>
);
export const Plus = (p: P) => (
  <svg {...base(p)}>
    <path d="M12 5v14M5 12h14" />
  </svg>
);
export const Warn = (p: P) => (
  <svg {...base(p)}>
    <path d="M12 4l9 16H3z" />
    <path d="M12 10v4M12 17v.5" />
  </svg>
);
export const ChevronLeft = (p: P) => (
  <svg {...base(p)}>
    <path d="M15 5l-7 7 7 7" />
  </svg>
);
export const ChevronRight = (p: P) => (
  <svg {...base(p)}>
    <path d="M9 5l7 7-7 7" />
  </svg>
);
export const ChevronDown = (p: P) => (
  <svg {...base(p)}>
    <path d="M5 9l7 7 7-7" />
  </svg>
);
export const Sun = (p: P) => (
  <svg {...base(p)}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2" />
  </svg>
);
export const Moon = (p: P) => (
  <svg {...base(p)}>
    <path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z" />
  </svg>
);
export const Search = (p: P) => (
  <svg {...base(p)}>
    <circle cx="10.5" cy="10.5" r="6" />
    <path d="M15 15l5 5" />
  </svg>
);
export const Lock = (p: P) => (
  <svg {...base(p)}>
    <rect x="5" y="11" width="14" height="10" />
    <path d="M8 11V7a4 4 0 0 1 8 0v4" />
  </svg>
);

// League pictograms: geometric figures on a 32px grid (Munich 1972 tradition).
const pict = (p: P) => ({
  viewBox: "0 0 32 32",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 3.4,
  strokeLinecap: "square" as const,
  strokeLinejoin: "miter" as const,
  "aria-hidden": true,
  ...p,
});

export const Pictogram = ({ league, ...p }: P & { league: string }) => {
  switch (league) {
    case "nba":
      return (
        <svg {...pict(p)}>
          <circle cx="14" cy="5" r="3" fill="currentColor" stroke="none" />
          <circle cx="24" cy="3.5" r="2.6" fill="currentColor" stroke="none" />
          <path d="M14 10v9M14 12l6-6M14 13l-4 4M14 19l4 4v6M14 19l-4 4v6" />
        </svg>
      );
    case "nfl":
      return (
        <svg {...pict(p)}>
          <circle cx="19" cy="5" r="3" fill="currentColor" stroke="none" />
          <path d="M18 10l-5 5v5l-5 5v4M13 20l6 6h4M17 11l5 5" />
          <rect x="21" y="14" width="6" height="4" transform="rotate(-45 24 16)" fill="currentColor" stroke="none" />
        </svg>
      );
    case "mlb":
      return (
        <svg {...pict(p)}>
          <circle cx="12" cy="5" r="3" fill="currentColor" stroke="none" />
          <path d="M12 10v10M13 12l9-9M12 20l-4 4v5M12 20l4 4v5" />
          <circle cx="26" cy="12" r="2" fill="currentColor" stroke="none" />
        </svg>
      );
    default:
      return (
        <svg {...pict(p)}>
          <circle cx="14" cy="5" r="3" fill="currentColor" stroke="none" />
          <path d="M14 10v8M14 13l8 8h5M14 18l-4 4v6M14 18l4 4v6" />
          <rect x="24" y="25" width="4" height="2.5" fill="currentColor" stroke="none" />
        </svg>
      );
  }
};

export const Mark = (p: P) => (
  <svg viewBox="0 0 32 32" aria-hidden {...p}>
    <rect width="32" height="32" rx="9" fill="var(--mood)" />
    <path d="M7.5 21.5 13 16l4 3.5 7.5-8" fill="none" stroke="var(--on-mood)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
    <circle cx="24.5" cy="11.5" r="2.2" fill="var(--on-mood)" />
  </svg>
);
