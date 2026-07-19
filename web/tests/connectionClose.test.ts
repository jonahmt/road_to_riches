import assert from "node:assert/strict";
import test from "node:test";

import {
  PLAYER_CONTROL_REPLACED_CLOSE_CODE,
  SLOW_CLIENT_CLOSE_CODE,
  SLOW_CLIENT_CLOSE_REASON,
  playerControlReplacementReason,
  slowClientCloseReason,
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

test("slow-client close codes tell the player to reconnect", () => {
  assert.equal(
    slowClientCloseReason(SLOW_CLIENT_CLOSE_CODE, "Connection lagged behind."),
    "Connection lagged behind.",
  );
  assert.equal(
    slowClientCloseReason(SLOW_CLIENT_CLOSE_CODE, ""),
    SLOW_CLIENT_CLOSE_REASON,
  );
  assert.equal(slowClientCloseReason(1000, "normal close"), null);
});
