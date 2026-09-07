import { ExtrudeGeometry, Path, Shape } from "three";

function roundedSquare<T extends Path>(path: T, half: number, radius: number): T {
  path.moveTo(-half + radius, -half);
  path.lineTo(half - radius, -half);
  path.quadraticCurveTo(half, -half, half, -half + radius);
  path.lineTo(half, half - radius);
  path.quadraticCurveTo(half, half, half - radius, half);
  path.lineTo(-half + radius, half);
  path.quadraticCurveTo(-half, half, -half, half - radius);
  path.lineTo(-half, -half + radius);
  path.quadraticCurveTo(-half, -half, -half + radius, -half);
  path.closePath();
  return path;
}

export function makeTileRim() {
  const outline = roundedSquare(new Shape(), 1.96, 0.13);
  outline.holes.push(roundedSquare(new Path(), 1.79, 0.11));
  return new ExtrudeGeometry(outline, { depth: 0.08, steps: 1, curveSegments: 5,
    bevelEnabled: true, bevelSegments: 2, bevelSize: 0.035, bevelThickness: 0.025 });
}
