import assert from "node:assert/strict";
import test from "node:test";

import {
  buyShopChoices,
  negotiationOfferFacts,
  normalizePositiveOfferPrice,
} from "../src/shopNegotiation.ts";
import { type GameState, type PlayerState, type SquareInfo } from "../src/protocol.ts";

function square(id: number, owner: number | null, value: number): SquareInfo {
  return {
    id,
    position: [id, 0],
    type: "SHOP",
    waypoints: [],
    statuses: [],
    property_owner: owner,
    property_district: 2,
    shop_base_value: value,
    shop_base_rent: 10,
    shop_current_value: value,
    suit: null,
    checkpoint_toll: 0,
    vacant_plot_options: [],
    backstreet_destination: null,
    doorway_destination: null,
    switch_next_state: null,
    custom_vars: {},
  };
}

function player(playerId: number, properties: number[], bankrupt = false): PlayerState {
  return {
    player_id: playerId,
    position: 0,
    from_square: null,
    ready_cash: 1_000,
    level: 1,
    suits: {},
    owned_properties: properties,
    owned_stock: {},
    statuses: [],
    bankrupt,
  };
}

function state(): GameState {
  return {
    current_player_index: 0,
    board: {
      max_dice_roll: 6,
      target_networth: 10_000,
      max_bankruptcies: 1,
      num_districts: 3,
      starting_cash: 1_000,
      promotion_info: {
        base_salary: 100,
        salary_increment: 50,
        shop_value_multiplier: 1,
        comeback_multiplier: 1,
      },
      squares: [square(0, 0, 100), square(1, 1, 240), square(2, 2, 300), square(3, 2, 400)],
    },
    stock: { stocks: [] },
    players: [player(0, [0]), player(1, [1]), player(2, [2, 3], true)],
  };
}

test("buy shop choices expose only live opponent-owned properties", () => {
  const gameState = state();
  gameState.players[1].owned_properties.push(3); // stale ownership row

  assert.deepEqual(buyShopChoices(gameState, 0), [
    {
      squareId: 1,
      ownerId: 1,
      currentValue: 240,
      districtId: 2,
      squareType: "SHOP",
    },
  ]);
});

test("offer prices must be positive whole numbers", () => {
  assert.equal(normalizePositiveOfferPrice(Number.NaN), 0);
  assert.equal(normalizePositiveOfferPrice(0), 0);
  assert.equal(normalizePositiveOfferPrice(74.9), 74);
});

test("buy offer context is parsed for response screens", () => {
  assert.deepEqual(
    negotiationOfferFacts({
      type: "buy",
      buyer_id: 0,
      seller_id: 1,
      square_id: 7,
      price: 350,
    }),
    {
      type: "buy",
      buyerId: 0,
      sellerId: 1,
      squareId: 7,
      price: 350,
      proposerId: null,
      targetId: null,
      offerShopIds: [],
      requestShopIds: [],
      goldOffer: null,
    },
  );
});
