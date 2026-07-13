import assert from "node:assert/strict";
import test from "node:test";

import {
  DISTRICT_BORDER_COLORS,
  getMinimapShopColor,
  PLAYER_COLORS,
  UNOWNED_MINIMAP_SHOP_COLOR,
} from "../src/boardColors.ts";

test("district border colors never duplicate a player color", () => {
  const playerColors = new Set(PLAYER_COLORS.map((color) => color.toLowerCase()));
  for (const borderColor of DISTRICT_BORDER_COLORS) {
    assert.equal(playerColors.has(borderColor.toLowerCase()), false, borderColor);
  }
});

test("unowned minimap shops use neutral grey while owned shops use player colors", () => {
  assert.equal(getMinimapShopColor(null), UNOWNED_MINIMAP_SHOP_COLOR);
  assert.equal(getMinimapShopColor(0), PLAYER_COLORS[0]);
  assert.equal(getMinimapShopColor(3), PLAYER_COLORS[3]);
});
