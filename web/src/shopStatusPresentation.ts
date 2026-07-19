import { type SquareStatus } from "./protocol.ts";

const CLOSED_STATUS = "closed";

export function closedShopTurns(statuses: readonly SquareStatus[]): number | null {
  let remainingTurns: number | null = null;
  for (const status of statuses) {
    if (status.type !== CLOSED_STATUS) {
      continue;
    }
    const duration = Number.isFinite(status.remaining_turns)
      ? Math.max(0, Math.trunc(status.remaining_turns))
      : 0;
    remainingTurns = Math.max(remainingTurns ?? 0, duration);
  }
  return remainingTurns;
}
