export const PLAYER_CONTROL_REPLACED_CLOSE_CODE = 4001;

export function playerControlReplacementReason(code: number, reason: string): string | null {
  if (code !== PLAYER_CONTROL_REPLACED_CLOSE_CODE) {
    return null;
  }
  return reason || "This game was opened in another browser tab.";
}
