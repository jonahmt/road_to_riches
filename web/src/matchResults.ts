import { netWorth } from "./format.ts";
import type { GameState } from "./protocol";

/** Winner is authoritative: arriving at the bank beats a richer opponent. */
export function matchStandings(state: GameState, winner: number | null) {
  return state.players.map(player => ({
    player, worth: netWorth(state, player),
    propertyValue: state.board.squares.filter(s => s.property_owner === player.player_id)
      .reduce((sum, s) => sum + (s.shop_current_value ?? 0), 0),
    stockValue: Object.entries(player.owned_stock).reduce((sum, [id, count]) => {
      const stock = state.stock.stocks.find(s => s.district_id === Number(id));
      return sum + count * (stock ? stock.value_component + stock.fluctuation_component : 0);
    }, 0),
  })).sort((a, b) => Number(b.player.player_id === winner) - Number(a.player.player_id === winner)
    || b.worth - a.worth || a.player.player_id - b.player.player_id);
}

export const RESULT_STORAGE_KEY = "rtr.completed-match.v1";
export interface CompletedMatch { state: GameState; winner: number | null; uri: string; playerId: number | null; }
export function readCompletedMatch(): CompletedMatch | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(RESULT_STORAGE_KEY) ?? "null");
    if (!value?.state?.players?.length || !value.state.board?.squares?.length || !value.state.stock?.stocks
      || !(value.winner === null || Number.isInteger(value.winner)) || typeof value.uri !== "string") return null;
    return value;
  } catch { return null; }
}
export function writeCompletedMatch(value: CompletedMatch | null) {
  try {
    if (value) sessionStorage.setItem(RESULT_STORAGE_KEY, JSON.stringify(value));
    else sessionStorage.removeItem(RESULT_STORAGE_KEY);
  } catch { /* In-memory results still work when browser storage is unavailable. */ }
}
