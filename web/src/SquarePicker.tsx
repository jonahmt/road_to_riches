import { lazy, Suspense, useEffect, useRef, type CSSProperties, type ReactNode } from "react";
import type { GameState, SquareInfo } from "./protocol";
import { PLAYER_COLORS, DISTRICT_BORDER_COLORS } from "./boardColors";
import { formatGold } from "./format";
import { cycleSquare, directionalSquare, initialSquare, type BoardSquareSelection, type SquareCursorControl } from "./squarePickerNavigation";
import type { BoardProjector } from "./board3d/geometry";
import { stockPrice } from "./protocol";

const ShopPreview = lazy(() => import("./board3d/ShopPreview"));

export function SquarePicker({ state, selection, title, confirmLabel, onBack, onSelect, projector, facts, extra,
  suspended, playerId, confirmDisabled, cursor, snapAll }: {
  state: GameState; selection: BoardSquareSelection; title: string; confirmLabel: string;
  onBack: (() => void) | null; onSelect: (id: number) => void; projector: { current: BoardProjector | null };
  facts: { value: number | null; rent: number | null; capital: number | null; note?: string };
  extra?: ReactNode; suspended: boolean; playerId: number | null; confirmDisabled: boolean;
  cursor: SquareCursorControl; snapAll: boolean;
}) {
  cursor.enabled = !suspended;
  cursor.snapAll = snapAll;
  const square = state.board.squares.find((item) => item.id === selection.selectedSquareId);
  const eligible = square !== undefined && selection.eligibleSquareIds.has(square.id);
  const district = square?.property_district;
  const stock = state.stock.stocks.find((item) => item.district_id === district);
  const color = PLAYER_COLORS[(playerId ?? 0) % PLAYER_COLORS.length];
  const select = (id: number) => {
    const target = state.board.squares.find((square) => square.id === id);
    if (target) { cursor.jumpTo = target.position; cursor.reframe = true; }
    onSelect(id);
  };
  const cycle = (direction: number) => {
    const id = cycleSquare(state.board.squares, selection.eligibleSquareIds, selection.selectedSquareId, direction);
    if (id !== null) select(id);
  };
  const confirm = () => { if (!suspended && !confirmDisabled && square && eligible) selection.onConfirmSquare(square.id); };
  const choicesKey = [...selection.eligibleSquareIds].join(",");
  const initialized = useRef<string | null>(null);
  useEffect(() => {
    if (initialized.current === choicesKey) return;
    initialized.current = choicesKey;
    if (square && selection.eligibleSquareIds.has(square.id)) { select(square.id); return; }
    const id = initialSquare(state.board.squares, selection.eligibleSquareIds,
      state.players.find((player) => player.player_id === playerId)?.position ?? null);
    if (id !== null) select(id);
  }, [choicesKey, selection.selectedSquareId]);

  useEffect(() => {
    if (suspended) cursor.keys.clear();
  }, [suspended]);
  useEffect(() => {
    const stop = () => cursor.keys.clear();
    const visibility = () => { if (document.hidden) stop(); };
    const up = (event: KeyboardEvent) => cursor.keys.delete(event.key.toLowerCase());
    window.addEventListener("keyup", up); window.addEventListener("blur", stop);
    document.addEventListener("visibilitychange", visibility);
    return () => {
      stop(); cursor.position = null; cursor.display = null; cursor.jumpTo = null;
      window.removeEventListener("keyup", up); window.removeEventListener("blur", stop);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, []);

  useEffect(() => {
    function keyDown(event: KeyboardEvent) {
      if (suspended || event.altKey || event.ctrlKey || event.metaKey ||
        document.body.dataset.gameplayHotkeysSuppressed === "true") return;
      const target = event.target;
      if (target instanceof HTMLElement && (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName))) return;
      const key = event.key.toLowerCase();
      const directions: Record<string, [number, number]> = {
        w: [0, -1], arrowup: [0, -1], s: [0, 1], arrowdown: [0, 1],
        a: [-1, 0], arrowleft: [-1, 0], d: [1, 0], arrowright: [1, 0],
      };
      if (![...Object.keys(directions), "q", "e", "enter", " ", "escape"].includes(key)) return;
      if (event.repeat) { event.preventDefault(); return; }
      event.preventDefault(); event.stopImmediatePropagation();
      if (target instanceof HTMLElement) target.blur();
      if (directions[key]) {
        if (cursor.attached) cursor.keys.add(key);
        else {
          const id = directionalSquare(state.board.squares, selection.selectedSquareId, directions[key], projector.current ?? undefined);
          if (id !== null) select(id);
        }
      } else if (key === "q" || key === "e") cycle(key === "q" ? -1 : 1);
      else if (key === "escape") onBack?.();
      else confirm();
    }
    window.addEventListener("keydown", keyDown, true);
    return () => window.removeEventListener("keydown", keyDown, true);
  }, [state, selection, suspended, onBack, onSelect]);

  return <div className="square-picker" style={{ "--picker-color": color } as CSSProperties}>
    <header className="square-picker-prompt"><span>Choose on the board</span><h1>{title}</h1></header>
    <section className="square-picker-card" aria-label="Selected square details" aria-live="polite">
      <div className="square-picker-stock" aria-label="District stock holdings">
        <div><small>Stock price</small><strong>{stock ? formatGold(stockPrice(stock)) : "—"}</strong></div>
        {state.players.map((player) => <div key={player.player_id} style={{ "--owner-color": PLAYER_COLORS[player.player_id % PLAYER_COLORS.length] } as CSSProperties}>
          <small>Player {player.player_id}</small><strong>{district == null ? "—" : player.owned_stock[String(district)] ?? 0}</strong>
        </div>)}
      </div>
      <div className="square-picker-district" style={{ borderColor: district == null ? color : DISTRICT_BORDER_COLORS[district % DISTRICT_BORDER_COLORS.length] }}>
        {district == null ? "Board square" : `District ${String.fromCharCode(65 + district)}`}
        <span>{square ? `#${square.id}` : "—"}</span>
      </div>
      <h2>{square ? squareName(square) : selection.eligibleSquareIds.size ? "Browse the board" : "No available squares"}</h2>
      {!square && selection.eligibleSquareIds.size > 0 && <p className="square-picker-empty">Move the cursor near a {snapAll ? "square" : "shop"} to snap into place and inspect it.</p>}
      {square && <p className="square-picker-owner">{square.property_owner == null ? (square.shop_current_value == null ? "Special square" : "Unowned") : `Owned by Player ${square.property_owner}`}</p>}
        <div className="square-picker-facts" hidden={!square}>
          <div className="square-picker-model" hidden={square?.type !== "SHOP"} aria-hidden="true">
            <Suspense fallback={null}><ShopPreview owner={square?.property_owner ?? null} closed={square?.statuses.some((status) => status.type === "closed") ?? false} /></Suspense>
          </div>
          <dl>
            <div><dt>{square?.type === "SHOP" ? "Shop value" : "Value"}</dt><dd>{formatGold(facts.value)}</dd></div>
            <div><dt>Shop price</dt><dd>{formatGold(facts.rent)}</dd></div>
            <div><dt>Max. capital</dt><dd>{formatGold(facts.capital)}</dd></div>
          </dl>
        </div>
      {square && <>
        {facts.note && <p className="square-picker-note">{facts.note}</p>}
      </>}
      <button className="square-picker-confirm" disabled={!eligible || suspended || confirmDisabled} onClick={confirm}>{square && !eligible ? "Unavailable for this action" : confirmLabel} <kbd>Enter</kbd></button>
    </section>
    <nav className="square-picker-navigation" aria-label="Square selection controls">
      {onBack && <button className="secondary" disabled={suspended} onClick={onBack}><kbd>Esc</kbd> Back</button>}
      <div className="square-picker-cycle">
        <button className="secondary" disabled={suspended || selection.eligibleSquareIds.size < 2} onClick={() => cycle(-1)}><kbd>Q</kbd> Previous</button>
        <span>{eligible ? [...selection.eligibleSquareIds].sort((a, b) => a - b).indexOf(square!.id) + 1 : "—"} / {selection.eligibleSquareIds.size}</span>
        <button className="secondary" disabled={suspended || selection.eligibleSquareIds.size < 2} onClick={() => cycle(1)}>Next <kbd>E</kbd></button>
      </div>
      {extra}
      <span className="square-picker-help"><strong>Hold WASD / arrows</strong> or move the pointer · Snap near a {snapAll ? "square" : "shop"} · Enter to choose</span>
    </nav>
  </div>;
}

function squareName(square: SquareInfo) {
  const name = square.custom_vars.name;
  return typeof name === "string" && name ? name : square.type.toLowerCase().split("_")
    .map((word) => word[0].toUpperCase() + word.slice(1)).join(" ") + ` #${square.id}`;
}
