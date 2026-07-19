import assert from "node:assert/strict";
import test from "node:test";

import { closedShopTurns } from "../src/shopStatusPresentation.ts";

test("open shops have no closed-state presentation", () => {
  assert.equal(
    closedShopTurns([{ type: "price_hike", modifier: 20, remaining_turns: 2 }]),
    null,
  );
});

test("closed shops expose the authoritative remaining duration", () => {
  assert.equal(
    closedShopTurns([{ type: "closed", modifier: 0, remaining_turns: 3 }]),
    3,
  );
});

test("overlapping closed statuses keep the shop closed for the longest duration", () => {
  assert.equal(
    closedShopTurns([
      { type: "closed", modifier: 0, remaining_turns: 1 },
      { type: "closed", modifier: 0, remaining_turns: 4 },
    ]),
    4,
  );
});
