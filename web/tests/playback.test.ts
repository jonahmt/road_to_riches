import test from "node:test";
import assert from "node:assert/strict";
import { playbackNow, playbackSpeed, setPlaybackSpeed } from "../src/playback.ts";

test("speed changes preserve a continuous presentation clock", () => {
  setPlaybackSpeed(1);
  const before = playbackNow();
  setPlaybackSpeed(2);
  const after = playbackNow();
  assert(after >= before && after - before < 20);
  const real = performance.now();
  assert(Math.abs(playbackNow(real + 100) - playbackNow(real) - 200) < 1e-6);
  setPlaybackSpeed(1.5);
  assert(Math.abs(playbackNow(real + 100) - playbackNow(real) - 150) < 1e-6);
  setPlaybackSpeed(7);
  assert.equal(playbackSpeed(), 1);
});
