import assert from "node:assert/strict";
import test from "node:test";

import { getRollPhaseVisibility } from "../src/rollPhaseVisibility.ts";

test("movement die exclusively owns the header corner throughout a roll", () => {
  for (const rollPhase of [
    {
      diceRemaining: 0,
      pendingRequestType: "PRE_ROLL",
      responsePending: true,
    },
    {
      diceRemaining: 4,
      pendingRequestType: null,
      responsePending: false,
    },
    {
      diceRemaining: 2,
      pendingRequestType: "CHOOSE_PATH",
      responsePending: false,
    },
    {
      diceRemaining: 0,
      pendingRequestType: "CONFIRM_STOP",
      responsePending: false,
    },
  ]) {
    assert.deepEqual(getRollPhaseVisibility({ ...rollPhase, toolsOpen: true }), {
      movementDie: true,
      gameHeader: false,
      tools: false,
    });
  }
});

test("header and requested tools return after roll resolution", () => {
  assert.deepEqual(
    getRollPhaseVisibility({
      diceRemaining: 0,
      pendingRequestType: "BUY_SHOP",
      responsePending: false,
      toolsOpen: true,
    }),
    {
      movementDie: false,
      gameHeader: true,
      tools: true,
    },
  );

  assert.equal(
    getRollPhaseVisibility({
      diceRemaining: 0,
      pendingRequestType: "PRE_ROLL",
      responsePending: false,
      toolsOpen: false,
    }).tools,
    false,
  );
});
