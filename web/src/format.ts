import { type GameState, type PlayerState, stockPrice } from "./protocol.ts";

export function formatGold(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return Math.round(value).toLocaleString();
}

export function stockValue(state: GameState, player: PlayerState): number {
  return Object.entries(player.owned_stock).reduce((total, [districtId, quantity]) => {
    const stock = state.stock.stocks[Number(districtId)];
    return total + (stock ? stockPrice(stock) * quantity : 0);
  }, 0);
}

export function netWorth(state: GameState, player: PlayerState): number {
  const propertyValue = player.owned_properties.reduce((total, squareId) => {
    const square = state.board.squares[squareId];
    return total + (square?.shop_current_value ?? 0);
  }, 0);
  return player.ready_cash + propertyValue + stockValue(state, player);
}

export function readableType(type: string): string {
  return type
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
