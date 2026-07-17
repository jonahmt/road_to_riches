import assert from "node:assert/strict";
import test from "node:test";

import {
  BOON_ICON_COLOR,
  DISTRICT_BORDER_COLORS,
  getMinimapShopColor,
  PLAYER_COLORS,
  STOCKBROKER_ICON_COLOR,
  SUIT_COLORS,
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

test("boon star color remains distinct from the diamond suit", () => {
  assert.notEqual(BOON_ICON_COLOR.toLowerCase(), SUIT_COLORS.DIAMOND.toLowerCase());
});

test("stockbroker market green remains distinct from player ownership colors", () => {
  const playerColors = new Set(PLAYER_COLORS.map((color) => color.toLowerCase()));
  assert.equal(playerColors.has(STOCKBROKER_ICON_COLOR.toLowerCase()), false);
});
