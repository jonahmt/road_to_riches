export const PLAYER_CONTROL_REPLACED_CLOSE_CODE = 4001;
export const SLOW_CLIENT_CLOSE_CODE = 4002;
export const SLOW_CLIENT_CLOSE_REASON = "Connection too slow; reconnect to resume.";

export function playerControlReplacementReason(code: number, reason: string): string | null {
  if (code !== PLAYER_CONTROL_REPLACED_CLOSE_CODE) {
    return null;
  }
  return reason || "This game was opened in another browser tab.";
}

export function slowClientCloseReason(code: number, reason: string): string | null {
  if (code !== SLOW_CLIENT_CLOSE_CODE) {
    return null;
  }
  return reason || SLOW_CLIENT_CLOSE_REASON;
}
