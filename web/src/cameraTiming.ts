import { PACING } from "./presentationTiming.ts";
export const HUMAN_ADJACENT_STEP_ANIMATION_MS = PACING.step;
export const AI_ADJACENT_STEP_ANIMATION_MS = PACING.step;

export function adjacentStepAnimationDuration(
  activePlayerId: number,
  assignedPlayerId: number | null,
): number {
  return activePlayerId === assignedPlayerId
    ? HUMAN_ADJACENT_STEP_ANIMATION_MS
    : AI_ADJACENT_STEP_ANIMATION_MS;
}
