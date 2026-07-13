import assert from "node:assert/strict";
import test from "node:test";

import { DISTRICT_BORDER_COLORS, PLAYER_COLORS } from "../src/boardColors.ts";

test("district border colors never duplicate a player color", () => {
  const playerColors = new Set(PLAYER_COLORS.map((color) => color.toLowerCase()));
  for (const borderColor of DISTRICT_BORDER_COLORS) {
    assert.equal(playerColors.has(borderColor.toLowerCase()), false, borderColor);
  }
});
