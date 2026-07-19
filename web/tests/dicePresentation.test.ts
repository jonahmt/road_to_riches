import assert from "node:assert/strict";
import test from "node:test";

import {
  dieFinalTransform,
  displayedDiceValue,
  nextDiceState,
} from "../src/dicePresentation.ts";

test("authoritative roll messages advance animation identity only when requested", () => {
  const rolled = nextDiceState(null, {
    value: 5,
    remaining: 5,
    purpose: "movement",
    animate: true,
  });
  const moved = nextDiceState(rolled, {
    value: 5,
    remaining: 4,
    purpose: "movement",
    animate: false,
  });
  const eventRoll = nextDiceState(moved, {
    value: 3,
    remaining: 0,
    purpose: "event",
    animate: true,
  });

  assert.equal(rolled.animationId, 1);
  assert.equal(moved.animationId, 1);
  assert.equal(eventRoll.animationId, 2);
  assert.equal(eventRoll.purpose, "event");
});

test("legacy dice messages remain static movement updates", () => {
  assert.deepEqual(nextDiceState(null, { value: 4, remaining: 2 }), {
    value: 4,
    remaining: 2,
    purpose: "movement",
    animationId: 0,
  });
});

test("movement dice switch from the rolled result to remaining movement", () => {
  const movement = nextDiceState(null, {
    value: 6,
    remaining: 4,
    purpose: "movement",
  });
  const event = nextDiceState(null, { value: 3, remaining: 0, purpose: "event" });

  assert.equal(displayedDiceValue(movement, false), 6);
  assert.equal(displayedDiceValue(movement, true), 4);
  assert.equal(displayedDiceValue(event, true), 3);
});

test("standard die results settle to distinct cube orientations", () => {
  const transforms = new Set(Array.from({ length: 6 }, (_, index) => dieFinalTransform(index + 1)));
  assert.equal(transforms.size, 6);
  assert.match(dieFinalTransform(8), /rotateX/);
});
