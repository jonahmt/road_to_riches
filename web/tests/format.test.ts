import assert from "node:assert/strict";
import test from "node:test";

import { formatGold } from "../src/format.ts";

test("formatGold renders monetary values without a G suffix", () => {
  assert.equal(formatGold(1_234), "1,234");
  assert.equal(formatGold(-42), "-42");
  assert.equal(formatGold(19.6), "20");
});

test("formatGold preserves the missing-value placeholder", () => {
  assert.equal(formatGold(null), "-");
  assert.equal(formatGold(undefined), "-");
});
