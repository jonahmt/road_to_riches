import { type InputRequest } from "./protocol";

export type WasdResponseMap = Record<string, unknown>;

export interface KeyPromptAction {
  key: string;
  value: unknown;
  squareId?: number;
  squareType?: string;
  label: string;
}

const DIRECTION_KEYS: Array<[number, string]> = [
  [0, "d"],
  [Math.PI / 4, "sd"],
  [Math.PI / 2, "s"],
  [(3 * Math.PI) / 4, "as"],
  [Math.PI, "a"],
  [(-3 * Math.PI) / 4, "wa"],
  [-Math.PI / 2, "w"],
  [-Math.PI / 4, "dw"],
];

const DIAGONAL_FALLBACKS: Record<string, [string, string]> = {
  sd: ["s", "d"],
  as: ["a", "s"],
  wa: ["w", "a"],
  dw: ["d", "w"],
};

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function asPoint(value: unknown): [number, number] | null {
  if (!Array.isArray(value) || value.length < 2) {
    return null;
  }
  const x = value[0];
  const y = value[1];
  if (typeof x !== "number" || typeof y !== "number") {
    return null;
  }
  return [x, y];
}

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function angleBetween(origin: [number, number], target: [number, number]): number {
  return Math.atan2(target[1] - origin[1], target[0] - origin[0]);
}

function closestDirection(angle: number): string {
  let bestKey = "d";
  let bestDiff = Number.POSITIVE_INFINITY;

  for (const [directionAngle, key] of DIRECTION_KEYS) {
    let diff = Math.abs(angle - directionAngle);
    if (diff > Math.PI) {
      diff = 2 * Math.PI - diff;
    }
    if (diff < bestDiff) {
      bestDiff = diff;
      bestKey = key;
    }
  }

  return bestKey;
}

function computeDirectionKeys(
  currentPosition: [number, number],
  choices: Array<[number, [number, number]]>,
  undoPosition: [number, number] | null,
): WasdResponseMap {
  if (choices.length === 0 && undoPosition === null) {
    return {};
  }

  const targets: Array<[string, number | "undo"]> = choices.map(([squareId, position]) => [
    closestDirection(angleBetween(currentPosition, position)),
    squareId,
  ]);
  if (undoPosition !== null) {
    targets.push([closestDirection(angleBetween(currentPosition, undoPosition)), "undo"]);
  }

  const usedKeys = new Set<string>();
  const mapping: WasdResponseMap = {};
  const conflicts: Array<[string, number | "undo"]> = [];

  function tryAssign(key: string, value: number | "undo"): boolean {
    if (usedKeys.has(key)) {
      return false;
    }
    mapping[key] = value;
    usedKeys.add(key);
    return true;
  }

  for (const [key, value] of targets) {
    if (!tryAssign(key, value)) {
      conflicts.push([key, value]);
    }
  }

  for (const [idealKey, value] of conflicts) {
    let assigned = false;
    const fallbacks = DIAGONAL_FALLBACKS[idealKey] ?? [];
    for (const fallback of fallbacks) {
      if (tryAssign(fallback, value)) {
        assigned = true;
        break;
      }
    }
    if (assigned) {
      continue;
    }
    for (const candidate of ["w", "a", "s", "d"]) {
      if (tryAssign(candidate, value)) {
        break;
      }
    }
  }

  return mapping;
}

export function getPathKeyActions(request: InputRequest): KeyPromptAction[] {
  if (request.type !== "CHOOSE_PATH") {
    return [];
  }

  const currentPosition = asPoint(request.data.current_position) ?? [0, 0];
  const choices = asArray(request.data.choices).map(asRecord);
  const choiceTargets: Array<[number, [number, number]]> = [];
  const choiceDetails = new Map<number, { type?: string }>();
  for (const choice of choices) {
    const squareId = asNumber(choice.square_id, Number.NaN);
    const position = asPoint(choice.position);
    if (!Number.isFinite(squareId) || position === null) {
      continue;
    }
    choiceTargets.push([squareId, position]);
    choiceDetails.set(squareId, { type: typeof choice.type === "string" ? choice.type : undefined });
  }

  const undoPosition = request.data.can_undo === true ? asPoint(request.data.undo_position) : null;
  const mapping = computeDirectionKeys(currentPosition, choiceTargets, undoPosition);
  return Object.entries(mapping)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, value]) => {
      if (value === "undo") {
        return { key, value, label: "Undo Step" };
      }
      const squareId = asNumber(value);
      return {
        key,
        value,
        squareId,
        squareType: choiceDetails.get(squareId)?.type,
        label: `Square #${squareId}`,
      };
    });
}

export function getWasdResponseMap(request: InputRequest): WasdResponseMap {
  if (request.type === "CHOOSE_PATH") {
    return Object.fromEntries(getPathKeyActions(request).map((action) => [action.key, action.value]));
  }

  if (request.type === "PRE_ROLL") {
    return { w: "roll" };
  }

  if (request.type === "BUY_SHOP" || request.type === "FORCED_BUYOUT") {
    return { d: true, a: false };
  }

  if (request.type === "ACCEPT_OFFER") {
    return { d: "accept", a: "reject", s: "counter" };
  }

  return {};
}
