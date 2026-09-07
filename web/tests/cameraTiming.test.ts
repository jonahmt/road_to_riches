import assert from "node:assert/strict";
import test from "node:test";

import {
  adjacentStepAnimationDuration,
  AI_ADJACENT_STEP_ANIMATION_MS,
  HUMAN_ADJACENT_STEP_ANIMATION_MS,
} from "../src/cameraTiming.ts";

test("human and AI steps share the readable motion profile", () => {
  assert.equal(HUMAN_ADJACENT_STEP_ANIMATION_MS, 300);
  assert.equal(AI_ADJACENT_STEP_ANIMATION_MS, 300);
  assert.equal(adjacentStepAnimationDuration(1, 0), 300);
  assert.equal(adjacentStepAnimationDuration(1, null), 300);
});

test("local movement uses the same visible step duration", () => {
  assert.equal(adjacentStepAnimationDuration(0, 0), 300);
});
