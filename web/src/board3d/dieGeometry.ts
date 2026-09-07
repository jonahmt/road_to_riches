import type { Point3 } from "./geometry";

export const DIE_FACES: Array<{ value: number; position: Point3; rotation: Point3 }> = [
  { value: 1, position: [0, 0, 1.002], rotation: [0, 0, 0] },
  { value: 6, position: [0, 0, -1.002], rotation: [0, Math.PI, 0] },
  { value: 3, position: [1.002, 0, 0], rotation: [0, Math.PI / 2, 0] },
  { value: 4, position: [-1.002, 0, 0], rotation: [0, -Math.PI / 2, 0] },
  { value: 2, position: [0, 1.002, 0], rotation: [-Math.PI / 2, 0, 0] },
  { value: 5, position: [0, -1.002, 0], rotation: [Math.PI / 2, 0, 0] },
];

// Bring the authoritative result directly toward the viewer, with no display tilt.
// Three.js Y points up, unlike the CSS cube's Y axis.
export function physicalDieRotation(value: number): Point3 {
  switch (value) {
    case 2: return [Math.PI / 2, 0, 0];
    case 3: return [0, -Math.PI / 2, 0];
    case 4: return [0, Math.PI / 2, 0];
    case 5: return [-Math.PI / 2, 0, 0];
    case 6: return [0, Math.PI, 0];
    default: return [0, 0, 0];
  }
}

export function physicalDieSpin(value: number, progress: number): Point3 {
  const p = Math.min(1, Math.max(0, progress));
  const result = physicalDieRotation(value);
  // A brisk toss followed by a short braking phase, ending square to the camera.
  const brake = Math.max(0, (p - 0.7) / 0.3);
  const remaining = p < 0.7 ? 1 - p : 0.3 * (1 - brake) ** 2 * (1 + brake);
  return [result[0] + remaining * Math.PI * 4,
    result[1] + remaining * Math.PI * 6, Math.sin(p * Math.PI) * 0.15];
}

export function physicalDieFaceValue(face: number, displayed: number): number {
  if (displayed === 0) return 0;
  return face === 1 && displayed > 6 ? displayed : face;
}
