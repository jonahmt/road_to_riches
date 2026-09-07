import assert from "node:assert/strict";
import test from "node:test";
import { Euler, Vector3 } from "three";
import { DIE_PIPS } from "../src/dicePresentation.ts";
import { DIE_FACES, physicalDieFaceValue, physicalDieRotation } from "../src/board3d/dieGeometry.ts";

test("every authoritative standard result faces the camera on the solid die", () => {
  for (let result = 1; result <= 6; result++) {
    const face = DIE_FACES.find((candidate) => candidate.value === result)!;
    const normal = new Vector3(0, 0, 1)
      .applyEuler(new Euler(...face.rotation))
      .applyEuler(new Euler(...physicalDieRotation(result)));
    assert.ok(normal.distanceTo(new Vector3(0, 0, 1)) < 1e-10, `result ${result} must face the viewer`);
    const opposite = DIE_FACES.find((candidate) => candidate.value === 7 - result)!;
    assert.ok(new Vector3(...face.position).add(new Vector3(...opposite.position)).length() < 1e-10);
  }
});

test("countdown zero is blank and extended board rolls retain their authoritative pip count", () => {
  for (const face of DIE_FACES) assert.equal(physicalDieFaceValue(face.value, 0), 0);
  for (let value = 0; value <= 9; value++) {
    const frontFace = value >= 1 && value <= 6 ? value : 1;
    const displayed = physicalDieFaceValue(frontFace, value);
    assert.equal(DIE_PIPS[displayed].length, value);
    assert.equal(new Set(DIE_PIPS[displayed]).size, value);
    if (value === 0 || value > 6) assert.deepEqual(physicalDieRotation(value), [0, 0, 0]);
  }
});
