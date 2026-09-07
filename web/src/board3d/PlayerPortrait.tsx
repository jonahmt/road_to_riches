import { useId } from "react";

/** A small companion portrait for the procedural board figure. */
export function PlayerPortrait({ color, playerId }: { color: string; playerId: number }) {
  const shine = useId();
  return <span className="player-portrait" aria-hidden="true">
    <svg viewBox="0 0 80 88" focusable="false">
      <defs>
        <linearGradient id={shine} x1="0" y1="0" x2="0.9" y2="1">
          <stop stopColor="#fff" stopOpacity=".34" />
          <stop offset=".55" stopColor="#fff" stopOpacity="0" />
          <stop offset="1" stopColor="#102d48" stopOpacity=".35" />
        </linearGradient>
      </defs>
      <ellipse cx="40" cy="79" rx="30" ry="6" fill="#071e37" opacity=".4" />
      <path d="M13 79Q13 55 40 55Q67 55 67 79Z" fill={color} stroke="#17324a" strokeWidth="2" />
      <path d="M26 57Q40 68 54 57L51 65Q40 73 29 65Z" fill="#fff0c5" />
      <ellipse cx="40" cy="39" rx="26" ry="27" fill={color} stroke="#17324a" strokeWidth="2" />
      <ellipse cx="40" cy="39" rx="26" ry="27" fill={`url(#${shine})`} />
      {[30, 49].map((x) => <g key={x}>
        <ellipse cx={x} cy="40" rx="7" ry="10" fill="#fffdf0" />
        <ellipse cx={x + 1} cy="41" rx="3.2" ry="5.6" fill="#18334a" />
        <circle cx={x} cy="38" r="1.5" fill="#fff" />
      </g>)}
      <ellipse cx="40" cy="50" rx="4.5" ry="3.5" fill="#fff" opacity=".3" />
      <path d="M33 55Q40 61 47 55" fill="none" stroke="#244354" strokeWidth="2.4" strokeLinecap="round" />
      <path d="M14 25Q9 5 38 5Q66 3 66 24Q39 32 14 25Z" fill={color} stroke="#17324a" strokeWidth="2" />
      <path d="M14 25Q9 5 38 5Q66 3 66 24Q39 32 14 25Z" fill="#10283e" opacity=".62" />
      <path d="M15 22Q38 29 67 22L70 27Q47 36 17 28Z" fill="#19364f" stroke="#10283e" strokeWidth="1.5" />
      <path d="M19 16Q25 9 38 10" fill="none" stroke="#fff" strokeOpacity=".2" strokeWidth="3" strokeLinecap="round" />
      <circle cx="38" cy="5" r="3.5" fill="#e7c16f" />
      <circle cx="40" cy="76" r="8" fill="#fff2c4" stroke="#997142" strokeWidth="1.5" />
      <text x="40" y="80" textAnchor="middle" fill="#284660" fontFamily="Arial,sans-serif" fontWeight="900" fontSize="12">{playerId}</text>
    </svg>
  </span>;
}
