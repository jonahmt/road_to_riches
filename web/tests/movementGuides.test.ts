import assert from "node:assert/strict";
import test from "node:test";
import type { InputRequest } from "../src/protocol.ts";
import { movementGuides } from "../src/board3d/movementPresentation.ts";

const request: InputRequest = { type: "CHOOSE_PATH", player_id: 7, data: {
  current_position: [-8, 2], choices: [
    { square_id: 0, position: [-12, 2], type: "BANK" },
    { square_id: 42, position: [-4, 6], type: "SHOP" },
  ], can_undo: true, undo_position: [-8, -2],
} };

test("movement guides preserve server choice IDs and undo without modifying the prompt", () => {
  const original = structuredClone(request);
  const guides = movementGuides(request, 7);
  assert.deepEqual(guides.map(guide => guide.value), [0, 42, "undo"]);
  assert.equal(guides[0].label, "Move to Square #0");
  assert.equal(guides[2].label, "Undo last step");
  assert.deepEqual(request, original);
});

test("movement guides cannot authorize a move for another player or outside path selection", () => {
  assert.deepEqual(movementGuides(request, 0), []);
  assert.deepEqual(movementGuides(request, null), []);
  assert.deepEqual(movementGuides(null, 7), []);
  for (const type of ["PRE_ROLL", "CONFIRM_STOP", "BUY_SHOP"]) {
    assert.deepEqual(movementGuides({ ...request, type }, 7), []);
  }
});

test("guides point along negative and fractional board coordinates without overshooting short links", () => {
  const guide = movementGuides(request, 7)[1];
  assert.ok(Math.abs(guide.rotation + Math.PI / 4) < 1e-10);
  assert.ok(guide.position[0] > -8 && guide.position[0] < -4);
  assert.ok(Math.abs((guide.position[0] + 8) - (guide.position[2] - 2)) < 1e-10);
  const short = movementGuides({ ...request, data: { current_position: [-8, 2],
    choices: [{ square_id: 8, position: [-7.5, 2.25] }], can_undo: false } }, 7);
  assert.equal(short[0].position[0], -7.75);
  assert.equal(short[0].position[2], 2.125);
});

test("malformed choices, duplicate IDs, self-links, and unavailable undo do not create extra guides", () => {
  const guides = movementGuides({ ...request, data: { current_position: [0, 0], choices: [
    null, { square_id: 1 }, { square_id: "2", position: [4, 0] },
    { square_id: 3, position: [Infinity, 0] }, { square_id: 4, position: [0, 0] },
    { square_id: 5, position: [4, 0] }, { square_id: 5, position: [-4, 0] },
  ], can_undo: false, undo_position: [0, -4] } }, 7);
  assert.deepEqual(guides.map(guide => guide.value), [5]);
  assert.ok(guides[0].position[0] > 0);
  assert.deepEqual(movementGuides({ ...request, data: { ...request.data, current_position: [NaN, 0] } }, 7), []);
});
