export type StockOverlayMode = "buy" | "sell" | "liquidate";

export function clampStockQuantity(quantity: number, maximum: number): number {
  if (!Number.isFinite(quantity) || maximum <= 0) {
    return 0;
  }
  return Math.min(maximum, Math.max(1, Math.floor(quantity)));
}

export function maxBuyQuantity(cash: number, price: number): number {
  if (cash <= 0 || price <= 0) {
    return 0;
  }
  return Math.min(99, Math.floor(cash / price));
}

export function defaultStockQuantity(
  mode: StockOverlayMode,
  maximum: number,
  price: number,
  cashDeficit = 0,
): number {
  if (maximum <= 0) {
    return 0;
  }
  if (mode === "liquidate" && price > 0 && cashDeficit > 0) {
    return clampStockQuantity(Math.ceil(cashDeficit / price), maximum);
  }
  return 1;
}

export function districtLabel(districtId: number): string {
  if (districtId >= 0 && districtId < 26) {
    return `District ${String.fromCharCode(65 + districtId)}`;
  }
  return `District ${districtId + 1}`;
}
