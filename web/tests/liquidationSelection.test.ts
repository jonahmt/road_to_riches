import assert from "node:assert/strict";
import test from "node:test";

import {
  hasLiquidatableStock,
  liquidationShopChoices,
} from "../src/liquidationSelection.ts";

test("liquidation shop choices preserve only valid board targets", () => {
  assert.deepEqual(
    liquidationShopChoices({
      shops: [
        { square_id: 4, sell_value: 120 },
        { square_id: 9, sell_value: 75 },
        { square_id: "bad", sell_value: 999 },
      ],
    }),
    [
      { squareId: 4, sellValue: 120 },
      { squareId: 9, sellValue: 75 },
    ],
  );
});

test("liquidation stock availability requires a positive holding", () => {
  assert.equal(hasLiquidatableStock({ stock: { 0: { quantity: 0 }, 1: { quantity: 3 } } }), true);
  assert.equal(hasLiquidatableStock({ stock: { 0: { quantity: 0 } } }), false);
});
