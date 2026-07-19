import { type InputRequest, type InputRequestType } from "./protocol.ts";

const PROMPT_TITLES: Partial<Record<InputRequestType, string>> = {
  PRE_ROLL: "Choose Your Move",
  CHOOSE_PATH: "Choose a Path",
  CONFIRM_STOP: "Stop on This Square?",
  BUY_SHOP: "Buy This Shop?",
  BUY_STOCK: "Buy Stock",
  SELL_STOCK: "Sell Stock",
  INVEST: "Invest in a Shop",
  CHOOSE_VENTURE_CELL: "Choosing Venture Cell",
  ACCEPT_OFFER: "Review Offer",
  COUNTER_PRICE: "Make a Counteroffer",
  SCRIPT_DECISION: "Make a Choice",
};

export function getPromptTitle(request: InputRequest): string {
  return PROMPT_TITLES[request.type] ?? readablePromptType(request.type);
}

function readablePromptType(value: string): string {
  return value
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function getPromptHelp(request: InputRequest): string {
  switch (request.type) {
    case "PRE_ROLL":
      return "Take any pre-roll actions, or roll the die to start moving.";
    case "CHOOSE_PATH":
      return "Pick where your piece should move next.";
    case "CONFIRM_STOP":
      return request.data.can_undo === true
        ? "Choose Stop Here to end your move, or undo the last step."
        : "Choose Stop Here to end your move on this square.";
    case "BUY_STOCK":
    case "SELL_STOCK":
      return "Set a quantity, then choose a district.";
    case "CHOOSE_VENTURE_CELL":
      return "The web client is choosing a random unclaimed venture grid cell.";
    case "ACCEPT_OFFER":
      return "Review the complete deal, then accept, counter, or reject it.";
    case "COUNTER_PRICE":
      return "Set the terms you want to send back to the other player.";
    case "SCRIPT_DECISION":
      return String(request.data.prompt ?? "Choose how this event should resolve.");
    default:
      return `Decision for Player ${request.player_id}.`;
  }
}
