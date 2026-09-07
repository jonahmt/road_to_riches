import type { InputRequest } from "../protocol.ts";
import { TILE_TOP, type Point3 } from "./geometry.ts";

export interface MovementGuide {
  value: number | "undo";
  position: Point3;
  rotation: number;
  label: string;
}

function point(value: unknown): [number, number] | null {
  return Array.isArray(value) && value.length >= 2 &&
    typeof value[0] === "number" && Number.isFinite(value[0]) &&
    typeof value[1] === "number" && Number.isFinite(value[1]) ? [value[0], value[1]] : null;
}

/** Present only the choices already offered to this player; board geometry cannot authorize a move. */
export function movementGuides(request: InputRequest | null, assignedPlayerId: number | null): MovementGuide[] {
  if (request?.type !== "CHOOSE_PATH" || assignedPlayerId === null || request.player_id !== assignedPlayerId) return [];
  const origin = point(request.data.current_position);
  if (!origin) return [];
  const guides = new Map<MovementGuide["value"], MovementGuide>();
  const add = (value: MovementGuide["value"], target: [number, number] | null, label: string) => {
    if (!target || guides.has(value)) return;
    const dx = target[0] - origin[0];
    const dz = target[1] - origin[1];
    const distance = Math.hypot(dx, dz);
    if (distance < 0.001) return;
    const radius = Math.min(2.05, distance / 2);
    guides.set(value, { value, label, rotation: -Math.atan2(dz, dx),
      position: [origin[0] + dx / distance * radius, TILE_TOP + 2.2, origin[1] + dz / distance * radius] });
  };
  for (const choice of Array.isArray(request.data.choices) ? request.data.choices : []) {
    if (!choice || typeof choice !== "object") continue;
    const id = (choice as { square_id?: unknown }).square_id;
    if (typeof id !== "number" || !Number.isFinite(id)) continue;
    add(id, point((choice as { position?: unknown }).position), `Move to Square #${id}`);
  }
  if (request.data.can_undo === true) add("undo", point(request.data.undo_position), "Undo last step");
  return [...guides.values()];
}
