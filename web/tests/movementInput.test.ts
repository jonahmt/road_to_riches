import assert from "node:assert/strict";
import test from "node:test";
import { MovementInput } from "../src/movementInput.ts";

test("taps during a hop resolve against successive authoritative choices", () => {
  const input = new MovementInput();
  for (let i = 0; i < 3; i++) { input.press("d"); input.release("d"); }
  assert.equal(input.next({ d: 4 }), 4);
  assert.equal(input.next({ d: 5 }), 5);
  assert.equal(input.next({ d: 6 }), 6);
  assert.equal(input.next({ d: 7 }), undefined);
});

test("a held direction chains until release without depending on OS repeat", () => {
  const input = new MovementInput();
  input.press("d"); input.press("d");
  assert.equal(input.next({ d: 4 }), 4);
  assert.equal(input.next({ d: 5 }), 5);
  input.release("d");
  assert.equal(input.next({ d: 6 }), undefined);
});

test("a corner cannot turn held movement into undo or retain invalid queued taps", () => {
  const input = new MovementInput();
  input.press("d"); assert.equal(input.next({ d: 4 }), 4);
  assert.equal(input.next({ d: "undo", s: 5 }), undefined);
  assert.equal(input.next({ d: 8 }), undefined);
  input.press("a"); input.release("a"); input.press("d");
  assert.equal(input.next({ a: "undo", d: 5 }), "undo");
  assert.equal(input.next({ d: 4 }), undefined);
});

test("buffered and held diagonal chords use the new camera-relative mapping", () => {
  const input = new MovementInput();
  input.press("w"); input.press("d");
  assert.equal(input.next({ dw: 2, s: "undo" }), 2);
  assert.equal(input.next({ dw: 3, a: "undo" }), 3);
  input.clear();
  input.press("s"); input.release("s");
  assert.equal(input.next({ s: 4 }), 4);
});

test("clearing for a dialog, final stop, blur or disconnect drops both taps and held keys", () => {
  const input = new MovementInput();
  input.press("d"); input.release("d"); input.press("d"); input.clear();
  assert.equal(input.next({ d: 4 }), undefined);
});
