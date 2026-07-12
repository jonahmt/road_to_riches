import assert from "node:assert/strict";
import test from "node:test";

import { stockPriceChangeFacts } from "../src/stockPricePresentation.ts";

test("stock price change facts preserve rise and holdings impact", () => {
  assert.deepEqual(
    stockPriceChangeFacts(
      {
        player_id: 3,
        district_id: 0,
        old_price: 9,
        new_price: 10,
        delta: 1,
        holdings: [
          { player_id: 0, quantity: 0, value_change: 0 },
          { player_id: 3, quantity: 153, value_change: 153 },
        ],
      },
      8,
    ),
    {
      playerId: 3,
      districtId: 0,
      oldPrice: 9,
      newPrice: 10,
      delta: 1,
      holdings: [
        { playerId: 0, quantity: 0, valueChange: 0 },
        { playerId: 3, quantity: 153, valueChange: 153 },
      ],
    },
  );
});

test("stock price change derives a negative delta from authoritative prices", () => {
  const facts = stockPriceChangeFacts(
    {
      district_id: 2,
      old_price: 14,
      new_price: 12,
      delta: 99,
      holdings: [{ player_id: 1, quantity: 8, value_change: -16 }],
    },
    1,
  );

  assert.equal(facts.delta, -2);
  assert.deepEqual(facts.holdings, [{ playerId: 1, quantity: 8, valueChange: -16 }]);
});
