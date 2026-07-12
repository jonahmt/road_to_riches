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
  return queue.some((item) => item.requestId === presentation.requestId)
    ? queue
    : [...queue, presentation];
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
