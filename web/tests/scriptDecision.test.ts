import assert from "node:assert/strict";
import test from "node:test";

import { scriptDecisionOptions } from "../src/scriptDecision.ts";

test("script decision options preserve labels, order, and response values", () => {
  const nestedValue = { destination: 7, cost: 100 };

  assert.deepEqual(
    scriptDecisionOptions({
      "Warp to the bank": nestedValue,
      "Stay here": false,
      "Take 20G": 20,
    }),
    [
      { label: "Warp to the bank", value: nestedValue },
      { label: "Stay here", value: false },
      { label: "Take 20G", value: 20 },
    ],
  );
});

test("script decision options reject non-object payloads", () => {
  assert.deepEqual(scriptDecisionOptions(null), []);
  assert.deepEqual(scriptDecisionOptions(["a", "b"]), []);
  assert.deepEqual(scriptDecisionOptions("choose"), []);
});
