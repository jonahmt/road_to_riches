import type { GameState } from "./protocol";

export interface PresentationState {
  requestId: string;
  type: string;
  playerId: number;
  data: Record<string, unknown>;
  acknowledgmentPending: boolean;
  requiresAcknowledgment: boolean;
  coordinated?: boolean;
  before?: GameState;
  after?: GameState;
  revision?: number;
  generation?: number;
  driverPlayerId?: number | null;
  serverResolved?: boolean;
  localComplete?: boolean;
  canContinue?: boolean;
  elapsed?: number;
  phase?: "enter" | "readable" | "exit" | "complete";
}

export function enqueuePresentation(
  queue: PresentationState[],
  presentation: PresentationState,
): PresentationState[] {
  if (queue.some((item) => item.requestId === presentation.requestId)) return queue;
  // Fast AI movement can collect several suits before their effects finish.
  // Those transient effects must not hide a server-paced card or payout, which
  // could otherwise resolve before ever reaching the front of this queue.
  const remaining = presentation.requiresAcknowledgment && !presentation.coordinated
    ? queue.filter((item) => item.requiresAcknowledgment || item.type !== "suit_collected")
    : queue;
  return [...remaining, presentation];
}

export function markPresentationAcknowledging(
  queue: PresentationState[],
  requestId: string,
): PresentationState[] {
  return queue.map((item) =>
    item.requestId === requestId ? { ...item, acknowledgmentPending: true } : item,
  );
}

export function resolvePresentation(
  queue: PresentationState[],
  requestId: string,
): PresentationState[] {
  return queue.flatMap((item) => item.requestId !== requestId ? [item]
    : item.coordinated && !item.localComplete ? [{ ...item, serverResolved: true }] : []);
}

export function completePresentation(queue: PresentationState[], requestId: string): PresentationState[] {
  return queue.flatMap((item) => item.requestId !== requestId ? [item]
    : item.serverResolved ? [] : [{ ...item, localComplete: true }]);
}

export function dismissNonblockingPresentation(
  queue: PresentationState[],
  requestId: string,
): PresentationState[] {
  return queue.filter(
    (item) => item.requestId !== requestId || item.requiresAcknowledgment,
  );
}
