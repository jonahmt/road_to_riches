import assert from "node:assert/strict";
import test from "node:test";

import {
  boardSelectionScrimPath,
  clampInvestmentAmount,
  investmentSquareChoices,
  maximumInvestment,
  squareIdsFromOptions,
} from "../src/squareSelection.ts";

test("selection scrim has cutouts only for eligible squares", () => {
  const path = boardSelectionScrimPath(
    { minX: -3, minY: -3, width: 20, height: 12 },
    [
      { id: 1, position: [0, 0] },
      { id: 2, position: [4, 0] },
      { id: 3, position: [8, 0] },
    ],
    new Set([1, 3]),
  );

  assert.ok(path?.startsWith("M-3 -3h20v12h-20Z"));
  assert.ok(path?.includes("M-2.07 -2.07h4.14v4.14h-4.14Z"));
  assert.ok(path?.includes("M5.93 -2.07h4.14v4.14h-4.14Z"));
  assert.equal(path?.includes("M1.93 -2.07h4.14v4.14h-4.14Z"), false);
});

test("selection scrim is omitted when every square is eligible", () => {
  assert.equal(
    boardSelectionScrimPath(
      { minX: -3, minY: -3, width: 12, height: 6 },
      [
        { id: 1, position: [0, 0] },
        { id: 2, position: [4, 0] },
      ],
      new Set([1, 2]),
    ),
    null,
  );
});

test("generic square options expose only valid square ids", () => {
  assert.deepEqual(
    squareIdsFromOptions([{ square_id: 4 }, { square_id: "9" }, { player_id: 2 }, null]),
    [4, 9],
  );
});

test("investment choices keep only shops with remaining capital", () => {
  assert.deepEqual(
    investmentSquareChoices([
      { square_id: 7, current_value: 240, max_capital: 180, district: 2 },
      { square_id: 8, current_value: 300, max_capital: 0, district: 2 },
      { square_id: -1, current_value: 100, max_capital: 20, district: null },
    ]),
    [{ squareId: 7, currentValue: 240, maxCapital: 180, districtId: 2 }],
  );
});

test("investment maximum respects capital and cash plus liquidatable stock", () => {
  const choice = { squareId: 7, currentValue: 240, maxCapital: 180, districtId: 2 };
  assert.equal(maximumInvestment(choice, 125), 125);
  assert.equal(maximumInvestment(choice, 500), 180);
});

test("investment amount remains integral and inside the legal range", () => {
  assert.equal(clampInvestmentAmount(0, 125), 1);
  assert.equal(clampInvestmentAmount(74.9, 125), 74);
  assert.equal(clampInvestmentAmount(200, 125), 125);
  assert.equal(clampInvestmentAmount(10, 0), 0);
});
