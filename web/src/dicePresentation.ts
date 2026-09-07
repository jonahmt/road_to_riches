export type DicePurpose = "movement" | "event";

export interface DiceState {
  value: number;
  remaining: number;
  purpose: DicePurpose;
  animationId: number;
  presentationId?: string;
}

export interface DiceMessage {
  value: number;
  remaining: number;
  purpose?: DicePurpose;
  animate?: boolean;
}

import { PACING } from "./presentationTiming.ts";
export const DICE_ROLL_DURATION_MS = PACING.dieTumble;
export const DICE_SETTLE_DURATION_MS = PACING.dieDock;
export const EVENT_DICE_HOLD_DURATION_MS = PACING.dieRead;
export const EVENT_DICE_FADE_DURATION_MS = 240;

export const DIE_PIPS: Record<number, readonly number[]> = {
  0: [],
  1: [5],
  2: [3, 7],
  3: [3, 5, 7],
  4: [1, 3, 7, 9],
  5: [1, 3, 5, 7, 9],
  6: [1, 3, 4, 6, 7, 9],
  7: [1, 3, 4, 5, 6, 7, 9],
  8: [1, 2, 3, 4, 6, 7, 8, 9],
  9: [1, 2, 3, 4, 5, 6, 7, 8, 9],
};

export function nextDiceState(current: DiceState | null, message: DiceMessage): DiceState {
  return {
    value: message.value,
    remaining: message.remaining,
    purpose: message.purpose === "event" ? "event" : "movement",
    animationId: (current?.animationId ?? 0) + (message.animate === true ? 1 : 0),
  };
}

export function diceForPresentation(
  current: DiceState | null,
  requestId: string,
  data: Record<string, unknown>,
): DiceState {
  if (current?.presentationId === requestId) return current;
  const value = Number(data.value);
  const purpose = data.purpose === "event" ? "event" : "movement";
  return {
    ...nextDiceState(current, {
      value: Number.isFinite(value) ? value : 0,
      remaining: purpose === "movement" && Number.isFinite(value) ? value : 0,
      purpose,
      animate: true,
    }),
    presentationId: requestId,
  };
}

export function displayedDiceValue(dice: DiceState, settledMovement: boolean): number {
  if (dice.purpose === "event" || !settledMovement) {
    return dice.value;
  }
  return Math.max(0, dice.remaining);
}

export function dieFinalTransform(value: number): string {
  switch (value) {
    case 1:
      return "rotateX(0deg) rotateY(0deg)";
    case 2:
      return "rotateX(-90deg) rotateY(0deg)";
    case 3:
      return "rotateX(0deg) rotateY(-90deg)";
    case 4:
      return "rotateX(0deg) rotateY(90deg)";
    case 5:
      return "rotateX(90deg) rotateY(0deg)";
    case 6:
      return "rotateX(0deg) rotateY(180deg)";
    default:
      return "rotateX(0deg) rotateY(0deg)";
  }
}
