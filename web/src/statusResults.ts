import type { GameState, SquareStatus } from "./protocol";
import { readableType } from "./format.ts";

function describe(status: SquareStatus) {
  switch (status.type) {
    case "commission": return `${status.modifier}% commission on rent payments`;
    case "closed": return "Closed · no rent charged";
    case "price_hike": return `Rent increased ${status.modifier}%`;
    case "discount": return `Rent reduced ${status.modifier}%`;
    case "fixed_price": return `Rent fixed at ${status.modifier}`;
    case "poison": return `Lose ${status.modifier} per step`;
    default: return `${readableType(status.type)}${status.modifier ? ` ${status.modifier}` : ""}`;
  }
}
function changes(old: SquareStatus[], next: SquareStatus[]) {
  const used = new Set<number>();
  const lines: string[] = [];
  for (const status of next) {
    const i = old.findIndex((s, i) => !used.has(i) && s.type === status.type && s.modifier === status.modifier);
    if (i >= 0) used.add(i);
    if (i < 0 || old[i].remaining_turns !== status.remaining_turns)
      lines.push(`${describe(status)} · ${status.remaining_turns} turn${status.remaining_turns === 1 ? "" : "s"} remaining`);
  }
  old.forEach((s, i) => { if (!used.has(i)) lines.push(s.type === "closed" && !next.some(s => s.type === "closed") ? "Shops reopen · rent resumes" : `${describe(s)} ended`); });
  return lines;
}
export function statusResult(before: GameState, after: GameState): { title: string; lines: string[] } | null {
  const lines: string[] = [];
  const titles: string[] = [];
  for (const p of after.players) {
    const old = before.players.find(o => o.player_id === p.player_id);
    if (!old) continue;
    const updates = changes(old.statuses, p.statuses);
    if (updates.length) {
      lines.push(...updates.map(t => `Player ${p.player_id} · ${t}`));
      const gained = p.statuses.find(s => s.type === "commission" && p.statuses.filter(n => n.type === s.type && n.modifier === s.modifier).length > old.statuses.filter(n => n.type === s.type && n.modifier === s.modifier).length);
      titles.push(gained ? (gained.modifier === 50 ? "Boom!" : gained.modifier === 20 ? "Boon!" : "Commission earned") : "Status update");
    }
    if (p.bankrupt && !old.bankrupt) { titles.push("Bankruptcy"); lines.push(`Player ${p.player_id} is out of the match.`); }
  }
  const shopGroups = new Map<string, number[]>();
  for (const square of after.board.squares) {
    const old = before.board.squares.find(s => s.id === square.id);
    for (const line of changes(old?.statuses ?? [], square.statuses)) {
      const label = `${square.property_owner === null ? "Unowned shops" : `Player ${square.property_owner}'s shops`} · ${line}`;
      shopGroups.set(label, [...(shopGroups.get(label) ?? []), square.id]);
    }
  }
  for (const [label, ids] of shopGroups) lines.push(`${label} (${ids.length} shop${ids.length === 1 ? "" : "s"})`);
  if (shopGroups.size) titles.push([...shopGroups.keys()].some(s => s.includes("Shops reopen")) ? "Shops reopen!" : [...shopGroups.keys()].some(s => s.includes("Closed")) ? "Take a break" : "Shop status update");
  return lines.length ? { title: titles.find(t => t !== "Status update") ?? "Status update", lines } : null;
}
