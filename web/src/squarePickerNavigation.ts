import type { SquareInfo } from "./protocol.ts";

export interface BoardSquareSelection {
  eligibleSquareIds: ReadonlySet<number>;
  selectedSquareId: number | null;
  chosenSquareIds?: ReadonlySet<number>;
  onConfirmSquare: (squareId: number) => void;
}

export interface SquareCursorControl {
  position: [number, number] | null;
  display: [number, number] | null;
  jumpTo: [number, number] | null;
  keys: Set<string>;
  reframe: boolean;
  enabled: boolean;
  attached: boolean;
  snapAll: boolean;
}

export function createSquareCursor(): SquareCursorControl {
  return { position: null, display: null, jumpTo: null, keys: new Set(), reframe: false,
    enabled: true, attached: false, snapAll: false };
}

export function nearbySquare(position: readonly [number, number], squares: readonly SquareInfo[], radius = 1.35) {
  return squares.map((square) => ({ square, distance: Math.hypot(square.position[0] - position[0], square.position[1] - position[1]) }))
    .filter((candidate) => candidate.distance <= radius)
    .sort((a, b) => a.distance - b.distance || a.square.id - b.square.id)[0]?.square ?? null;
}

export function cycleSquare(squares: readonly SquareInfo[], eligible: ReadonlySet<number>, current: number | null, direction: number) {
  const choices = squares.filter((square) => eligible.has(square.id)).sort((a, b) => a.id - b.id);
  if (!choices.length) return null;
  const index = choices.findIndex((square) => square.id === current);
  return choices[index < 0 ? (direction > 0 ? 0 : choices.length - 1)
    : (index + direction + choices.length) % choices.length]!.id;
}

export function initialSquare(squares: readonly SquareInfo[], eligible: ReadonlySet<number>, origin: number | null) {
  const from = squares.find((square) => square.id === origin)?.position ?? [0, 0];
  return squares.filter((square) => eligible.has(square.id)).sort((a, b) =>
    Math.hypot(a.position[0] - from[0], a.position[1] - from[1])
    - Math.hypot(b.position[0] - from[0], b.position[1] - from[1]) || a.id - b.id)[0]?.id ?? null;
}

/** Spatial browsing includes unavailable squares; only confirmation requires eligibility. */
export function directionalSquare(squares: readonly SquareInfo[], current: number | null, direction: readonly [number, number],
  project: (position: readonly [number, number]) => readonly [number, number] = (position) => position) {
  const origin = squares.find((square) => square.id === current);
  if (!origin) return null;
  const from = project(origin.position);
  return squares.filter((square) => square.id !== current).map((square) => {
    const position = project(square.position), dx = position[0] - from[0], dy = position[1] - from[1];
    const forward = dx * direction[0] + dy * direction[1];
    const sideways = Math.abs(dx * direction[1] - dy * direction[0]);
    return { id: square.id, forward, score: Math.hypot(dx, dy) + sideways * 2 };
  }).filter((square) => square.forward > 0.01).sort((a, b) => a.score - b.score || a.id - b.id)[0]?.id ?? null;
}
