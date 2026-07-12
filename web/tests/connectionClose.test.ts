import assert from "node:assert/strict";
import test from "node:test";

import {
  PLAYER_CONTROL_REPLACED_CLOSE_CODE,
  playerControlReplacementReason,
} from "../src/connectionClose.ts";

test("player takeover close codes produce a visible reason", () => {
  assert.equal(
    playerControlReplacementReason(
      PLAYER_CONTROL_REPLACED_CLOSE_CODE,
      "Player 0 was opened in another browser tab.",
    ),
    "Player 0 was opened in another browser tab.",
  );
  assert.equal(
    playerControlReplacementReason(PLAYER_CONTROL_REPLACED_CLOSE_CODE, ""),
    "This game was opened in another browser tab.",
  );
});

test("ordinary disconnects do not masquerade as player replacement", () => {
  assert.equal(playerControlReplacementReason(1000, "normal close"), null);
});
