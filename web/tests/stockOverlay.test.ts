import assert from "node:assert/strict";
import test from "node:test";

import {
  clampStockQuantity,
  defaultStockQuantity,
  districtLabel,
  maxBuyQuantity,
} from "../src/stockOverlay.ts";

test("buy quantity respects cash and the per-opportunity cap", () => {
  assert.equal(maxBuyQuantity(1_345, 4), 99);
  assert.equal(maxBuyQuantity(30, 13), 2);
  assert.equal(maxBuyQuantity(30, 0), 0);
});

test("liquidation defaults to the minimum shares needed to cover the deficit", () => {
  assert.equal(defaultStockQuantity("liquidate", 20, 10, 21), 3);
  assert.equal(defaultStockQuantity("liquidate", 2, 10, 50), 2);
  assert.equal(defaultStockQuantity("sell", 20, 10, 21), 1);
});

test("stock quantities remain integral and inside the legal range", () => {
  assert.equal(clampStockQuantity(0, 12), 1);
  assert.equal(clampStockQuantity(7.9, 12), 7);
  assert.equal(clampStockQuantity(20, 12), 12);
  assert.equal(clampStockQuantity(5, 0), 0);
});

test("district labels use compact letter names", () => {
  assert.equal(districtLabel(0), "District A");
  assert.equal(districtLabel(4), "District E");
  assert.equal(districtLabel(26), "District 27");
});
