import assert from "node:assert/strict";
import test from "node:test";

import { getPromptHelp, getPromptTitle } from "../src/promptMetadata.ts";
import { type InputRequest } from "../src/protocol.ts";

function request(type: InputRequest["type"], data: Record<string, unknown> = {}): InputRequest {
  return { type, player_id: 2, data };
}

test("prompt titles use dedicated copy and readable fallbacks", () => {
  assert.equal(getPromptTitle(request("PRE_ROLL")), "Choose Your Move");
  assert.equal(getPromptTitle(request("CHOOSE_ANY_SQUARE")), "Choose Any Square");
});

test("stop prompt help explains whether undo is available", () => {
  assert.equal(
    getPromptHelp(request("CONFIRM_STOP", { can_undo: true })),
    "Choose Stop Here to end your move, or undo the last step.",
  );
  assert.equal(
    getPromptHelp(request("CONFIRM_STOP", { can_undo: false })),
    "Choose Stop Here to end your move on this square.",
  );
});

test("script decisions expose their server-authored prompt", () => {
  assert.equal(
    getPromptHelp(request("SCRIPT_DECISION", { prompt: "Choose a district" })),
    "Choose a district",
  );
});

test("generic prompt help identifies the acting player", () => {
  assert.equal(getPromptHelp(request("CANNON_TARGET")), "Decision for Player 2.");
});
