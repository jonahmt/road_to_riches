export interface StockHoldingImpact {
  playerId: number;
  quantity: number;
  valueChange: number;
}

export interface StockPriceChangeFacts {
  playerId: number;
  districtId: number;
  oldPrice: number;
  newPrice: number;
  delta: number;
  holdings: StockHoldingImpact[];
}

function finiteInteger(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? Math.trunc(value) : fallback;
}

function parseHoldings(value: unknown): StockHoldingImpact[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((entry) => {
    if (typeof entry !== "object" || entry === null) {
      return [];
    }
    const record = entry as Record<string, unknown>;
    const playerId = finiteInteger(record.player_id, -1);
    if (playerId < 0) {
      return [];
    }
    return [
      {
        playerId,
        quantity: Math.max(0, finiteInteger(record.quantity, 0)),
        valueChange: finiteInteger(record.value_change, 0),
      },
    ];
  });
}

export function stockPriceChangeFacts(
  data: Record<string, unknown>,
  fallbackPlayerId: number,
): StockPriceChangeFacts {
  const oldPrice = Math.max(0, finiteInteger(data.old_price, 0));
  const newPrice = Math.max(0, finiteInteger(data.new_price, oldPrice));
  return {
    playerId: finiteInteger(data.player_id, fallbackPlayerId),
    districtId: finiteInteger(data.district_id, -1),
    oldPrice,
    newPrice,
    delta: newPrice - oldPrice,
    holdings: parseHoldings(data.holdings),
  };
}
