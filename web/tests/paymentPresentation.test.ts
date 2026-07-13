import assert from "node:assert/strict";
import test from "node:test";

import { rentPaymentCashDeltas, rentPaymentFacts } from "../src/paymentPresentation.ts";

test("rent payment facts preserve a payment without dividends", () => {
  assert.deepEqual(
    rentPaymentFacts(
      {
        payer_id: 0,
        owner_id: 2,
        square_id: 14,
        district_id: 3,
        rent_amount: 72,
        dividends: [],
      },
      9,
    ),
    {
      payerId: 0,
      ownerId: 2,
      squareId: 14,
      districtId: 3,
      rentAmount: 72,
      dividends: [],
    },
  );
});

test("rent payment facts keep positive dividend payouts", () => {
  assert.deepEqual(
    rentPaymentFacts(
      {
        payer_id: 3,
        owner_id: 1,
        square_id: 20,
        district_id: 4,
        rent_amount: 27,
        dividends: [
          { player_id: 0, amount: 5 },
          { player_id: 1, amount: 0 },
          { player_id: "bad", amount: 9 },
        ],
      },
      9,
    ),
    {
      payerId: 3,
      ownerId: 1,
      squareId: 20,
      districtId: 4,
      rentAmount: 27,
      dividends: [{ playerId: 0, amount: 5 }],
    },
  );
});

test("payment cash deltas combine rent and dividends for the player HUD", () => {
  assert.deepEqual(
    rentPaymentCashDeltas({
      payerId: 3,
      ownerId: 1,
      squareId: 7,
      districtId: 4,
      rentAmount: 27,
      dividends: [
        { playerId: 0, amount: 5 },
        { playerId: 1, amount: 2 },
      ],
    }),
    [
      { playerId: 0, amount: 5 },
      { playerId: 1, amount: 29 },
      { playerId: 3, amount: -27 },
    ],
  );
});
