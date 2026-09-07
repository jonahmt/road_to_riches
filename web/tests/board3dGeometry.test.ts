import assert from "node:assert/strict";
import test from "node:test";
import { boardExtent, boardPoint, canPickSquare, focusPoint, piecePositions, projectMovementRequest } from "../src/board3d/geometry.ts";
import { getWasdResponseMap } from "../src/controls.ts";
import type { GameState, InputRequest, SquareInfo } from "../src/protocol.ts";

test("3D tiles preserve negative and fractional board coordinates and touching edges", () => {
  assert.deepEqual(boardPoint([-4.5, 2.25]), [-4.5, 0.4, 2.25]);
  assert.deepEqual(boardExtent([{ position: [-4, 0] }, { position: [0, 0] }]),
    { center: [-2, 0, 0], width: 8, depth: 4 });
  assert.deepEqual(boardExtent([]), { center: [0, 0, 0], width: 4, depth: 4 });
});

const squares = [
  { id: 0, position: [0, 0], type: "BANK", property_district: null },
  { id: 4, position: [-4, 0], type: "SHOP", property_district: 2 },
  { id: 5, position: [-4, 8], type: "SHOP", property_district: 2 },
] as SquareInfo[];

test("district focus averages authoritative shops and falls back to the active player's square", () => {
  const state = { board: { squares }, players: [{ player_id: 9, position: 4 }], current_player_index: 0 } as GameState;
  assert.deepEqual(focusPoint(state, 2), [-4, 0.4, 4]);
  assert.deepEqual(focusPoint(state, 99), [-4, 0.4, 0]);
  assert.deepEqual(focusPoint(state, null), [-4, 0.4, 0]);
});

test("piece layout follows player identity rather than index and excludes bankrupt or missing pieces", () => {
  const state = { board: { squares }, players: [
    { player_id: 5, position: 0, bankrupt: false },
    { player_id: 9, position: 0, bankrupt: false },
    { player_id: 11, position: 0, bankrupt: false },
    { player_id: 12, position: 0, bankrupt: true },
    { player_id: 13, position: 999, bankrupt: false },
  ], current_player_index: 1 } as GameState;
  const pieces = piecePositions(state);
  assert.deepEqual(pieces.map((piece) => piece.player.player_id), [5, 9, 11]);
  assert.equal(pieces[1].active, true);
  assert.notDeepEqual(pieces[0].position, pieces[2].position);
});

test("two to four co-located figures have separate bases inside their authoritative tile", () => {
  for (const count of [2, 3, 4]) {
    const state = { board: { squares }, players: Array.from({ length: count }, (_, player_id) =>
      ({ player_id, position: 4, bankrupt: false })), current_player_index: count - 1 } as GameState;
    const original = structuredClone(state);
    const pieces = piecePositions(state);
    for (let index = 0; index < pieces.length; index++) {
      const piece = pieces[index];
      const radius = 0.8 * piece.scale;
      assert.ok(Math.abs(piece.position[0] - (-4)) + radius <= 2);
      assert.ok(Math.abs(piece.position[2]) + radius <= 2);
      for (const other of pieces.slice(index + 1)) {
        const distance = Math.hypot(piece.position[0] - other.position[0], piece.position[2] - other.position[2]);
        assert.ok(distance >= radius + 0.8 * other.scale, "figure bases must not overlap");
      }
    }
    assert.deepEqual(state, original);
  }
});

test("an empty legal-square set allows no selections while ordinary inspection allows all", () => {
  assert.equal(canPickSquare(4, null), true);
  assert.equal(canPickSquare(4, new Set()), false);
  assert.equal(canPickSquare(4, new Set([4])), true);
  assert.equal(canPickSquare(5, new Set([4])), false);
});

test("orbiting changes screen-direction keys without changing server response values or source prompt", () => {
  const request: InputRequest = { type: "CHOOSE_PATH", player_id: 9, data: {
    current_position: [0, 0], can_undo: true, undo_position: [-4, 0],
    choices: [{ square_id: 4, position: [4, 0], type: "SHOP" }],
  } };
  const original = structuredClone(request);
  const rotated = projectMovementRequest(request, ([x, z]) => [-z, x]);
  assert.deepEqual(getWasdResponseMap(request), { a: "undo", d: 4 });
  assert.deepEqual(getWasdResponseMap(rotated), { s: 4, w: "undo" });
  assert.deepEqual(request, original);
  assert.strictEqual(projectMovementRequest(request, null), request);
  const stop: InputRequest = { type: "CONFIRM_STOP", player_id: 9, data: { can_undo: true } };
  assert.strictEqual(projectMovementRequest(stop, ([x, z]) => [-z, x]), stop);
});
