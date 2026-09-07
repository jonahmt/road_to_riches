import type { Point3 } from "./geometry";

export const DIE_FACES: Array<{ value: number; position: Point3; rotation: Point3 }> = [
  { value: 1, position: [0, 0, 1.002], rotation: [0, 0, 0] },
  { value: 6, position: [0, 0, -1.002], rotation: [0, Math.PI, 0] },
  { value: 3, position: [1.002, 0, 0], rotation: [0, Math.PI / 2, 0] },
  { value: 4, position: [-1.002, 0, 0], rotation: [0, -Math.PI / 2, 0] },
  { value: 2, position: [0, 1.002, 0], rotation: [-Math.PI / 2, 0, 0] },
  { value: 5, position: [0, -1.002, 0], rotation: [Math.PI / 2, 0, 0] },
];

// Bring the authoritative result toward the viewer before applying the display tilt.
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

export function physicalDieFaceValue(face: number, displayed: number): number {
  if (displayed === 0) return 0;
  return face === 1 && displayed > 6 ? displayed : face;
}
