export const HUMAN_ADJACENT_STEP_ANIMATION_MS = 100;
export const AI_ADJACENT_STEP_ANIMATION_MS = 135;

export function adjacentStepAnimationDuration(
  activePlayerId: number,
  assignedPlayerId: number | null,
): number {
  return activePlayerId === assignedPlayerId
    ? HUMAN_ADJACENT_STEP_ANIMATION_MS
    : AI_ADJACENT_STEP_ANIMATION_MS;
}
