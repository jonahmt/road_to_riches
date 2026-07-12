import assert from "node:assert/strict";
import test from "node:test";

import {
  adjacentStepAnimationDuration,
  AI_ADJACENT_STEP_ANIMATION_MS,
  HUMAN_ADJACENT_STEP_ANIMATION_MS,
} from "../src/cameraTiming.ts";

test("AI adjacent movement is 35 percent slower than local movement", () => {
  assert.equal(HUMAN_ADJACENT_STEP_ANIMATION_MS, 100);
  assert.equal(AI_ADJACENT_STEP_ANIMATION_MS, 135);
  assert.equal(adjacentStepAnimationDuration(1, 0), 135);
  assert.equal(adjacentStepAnimationDuration(1, null), 135);
});

test("the locally assigned player keeps the fast adjacent movement timing", () => {
  assert.equal(adjacentStepAnimationDuration(0, 0), 100);
});
