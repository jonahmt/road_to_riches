export type InputRequestType =
  | "PRE_ROLL"
  | "CHOOSE_PATH"
  | "BUY_SHOP"
  | "INVEST"
  | "BUY_STOCK"
  | "SELL_STOCK"
  | "CANNON_TARGET"
  | "VACANT_PLOT_TYPE"
  | "FORCED_BUYOUT"
  | "AUCTION_BID"
  | "CHOOSE_SHOP_AUCTION"
  | "CHOOSE_SHOP_BUY"
  | "CHOOSE_SHOP_SELL"
  | "ACCEPT_OFFER"
  | "COUNTER_PRICE"
  | "RENOVATE"
  | "TRADE"
  | "CONFIRM_STOP"
  | "LIQUIDATION"
  | "SCRIPT_DECISION"
  | "CHOOSE_ANY_SQUARE"
  | "CHOOSE_VENTURE_CELL";

export interface InputRequest {
  type: InputRequestType;
  player_id: number;
  data: Record<string, unknown>;
}

export interface PresentationRequest {
  request_id: string;
  type: string;
  player_id: number;
  data: Record<string, unknown>;
}

export interface PromotionInfo {
  base_salary: number;
  salary_increment: number;
  shop_value_multiplier: number;
  comeback_multiplier: number;
}

export interface Waypoint {
  from_id: number | null;
  to_ids: number[];
}

export interface SquareStatus {
  type: string;
  modifier: number;
  remaining_turns: number;
}

export interface SquareInfo {
  id: number;
  position: [number, number];
  type: string;
  waypoints: Waypoint[];
  statuses: SquareStatus[];
  property_owner: number | null;
  property_district: number | null;
  shop_base_value: number | null;
  shop_base_rent: number | null;
  shop_current_value: number | null;
  suit: string | null;
  checkpoint_toll: number;
  vacant_plot_options: string[];
  backstreet_destination: number | null;
  doorway_destination: number | null;
  switch_next_state: number | null;
  custom_vars: Record<string, unknown>;
}

export interface BoardState {
  max_dice_roll: number;
  target_networth: number;
  max_bankruptcies: number;
  num_districts: number;
  starting_cash: number;
  promotion_info: PromotionInfo;
  squares: SquareInfo[];
}

export interface StockPrice {
  district_id: number;
  value_component: number;
  fluctuation_component: number;
  pending_fluctuation?: number;
}

export interface StockState {
  stocks: StockPrice[];
}

export interface PlayerStatus {
  type: string;
  modifier: number;
  remaining_turns: number;
}

export interface PlayerState {
  player_id: number;
  position: number;
  from_square: number | null;
  ready_cash: number;
  level: number;
  suits: Record<string, number>;
  owned_properties: number[];
  owned_stock: Record<string, number>;
  statuses: PlayerStatus[];
  bankrupt: boolean;
}

export interface GameState {
  current_player_index: number;
  board: BoardState;
  stock: StockState;
  players: PlayerState[];
  venture_deck?: unknown;
  venture_grid?: unknown;
}

export type ServerMessage =
  | { msg: "assign_player"; player_id: number; game_id?: string }
  | { msg: "state_sync"; state: GameState; game_id?: string }
  | { msg: "input_request"; type: InputRequestType; player_id: number; data?: Record<string, unknown>; game_id?: string }
  | { msg: "log"; text: string; game_id?: string }
  | { msg: "log_retract"; count: number; game_id?: string }
  | { msg: "ui_notification"; type: string; data?: Record<string, unknown>; game_id?: string }
  | { msg: "presentation_request"; request_id: string; type: string; player_id: number; data?: Record<string, unknown>; game_id?: string }
  | { msg: "presentation_resolved"; request_id: string; game_id?: string }
  | { msg: "dice"; value: number; remaining: number; game_id?: string }
  | { msg: "game_over"; winner: number | null; game_id?: string }
  | { msg: "save_result"; success: boolean; path?: string; error?: string; game_id?: string }
  | { msg: "input_rejected"; error: string; ownership_lost: boolean; game_id?: string }
  | { msg: "error"; error: string; game_id?: string }
  | { msg: "game_created"; game_id: string; config: Record<string, unknown> }
  | { msg: "joined_game"; game_id: string; player_id: number }
  | { msg: "games_list"; games: Record<string, unknown>[] }
  | { msg: "game_starting"; game_id: string; summary: Record<string, unknown> };

export type ClientMessage =
  | { msg: "input_response"; value: unknown; player_id?: number; game_id?: string }
  | { msg: "presentation_ack"; request_id: string; player_id?: number; game_id?: string }
  | { msg: "save_game"; player_id?: number; save_name?: string; game_id?: string }
  | { msg: "sync_request"; game_id?: string }
  | { msg: "start_game"; config: Record<string, unknown>; game_id?: string }
  | { msg: "list_games" }
  | { msg: "join_game"; game_id: string }
  | { msg: "claim_player"; player_id: number; game_id?: string; force?: boolean }
  | { msg: "create_game"; config: Record<string, unknown> };

export function stockPrice(stock: StockPrice): number {
  return stock.value_component + stock.fluctuation_component;
}

export function encode(message: ClientMessage): string {
  return JSON.stringify(message);
}

export function decode(raw: string): ServerMessage {
  return JSON.parse(raw) as ServerMessage;
}
