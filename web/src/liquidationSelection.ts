export interface LiquidationShopChoice {
  squareId: number;
  sellValue: number;
}

function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function integer(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? Math.trunc(value) : fallback;
}

export function liquidationShopChoices(options: unknown): LiquidationShopChoice[] {
  const shops = record(options).shops;
  if (!Array.isArray(shops)) {
    return [];
  }
  return shops.flatMap((rawShop) => {
    const shop = record(rawShop);
    const squareId = integer(shop.square_id, -1);
    return squareId >= 0
      ? [{ squareId, sellValue: Math.max(0, integer(shop.sell_value)) }]
      : [];
  });
}

export function hasLiquidatableStock(options: unknown): boolean {
  const stocks = record(record(options).stock);
  return Object.values(stocks).some((rawStock) => integer(record(rawStock).quantity) > 0);
}
