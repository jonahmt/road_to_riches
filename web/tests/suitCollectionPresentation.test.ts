import assert from "node:assert/strict";
import test from "node:test";

import {
  suitCollectionFacts,
  suitCollectionTargetSelector,
} from "../src/suitCollectionPresentation.ts";

test("suit collection facts retain authoritative player, suit, and source square", () => {
  assert.deepEqual(
    suitCollectionFacts({ player_id: 2, suit: "heart", square_id: 7 }, 0),
    { playerId: 2, suit: "HEART", squareId: 7 },
  );
});

test("malformed collection facts use safe wild and location fallbacks", () => {
  assert.deepEqual(suitCollectionFacts({ suit: "unknown" }, 3), {
    playerId: 3,
    suit: "WILD",
    squareId: -1,
  });
});

test("standard suits target their slot while wild targets the complete suit bank", () => {
  assert.equal(
    suitCollectionTargetSelector({ playerId: 1, suit: "SPADE", squareId: 6 }),
    '[data-hud-player-id="1"][data-hud-suit="SPADE"]',
  );
  assert.equal(
    suitCollectionTargetSelector({ playerId: 1, suit: "WILD", squareId: 8 }),
    '[data-hud-player-id="1"][data-hud-suits]',
  );
});
