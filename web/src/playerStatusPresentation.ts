import { type PlayerStatus } from "./protocol.ts";

const COMMISSION_STATUS = "commission";
const BOOM_COMMISSION_PERCENT = 50;

export type CommissionIndicatorKind = "boon" | "boom";

export interface CommissionStatusIndicator {
  kind: CommissionIndicatorKind;
  percent: number;
  remainingTurns: number;
}

export function commissionStatusIndicators(
  statuses: readonly PlayerStatus[],
): CommissionStatusIndicator[] {
  return statuses.flatMap((status) => {
    if (status.type !== COMMISSION_STATUS) {
      return [];
    }
    const percent = Number.isFinite(status.modifier) ? Math.max(0, status.modifier) : 0;
    const remainingTurns = Number.isFinite(status.remaining_turns)
      ? Math.max(0, Math.trunc(status.remaining_turns))
      : 0;
    return [
      {
        kind: percent >= BOOM_COMMISSION_PERCENT ? "boom" : "boon",
        percent,
        remainingTurns,
      },
    ];
  });
}
