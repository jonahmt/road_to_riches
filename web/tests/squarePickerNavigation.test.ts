import assert from "node:assert/strict";
import test from "node:test";
import type { SquareInfo } from "../src/protocol.ts";
import { nearbySquare, cycleSquare, initialSquare, directionalSquare } from "../src/squarePickerNavigation.ts";

const squares = [
  { id: 9, position: [-4.5, 2.25] },
  { id: 3, position: [-0.5, 2.25] },
  { id: 7, position: [-0.5, 6.25] },
] as SquareInfo[];

test("cursor snaps near a center but remains free between squares", () => {
  assert.equal(nearbySquare([-4.5, 2.25], squares)?.id, 9);
  assert.equal(nearbySquare([-4.5 + 1.3, 2.25], squares)?.id, 9);
  assert.equal(nearbySquare([-4.5 + 1.4, 2.25], squares), null);
  assert.equal(nearbySquare([-2.5, 2.25], squares), null);
  assert.equal(nearbySquare([-4.5, 2.25], []), null);
});

test("snapping chooses the nearest square with deterministic ties", () => {
  assert.equal(nearbySquare([-2.4, 2.25], squares, 3)?.id, 3);
  assert.equal(nearbySquare([-2.5, 2.25], squares, 3)?.id, 3);
  assert.equal(nearbySquare([-2.5, 2.25], [...squares].reverse(), 3)?.id, 3);
});

test("previous and next cycle only legal choices, including from free space", () => {
  const eligible = new Set([7, 9, 999]);
  assert.equal(cycleSquare(squares, eligible, null, 1), 7);
  assert.equal(cycleSquare(squares, eligible, null, -1), 9);
  assert.equal(cycleSquare(squares, eligible, 9, 1), 7);
  assert.equal(cycleSquare(squares, eligible, 7, -1), 9);
  assert.equal(cycleSquare(squares, new Set(), 7, 1), null);
});

test("initial selection finds the closest legal square without changing board order", () => {
  const before = structuredClone(squares);
  assert.equal(initialSquare(squares, new Set([7, 9]), 3), 7);
  assert.equal(initialSquare(squares, new Set([9]), 7), 9);
  assert.equal(initialSquare(squares, new Set(), 3), null);
  assert.deepEqual(squares, before);
});

test("2D spatial browsing follows the projection and stops at board edges", () => {
  assert.equal(directionalSquare(squares, 9, [1, 0]), 3);
  assert.equal(directionalSquare(squares, 3, [0, 1]), 7);
  assert.equal(directionalSquare(squares, 9, [-1, 0]), null);
  assert.equal(directionalSquare(squares, 3, [1, 0], ([x, z]) => [-x, z]), 9);
  assert.equal(directionalSquare(squares, null, [1, 0]), null);
});
