import { useEffect, useState } from "react";
import type { PresentationState } from "./presentationQueue";
import { formatGold } from "./format";
import { SUIT_COLORS } from "./boardColors";
import "./arcade.css";

const SUITS = ["SPADE", "HEART", "DIAMOND", "CLUB"];
const ICONS: Record<string,string> = { SPADE: "♠", HEART: "♥", DIAMOND: "♦", CLUB: "♣" };
export function ArcadePresentation({ presentation, assignedPlayerId, onContinue }: {
  presentation: PresentationState; assignedPlayerId: number | null; onContinue: () => void;
}) {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const intro = presentation.type === "arcade_intro";
  const [legacyElapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (presentation.coordinated) return;
    const start = performance.now(); const timer = window.setInterval(() => setElapsed(performance.now()-start), 40);
    return () => clearInterval(timer);
  }, [presentation.requestId, presentation.coordinated]);
  const elapsed = presentation.elapsed ?? legacyElapsed;
  const reels = (presentation.data.reels as string[] | undefined) ?? SUITS.slice(0,3);
  const amount = Number(presentation.data.amount ?? 0);
  const settled = !intro && elapsed >= 2200;
  const owner = presentation.playerId === assignedPlayerId;
  const canContinue = owner && !presentation.acknowledgmentPending && presentation.canContinue !== false && (intro || elapsed >= 2700);
  return <div className="arcade-overlay" role="dialog" aria-modal="true" aria-labelledby="arcade-title">
    <div className="arcade-instructions"><strong id="arcade-title">{intro ? "Welcome to the Arcade!" : settled ? amount ? "A winning match!" : "Better luck next time!" : "Round and round…"}</strong>
      <span>{intro ? "Match the suits to win a prize. Playing is free!" : `Player ${presentation.playerId} · Suit Reels`}</span></div>
    <div className="arcade-machine">
      <div className="arcade-marquee">★ SUIT REELS ★</div>
      <div className="arcade-reels" aria-label={settled ? reels.map(s => s.toLowerCase()).join(", ") : "Three suit reels"}>
        {reels.map((s,i) => { const spinning = !intro && elapsed < 1200 + i*500;
          const face = spinning && reduced ? "UNKNOWN" : spinning ? SUITS[(Math.floor(elapsed/90)+i)%4] : intro ? SUITS[i] : s;
          return <span key={i} className={spinning ? "is-spinning" : ""} style={{color:SUIT_COLORS[face]}} aria-hidden="true">{ICONS[face] ?? "?"}</span>; })}
      </div>
      {intro ? <div className="arcade-paytable"><span>Three matching <b>{formatGold(Number(presentation.data.triple_prize))}</b></span><span>Two matching <b>{formatGold(Number(presentation.data.pair_prize))}</b></span><small>No match: no prize · Each reel has four equally likely suits</small></div>
      : <div className="arcade-winnings" aria-live="polite">{settled ? <><small>{amount ? `Player ${presentation.playerId} receives` : "No prize this time"}</small><strong>{amount ? `+${formatGold(amount)}` : "—"}</strong></> : <span>Good luck!</span>}</div>}
    </div>
    <div className="arcade-footer">{owner ? <button disabled={!canContinue} onClick={onContinue}>{presentation.acknowledgmentPending ? "Continuing…" : intro ? "Spin the reels" : "Continue"}</button> : <span>Waiting for Player {presentation.playerId}…</span>}</div>
  </div>;
}
