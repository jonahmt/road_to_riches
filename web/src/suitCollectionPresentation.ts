export const STANDARD_SUITS = ["SPADE", "HEART", "DIAMOND", "CLUB"] as const;
export const SUIT_COLLECTION_DURATION_MS = 1_760;

export type CollectedSuit = (typeof STANDARD_SUITS)[number] | "WILD";

export interface SuitCollectionFacts {
  playerId: number;
  suit: CollectedSuit;
  squareId: number;
}

const COLLECTED_SUITS = new Set<CollectedSuit>([...STANDARD_SUITS, "WILD"]);

function finiteInteger(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isInteger(value) ? value : fallback;
}

export function suitCollectionFacts(
  data: Record<string, unknown>,
  fallbackPlayerId: number,
): SuitCollectionFacts {
  const normalizedSuit = String(data.suit ?? "WILD").toUpperCase() as CollectedSuit;
  return {
    playerId: finiteInteger(data.player_id, fallbackPlayerId),
    suit: COLLECTED_SUITS.has(normalizedSuit) ? normalizedSuit : "WILD",
    squareId: finiteInteger(data.square_id, -1),
  };
}

export function suitCollectionTargetSelector(facts: SuitCollectionFacts): string {
  return facts.suit === "WILD"
    ? `[data-hud-player-id="${facts.playerId}"][data-hud-suits]`
    : `[data-hud-player-id="${facts.playerId}"][data-hud-suit="${facts.suit}"]`;
}
