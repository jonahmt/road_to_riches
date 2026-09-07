import type { GameState, InputRequest, SquareInfo } from "../protocol.ts";

export const TILE_SIZE = 4;
export const TILE_TOP = 0.4;
export const TILE_SURFACE_SIZE = 3.59;
export type Point3 = [number, number, number];
export type BoardProjector = (position: readonly [number, number]) => [number, number];

export function projectMovementRequest(request: InputRequest, project: BoardProjector | null): InputRequest {
  if (request.type !== "CHOOSE_PATH" || !project) return request;
  const point = (value: unknown) => Array.isArray(value) && value.length >= 2 &&
    typeof value[0] === "number" && typeof value[1] === "number" ? project([value[0], value[1]]) : value;
  return { ...request, data: { ...request.data,
    current_position: point(request.data.current_position),
    undo_position: point(request.data.undo_position),
    choices: Array.isArray(request.data.choices) ? request.data.choices.map((choice: unknown) =>
      choice && typeof choice === "object" ? { ...choice, position: point((choice as { position?: unknown }).position) } : choice,
    ) : request.data.choices,
  } };
}

// Board coordinates remain authoritative. Height is presentation-only.
export function boardPoint(position: readonly [number, number], height = TILE_TOP): Point3 {
  return [position[0], height, position[1]];
}

export function boardExtent(squares: readonly Pick<SquareInfo, "position">[]) {
  const xs = squares.map((square) => square.position[0]);
  const zs = squares.map((square) => square.position[1]);
  const minX = squares.length ? Math.min(...xs) - TILE_SIZE / 2 : -2;
  const maxX = squares.length ? Math.max(...xs) + TILE_SIZE / 2 : 2;
  const minZ = squares.length ? Math.min(...zs) - TILE_SIZE / 2 : -2;
  const maxZ = squares.length ? Math.max(...zs) + TILE_SIZE / 2 : 2;
  return { center: [(minX + maxX) / 2, 0, (minZ + maxZ) / 2] as Point3,
    width: maxX - minX, depth: maxZ - minZ };
}

export function focusPoint(state: GameState, districtId: number | null): Point3 {
  const district = districtId === null ? [] : state.board.squares.filter(
    (square) => square.type === "SHOP" && square.property_district === districtId,
  );
  if (district.length) {
    return [district.reduce((sum, square) => sum + square.position[0], 0) / district.length,
      TILE_TOP, district.reduce((sum, square) => sum + square.position[1], 0) / district.length];
  }
  const player = state.players[state.current_player_index];
  const square = state.board.squares.find((candidate) => candidate.id === player?.position);
  return square ? boardPoint(square.position) : boardExtent(state.board.squares).center;
}

export function piecePositions(state: GameState) {
  const activeId = state.players[state.current_player_index]?.player_id;
  const squares = new Map(state.board.squares.map((square) => [square.id, square]));
  return state.players.filter((player) => !player.bankrupt).flatMap((player) => {
    const square = squares.get(player.position);
    if (!square) return [];
    const active = player.player_id === activeId;
    const others = state.players.filter((other) => !other.bankrupt &&
      other.position === player.position && other.player_id !== activeId);
    const index = others.findIndex((other) => other.player_id === player.player_id);
    return [{ player, active, position: boardPoint([
      square.position[0] + (active ? 0 : (index - (others.length - 1) / 2) * 0.85),
      square.position[1] + (active ? 0.85 : 1.35),
    ]), scale: active ? 1.22 : 0.48 }];
  });
}

export function canPickSquare(id: number, eligibleIds: ReadonlySet<number> | null): boolean {
  return eligibleIds === null || eligibleIds.has(id);
}
