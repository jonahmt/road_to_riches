import type { PresentationState } from "./presentationQueue";
import type { GameState } from "./protocol";

export const PACING = {
  step: 300, arrival: 400, turn: 900, exit: 250,
  dieTumble: 1300, dieRead: 700, dieDock: 350,
  rentTransfer: 650, rentTransferEnd: 1450, dividends: 1650, dividendsEnd: 2350,
  suit: 1760,
} as const;

export function beatTiming(beat: PresentationState) {
  switch (beat.type) {
    case "piece_moved": return { reveal: PACING.step + (beat.data.remaining === 0 ? PACING.arrival : 0), human: 0, auto: 0, exit: 0, motion: ["piece", "camera"] };
    case "turn_started": return { reveal: PACING.turn, human: 0, auto: 0, exit: 120, motion: ["camera"] };
    case "dice_rolled": return { reveal: 2350, human: 0, auto: 0, exit: 100, motion: ["dice"] };
    case "suit_collected": return { reveal: PACING.suit, human: 0, auto: 0, exit: 100, motion: ["suit"] };
    case "venture_selected": return { reveal: 550, human: 0, auto: 0, exit: 100, motion: [] };
    case "rent_payment": return { reveal: Array.isArray(beat.data.dividends) && beat.data.dividends.length ? PACING.dividendsEnd : PACING.rentTransferEnd, human: 800, auto: 1400, exit: PACING.exit, motion: [] };
    case "stock_price_changed": return { reveal: 1400, human: 800, auto: 1600, exit: PACING.exit, motion: ["camera"] };
    case "promotion_completed": return { reveal: 2400, human: 900, auto: 1800, exit: PACING.exit, motion: [] };
    case "venture_card_revealed": return { reveal: 600, human: 800, auto: 2600, exit: PACING.exit, motion: [] };
    default: return { reveal: 1000, human: 800, auto: 1400, exit: PACING.exit, motion: [] };
  }
}

export function automaticBeat(beat: PresentationState): boolean {
  return !beat.requiresAcknowledgment || beat.type === "dice_rolled";
}

function interpolate(from: number, to: number, elapsed: number, start: number, end: number) {
  const progress = Math.min(1, Math.max(0, (elapsed - start) / (end - start)));
  return Math.round(from + (to - from) * progress);
}

export function presentedState(beat: PresentationState, elapsed: number): GameState | undefined {
  const { before, after } = beat;
  if (!before || !after) return after;
  if (["piece_moved", "turn_started"].includes(beat.type)) return after;
  if (beat.type === "dice_rolled") return before;
  if (beat.type === "suit_collected") return elapsed >= 1600 ? after : before;
  const release = beat.type === "promotion_completed" ? 900 : beat.type === "stock_price_changed" ? 1000 : 550;
  const result = elapsed >= release ? after : before;
  const rentCash = beat.data.rent_cash as Record<string, number> | undefined;
  return { ...result, players: result.players.map((player) => {
    const old = before.players.find((p) => p.player_id === player.player_id)!;
    const next = after.players.find((p) => p.player_id === player.player_id)!;
    let cash: number;
    if (beat.type === "rent_payment" && rentCash) {
      const intermediate = rentCash[String(player.player_id)] ?? old.ready_cash;
      cash = elapsed < PACING.dividends
        ? interpolate(old.ready_cash, intermediate, elapsed, PACING.rentTransfer, PACING.rentTransferEnd)
        : interpolate(intermediate, next.ready_cash, elapsed, PACING.dividends, PACING.dividendsEnd);
    } else {
      cash = interpolate(old.ready_cash, next.ready_cash, elapsed, release, beatTiming(beat).reveal);
    }
    return { ...player, ready_cash: cash };
  }) };
}
