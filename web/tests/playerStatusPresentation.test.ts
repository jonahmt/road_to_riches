import assert from "node:assert/strict";
import test from "node:test";

import { commissionStatusIndicators } from "../src/playerStatusPresentation.ts";

test("non-commission statuses do not create HUD stars", () => {
  assert.deepEqual(
    commissionStatusIndicators([{ type: "poison", modifier: 10, remaining_turns: 2 }]),
    [],
  );
});

test("Boon and Boom commissions map to white and orange star kinds", () => {
  assert.deepEqual(
    commissionStatusIndicators([
      { type: "commission", modifier: 20, remaining_turns: 3 },
      { type: "commission", modifier: 50, remaining_turns: 2 },
    ]),
    [
      { kind: "boon", percent: 20, remainingTurns: 3 },
      { kind: "boom", percent: 50, remainingTurns: 2 },
    ],
  );
});

test("stacked commission statuses retain one indicator per active effect", () => {
  assert.equal(
    commissionStatusIndicators([
      { type: "commission", modifier: 20, remaining_turns: 4 },
      { type: "commission", modifier: 20, remaining_turns: 1 },
    ]).length,
    2,
  );
});
