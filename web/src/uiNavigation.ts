export type Direction = "up" | "down" | "left" | "right";
export interface ControlRect { x: number; y: number; width: number; height: number }

export function navigationDirection(key: string): Direction | null {
  return ({ w: "up", arrowup: "up", s: "down", arrowdown: "down",
    a: "left", arrowleft: "left", d: "right", arrowright: "right" } as Record<string, Direction>)[key.toLowerCase()] ?? null;
}

// Follow the visible layout; use document order at an edge so every control is reachable.
export function nextControl(rects: ControlRect[], index: number, direction: Direction): number {
  if (!rects.length) return -1;
  if (index < 0 || index >= rects.length) return 0;
  const current = rects[index];
  const horizontal = direction === "left" || direction === "right";
  const sign = direction === "left" || direction === "up" ? -1 : 1;
  const center = (rect: ControlRect) => [rect.x + rect.width / 2, rect.y + rect.height / 2];
  const origin = center(current);
  let best = -1, bestScore = Infinity;
  rects.forEach((rect, candidate) => {
    if (candidate === index) return;
    const point = center(rect);
    const along = (point[horizontal ? 0 : 1] - origin[horizontal ? 0 : 1]) * sign;
    const across = Math.abs(point[horizontal ? 1 : 0] - origin[horizontal ? 1 : 0]);
    if (along <= 2) return;
    const score = along + across * 3;
    if (score < bestScore) { best = candidate; bestScore = score; }
  });
  return best >= 0 ? best : (index + sign + rects.length) % rects.length;
}
