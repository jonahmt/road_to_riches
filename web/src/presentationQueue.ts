export interface PresentationState {
  requestId: string;
  type: string;
  playerId: number;
  data: Record<string, unknown>;
  acknowledgmentPending: boolean;
  requiresAcknowledgment: boolean;
}

export function enqueuePresentation(
  queue: PresentationState[],
  presentation: PresentationState,
): PresentationState[] {
  if (queue.some((item) => item.requestId === presentation.requestId)) return queue;
  // Fast AI movement can collect several suits before their effects finish.
  // Those transient effects must not hide a server-paced card or payout, which
  // could otherwise resolve before ever reaching the front of this queue.
  const remaining = presentation.requiresAcknowledgment
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
  return queue.filter((item) => item.requestId !== requestId);
}

export function dismissNonblockingPresentation(
  queue: PresentationState[],
  requestId: string,
): PresentationState[] {
  return queue.filter(
    (item) => item.requestId !== requestId || item.requiresAcknowledgment,
  );
}
