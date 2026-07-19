export type DicePurpose = "movement" | "event";

export interface DiceState {
  value: number;
  remaining: number;
  purpose: DicePurpose;
  animationId: number;
}

export interface DiceMessage {
  value: number;
  remaining: number;
  purpose?: DicePurpose;
  animate?: boolean;
}

export const DICE_ROLL_DURATION_MS = 760;
export const DICE_SETTLE_DURATION_MS = 360;
export const EVENT_DICE_HOLD_DURATION_MS = 1_000;
export const EVENT_DICE_FADE_DURATION_MS = 240;

export function nextDiceState(current: DiceState | null, message: DiceMessage): DiceState {
  return {
    value: message.value,
    remaining: message.remaining,
    purpose: message.purpose === "event" ? "event" : "movement",
    animationId: (current?.animationId ?? 0) + (message.animate === true ? 1 : 0),
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
