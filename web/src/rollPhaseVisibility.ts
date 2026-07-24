export interface RollPhaseVisibilityInput {
  diceRemaining: number | null | undefined;
  pendingRequestType: string | null | undefined;
  responsePending: boolean;
  toolsOpen: boolean;
}

export interface RollPhaseVisibility {
  movementDie: boolean;
  gameHeader: boolean;
  tools: boolean;
}

export function getRollPhaseVisibility({
  diceRemaining,
  pendingRequestType,
  responsePending,
  toolsOpen,
}: RollPhaseVisibilityInput): RollPhaseVisibility {
  const movementRequest =
    pendingRequestType === "CHOOSE_PATH" || pendingRequestType === "CONFIRM_STOP";
  const movementDie =
    (diceRemaining ?? 0) > 0 ||
    movementRequest ||
    (responsePending && pendingRequestType === "PRE_ROLL");
  const gameHeader = !movementDie;

  return {
    movementDie,
    gameHeader,
    tools: gameHeader && toolsOpen,
  };
}
