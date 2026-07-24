import assert from "node:assert/strict";
import test from "node:test";

import { getWasdResponseMap } from "../src/controls.ts";
import { type InputRequest } from "../src/protocol.ts";

function request(type: InputRequest["type"], data: Record<string, unknown> = {}): InputRequest {
  return { type, player_id: 0, data };
}

test("WASD selects paths and undo destinations during path choice", () => {
  assert.deepEqual(
    getWasdResponseMap(
      request("CHOOSE_PATH", {
        current_position: [0, 0],
        choices: [
          { square_id: 4, position: [4, 0] },
          { square_id: 7, position: [0, -4] },
        ],
        can_undo: true,
        undo_position: [-4, 0],
      }),
    ),
    { d: 4, w: 7, a: "undo" },
  );
});

test("WASD cannot submit stop or undo at final stop confirmation", () => {
  assert.deepEqual(
    getWasdResponseMap(
      request("CONFIRM_STOP", {
        square_id: 9,
        can_undo: true,
        current_position: [4, 0],
        undo_position: [0, 0],
      }),
    ),
    {},
  );
  assert.deepEqual(
    getWasdResponseMap(request("CONFIRM_STOP", { square_id: 9, can_undo: false })),
    {},
  );
});
