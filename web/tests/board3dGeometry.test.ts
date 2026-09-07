import assert from "node:assert/strict";
import test from "node:test";
import { boardExtent, boardPoint, canPickSquare, focusPoint, piecePositions, pieceStepPosition, projectMovementRequest, shopModelPose } from "../src/board3d/geometry.ts";
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
      const radius = piece.baseRadius * piece.scale;
      assert.ok(Math.abs(piece.position[0] - (-4)) + radius <= 2);
      assert.ok(Math.abs(piece.position[2]) + radius <= 2);
      for (const other of pieces.slice(index + 1)) {
        const distance = Math.hypot(piece.position[0] - other.position[0], piece.position[2] - other.position[2]);
        assert.ok(distance >= radius + other.baseRadius * other.scale, "figure bases must not overlap");
      }
    }
    assert.deepEqual(state, original);
  }
});

test("occupied shops keep rent strips, figures and shop models separate through turn handoffs", () => {
  const shop = { ...squares[1], property_owner: 0 };
  for (const count of [1, 2, 3, 4]) {
    for (const activeIndex of Array.from({ length: count + 1 }, (_, index) => index)) {
      if (count === 4 && activeIndex === count) continue;
      const players = Array.from({ length: count }, (_, index) =>
        ({ player_id: index + 5, position: shop.id, bankrupt: false }));
      // The last case keeps every shop occupant inactive, with the turn elsewhere.
      if (activeIndex === count) players.push({ player_id: 99, position: 0, bankrupt: false });
      const state = { board: { squares: [squares[0], shop] }, players, current_player_index: activeIndex } as GameState;
      const original = structuredClone(state);
      const pieces = piecePositions(state).filter((piece) => piece.player.position === shop.id);
      const pose = shopModelPose(activeIndex < count);
      // Conservative roof/eave and awning bounds before the root transform.
      const model = {
        left: pose.position[0] - 1.12 * pose.scale, right: pose.position[0] + 1.12 * pose.scale,
        back: pose.position[2] - 0.99 * pose.scale, front: pose.position[2] + 1.24 * pose.scale,
      };
      for (const [index, piece] of pieces.entries()) {
        const x = piece.position[0] - shop.position[0], z = piece.position[2] - shop.position[1];
        const radius = piece.baseRadius * piece.scale;
        assert.ok(Math.abs(x) + radius <= 2 && Math.abs(z) + radius <= 2, "bases stay inside the tile");
        assert.ok(z + radius < 0.58, "no base covers the rent plaque");
        const distanceToModel = Math.hypot(Math.max(model.left - x, 0, x - model.right),
          Math.max(model.back - z, 0, z - model.front));
        assert.ok(distanceToModel > radius, "bases stay clear of the house and awning");
        for (const other of pieces.slice(index + 1)) {
          assert.ok(Math.hypot(piece.position[0] - other.position[0], piece.position[2] - other.position[2])
            >= radius + other.baseRadius * other.scale, "bases stay separate");
        }
      }
      assert.deepEqual(state, original);
    }
  }
});

test("larger custom parties retain a finite layout when the four-player shop arrangement is full", () => {
  const state = { board: { squares: [{ ...squares[1], property_owner: 0 }] },
    players: Array.from({ length: 6 }, (_, player_id) => ({ player_id, position: 4, bankrupt: false })),
    current_player_index: 0 } as GameState;
  assert.equal(piecePositions(state).length, 6);
  assert.ok(piecePositions(state).every((piece) => piece.position.every(Number.isFinite)));
});

test("inactive shop figures stay put and clear the house throughout arrival and departure", () => {
  const shop = { ...squares[1], property_owner: 0 };
  const state = { board: { squares: [squares[0], shop] },
    players: Array.from({ length: 4 }, (_, player_id) => ({ player_id, position: shop.id, bankrupt: false })),
    current_player_index: 0 } as GameState;
  const occupied = piecePositions(state).filter((piece) => !piece.active);
  state.players[0].position = 0;
  const unoccupied = piecePositions(state).filter((piece) => !piece.active);
  assert.deepEqual(occupied, unoccupied, "inactive figures need no rearrangement as the active figure moves");
  const compact = shopModelPose(true), full = shopModelPose(false);
  for (let frame = 0; frame <= 40; frame++) {
    const t = frame / 40;
    const right = compact.position[0] + (full.position[0] - compact.position[0]) * t
      + 1.12 * (compact.scale + (full.scale - compact.scale) * t);
    for (const piece of occupied) {
      assert.ok(piece.position[0] - shop.position[0] - piece.baseRadius * piece.scale > right,
        "the growing roof never reaches the inactive figures");
    }
  }
});

test("shop steps pass in front of the miniature house in either direction and keep exact endpoints", () => {
  const pose = shopModelPose(true);
  for (const direction of [-1, 1]) {
    const from: [number, number, number] = [-0.9, 0.4, -0.35];
    const to: [number, number, number] = [from[0] + direction * 4, 0.4, -0.35];
    const houseX = (direction === 1 ? 0 : -4) + pose.position[0];
    for (let index = 0; index <= 20; index++) {
      const point = pieceStepPosition(from, to, index / 20, 1.3);
      const distance = Math.hypot(Math.max(houseX - 1.12 * pose.scale - point[0], 0, point[0] - houseX - 1.12 * pose.scale),
        Math.max(pose.position[2] - 0.99 * pose.scale - point[2], 0, point[2] - (pose.position[2] + 1.24 * pose.scale)));
      assert.ok(distance > 0.65 * 1.22, "the moving base clears the miniature shop");
      assert.ok(point[2] + 0.65 * 1.22 < 2, "the path stays inside the row of tiles");
    }
    assert.deepEqual(pieceStepPosition(from, to, 0, 1.3), from);
    const end = pieceStepPosition(from, to, 1, 1.3);
    assert.ok(end.every((value, index) => Math.abs(value - to[index]!) < 1e-12));
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
