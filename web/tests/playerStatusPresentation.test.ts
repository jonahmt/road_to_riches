import assert from "node:assert/strict";
import test from "node:test";

import { BOOM_ICON_COLOR, BOON_ICON_COLOR } from "../src/boardColors.ts";
import {
  commissionIndicatorColor,
  commissionStatusIndicators,
} from "../src/playerStatusPresentation.ts";

test("non-commission statuses do not create HUD stars", () => {
  assert.deepEqual(
    commissionStatusIndicators([{ type: "poison", modifier: 10, remaining_turns: 2 }]),
    [],
  );
});

test("Boon and Boom commissions map to their status star kinds", () => {
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

test("HUD commission stars reuse the established Boon and Boom icon colors", () => {
  assert.equal(commissionIndicatorColor("boon"), BOON_ICON_COLOR);
  assert.equal(commissionIndicatorColor("boom"), BOOM_ICON_COLOR);
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
