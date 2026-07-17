interface BuyShopState {
  board: {
    squares: Array<{
      id: number;
      type: string;
      property_owner: number | null;
      property_district: number | null;
      shop_base_value: number | null;
      shop_current_value: number | null;
    }>;
  };
  players: Array<{
    player_id: number;
    ready_cash: number;
    owned_properties: number[];
    bankrupt: boolean;
  }>;
}

export interface BuyShopChoice {
  squareId: number;
  ownerId: number;
  currentValue: number;
  districtId: number | null;
  squareType: string;
}

export interface TradePlayerChoice {
  playerId: number;
  readyCash: number;
  properties: BuyShopChoice[];
}

export interface NegotiationOfferFacts {
  type: "buy" | "sell" | "trade";
  buyerId: number | null;
  sellerId: number | null;
  squareId: number | null;
  price: number | null;
  proposerId: number | null;
  targetId: number | null;
  offerShopIds: number[];
  requestShopIds: number[];
  goldOffer: number | null;
}

export function buyShopChoices(state: BuyShopState | null, buyerId: number): BuyShopChoice[] {
  if (!state) {
    return [];
  }

  const squaresById = new Map(state.board.squares.map((square) => [square.id, square]));
  return state.players
    .filter((player) => player.player_id !== buyerId && !player.bankrupt)
    .flatMap((player) =>
      player.owned_properties.flatMap((squareId) => {
        const square = squaresById.get(squareId);
        if (!square || square.property_owner !== player.player_id) {
          return [];
        }
        return [propertyChoice(square, player.player_id)];
      }),
    )
    .sort((left, right) => left.squareId - right.squareId);
}

export function tradePlayerChoices(
  state: BuyShopState | null,
  proposerId: number,
): TradePlayerChoice[] {
  if (!state) {
    return [];
  }
  return state.players
    .filter((player) => player.player_id !== proposerId && !player.bankrupt)
    .map((player) => ({
      playerId: player.player_id,
      readyCash: finiteInteger(player.ready_cash),
      properties: propertyChoicesForPlayer(state, player.player_id),
    }))
    .filter((player) => player.properties.length > 0)
    .sort((left, right) => left.playerId - right.playerId);
}

export function propertyChoicesForPlayer(
  state: BuyShopState | null,
  playerId: number,
): BuyShopChoice[] {
  if (!state) {
    return [];
  }
  const player = state.players.find((candidate) => candidate.player_id === playerId);
  if (!player || player.bankrupt) {
    return [];
  }
  const squaresById = new Map(state.board.squares.map((square) => [square.id, square]));
  return player.owned_properties
    .flatMap((squareId) => {
      const square = squaresById.get(squareId);
      if (!square || square.property_owner !== playerId) {
        return [];
      }
      return [propertyChoice(square, playerId)];
    })
    .sort((left, right) => left.squareId - right.squareId);
}

export function toggleTradeSquare(
  selectedSquareIds: readonly number[],
  squareId: number,
  maximum = 2,
): number[] {
  if (selectedSquareIds.includes(squareId)) {
    return selectedSquareIds.filter((selectedSquareId) => selectedSquareId !== squareId);
  }
  if (selectedSquareIds.length >= maximum) {
    return [...selectedSquareIds];
  }
  return [...selectedSquareIds, squareId].sort((left, right) => left - right);
}

export function isCompleteShopExchange(
  offeredSquareIds: readonly number[],
  requestedSquareIds: readonly number[],
): boolean {
  return (
    offeredSquareIds.length >= 1 &&
    offeredSquareIds.length <= 2 &&
    requestedSquareIds.length >= 1 &&
    requestedSquareIds.length <= 2
  );
}

export function normalizePositiveOfferPrice(value: number): number {
  if (!Number.isFinite(value) || value <= 0) {
    return 0;
  }
  return Math.max(1, Math.floor(value));
}

export function negotiationOfferFacts(value: unknown): NegotiationOfferFacts | null {
  if (!isRecord(value)) {
    return null;
  }
  const type = value.type;
  if (type !== "buy" && type !== "sell" && type !== "trade") {
    return null;
  }

  return {
    type,
    buyerId: optionalInteger(value.buyer_id),
    sellerId: optionalInteger(value.seller_id),
    squareId: optionalInteger(value.square_id),
    price: optionalInteger(value.price),
    proposerId: optionalInteger(value.proposer_id),
    targetId: optionalInteger(value.target_id),
    offerShopIds: integerArray(value.offer_shops),
    requestShopIds: integerArray(value.request_shops),
    goldOffer: optionalInteger(value.gold_offer),
  };
}

function integerArray(value: unknown): number[] {
  return Array.isArray(value)
    ? value.flatMap((entry) => {
        const integer = optionalInteger(entry);
        return integer === null ? [] : [integer];
      })
    : [];
}

function optionalInteger(value: unknown): number | null {
  const number = typeof value === "number" ? value : Number(value);
  return Number.isFinite(number) ? Math.floor(number) : null;
}

function finiteInteger(value: unknown, fallback = 0): number {
  return optionalInteger(value) ?? fallback;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function propertyChoice(
  square: BuyShopState["board"]["squares"][number],
  ownerId: number,
): BuyShopChoice {
  return {
    squareId: square.id,
    ownerId,
    currentValue: Math.max(
      0,
      finiteInteger(square.shop_current_value, finiteInteger(square.shop_base_value)),
    ),
    districtId: square.property_district,
    squareType: square.type,
  };
}
