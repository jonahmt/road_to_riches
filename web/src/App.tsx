import {
  type CSSProperties,
  FormEvent,
  type PointerEvent as ReactPointerEvent,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  BOOM_ICON_COLOR,
  BOON_ICON_COLOR,
  DISTRICT_BORDER_COLORS,
  DISTRICT_COLORS,
  getMinimapShopColor,
  PLAYER_COLORS,
  STOCKBROKER_ICON_COLOR,
  SUIT_COLORS,
  TAKE_A_BREAK_ICON_COLOR,
} from "./boardColors";
import { getPathKeyActions, getWasdResponseMap, type WasdResponseMap } from "./controls";
import {
  DICE_ROLL_DURATION_MS,
  DICE_SETTLE_DURATION_MS,
  EVENT_DICE_FADE_DURATION_MS,
  EVENT_DICE_HOLD_DURATION_MS,
  dieFinalTransform,
  displayedDiceValue,
} from "./dicePresentation";
import { formatGold, netWorth, readableType } from "./format";
import {
  type GameState,
  type InputRequest,
  type PlayerState,
  type SquareInfo,
  stockPrice,
} from "./protocol";
import { adjacentStepAnimationDuration } from "./cameraTiming";
import {
  hasLiquidatableStock,
  liquidationShopChoices,
  type LiquidationShopChoice,
} from "./liquidationSelection";
import { rentPaymentCashDeltas, rentPaymentFacts } from "./paymentPresentation";
import {
  commissionIndicatorColor,
  commissionStatusIndicators,
} from "./playerStatusPresentation";
import { getPromptHelp, getPromptTitle } from "./promptMetadata";
import { stockPriceChangeFacts } from "./stockPricePresentation";
import {
  boardSelectionScrimPath,
  clampInvestmentAmount,
  investmentSquareChoices,
  maximumInvestment,
  squareIdsFromOptions,
  type InvestmentSquareChoice,
} from "./squareSelection";
import { scriptDecisionOptions } from "./scriptDecision";
import { closedShopTurns } from "./shopStatusPresentation";
import {
  buyShopChoices,
  isCompleteShopExchange,
  negotiationPlayerChoices,
  negotiationOfferFacts,
  normalizePositiveOfferPrice,
  propertyChoicesForPlayer,
  sellShopChoices,
  toggleTradeSquare,
  tradePlayerChoices,
  type BuyShopChoice,
  type NegotiationPlayerChoice,
  type NegotiationOfferFacts,
  type TradePlayerChoice,
} from "./shopNegotiation";
import {
  clampStockQuantity,
  defaultStockQuantity,
  districtLabel,
  maxBuyQuantity,
  projectedStockPrice,
  type StockOverlayMode,
} from "./stockOverlay";
import { type DiceState, type PresentationState, useGameClient } from "./useGameClient";

const DEFAULT_URI = "ws://localhost:8765";
const DEFAULT_BACKSTREET_COLOR = "#56cfff";

const SUIT_ORDER = ["SPADE", "HEART", "DIAMOND", "CLUB"];
const RENT_MULTIPLIERS: Record<string, number> = {
  "1:1": 1,
  "1:2": 1,
  "2:2": 2,
  "1:3": 1,
  "2:3": 1.5,
  "3:3": 3.75,
  "1:4": 1,
  "2:4": 1.25,
  "3:4": 2.5,
  "4:4": 5,
  "1:5": 1,
  "2:5": 1.25,
  "3:5": 2,
  "4:5": 3.25,
  "5:5": 6,
  "1:6": 1,
  "2:6": 1.25,
  "3:6": 2,
  "4:6": 2.75,
  "5:6": 4.25,
  "6:6": 6.75,
  "1:7": 1,
  "2:7": 1.25,
  "3:7": 1.75,
  "4:7": 2.75,
  "5:7": 3.75,
  "6:7": 5.25,
  "7:7": 7.5,
  "1:8": 1,
  "2:8": 1.25,
  "3:8": 1.75,
  "4:8": 2.5,
  "5:8": 3.5,
  "6:8": 4.5,
  "7:8": 6,
  "8:8": 8,
};
const MAX_CAP_MULTIPLIERS: Record<string, number> = {
  "1:1": 2,
  "1:2": 1.5,
  "2:2": 3,
  "1:3": 1.5,
  "2:3": 2.25,
  "3:3": 6,
  "1:4": 1.5,
  "2:4": 2,
  "3:4": 4,
  "4:4": 10,
  "1:5": 1.5,
  "2:5": 2,
  "3:5": 4,
  "4:5": 10,
  "5:5": 12,
  "1:6": 1.5,
  "2:6": 2,
  "3:6": 4,
  "4:6": 10,
  "5:6": 12,
  "6:6": 14,
  "1:7": 1.5,
  "2:7": 2,
  "3:7": 4,
  "4:7": 10,
  "5:7": 12,
  "6:7": 14,
  "7:7": 16,
  "1:8": 1.5,
  "2:8": 2,
  "3:8": 4,
  "4:8": 10,
  "5:8": 12,
  "6:8": 14,
  "7:8": 16,
  "8:8": 19,
};
const BOARD_TILE_SIZE = 4;
const BOARD_TILE_RADIUS = BOARD_TILE_SIZE / 2;
const BOARD_TILE_STROKE_WIDTH = 0.24;
const BOARD_TILE_STROKE_INSET = BOARD_TILE_STROKE_WIDTH / 2;
const BOARD_TILE_DRAW_SIZE = BOARD_TILE_SIZE - BOARD_TILE_STROKE_WIDTH;
const MINIMAP_TILE_STROKE_WIDTH = 0.22;
const MINIMAP_TILE_STROKE_INSET = MINIMAP_TILE_STROKE_WIDTH / 2;
const MINIMAP_TILE_DRAW_SIZE = BOARD_TILE_SIZE - MINIMAP_TILE_STROKE_WIDTH;
const BOARD_TILE_SELECTION_INSET = 0.34;
const BOARD_TILE_SELECTION_STROKE_WIDTH = 0.12;
const BOARD_TILE_SELECTION_SIZE = BOARD_TILE_SIZE - BOARD_TILE_SELECTION_INSET * 2;
const WASD_KEYS = new Set(["w", "a", "s", "d"]);
const CHORD_TIMEOUT_MS = 180;
const MIN_BOARD_ZOOM = 0.5;
const MAX_BOARD_ZOOM = 3;
const FOLLOW_VISIBLE_TILE_WIDTHS = 6;
const FOLLOW_CAMERA_ANIMATION_MS = 360;
const PLAYER_TOKEN_RADIUS = 0.34;
const ACTIVE_PLAYER_TOKEN_RADIUS = 0.95;
const BOARD_ZOOM_STEP = 0.25;
const BOARD_WHEEL_ZOOM_SPEED = 0.0015;
const BOARD_DRAG_THRESHOLD = 4;
const VENTURE_LINE_BONUSES: Record<number, number> = { 4: 40, 5: 50, 6: 60, 7: 70, 8: 200 };
const VENTURE_AXES: ReadonlyArray<readonly [number, number]> = [
  [0, 1],
  [1, 0],
  [1, 1],
  [1, -1],
];
const DIE_PIPS: Record<number, readonly number[]> = {
  0: [],
  1: [5],
  2: [3, 7],
  3: [3, 5, 7],
  4: [1, 3, 7, 9],
  5: [1, 3, 5, 7, 9],
  6: [1, 3, 4, 6, 7, 9],
  7: [1, 3, 4, 5, 6, 7, 9],
  8: [1, 2, 3, 4, 6, 7, 8, 9],
  9: [1, 2, 3, 4, 5, 6, 7, 8, 9],
};

interface BoardCamera {
  zoom: number;
  minX: number;
  minY: number;
}

type BoardCameraMode = "follow" | "free";
type BoardAnimationCurve = "cubic" | "linear";
type LiquidationAssetMode = "choose" | "stock" | "shop";
type TradePhase = "target" | "offer" | "request" | "terms";
type VentureCellOwner = number | null;
type VentureCursor = readonly [number, number];

interface BoardSquareSelection {
  eligibleSquareIds: ReadonlySet<number>;
  selectedSquareId: number | null;
  chosenSquareIds?: ReadonlySet<number>;
  onConfirmSquare: (squareId: number) => void;
}

type ActivePlayerFrame = {
  playerId: number;
  squareId: number;
};

type BoardTokenVisual = {
  x: number;
  y: number;
  radius: number;
};

type BoardPlayerToken = BoardTokenVisual & {
  player: PlayerState;
  isActive: boolean;
};

interface BoardBounds {
  minX: number;
  minY: number;
  width: number;
  height: number;
}

interface BoardDrag {
  pointerId: number;
  startX: number;
  startY: number;
  lastX: number;
  lastY: number;
}

function clampBoardZoom(zoom: number): number {
  return Math.min(MAX_BOARD_ZOOM, Math.max(MIN_BOARD_ZOOM, zoom));
}

function zoomBoardCameraAt(
  camera: BoardCamera,
  requestedZoom: number,
  point: { x: number; y: number },
  bounds: BoardBounds,
): BoardCamera {
  const zoom = clampBoardZoom(requestedZoom);
  if (zoom === camera.zoom) {
    return camera;
  }
  const currentWidth = bounds.width / camera.zoom;
  const nextWidth = bounds.width / zoom;
  const ratio = nextWidth / currentWidth;
  return {
    zoom,
    minX: point.x - (point.x - camera.minX) * ratio,
    minY: point.y - (point.y - camera.minY) * ratio,
  };
}

function resetBoardCamera(bounds: BoardBounds): BoardCamera {
  return { zoom: 1, minX: bounds.minX, minY: bounds.minY };
}

function centeredBoardCamera(
  bounds: BoardBounds,
  zoom: number,
  center: { x: number; y: number },
): BoardCamera {
  return {
    zoom,
    minX: center.x - bounds.width / zoom / 2,
    minY: center.y - bounds.height / zoom / 2,
  };
}

function getFollowBoardZoom(bounds: BoardBounds): number {
  return bounds.width / (BOARD_TILE_SIZE * FOLLOW_VISIBLE_TILE_WIDTHS);
}

function easeInOutCubic(progress: number): number {
  return progress < 0.5
    ? 4 * progress * progress * progress
    : 1 - Math.pow(-2 * progress + 2, 3) / 2;
}

function animationProgress(progress: number, curve: BoardAnimationCurve): number {
  return curve === "linear" ? progress : easeInOutCubic(progress);
}

function areBoardSquaresAdjacent(state: GameState, fromId: number, toId: number): boolean {
  const from = state.board.squares.find((square) => square.id === fromId);
  const to = state.board.squares.find((square) => square.id === toId);
  return Boolean(
    from?.waypoints.some((waypoint) => waypoint.to_ids.includes(toId)) ||
      to?.waypoints.some((waypoint) => waypoint.to_ids.includes(fromId)),
  );
}

function interpolateBoardCamera(from: BoardCamera, to: BoardCamera, progress: number): BoardCamera {
  return {
    zoom: from.zoom + (to.zoom - from.zoom) * progress,
    minX: from.minX + (to.minX - from.minX) * progress,
    minY: from.minY + (to.minY - from.minY) * progress,
  };
}

function interpolateBoardToken(
  from: BoardTokenVisual,
  to: BoardTokenVisual,
  progress: number,
): BoardTokenVisual {
  return {
    x: from.x + (to.x - from.x) * progress,
    y: from.y + (to.y - from.y) * progress,
    radius: from.radius + (to.radius - from.radius) * progress,
  };
}

function applyBoardTokenVisual(element: SVGGElement, visual: BoardTokenVisual) {
  element.setAttribute("transform", `translate(${visual.x} ${visual.y})`);
  element.querySelector("circle")?.setAttribute("r", String(visual.radius));
}

function getBoardPlayerTokens(state: GameState | null): BoardPlayerToken[] {
  if (!state) {
    return [];
  }
  const squares = new Map(state.board.squares.map((square) => [square.id, square]));
  const groups = groupPlayersBySquare(state.players);
  const activePlayer = state.players[state.current_player_index] ?? null;

  return state.players.flatMap((player) => {
    const square = squares.get(player.position);
    if (!square) {
      return [];
    }
    const isActive = player.player_id === activePlayer?.player_id;
    const index = (groups.get(square.id) ?? []).findIndex(
      (groupedPlayer) => groupedPlayer.player_id === player.player_id,
    );
    return [
      {
        player,
        isActive,
        x: isActive ? square.position[0] : square.position[0] - 1.45 + index * 0.58,
        y: isActive ? square.position[1] : square.position[1] + 1.35,
        radius: isActive ? ACTIVE_PLAYER_TOKEN_RADIUS : PLAYER_TOKEN_RADIUS,
      },
    ];
  });
}

function applyBoardCamera(svg: SVGSVGElement, camera: BoardCamera, bounds: BoardBounds) {
  const width = bounds.width / camera.zoom;
  const height = bounds.height / camera.zoom;
  svg.setAttribute("viewBox", `${camera.minX} ${camera.minY} ${width} ${height}`);
  svg.dataset.zoom = camera.zoom.toFixed(2);
}

function svgPointAt(svg: SVGSVGElement, clientX: number, clientY: number): { x: number; y: number } | null {
  const matrix = svg.getScreenCTM();
  if (!matrix) {
    return null;
  }
  const point = svg.createSVGPoint();
  point.x = clientX;
  point.y = clientY;
  const transformed = point.matrixTransform(matrix.inverse());
  return { x: transformed.x, y: transformed.y };
}

function getPlayerColor(playerId: number): string {
  return PLAYER_COLORS[playerId % PLAYER_COLORS.length];
}

function getDistrictColor(districtId: number | null): string {
  if (districtId === null) {
    return "#ffffff";
  }
  return DISTRICT_COLORS[districtId % DISTRICT_COLORS.length];
}

function getDistrictBorderColor(districtId: number | null): string {
  if (districtId === null) {
    return "#f7f7f2";
  }
  return DISTRICT_BORDER_COLORS[districtId % DISTRICT_BORDER_COLORS.length];
}

function hexToRgba(hex: string, alpha: number): string {
  const value = hex.replace("#", "");
  const red = parseInt(value.slice(0, 2), 16);
  const green = parseInt(value.slice(2, 4), 16);
  const blue = parseInt(value.slice(4, 6), 16);
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

function isTintablePropertyTile(square: SquareInfo): boolean {
  return ["SHOP", "VP_CHECKPOINT", "VP_TAX_OFFICE"].includes(square.type);
}

function getSquareFill(square: SquareInfo): string {
  const ownerId = square.property_owner;
  if (ownerId !== null && isTintablePropertyTile(square)) {
    if (square.type === "SHOP") {
      return getPlayerColor(ownerId);
    }
    return hexToRgba(getPlayerColor(ownerId), 0.34);
  }
  return "rgba(8, 10, 14, 0.92)";
}

function getBackstreetColor(square: SquareInfo): string {
  const configuredColor = square.custom_vars.backstreet_color;
  return typeof configuredColor === "string" && /^#[0-9a-f]{6}$/i.test(configuredColor)
    ? configuredColor
    : DEFAULT_BACKSTREET_COLOR;
}

function getDoorwayColor(square: SquareInfo): string {
  const configuredColor = square.custom_vars.doorway_color;
  return typeof configuredColor === "string" && /^#[0-9a-f]{6}$/i.test(configuredColor)
    ? configuredColor
    : DEFAULT_BACKSTREET_COLOR;
}

function getMinimapSquareFill(square: SquareInfo): string {
  if (isMinimapShopLikeSquare(square)) {
    return getMinimapShopColor(square.property_owner);
  }
  return "#080a0e";
}

function parseResponseInput(value: string): unknown {
  const trimmed = value.trim();
  if (trimmed === "") {
    return null;
  }
  if (trimmed === "true") {
    return true;
  }
  if (trimmed === "false") {
    return false;
  }
  if (trimmed === "null") {
    return null;
  }
  if (/^-?\d+(\.\d+)?$/.test(trimmed)) {
    return Number(trimmed);
  }
  try {
    return JSON.parse(trimmed);
  } catch {
    return trimmed;
  }
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function getVentureCells(request: InputRequest): VentureCellOwner[][] {
  return asArray(request.data.cells).map((row) =>
    asArray(row).map((cell) => (typeof cell === "number" && Number.isInteger(cell) ? cell : null)),
  );
}

function findFirstUnclaimedVentureCell(cells: VentureCellOwner[][]): VentureCursor {
  for (let row = 0; row < cells.length; row += 1) {
    for (let col = 0; col < cells[row].length; col += 1) {
      if (cells[row][col] === null) {
        return [row, col];
      }
    }
  }
  return [0, 0];
}

function ventureCoordinateLabel(row: number, col: number): string {
  return `${String.fromCharCode(65 + row)}${col + 1}`;
}

function getVentureLinePreview(
  cells: VentureCellOwner[][],
  row: number,
  col: number,
  playerId: number,
): { bonus: number; cells: Set<string> } {
  if (cells[row]?.[col] !== null) {
    return { bonus: 0, cells: new Set() };
  }

  let bonus = 0;
  const previewCells = new Set<string>();

  for (const [dr, dc] of VENTURE_AXES) {
    const line: Array<readonly [number, number]> = [[row, col]];
    for (const direction of [-1, 1]) {
      let nextRow = row + dr * direction;
      let nextCol = col + dc * direction;
      while (cells[nextRow]?.[nextCol] === playerId) {
        line.push([nextRow, nextCol]);
        nextRow += dr * direction;
        nextCol += dc * direction;
      }
    }

    for (const [threshold, reward] of Object.entries(VENTURE_LINE_BONUSES)) {
      if (line.length >= Number(threshold)) {
        bonus += reward;
      }
    }
    if (line.length >= 4) {
      line.forEach(([lineRow, lineCol]) => previewCells.add(`${lineRow}:${lineCol}`));
    }
  }

  return { bonus, cells: previewCells };
}

function useWasdPromptControls(request: InputRequest | null, onSubmit: (value: unknown) => void) {
  const bufferedKey = useRef("");
  const timeoutId = useRef<number | null>(null);

  useEffect(() => {
    bufferedKey.current = "";
    if (timeoutId.current !== null) {
      window.clearTimeout(timeoutId.current);
      timeoutId.current = null;
    }
  }, [request]);

  useEffect(() => {
    function clearBuffer() {
      bufferedKey.current = "";
      if (timeoutId.current !== null) {
        window.clearTimeout(timeoutId.current);
        timeoutId.current = null;
      }
    }

    function hasKey(mapping: WasdResponseMap, key: string): boolean {
      return Object.prototype.hasOwnProperty.call(mapping, key);
    }

    function submitKey(mapping: WasdResponseMap, key: string): boolean {
      if (!hasKey(mapping, key)) {
        return false;
      }
      clearBuffer();
      onSubmit(mapping[key]);
      return true;
    }

    function mayCombo(mapping: WasdResponseMap, key: string): boolean {
      return Object.keys(mapping).some((mappedKey) => mappedKey.length > 1 && mappedKey.includes(key));
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (!request || event.repeat || event.altKey || event.ctrlKey || event.metaKey) {
        return;
      }
      if (isTypingTarget(event.target)) {
        return;
      }

      const key = event.key.toLowerCase();
      if (!WASD_KEYS.has(key)) {
        return;
      }

      const mapping = getWasdResponseMap(request);
      if (Object.keys(mapping).length === 0) {
        return;
      }

      event.preventDefault();
      if (timeoutId.current !== null) {
        window.clearTimeout(timeoutId.current);
        timeoutId.current = null;
      }

      if (bufferedKey.current) {
        const first = bufferedKey.current;
        bufferedKey.current = "";
        if (submitKey(mapping, `${first}${key}`) || submitKey(mapping, `${key}${first}`)) {
          return;
        }
        submitKey(mapping, key);
        return;
      }

      if (mayCombo(mapping, key)) {
        bufferedKey.current = key;
        timeoutId.current = window.setTimeout(() => {
          const pending = bufferedKey.current;
          bufferedKey.current = "";
          timeoutId.current = null;
          if (pending) {
            submitKey(mapping, pending);
          }
        }, CHORD_TIMEOUT_MS);
        return;
      }

      submitKey(mapping, key);
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      clearBuffer();
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [request, onSubmit]);
}

function isTypingTarget(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName))
  );
}

function App() {
  const {
    clientState,
    connect,
    disconnect,
    submitResponse,
    saveGame,
    requestSync,
    acknowledgePresentation,
    dismissPresentation,
  } = useGameClient(DEFAULT_URI);
  const [uri, setUri] = useState(DEFAULT_URI);
  const [devPanelOpen, setDevPanelOpen] = useState(false);
  const [selectedSquareId, setSelectedSquareId] = useState<number | null>(null);
  const [confirmedInvestmentSquareId, setConfirmedInvestmentSquareId] = useState<number | null>(null);
  const [confirmedBuyShopSquareId, setConfirmedBuyShopSquareId] = useState<number | null>(null);
  const [confirmedSellShopSquareId, setConfirmedSellShopSquareId] = useState<number | null>(null);
  const [liquidationAssetMode, setLiquidationAssetMode] = useState<LiquidationAssetMode>("choose");
  const [tradePhase, setTradePhase] = useState<TradePhase>("target");
  const [tradeTargetPlayerId, setTradeTargetPlayerId] = useState<number | null>(null);
  const [tradeOfferSquareIds, setTradeOfferSquareIds] = useState<number[]>([]);
  const [tradeRequestSquareIds, setTradeRequestSquareIds] = useState<number[]>([]);
  const ventureRequest =
    clientState.pendingRequest?.type === "CHOOSE_VENTURE_CELL" ? clientState.pendingRequest : null;
  const investmentRequest =
    clientState.pendingRequest?.type === "INVEST" ? clientState.pendingRequest : null;
  const buyShopRequest =
    clientState.pendingRequest?.type === "CHOOSE_SHOP_BUY" ? clientState.pendingRequest : null;
  const sellShopRequest =
    clientState.pendingRequest?.type === "CHOOSE_SHOP_SELL" ? clientState.pendingRequest : null;
  const tradeRequest =
    clientState.pendingRequest?.type === "TRADE" ? clientState.pendingRequest : null;
  const simpleSquareRequest =
    clientState.pendingRequest &&
    ["CHOOSE_ANY_SQUARE", "CHOOSE_SHOP_AUCTION"].includes(clientState.pendingRequest.type)
      ? clientState.pendingRequest
      : null;
  const investmentChoices = useMemo(
    () => investmentSquareChoices(investmentRequest?.data.investable),
    [investmentRequest],
  );
  const investmentSquareIds = useMemo(
    () => new Set(investmentChoices.map((choice) => choice.squareId)),
    [investmentChoices],
  );
  const investmentRequestKey = investmentRequest
    ? `${investmentRequest.player_id}:${investmentChoices.map((choice) => `${choice.squareId}-${choice.maxCapital}`).join("|")}`
    : "";
  const availableBuyShopChoices = useMemo(
    () => buyShopChoices(clientState.gameState, buyShopRequest?.player_id ?? -1),
    [clientState.gameState, buyShopRequest?.player_id],
  );
  const buyShopSquareIds = useMemo(
    () => new Set(availableBuyShopChoices.map((choice) => choice.squareId)),
    [availableBuyShopChoices],
  );
  const buyShopRequestKey = buyShopRequest
    ? `${buyShopRequest.player_id}:${availableBuyShopChoices.map((choice) => `${choice.ownerId}-${choice.squareId}-${choice.currentValue}`).join("|")}`
    : "";
  const availableSellShopChoices = useMemo(
    () =>
      sellShopChoices(
        clientState.gameState,
        sellShopRequest?.player_id ?? -1,
        sellShopRequest?.data.shops,
      ),
    [clientState.gameState, sellShopRequest],
  );
  const sellShopSquareIds = useMemo(
    () => new Set(availableSellShopChoices.map((choice) => choice.squareId)),
    [availableSellShopChoices],
  );
  const availableSellTargets = useMemo(
    () => negotiationPlayerChoices(clientState.gameState, sellShopRequest?.player_id ?? -1),
    [clientState.gameState, sellShopRequest?.player_id],
  );
  const sellShopRequestKey = sellShopRequest
    ? `${sellShopRequest.player_id}:${availableSellShopChoices.map((choice) => `${choice.squareId}-${choice.currentValue}`).join("|")}:${availableSellTargets.map((player) => player.playerId).join("-")}`
    : "";
  const availableTradePlayers = useMemo(
    () => tradePlayerChoices(clientState.gameState, tradeRequest?.player_id ?? -1),
    [clientState.gameState, tradeRequest?.player_id],
  );
  const tradeProposerProperties = useMemo(
    () => propertyChoicesForPlayer(clientState.gameState, tradeRequest?.player_id ?? -1),
    [clientState.gameState, tradeRequest?.player_id],
  );
  const tradeTargetPlayer =
    availableTradePlayers.find((player) => player.playerId === tradeTargetPlayerId) ?? null;
  const tradePhaseProperties =
    tradePhase === "offer"
      ? tradeProposerProperties
      : tradePhase === "request"
        ? (tradeTargetPlayer?.properties ?? [])
        : [];
  const tradeEligibleSquareIds = useMemo(
    () => new Set(tradePhaseProperties.map((choice) => choice.squareId)),
    [tradePhaseProperties],
  );
  const tradeChosenSquareIds = useMemo(
    () => new Set(tradePhase === "offer" ? tradeOfferSquareIds : tradeRequestSquareIds),
    [tradeOfferSquareIds, tradePhase, tradeRequestSquareIds],
  );
  const tradeRequestKey = tradeRequest
    ? `${tradeRequest.player_id}:${tradeProposerProperties.map((choice) => choice.squareId).join("-")}:${availableTradePlayers.map((player) => `${player.playerId}-${player.properties.map((choice) => choice.squareId).join(".")}`).join("|")}`
    : "";
  const simpleSquareIds = useMemo(() => {
    if (!simpleSquareRequest) {
      return new Set<number>();
    }
    const optionKey = simpleSquareRequest.type === "CHOOSE_ANY_SQUARE" ? "squares" : "shops";
    return new Set(squareIdsFromOptions(simpleSquareRequest.data[optionKey]));
  }, [simpleSquareRequest]);
  const simpleSquareRequestKey = simpleSquareRequest
    ? `${simpleSquareRequest.type}:${simpleSquareRequest.player_id}:${[...simpleSquareIds].join("|")}`
    : "";
  const liquidationRequest =
    clientState.pendingRequest?.type === "LIQUIDATION" ? clientState.pendingRequest : null;
  const liquidationChoices = useMemo(
    () => liquidationShopChoices(liquidationRequest?.data.options),
    [liquidationRequest],
  );
  const liquidationSquareIds = useMemo(
    () => new Set(liquidationChoices.map((choice) => choice.squareId)),
    [liquidationChoices],
  );
  const liquidationHasStock = hasLiquidatableStock(liquidationRequest?.data.options);
  const liquidationRequestKey = liquidationRequest
    ? `${liquidationRequest.player_id}:${asNumber(liquidationRequest.data.cash)}:${liquidationChoices.map((choice) => `${choice.squareId}-${choice.sellValue}`).join("|")}:${liquidationHasStock}`
    : "";
  const stockRequest =
    clientState.pendingRequest &&
    (["BUY_STOCK", "SELL_STOCK"].includes(clientState.pendingRequest.type) ||
      (clientState.pendingRequest.type === "LIQUIDATION" && liquidationAssetMode === "stock"))
      ? clientState.pendingRequest
      : null;
  const activePresentation = clientState.presentations[0] ?? null;
  const activeStockPriceChange =
    activePresentation?.type === "stock_price_changed"
      ? stockPriceChangeFacts(activePresentation.data, activePresentation.playerId)
      : null;
  const paymentCashDeltas =
    activePresentation?.type === "rent_payment"
      ? new Map(
          rentPaymentCashDeltas(
            rentPaymentFacts(activePresentation.data, activePresentation.playerId),
          ).map((delta) => [delta.playerId, delta.amount]),
        )
      : null;
  const blockingPresentationActive = activePresentation !== null;
  const standardKeyboardRequest =
    ventureRequest ||
    investmentRequest ||
    buyShopRequest ||
    sellShopRequest ||
    tradeRequest ||
    simpleSquareRequest ||
    liquidationRequest ||
    stockRequest ||
    blockingPresentationActive
      ? null
      : clientState.pendingRequest;
  useWasdPromptControls(clientState.responsePending ? null : standardKeyboardRequest, submitResponse);

  useEffect(() => {
    setConfirmedInvestmentSquareId(null);
    if (investmentRequest) {
      setSelectedSquareId(null);
    }
  }, [investmentRequestKey]);

  useEffect(() => {
    setConfirmedBuyShopSquareId(null);
    if (buyShopRequest) {
      setSelectedSquareId(null);
    }
  }, [buyShopRequestKey]);

  useEffect(() => {
    setConfirmedSellShopSquareId(null);
    if (sellShopRequest) {
      setSelectedSquareId(null);
    }
  }, [sellShopRequestKey]);

  useEffect(() => {
    setTradePhase("target");
    setTradeTargetPlayerId(null);
    setTradeOfferSquareIds([]);
    setTradeRequestSquareIds([]);
    if (tradeRequest) {
      setSelectedSquareId(null);
    }
  }, [tradeRequestKey]);

  useEffect(() => {
    if (simpleSquareRequest) {
      setSelectedSquareId(null);
    }
  }, [simpleSquareRequestKey]);

  useEffect(() => {
    setLiquidationAssetMode("choose");
    if (liquidationRequest) {
      setSelectedSquareId(null);
    }
  }, [liquidationRequestKey]);

  const currentPlayer = clientState.gameState
    ? clientState.gameState.players[clientState.gameState.current_player_index]
    : null;
  const assignedPlayer = clientState.gameState
    ? clientState.gameState.players.find((player) => player.player_id === clientState.playerId) ?? null
    : null;
  const latestEvent = getLatestGameLog(clientState.logs);
  const movementRequest = ["CHOOSE_PATH", "CONFIRM_STOP"].includes(
    clientState.pendingRequest?.type ?? "",
  );
  const stopConfirmationActive = clientState.pendingRequest?.type === "CONFIRM_STOP";
  const rollActionPromptActive = Boolean(
    clientState.pendingRequest &&
      !["PRE_ROLL", "CHOOSE_PATH", "CONFIRM_STOP", "CHOOSE_VENTURE_CELL"].includes(
        clientState.pendingRequest.type,
      ),
  );
  const isRollingOrMoving = Boolean(
    (clientState.dice?.remaining ?? 0) > 0 ||
      movementRequest ||
      (clientState.responsePending && clientState.pendingRequest?.type === "PRE_ROLL"),
  );

  const selectedSquare = useMemo(() => {
    if (!clientState.gameState || selectedSquareId === null) {
      return null;
    }
    return clientState.gameState.board.squares.find((square) => square.id === selectedSquareId) ?? null;
  }, [clientState.gameState, selectedSquareId]);

  const focusSquare =
    selectedSquare ??
    (clientState.gameState && assignedPlayer
      ? clientState.gameState.board.squares.find((square) => square.id === assignedPlayer.position) ?? null
      : null);

  function handleConnect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    connect(uri);
  }

  return (
    <main
      className={`app-shell layout-immersive ${clientState.gameState ? "is-playing" : "is-starting"} ${isRollingOrMoving ? "is-roll-active" : ""} ${stopConfirmationActive ? "is-stop-confirmation" : ""} ${rollActionPromptActive ? "is-roll-action-prompt" : ""} ${ventureRequest ? "has-venture-grid" : ""}`}
    >
      <header className="game-header">
        <div className="brand-lockup">
          <p className="eyebrow">Road to Riches</p>
          <h1>{clientState.gameState ? "Local Match" : "Join Local Match"}</h1>
        </div>
        {clientState.gameState && (
          <div className="match-summary" aria-label="Match summary">
            <span>Target {formatGold(clientState.gameState.board.target_networth)}</span>
            <span>{currentPlayer ? `Turn P${currentPlayer.player_id}` : "Turn -"}</span>
            <span>{clientState.dice ? `Die ${clientState.dice.value} / ${clientState.dice.remaining}` : "Die -"}</span>
          </div>
        )}
        <div className="game-header-actions">
          <button
            type="button"
            className="secondary dev-toggle"
            onClick={() => setDevPanelOpen((open) => !open)}
          >
            {devPanelOpen ? "Hide Tools" : "Tools"}
          </button>
        </div>
      </header>

      {clientState.error && <div className="error-banner">{clientState.error}</div>}

      {!clientState.gameState ? (
        <ConnectPanel
          uri={uri}
          status={clientState.status}
          playerId={clientState.playerId}
          gameId={clientState.gameId}
          onUriChange={setUri}
          onConnect={handleConnect}
          onDisconnect={disconnect}
          latestEvent={latestEvent}
        />
      ) : (
        <>
          <PlayerHud
            state={clientState.gameState}
            assignedPlayerId={clientState.playerId}
            cashDeltas={paymentCashDeltas}
          />
          <section className="game-layout">
            <BoardPanel
              state={clientState.gameState}
              assignedPlayerId={clientState.playerId}
              dice={clientState.dice}
              showDice={isRollingOrMoving}
              selectedSquare={selectedSquare}
              focusDistrictId={activeStockPriceChange?.districtId ?? null}
              temporaryFreeCamera={Boolean(
                (investmentRequest ||
                  buyShopRequest ||
                  sellShopRequest ||
                  (tradeRequest && ["offer", "request"].includes(tradePhase)) ||
                  simpleSquareRequest ||
                  (liquidationRequest && liquidationAssetMode === "shop")) &&
                  !clientState.responsePending,
              )}
              squareSelection={
                investmentRequest && !clientState.responsePending && confirmedInvestmentSquareId === null
                  ? {
                      eligibleSquareIds: investmentSquareIds,
                      selectedSquareId,
                      onConfirmSquare: (squareId) => {
                        setSelectedSquareId(squareId);
                        setConfirmedInvestmentSquareId(squareId);
                      },
                    }
                  : buyShopRequest &&
                      !clientState.responsePending &&
                      confirmedBuyShopSquareId === null
                    ? {
                        eligibleSquareIds: buyShopSquareIds,
                        selectedSquareId,
                        onConfirmSquare: (squareId) => {
                          setSelectedSquareId(squareId);
                          setConfirmedBuyShopSquareId(squareId);
                        },
                      }
                  : sellShopRequest &&
                      !clientState.responsePending &&
                      confirmedSellShopSquareId === null
                    ? {
                        eligibleSquareIds: sellShopSquareIds,
                        selectedSquareId,
                        onConfirmSquare: (squareId) => {
                          setSelectedSquareId(squareId);
                          setConfirmedSellShopSquareId(squareId);
                        },
                      }
                  : tradeRequest &&
                      !clientState.responsePending &&
                      (tradePhase === "offer" || tradePhase === "request")
                    ? {
                        eligibleSquareIds: tradeEligibleSquareIds,
                        selectedSquareId,
                        chosenSquareIds: tradeChosenSquareIds,
                        onConfirmSquare: (squareId) => {
                          setSelectedSquareId(squareId);
                          if (tradePhase === "offer") {
                            setTradeOfferSquareIds((current) =>
                              toggleTradeSquare(current, squareId),
                            );
                          } else {
                            setTradeRequestSquareIds((current) =>
                              toggleTradeSquare(current, squareId),
                            );
                          }
                        },
                      }
                  : simpleSquareRequest && !clientState.responsePending
                    ? {
                        eligibleSquareIds: simpleSquareIds,
                        selectedSquareId,
                        onConfirmSquare: submitResponse,
                      }
                    : liquidationRequest &&
                        liquidationAssetMode === "shop" &&
                        !clientState.responsePending
                      ? {
                          eligibleSquareIds: liquidationSquareIds,
                          selectedSquareId,
                          onConfirmSquare: (squareId) =>
                            submitResponse(["shop", squareId, 0]),
                        }
                    : null
              }
              onSelectSquare={setSelectedSquareId}
            />
            <aside className="game-side">
              <TurnPanel
                state={clientState.gameState}
                assignedPlayer={assignedPlayer}
                currentPlayer={currentPlayer}
                request={clientState.pendingRequest}
                dice={clientState.dice}
                latestEvent={latestEvent}
                gameOverWinner={clientState.gameOverWinner}
              />
              {!stockRequest &&
                (liquidationRequest ? (
                  liquidationAssetMode === "choose" ? (
                    <LiquidationChoiceWidget
                      request={liquidationRequest}
                      hasStock={liquidationHasStock}
                      hasShops={liquidationChoices.length > 0}
                      onChoose={setLiquidationAssetMode}
                    />
                  ) : liquidationAssetMode === "shop" ? (
                    <LiquidationShopWidget
                      request={liquidationRequest}
                      choices={liquidationChoices}
                      selectedSquareId={selectedSquareId}
                      responsePending={clientState.responsePending}
                      onConfirm={(squareId) => submitResponse(["shop", squareId, 0])}
                      onBack={() => {
                        setSelectedSquareId(null);
                        setLiquidationAssetMode("choose");
                      }}
                    />
                  ) : null
                ) : investmentRequest ? (
                  <InvestmentWidget
                    request={investmentRequest}
                    choices={investmentChoices}
                    selectedSquareId={selectedSquareId}
                    confirmedSquareId={confirmedInvestmentSquareId}
                    responsePending={clientState.responsePending}
                    onConfirmSquare={(squareId) => {
                      setSelectedSquareId(squareId);
                      setConfirmedInvestmentSquareId(squareId);
                    }}
                    onChangeSquare={() => setConfirmedInvestmentSquareId(null)}
                    onSubmit={submitResponse}
                  />
                ) : buyShopRequest ? (
                  <BuyShopOfferWidget
                    request={buyShopRequest}
                    choices={availableBuyShopChoices}
                    selectedSquareId={selectedSquareId}
                    confirmedSquareId={confirmedBuyShopSquareId}
                    responsePending={clientState.responsePending}
                    onConfirmSquare={(squareId) => {
                      setSelectedSquareId(squareId);
                      setConfirmedBuyShopSquareId(squareId);
                    }}
                    onChangeSquare={() => setConfirmedBuyShopSquareId(null)}
                    onSubmit={submitResponse}
                  />
                ) : sellShopRequest ? (
                  <SellShopOfferWidget
                    request={sellShopRequest}
                    choices={availableSellShopChoices}
                    targets={availableSellTargets}
                    selectedSquareId={selectedSquareId}
                    confirmedSquareId={confirmedSellShopSquareId}
                    responsePending={clientState.responsePending}
                    onConfirmSquare={(squareId) => {
                      setSelectedSquareId(squareId);
                      setConfirmedSellShopSquareId(squareId);
                    }}
                    onChangeSquare={() => setConfirmedSellShopSquareId(null)}
                    onSubmit={submitResponse}
                  />
                ) : tradeRequest ? (
                  <TradeExchangeWidget
                    request={tradeRequest}
                    phase={tradePhase}
                    players={availableTradePlayers}
                    proposerProperties={tradeProposerProperties}
                    targetPlayer={tradeTargetPlayer}
                    selectedSquareId={selectedSquareId}
                    offeredSquareIds={tradeOfferSquareIds}
                    requestedSquareIds={tradeRequestSquareIds}
                    responsePending={clientState.responsePending}
                    onChooseTarget={(playerId) => {
                      setTradeTargetPlayerId(playerId);
                      setTradeOfferSquareIds([]);
                      setTradeRequestSquareIds([]);
                      setSelectedSquareId(null);
                      setTradePhase("offer");
                    }}
                    onToggleSquare={(squareId) => {
                      if (tradePhase === "offer") {
                        setTradeOfferSquareIds((current) =>
                          toggleTradeSquare(current, squareId),
                        );
                      } else if (tradePhase === "request") {
                        setTradeRequestSquareIds((current) =>
                          toggleTradeSquare(current, squareId),
                        );
                      }
                    }}
                    onPhaseChange={(phase) => {
                      setSelectedSquareId(null);
                      setTradePhase(phase);
                    }}
                    onSubmit={submitResponse}
                  />
                ) : simpleSquareRequest ? (
                  <SquareChoiceWidget
                    request={simpleSquareRequest}
                    selectedSquareId={selectedSquareId}
                    eligibleSquareIds={simpleSquareIds}
                    responsePending={clientState.responsePending}
                    onConfirmSquare={submitResponse}
                    onCancel={
                      simpleSquareRequest.type === "CHOOSE_SHOP_AUCTION"
                        ? () => submitResponse(null)
                        : null
                    }
                  />
                ) : (
                  <PromptPanel
                    request={clientState.pendingRequest}
                    state={clientState.gameState}
                    onSubmit={submitResponse}
                    connected={clientState.status === "connected"}
                    responsePending={clientState.responsePending}
                  />
                ))}
              <SquarePanel square={focusSquare} state={clientState.gameState} />
            </aside>
          </section>
          {ventureRequest && (
            <VentureGridOverlay
              request={ventureRequest}
              responsePending={clientState.responsePending}
              onSubmit={submitResponse}
            />
          )}
          {stockRequest && (
            <StockOverlay
              request={stockRequest}
              state={clientState.gameState}
              responsePending={clientState.responsePending}
              onSubmit={submitResponse}
              onBack={
                stockRequest.type === "LIQUIDATION"
                  ? () => setLiquidationAssetMode("choose")
                  : null
              }
            />
          )}
        </>
      )}

      {activePresentation?.type === "venture_card_revealed" && (
        <VentureCardReveal
          presentation={activePresentation}
          assignedPlayerId={clientState.playerId}
          onContinue={() =>
            activePresentation.requiresAcknowledgment
              ? acknowledgePresentation(activePresentation.requestId)
              : dismissPresentation(activePresentation.requestId)
          }
        />
      )}

      {activePresentation?.type === "promotion_completed" && (
        <PromotionCeremony
          presentation={activePresentation}
          assignedPlayerId={clientState.playerId}
          onContinue={() =>
            activePresentation.requiresAcknowledgment
              ? acknowledgePresentation(activePresentation.requestId)
              : dismissPresentation(activePresentation.requestId)
          }
        />
      )}

      {activePresentation?.type === "rent_payment" && (
        <RentPaymentOverlay
          presentation={activePresentation}
          state={clientState.gameState}
          assignedPlayerId={clientState.playerId}
          onContinue={() =>
            activePresentation.requiresAcknowledgment
              ? acknowledgePresentation(activePresentation.requestId)
              : dismissPresentation(activePresentation.requestId)
          }
        />
      )}

      {activePresentation?.type === "stock_price_changed" && (
        <StockPriceChangeOverlay
          presentation={activePresentation}
          state={clientState.gameState}
          assignedPlayerId={clientState.playerId}
          onContinue={() =>
            activePresentation.requiresAcknowledgment
              ? acknowledgePresentation(activePresentation.requestId)
              : dismissPresentation(activePresentation.requestId)
          }
        />
      )}

      {activePresentation &&
        ![
          "venture_card_revealed",
          "promotion_completed",
          "rent_payment",
          "stock_price_changed",
        ].includes(activePresentation.type) && (
          <GenericPresentation
            presentation={activePresentation}
            assignedPlayerId={clientState.playerId}
            onContinue={() =>
              activePresentation.requiresAcknowledgment
                ? acknowledgePresentation(activePresentation.requestId)
                : dismissPresentation(activePresentation.requestId)
            }
          />
        )}

      <DevPanel
        open={devPanelOpen}
        uri={uri}
        status={clientState.status}
        playerId={clientState.playerId}
        gameId={clientState.gameId}
        request={clientState.pendingRequest}
        logs={clientState.logs}
        onUriChange={setUri}
        onConnect={handleConnect}
        onDisconnect={disconnect}
        onSave={() => saveGame()}
        onSync={requestSync}
        onSubmitRaw={submitResponse}
      />

      {clientState.gameOverWinner !== undefined && (
        <div className="game-over-banner">Game over. Winner: Player {clientState.gameOverWinner ?? "none"}</div>
      )}
    </main>
  );
}

function getLatestGameLog(logs: string[]): string | null {
  return (
    [...logs]
      .reverse()
      .find(
        (line) =>
          !line.startsWith("Connected to ") &&
          !line.startsWith("Assigned Player ") &&
          !line.startsWith("Disconnected from server") &&
          !line.startsWith("WebSocket connection error"),
      ) ?? null
  );
}

function ConnectPanel({
  uri,
  status,
  playerId,
  gameId,
  latestEvent,
  onUriChange,
  onConnect,
  onDisconnect,
}: {
  uri: string;
  status: string;
  playerId: number | null;
  gameId: string | null;
  latestEvent: string | null;
  onUriChange: (value: string) => void;
  onConnect: (event: FormEvent<HTMLFormElement>) => void;
  onDisconnect: () => void;
}) {
  const statusMessage = getConnectStatusMessage(status, playerId, gameId, latestEvent);

  return (
    <section className="connect-stage">
      <div className="connect-card">
        <div>
          <p className="eyebrow">Local Play</p>
          <h2>Start a match on this machine</h2>
        </div>
        <div className="connect-status-grid" aria-label="Connection status">
          <StatusPill
            label="Status"
            value={status}
            tone={status as "connected" | "connecting" | "disconnected"}
          />
          <StatusPill label="Player" value={playerId === null ? "-" : `P${playerId}`} />
          <StatusPill label="Game" value={gameId ?? "-"} />
        </div>
        <form className="connect-form" onSubmit={onConnect}>
          <label>
            Local game address
            <input value={uri} onChange={(event) => onUriChange(event.target.value)} />
          </label>
          <button type="submit" disabled={status === "connecting"}>
            {status === "connecting" ? "Joining" : status === "connected" ? "Reconnect" : "Join Game"}
          </button>
          {status === "connected" && (
            <button type="button" className="secondary" onClick={onDisconnect}>
              Disconnect
            </button>
          )}
        </form>
        <p className="muted">{statusMessage}</p>
      </div>
    </section>
  );
}

function getConnectStatusMessage(
  status: string,
  playerId: number | null,
  gameId: string | null,
  latestEvent: string | null,
): string {
  if (status === "connecting") {
    return "Connecting to the local Road to Riches server...";
  }
  if (status === "connected" && playerId !== null) {
    return `Joined ${gameId ?? "the local match"} as Player ${playerId}. Waiting for the board state...`;
  }
  if (status === "connected") {
    return "Connected to the server, but no player slot has been assigned yet. The current match may already have its human player.";
  }
  return latestEvent ?? "Waiting for a local Road to Riches server to host the match.";
}

function StatusPill({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "connected" | "connecting" | "disconnected";
}) {
  return (
    <div className={`status-pill ${tone ?? ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function BoardPanel({
  state,
  assignedPlayerId,
  dice,
  showDice,
  selectedSquare,
  focusDistrictId,
  temporaryFreeCamera,
  squareSelection,
  onSelectSquare,
}: {
  state: GameState | null;
  assignedPlayerId: number | null;
  dice: DiceState | null;
  showDice: boolean;
  selectedSquare: SquareInfo | null;
  focusDistrictId: number | null;
  temporaryFreeCamera: boolean;
  squareSelection: BoardSquareSelection | null;
  onSelectSquare: (squareId: number) => void;
}) {
  const boardCanvasRef = useRef<HTMLDivElement>(null);
  const boardSvgRef = useRef<SVGSVGElement>(null);
  const boardDragRef = useRef<BoardDrag | null>(null);
  const didDragRef = useRef(false);
  const cameraRef = useRef<BoardCamera>({ zoom: 1, minX: 0, minY: 0 });
  const cameraBoundsKeyRef = useRef("");
  const cameraAnimationFrameRef = useRef<number | null>(null);
  const cameraReadyRef = useRef(false);
  const followZoomScaleRef = useRef(1);
  const activePlayerFrameRef = useRef<ActivePlayerFrame | null>(null);
  const tokenElementsRef = useRef(new Map<number, SVGGElement>());
  const tokenVisualsRef = useRef(new Map<number, BoardTokenVisual>());
  const tokenAnimationFrameRef = useRef<number | null>(null);
  const temporaryAutoFreeRef = useRef(false);
  const [cameraMode, setCameraMode] = useState<BoardCameraMode>("follow");
  const [isDragging, setIsDragging] = useState(false);
  const squareSelectionActive = squareSelection !== null;
  const boardBounds = state ? getBoardBounds(state) : null;
  const activePlayer = state?.players[state.current_player_index] ?? null;
  const activeSquare =
    state && activePlayer
      ? state.board.squares.find((square) => square.id === activePlayer.position) ?? null
      : null;
  const activePositionKey = activeSquare ? `${activeSquare.position[0]}:${activeSquare.position[1]}` : "";
  const focusedDistrictSquares =
    state && focusDistrictId !== null
      ? state.board.squares.filter(
          (square) => square.type === "SHOP" && square.property_district === focusDistrictId,
        )
      : [];
  const focusedDistrictCenter =
    focusedDistrictSquares.length > 0
      ? {
          x:
            focusedDistrictSquares.reduce((total, square) => total + square.position[0], 0) /
            focusedDistrictSquares.length,
          y:
            focusedDistrictSquares.reduce((total, square) => total + square.position[1], 0) /
            focusedDistrictSquares.length,
        }
      : null;
  const districtFocusKey = focusedDistrictCenter
    ? `${focusDistrictId}:${focusedDistrictCenter.x}:${focusedDistrictCenter.y}`
    : "";
  const followCenter =
    focusedDistrictCenter ??
    (activeSquare
      ? { x: activeSquare.position[0], y: activeSquare.position[1] }
      : boardBounds
        ? {
            x: boardBounds.minX + boardBounds.width / 2,
            y: boardBounds.minY + boardBounds.height / 2,
          }
        : null);
  const automaticAnimation = useMemo(() => {
    const previous = activePlayerFrameRef.current;
    const isAdjacentActiveMove = Boolean(
      focusDistrictId === null &&
        state &&
        activePlayer &&
        activeSquare &&
        previous &&
        previous.playerId === activePlayer.player_id &&
        previous.squareId !== activeSquare.id &&
        areBoardSquaresAdjacent(state, previous.squareId, activeSquare.id),
    );
    return {
      curve: (isAdjacentActiveMove ? "linear" : "cubic") as BoardAnimationCurve,
      duration: isAdjacentActiveMove
        ? adjacentStepAnimationDuration(activePlayer?.player_id ?? -1, assignedPlayerId)
        : FOLLOW_CAMERA_ANIMATION_MS,
    };
  }, [activePlayer?.player_id, activeSquare?.id, assignedPlayerId, focusDistrictId]);
  const automaticAnimationCurve = automaticAnimation.curve;
  const automaticAnimationDuration = automaticAnimation.duration;
  const playerTokens = useMemo(() => getBoardPlayerTokens(state), [state]);
  const playerTokenKey = playerTokens
    .map((token) => `${token.player.player_id}:${token.x}:${token.y}:${token.radius}`)
    .join("|");
  const boundsKey = boardBounds
    ? `${boardBounds.minX}:${boardBounds.minY}:${boardBounds.width}:${boardBounds.height}`
    : "";

  useEffect(() => {
    if (temporaryFreeCamera && cameraMode === "follow") {
      temporaryAutoFreeRef.current = true;
      setCameraMode("free");
      return;
    }
    if (!temporaryFreeCamera && temporaryAutoFreeRef.current) {
      temporaryAutoFreeRef.current = false;
      setCameraMode("follow");
    }
  }, [cameraMode, temporaryFreeCamera]);

  useLayoutEffect(() => {
    const svg = boardSvgRef.current;
    if (!svg || !boardBounds) {
      return;
    }
    if (cameraAnimationFrameRef.current !== null) {
      window.cancelAnimationFrame(cameraAnimationFrameRef.current);
      cameraAnimationFrameRef.current = null;
    }
    const boundsChanged = cameraBoundsKeyRef.current !== boundsKey;
    if (boundsChanged) {
      cameraRef.current = resetBoardCamera(boardBounds);
      cameraBoundsKeyRef.current = boundsKey;
      followZoomScaleRef.current = 1;
    }
    svg.dataset.cameraMode = cameraMode;
    if (cameraMode === "follow") {
      const target = centeredBoardCamera(
        boardBounds,
        clampBoardZoom(getFollowBoardZoom(boardBounds) * followZoomScaleRef.current),
        followCenter ?? {
          x: boardBounds.minX + boardBounds.width / 2,
          y: boardBounds.minY + boardBounds.height / 2,
        },
      );
      const from = { ...cameraRef.current };
      const shouldAnimate =
        cameraReadyRef.current &&
        !boundsChanged &&
        (Math.abs(from.zoom - target.zoom) > 0.0001 ||
          Math.abs(from.minX - target.minX) > 0.0001 ||
          Math.abs(from.minY - target.minY) > 0.0001);

      if (shouldAnimate) {
        svg.dataset.cameraAnimating = "true";
        svg.dataset.cameraAnimationCurve = automaticAnimationCurve;
        svg.dataset.cameraAnimationDuration = String(automaticAnimationDuration);
        const startedAt = window.performance.now();
        const animate = (timestamp: number) => {
          const progress = Math.min(1, (timestamp - startedAt) / automaticAnimationDuration);
          cameraRef.current = interpolateBoardCamera(
            from,
            target,
            animationProgress(progress, automaticAnimationCurve),
          );
          applyBoardCamera(svg, cameraRef.current, boardBounds);
          if (progress < 1) {
            cameraAnimationFrameRef.current = window.requestAnimationFrame(animate);
          } else {
            cameraRef.current = target;
            cameraAnimationFrameRef.current = null;
            svg.dataset.cameraAnimating = "false";
          }
        };
        cameraAnimationFrameRef.current = window.requestAnimationFrame(animate);
      } else {
        cameraRef.current = target;
        svg.dataset.cameraAnimating = "false";
        applyBoardCamera(svg, cameraRef.current, boardBounds);
      }
    } else {
      svg.dataset.cameraAnimating = "false";
      applyBoardCamera(svg, cameraRef.current, boardBounds);
    }

    cameraReadyRef.current = true;
    return () => {
      if (cameraAnimationFrameRef.current !== null) {
        window.cancelAnimationFrame(cameraAnimationFrameRef.current);
        cameraAnimationFrameRef.current = null;
      }
      svg.dataset.cameraAnimating = "false";
    };
  }, [
    activePositionKey,
    boundsKey,
    cameraMode,
    automaticAnimationCurve,
    automaticAnimationDuration,
    districtFocusKey,
  ]);

  useEffect(() => {
    const canvas = boardCanvasRef.current;
    const svg = boardSvgRef.current;
    if (!canvas || !svg || !boardBounds) {
      return;
    }
    const activeSvg = svg;
    const activeBounds = boardBounds;

    function handleWheel(event: WheelEvent) {
      event.preventDefault();
      const factor = Math.exp(-event.deltaY * BOARD_WHEEL_ZOOM_SPEED);
      if (cameraMode === "follow") {
        if (!followCenter) {
          return;
        }
        if (cameraAnimationFrameRef.current !== null) {
          window.cancelAnimationFrame(cameraAnimationFrameRef.current);
          cameraAnimationFrameRef.current = null;
        }
        const zoom = clampBoardZoom(cameraRef.current.zoom * factor);
        followZoomScaleRef.current = zoom / getFollowBoardZoom(activeBounds);
        cameraRef.current = centeredBoardCamera(activeBounds, zoom, followCenter);
        activeSvg.dataset.cameraAnimating = "false";
        applyBoardCamera(activeSvg, cameraRef.current, activeBounds);
        return;
      }
      const point = svgPointAt(activeSvg, event.clientX, event.clientY);
      if (!point) {
        return;
      }
      cameraRef.current = zoomBoardCameraAt(
        cameraRef.current,
        cameraRef.current.zoom * factor,
        point,
        activeBounds,
      );
      applyBoardCamera(activeSvg, cameraRef.current, activeBounds);
    }

    canvas.addEventListener("wheel", handleWheel, { passive: false });
    return () => canvas.removeEventListener("wheel", handleWheel);
  }, [activePositionKey, boundsKey, cameraMode, districtFocusKey]);

  useLayoutEffect(() => {
    if (tokenAnimationFrameRef.current !== null) {
      window.cancelAnimationFrame(tokenAnimationFrameRef.current);
      tokenAnimationFrameRef.current = null;
    }

    const transitions = playerTokens.flatMap((target) => {
      const element = tokenElementsRef.current.get(target.player.player_id);
      if (!element) {
        return [];
      }
      const from = tokenVisualsRef.current.get(target.player.player_id) ?? target;
      applyBoardTokenVisual(element, from);
      const moved =
        Math.abs(from.x - target.x) > 0.0001 ||
        Math.abs(from.y - target.y) > 0.0001 ||
        Math.abs(from.radius - target.radius) > 0.0001;
      if (!moved) {
        tokenVisualsRef.current.set(target.player.player_id, target);
        element.dataset.tokenAnimating = "false";
        return [];
      }
      element.dataset.tokenAnimating = "true";
      element.dataset.tokenAnimationCurve = automaticAnimationCurve;
      element.dataset.tokenAnimationDuration = String(automaticAnimationDuration);
      return [{ element, from, target }];
    });

    if (transitions.length === 0) {
      return;
    }

    const startedAt = window.performance.now();
    const animate = (timestamp: number) => {
      const progress = Math.min(1, (timestamp - startedAt) / automaticAnimationDuration);
      const easedProgress = animationProgress(progress, automaticAnimationCurve);
      for (const transition of transitions) {
        const visual = interpolateBoardToken(transition.from, transition.target, easedProgress);
        tokenVisualsRef.current.set(transition.target.player.player_id, visual);
        applyBoardTokenVisual(transition.element, visual);
      }
      if (progress < 1) {
        tokenAnimationFrameRef.current = window.requestAnimationFrame(animate);
      } else {
        for (const transition of transitions) {
          tokenVisualsRef.current.set(transition.target.player.player_id, transition.target);
          applyBoardTokenVisual(transition.element, transition.target);
          transition.element.dataset.tokenAnimating = "false";
        }
        tokenAnimationFrameRef.current = null;
      }
    };
    tokenAnimationFrameRef.current = window.requestAnimationFrame(animate);

    return () => {
      if (tokenAnimationFrameRef.current !== null) {
        window.cancelAnimationFrame(tokenAnimationFrameRef.current);
        tokenAnimationFrameRef.current = null;
      }
    };
  }, [automaticAnimationCurve, automaticAnimationDuration, playerTokenKey]);

  useLayoutEffect(() => {
    activePlayerFrameRef.current =
      activePlayer && activeSquare
        ? { playerId: activePlayer.player_id, squareId: activeSquare.id }
        : null;
  }, [activePlayer?.player_id, activeSquare?.id]);

  if (!state || !boardBounds) {
    return (
      <section className="board-panel empty-board">
        <div className="location-backdrop" />
        <div className="empty-message">
          <h2>Waiting for the board</h2>
          <p>The match will appear here as soon as state sync arrives.</p>
          <code>python -m road_to_riches server --humans 1 --ai 3</code>
        </div>
      </section>
    );
  }

  const bounds = boardBounds;
  const selectionScrimPath =
    squareSelectionActive && squareSelection
      ? boardSelectionScrimPath(bounds, state.board.squares, squareSelection.eligibleSquareIds)
      : null;

  function zoomFromCenter(delta: number) {
    const svg = boardSvgRef.current;
    if (!svg) {
      return;
    }
    const camera = cameraRef.current;
    if (cameraMode === "follow" && followCenter) {
      if (cameraAnimationFrameRef.current !== null) {
        window.cancelAnimationFrame(cameraAnimationFrameRef.current);
        cameraAnimationFrameRef.current = null;
      }
      const zoom = clampBoardZoom(camera.zoom + delta);
      followZoomScaleRef.current = zoom / getFollowBoardZoom(bounds);
      cameraRef.current = centeredBoardCamera(bounds, zoom, followCenter);
      svg.dataset.cameraAnimating = "false";
      applyBoardCamera(svg, cameraRef.current, bounds);
      return;
    }
    const point = {
      x: camera.minX + bounds.width / camera.zoom / 2,
      y: camera.minY + bounds.height / camera.zoom / 2,
    };
    cameraRef.current = zoomBoardCameraAt(camera, camera.zoom + delta, point, bounds);
    applyBoardCamera(svg, cameraRef.current, bounds);
  }

  function resetCamera() {
    const svg = boardSvgRef.current;
    if (!svg) {
      return;
    }
    if (cameraMode === "follow" && followCenter) {
      if (cameraAnimationFrameRef.current !== null) {
        window.cancelAnimationFrame(cameraAnimationFrameRef.current);
        cameraAnimationFrameRef.current = null;
      }
      followZoomScaleRef.current = 1;
      cameraRef.current = centeredBoardCamera(
        bounds,
        clampBoardZoom(getFollowBoardZoom(bounds)),
        followCenter,
      );
      svg.dataset.cameraAnimating = "false";
      applyBoardCamera(svg, cameraRef.current, bounds);
      return;
    }
    cameraRef.current = resetBoardCamera(bounds);
    applyBoardCamera(svg, cameraRef.current, bounds);
  }

  function enableFreeCamera() {
    if (cameraAnimationFrameRef.current !== null) {
      window.cancelAnimationFrame(cameraAnimationFrameRef.current);
      cameraAnimationFrameRef.current = null;
    }
    if (boardSvgRef.current) {
      boardSvgRef.current.dataset.cameraAnimating = "false";
    }
    setCameraMode("free");
  }

  function enableFollowCamera() {
    if (temporaryFreeCamera) {
      return;
    }
    boardDragRef.current = null;
    setIsDragging(false);
    setCameraMode("follow");
  }

  function handlePointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    if (cameraMode !== "free" || event.button !== 0) {
      return;
    }
    didDragRef.current = false;
    boardDragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      lastX: event.clientX,
      lastY: event.clientY,
    };
  }

  function handlePointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    const drag = boardDragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) {
      return;
    }
    const deltaX = event.clientX - drag.lastX;
    const deltaY = event.clientY - drag.lastY;
    drag.lastX = event.clientX;
    drag.lastY = event.clientY;

    if (
      !didDragRef.current &&
      Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY) < BOARD_DRAG_THRESHOLD
    ) {
      return;
    }
    if (!didDragRef.current) {
      didDragRef.current = true;
      event.currentTarget.setPointerCapture(event.pointerId);
      setIsDragging(true);
    }
    event.preventDefault();
    const svg = boardSvgRef.current;
    const matrix = svg?.getScreenCTM();
    if (!svg || !matrix) {
      return;
    }
    const scaleX = Math.hypot(matrix.a, matrix.b);
    const scaleY = Math.hypot(matrix.c, matrix.d);
    if (scaleX <= 0 || scaleY <= 0) {
      return;
    }
    cameraRef.current = {
      ...cameraRef.current,
      minX: cameraRef.current.minX - deltaX / scaleX,
      minY: cameraRef.current.minY - deltaY / scaleY,
    };
    applyBoardCamera(svg, cameraRef.current, bounds);
  }

  function finishPointerDrag(event: ReactPointerEvent<HTMLDivElement>) {
    if (boardDragRef.current?.pointerId !== event.pointerId) {
      return;
    }
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    boardDragRef.current = null;
    setIsDragging(false);
  }

  return (
    <section className="board-panel">
      <div className="location-backdrop" />
      <div
        ref={boardCanvasRef}
        className={`board-canvas ${cameraMode === "free" ? "is-free-camera" : "is-follow-camera"} ${isDragging ? "is-dragging" : ""} ${squareSelectionActive ? "is-square-selection-active" : ""}`}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={finishPointerDrag}
        onPointerCancel={finishPointerDrag}
        onClickCapture={(event) => {
          if (didDragRef.current) {
            event.preventDefault();
            event.stopPropagation();
            didDragRef.current = false;
          }
        }}
      >
        <svg
          ref={boardSvgRef}
          className="board-svg"
          viewBox={`${bounds.minX} ${bounds.minY} ${bounds.width} ${bounds.height}`}
          preserveAspectRatio="xMidYMid meet"
          aria-label="Game board"
          role="img"
        >
          {state.board.squares.map((square) => {
            const isSelectionChosen = squareSelection?.chosenSquareIds?.has(square.id) === true;
            const isSelected =
              selectedSquare?.id === square.id ||
              squareSelection?.selectedSquareId === square.id ||
              isSelectionChosen;
            const isSelectionEligible =
              squareSelection?.eligibleSquareIds.has(square.id) ?? false;
            const ownerColor =
              square.property_owner === null ? "rgba(255,255,255,0.78)" : getPlayerColor(square.property_owner);
            const label = labelForSquare(square);
            const valueLabel = valueLabelForSquare(square, state);
            const shouldRenderSuitIcon = isSuitIconSquare(square);
            const shouldRenderBankIcon = isBankIconSquare(square);
            const shouldRenderVentureIcon = isVentureIconSquare(square);
            const shouldRenderBoonIcon = isBoonIconSquare(square);
            const shouldRenderBoomIcon = isBoomIconSquare(square);
            const shouldRenderTakeABreakIcon = isTakeABreakIconSquare(square);
            const shouldRenderArcadeIcon = isArcadeIconSquare(square);
            const shouldRenderRollOnIcon = isRollOnIconSquare(square);
            const shouldRenderCannonIcon = isCannonIconSquare(square);
            const shouldRenderBackstreetIcon = isBackstreetIconSquare(square);
            const shouldRenderDoorwayIcon = isDoorwayIconSquare(square);
            const shouldRenderSwitchIcon = isSwitchIconSquare(square);
            const shouldRenderSuitYourselfIcon = isSuitYourselfIconSquare(square);
            const shouldRenderStockbrokerIcon = isStockbrokerIconSquare(square);
            const shouldRenderShopTile = isShopSquare(square);
            const closedTurns = shouldRenderShopTile ? closedShopTurns(square.statuses) : null;
            const closedShopLabel =
              closedTurns === null
                ? ""
                : `, closed for ${closedTurns} more ${closedTurns === 1 ? "turn" : "turns"}`;
            const isStockPriceFocus =
              shouldRenderShopTile && square.property_district === focusDistrictId;
            const shouldRenderDefaultText =
              !shouldRenderSuitIcon &&
              !shouldRenderBankIcon &&
              !shouldRenderVentureIcon &&
              !shouldRenderBoonIcon &&
              !shouldRenderBoomIcon &&
              !shouldRenderTakeABreakIcon &&
              !shouldRenderArcadeIcon &&
              !shouldRenderRollOnIcon &&
              !shouldRenderCannonIcon &&
              !shouldRenderBackstreetIcon &&
              !shouldRenderDoorwayIcon &&
              !shouldRenderSwitchIcon &&
              !shouldRenderSuitYourselfIcon &&
              !shouldRenderStockbrokerIcon &&
              !shouldRenderShopTile;
            const squareStyle = {
              ...(isStockPriceFocus
                ? { "--stock-focus-color": getDistrictColor(square.property_district) }
                : {}),
            } as CSSProperties;
            return (
              <g
                key={square.id}
                className={`board-square-group ${isSelected ? "selected" : ""} ${isStockPriceFocus ? "stock-price-focus" : ""} ${isSelectionEligible ? "square-selection-eligible" : ""}`}
                style={squareStyle}
                role="button"
                tabIndex={squareSelectionActive && !isSelectionEligible ? -1 : 0}
                aria-disabled={squareSelectionActive && !isSelectionEligible}
                aria-label={`${isSelectionChosen ? "Included " : isSelectionEligible ? "Eligible " : ""}Square ${square.id}: ${displayTypeForSquare(square)}${closedShopLabel}`}
                onClick={() => {
                  if (!squareSelectionActive || isSelectionEligible) {
                    onSelectSquare(square.id);
                  }
                }}
                onDoubleClick={() => {
                  if (isSelectionEligible) {
                    squareSelection?.onConfirmSquare(square.id);
                  }
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    if (isSelectionEligible) {
                      onSelectSquare(square.id);
                      squareSelection?.onConfirmSquare(square.id);
                    } else if (!squareSelectionActive) {
                      onSelectSquare(square.id);
                    }
                  }
                }}
              >
                <rect
                  className="board-square-tile"
                  data-square-id={square.id}
                  x={square.position[0] - BOARD_TILE_RADIUS + BOARD_TILE_STROKE_INSET}
                  y={square.position[1] - BOARD_TILE_RADIUS + BOARD_TILE_STROKE_INSET}
                  width={BOARD_TILE_DRAW_SIZE}
                  height={BOARD_TILE_DRAW_SIZE}
                  rx="0.32"
                  ry="0.32"
                  style={{
                    fill: getSquareFill(square),
                  }}
                />
                {shouldRenderSuitIcon ? (
                  <SuitIcon suit={square.suit} squareType={square.type} x={square.position[0]} y={square.position[1]} />
                ) : shouldRenderBankIcon ? (
                  <BankIcon x={square.position[0]} y={square.position[1]} />
                ) : shouldRenderStockbrokerIcon ? (
                  <StockbrokerIcon x={square.position[0]} y={square.position[1]} />
                ) : shouldRenderVentureIcon ? (
                  <VentureIcon x={square.position[0]} y={square.position[1]} />
                ) : shouldRenderBoonIcon ? (
                  <BoonIcon x={square.position[0]} y={square.position[1]} />
                ) : shouldRenderBoomIcon ? (
                  <BoomIcon x={square.position[0]} y={square.position[1]} />
                ) : shouldRenderTakeABreakIcon ? (
                  <TakeABreakIcon x={square.position[0]} y={square.position[1]} />
                ) : shouldRenderArcadeIcon ? (
                  <ArcadeIcon x={square.position[0]} y={square.position[1]} />
                ) : shouldRenderRollOnIcon ? (
                  <RollOnIcon x={square.position[0]} y={square.position[1]} />
                ) : shouldRenderCannonIcon ? (
                  <CannonIcon x={square.position[0]} y={square.position[1]} />
                ) : shouldRenderBackstreetIcon ? (
                  <BackstreetIcon square={square} x={square.position[0]} y={square.position[1]} />
                ) : shouldRenderDoorwayIcon ? (
                  <DoorwayIcon square={square} x={square.position[0]} y={square.position[1]} />
                ) : shouldRenderSwitchIcon ? (
                  <SwitchIcon x={square.position[0]} y={square.position[1]} />
                ) : shouldRenderSuitYourselfIcon ? (
                  <SuitYourselfIcon x={square.position[0]} y={square.position[1]} />
                ) : shouldRenderShopTile ? (
                  <ShopTile
                    square={square}
                    state={state}
                    x={square.position[0]}
                    y={square.position[1]}
                    closedTurns={closedTurns}
                  />
                ) : (
                  <text
                    className="square-type"
                    x={square.position[0]}
                    y={square.position[1] - 0.55}
                    fill={ownerColor}
                  >
                    {fitLabel(label, 8)}
                  </text>
                )}
                {shouldRenderDefaultText && valueLabel !== null && (
                  <text className="square-value" x={square.position[0]} y={square.position[1] + 0.38}>
                    {valueLabel}
                  </text>
                )}
                <rect
                  className="board-square-border"
                  x={square.position[0] - BOARD_TILE_RADIUS + BOARD_TILE_STROKE_INSET}
                  y={square.position[1] - BOARD_TILE_RADIUS + BOARD_TILE_STROKE_INSET}
                  width={BOARD_TILE_DRAW_SIZE}
                  height={BOARD_TILE_DRAW_SIZE}
                  rx="0.32"
                  ry="0.32"
                  strokeWidth={BOARD_TILE_STROKE_WIDTH}
                  style={{
                    stroke:
                      shouldRenderSuitIcon ||
                      shouldRenderBankIcon ||
                      shouldRenderVentureIcon ||
                      shouldRenderBoonIcon ||
                      shouldRenderBoomIcon ||
                      shouldRenderTakeABreakIcon ||
                      shouldRenderArcadeIcon ||
                      shouldRenderRollOnIcon ||
                      shouldRenderCannonIcon ||
                      shouldRenderBackstreetIcon ||
                      shouldRenderDoorwayIcon ||
                      shouldRenderSwitchIcon ||
                      shouldRenderSuitYourselfIcon ||
                      shouldRenderStockbrokerIcon
                        ? "#f7f7f2"
                        : getDistrictBorderColor(square.property_district),
                  }}
                />
                {isSelected && (
                  <rect
                    className={`board-square-selection ${isSelectionChosen ? "is-chosen" : ""}`}
                    x={square.position[0] - BOARD_TILE_RADIUS + BOARD_TILE_SELECTION_INSET}
                    y={square.position[1] - BOARD_TILE_RADIUS + BOARD_TILE_SELECTION_INSET}
                    width={BOARD_TILE_SELECTION_SIZE}
                    height={BOARD_TILE_SELECTION_SIZE}
                    rx="0.24"
                    ry="0.24"
                    strokeWidth={BOARD_TILE_SELECTION_STROKE_WIDTH}
                  />
                )}
              </g>
            );
          })}
          {selectionScrimPath && (
            <path
              className="board-square-selection-scrim"
              d={selectionScrimPath}
              fillRule="evenodd"
              clipRule="evenodd"
            />
          )}
          <g className="player-token-layer" aria-label="Player positions">
            {playerTokens.map((token) => {
              const renderedVisual = tokenVisualsRef.current.get(token.player.player_id) ?? token;
              return (
                <g
                  key={token.player.player_id}
                  ref={(element) => {
                    if (element) {
                      tokenElementsRef.current.set(token.player.player_id, element);
                    } else {
                      tokenElementsRef.current.delete(token.player.player_id);
                    }
                  }}
                  className={`player-token-svg ${token.isActive ? "active" : ""}`}
                  data-player-id={token.player.player_id}
                  data-token-animating="false"
                  transform={`translate(${renderedVisual.x} ${renderedVisual.y})`}
                >
                  <circle r={renderedVisual.radius} fill={getPlayerColor(token.player.player_id)} />
                  <text x="0" y="0.08">
                    {token.player.player_id}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>
      </div>
      <BoardDice dice={dice} showSettled={showDice} />
      <BoardMinimap state={state} bounds={bounds} />
      <div className="board-camera-controls" aria-label="Board zoom controls">
        <button
          type="button"
          aria-label="Zoom out"
          title="Zoom out"
          onClick={() => zoomFromCenter(-BOARD_ZOOM_STEP)}
        >
          −
        </button>
        <button
          type="button"
          className="board-camera-reset"
          aria-label="Reset board view"
          title="Reset board view"
          onClick={resetCamera}
        >
          Reset
        </button>
        <button
          type="button"
          aria-label="Zoom in"
          title="Zoom in"
          onClick={() => zoomFromCenter(BOARD_ZOOM_STEP)}
        >
          +
        </button>
        {cameraMode === "follow" ? (
          <button
            type="button"
            className="board-camera-mode"
            aria-label="Use free camera"
            title="Use free camera"
            onClick={enableFreeCamera}
          >
            Free Cam
          </button>
        ) : (
          <button
            type="button"
            className="board-camera-mode"
            aria-label="Follow active player"
            title="Follow active player"
            disabled={temporaryFreeCamera}
            onClick={enableFollowCamera}
          >
            {temporaryFreeCamera ? "Choosing" : "Follow"}
          </button>
        )}
      </div>
    </section>
  );
}

type DicePresentationPhase =
  | "hidden"
  | "rolling"
  | "settling"
  | "settled"
  | "event-hold"
  | "event-fading";

const PHYSICAL_DIE_FACES = [
  ["front", 1],
  ["back", 6],
  ["right", 3],
  ["left", 4],
  ["top", 2],
  ["bottom", 5],
] as const;

function DieFace({ value, side }: { value: number; side: string }) {
  const activePips = new Set(DIE_PIPS[value] ?? DIE_PIPS[0]);
  return (
    <div className={`physical-die-face is-${side}`}>
      {Array.from({ length: 9 }, (_, index) => {
        const position = index + 1;
        return (
          <span
            key={position}
            className={`physical-die-pip ${activePips.has(position) ? "is-visible" : ""}`}
          />
        );
      })}
    </div>
  );
}

function BoardDice({ dice, showSettled }: { dice: DiceState | null; showSettled: boolean }) {
  const [phase, setPhase] = useState<DicePresentationPhase>("hidden");
  const [presentedRoll, setPresentedRoll] = useState<DiceState | null>(null);
  const lastAnimationIdRef = useRef(0);

  useEffect(() => {
    if (!dice || dice.animationId === 0 || dice.animationId === lastAnimationIdRef.current) {
      return;
    }
    lastAnimationIdRef.current = dice.animationId;
    setPresentedRoll(dice);
    setPhase("rolling");

    const timers: number[] = [];
    timers.push(
      window.setTimeout(() => {
        setPhase(dice.purpose === "movement" ? "settling" : "event-hold");
      }, DICE_ROLL_DURATION_MS),
    );

    if (dice.purpose === "movement") {
      timers.push(
        window.setTimeout(() => {
          setPhase("settled");
          setPresentedRoll(null);
        }, DICE_ROLL_DURATION_MS + DICE_SETTLE_DURATION_MS),
      );
    } else {
      timers.push(
        window.setTimeout(() => {
          setPhase("event-fading");
        }, DICE_ROLL_DURATION_MS + EVENT_DICE_HOLD_DURATION_MS),
      );
      timers.push(
        window.setTimeout(() => {
          setPhase("hidden");
          setPresentedRoll(null);
        }, DICE_ROLL_DURATION_MS + EVENT_DICE_HOLD_DURATION_MS + EVENT_DICE_FADE_DURATION_MS),
      );
    }

    return () => {
      for (const timer of timers) {
        window.clearTimeout(timer);
      }
    };
  }, [dice?.animationId]);

  const activeDice = presentedRoll ?? dice;
  const shouldShowSettledMovement = showSettled && activeDice?.purpose === "movement";
  const visualPhase = phase === "hidden" && shouldShowSettledMovement ? "settled" : phase;
  const isAnimated = ["rolling", "settling", "event-hold", "event-fading"].includes(
    visualPhase,
  );
  if (!activeDice || (!shouldShowSettledMovement && !isAnimated)) {
    return null;
  }

  const settledMovement = visualPhase === "settled";
  const faceValue = displayedDiceValue(activeDice, settledMovement);
  const frontFaceValue = faceValue === 0 || faceValue > 6 ? faceValue : 1;
  const description =
    activeDice.purpose === "event"
      ? `Rolled ${activeDice.value} for event`
      : `Rolled ${activeDice.value}; ${activeDice.remaining} moves remaining`;

  return (
    <div
      className={`board-dice is-${visualPhase} is-${activeDice.purpose}`}
      role="img"
      aria-label={description}
      aria-live="polite"
    >
      <div className="physical-die-stage" aria-hidden="true">
        <div
          className="physical-die-cube"
          style={{ "--die-final-transform": dieFinalTransform(faceValue) } as CSSProperties}
        >
          {PHYSICAL_DIE_FACES.map(([side, value]) => (
            <DieFace key={side} side={side} value={side === "front" ? frontFaceValue : value} />
          ))}
        </div>
      </div>
      <span className="board-die-roll">
        {activeDice.purpose === "event" ? "Rolled" : "Roll"} {activeDice.value}
      </span>
    </div>
  );
}

function BoardMinimap({ state, bounds }: { state: GameState; bounds: BoardBounds }) {
  const groups = groupPlayersBySquare(state.players);
  const activePlayer = state.players[state.current_player_index] ?? null;
  return (
    <aside className="board-minimap" aria-label="Board minimap">
      <svg
        viewBox={`${bounds.minX} ${bounds.minY} ${bounds.width} ${bounds.height}`}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="Miniature board and player locations"
      >
        {state.board.squares.map((square) => {
          const hasIcon = isMinimapIconSquare(square);
          const isShopLike = isMinimapShopLikeSquare(square);
          return (
            <g
              key={square.id}
              className={`minimap-square ${isShopLike ? "is-shop-like" : "is-non-shop"} ${hasIcon ? "has-icon" : ""}`}
              style={
                isShopLike
                  ? ({ "--minimap-district-color": getDistrictColor(square.property_district) } as CSSProperties)
                  : undefined
              }
            >
              <rect
                className="minimap-square-tile"
                data-square-id={square.id}
                x={square.position[0] - BOARD_TILE_RADIUS + MINIMAP_TILE_STROKE_INSET}
                y={square.position[1] - BOARD_TILE_RADIUS + MINIMAP_TILE_STROKE_INSET}
                width={MINIMAP_TILE_DRAW_SIZE}
                height={MINIMAP_TILE_DRAW_SIZE}
                rx="0.24"
                fill={getMinimapSquareFill(square)}
              />
              {hasIcon && (
                <MinimapSquareIcon square={square} x={square.position[0]} y={square.position[1]} />
              )}
            </g>
          );
        })}
        {state.players
          .filter((player) => !player.bankrupt)
          .map((player) => {
            const square = state.board.squares.find((candidate) => candidate.id === player.position);
            if (!square) {
              return null;
            }
            const group = groups.get(square.id) ?? [player];
            const index = Math.max(0, group.findIndex((candidate) => candidate.player_id === player.player_id));
            const offsetX = group.length > 1 ? (index % 2 === 0 ? -1 : 1) : 0;
            const offsetY = group.length > 2 ? (index < 2 ? -1 : 1) : 0;
            const isActive = activePlayer?.player_id === player.player_id;
            return (
              <g
                key={player.player_id}
                className={`minimap-player ${isActive ? "active" : ""}`}
                transform={`translate(${square.position[0] + offsetX} ${square.position[1] + offsetY})`}
              >
                <circle r={isActive ? 1.12 : 0.88} fill={getPlayerColor(player.player_id)} />
                <text x="0" y="0.04">{player.player_id}</text>
              </g>
            );
          })}
      </svg>
    </aside>
  );
}

function getBoardBounds(state: GameState) {
  const xs = state.board.squares.map((square) => square.position[0]);
  const ys = state.board.squares.map((square) => square.position[1]);
  const outerPadding = 1;
  const minX = Math.min(...xs) - BOARD_TILE_RADIUS - outerPadding;
  const maxX = Math.max(...xs) + BOARD_TILE_RADIUS + outerPadding;
  const minY = Math.min(...ys) - BOARD_TILE_RADIUS - outerPadding;
  const maxY = Math.max(...ys) + BOARD_TILE_RADIUS + outerPadding;
  return {
    minX,
    minY,
    width: Math.max(1, maxX - minX),
    height: Math.max(1, maxY - minY),
  };
}

function fitLabel(label: string, maxLength: number): string {
  if (label.length <= maxLength) {
    return label;
  }
  return `${label.slice(0, Math.max(1, maxLength - 1))}...`;
}

function shortGold(value: number): string {
  return `${Math.round(value)}G`;
}

function formatWasdKey(key: string): string {
  return key
    .split("")
    .map((part) => part.toUpperCase())
    .join(" + ");
}

function keyedActionLabel(request: InputRequest, value: unknown): string {
  if (request.type === "CONFIRM_STOP" && value === true) {
    return "Stop Here";
  }
  if (request.type === "CONFIRM_STOP" && (value === false || value === "undo")) {
    return "Undo Step";
  }
  if (value === true) {
    return "Confirm";
  }
  if (value === false) {
    return "Decline";
  }
  if (value === "accept") {
    return "Accept";
  }
  if (value === "reject") {
    return "Reject";
  }
  if (value === "counter") {
    return "Counter";
  }
  return "Choose";
}

function getSimpleKeyActions(request: InputRequest) {
  return Object.entries(getWasdResponseMap(request))
    .sort(([leftKey], [rightKey]) => keyedActionSort(leftKey, rightKey))
    .map(([key, value]) => ({ key, value, label: keyedActionLabel(request, value) }));
}

function keyedActionSort(leftKey: string, rightKey: string): number {
  const keyOrder = ["w", "a", "s", "d"];
  const leftIndex = keyOrder.indexOf(leftKey);
  const rightIndex = keyOrder.indexOf(rightKey);
  if (leftIndex === -1 || rightIndex === -1) {
    return leftKey.localeCompare(rightKey);
  }
  return leftIndex - rightIndex;
}

function groupPlayersBySquare(players: PlayerState[]) {
  const groups = new Map<number, PlayerState[]>();
  for (const player of players) {
    const current = groups.get(player.position) ?? [];
    current.push(player);
    groups.set(player.position, current);
  }
  return groups;
}

function isShopSquare(square: SquareInfo): boolean {
  return square.type === "SHOP";
}

function isSuitIconSquare(square: SquareInfo): boolean {
  return Boolean(square.suit && ["SUIT", "CHANGE_OF_SUIT"].includes(square.type));
}

function isBankIconSquare(square: SquareInfo): boolean {
  return square.type === "BANK";
}

function isVentureIconSquare(square: SquareInfo): boolean {
  return square.type === "VENTURE";
}

function isBoonIconSquare(square: SquareInfo): boolean {
  return square.type === "BOON";
}

function isBoomIconSquare(square: SquareInfo): boolean {
  return square.type === "BOOM";
}

function isTakeABreakIconSquare(square: SquareInfo): boolean {
  return square.type === "TAKE_A_BREAK";
}

function isArcadeIconSquare(square: SquareInfo): boolean {
  return square.type === "ARCADE";
}

function isRollOnIconSquare(square: SquareInfo): boolean {
  return square.type === "ROLL_ON";
}

function isCannonIconSquare(square: SquareInfo): boolean {
  return square.type === "CANNON";
}

function isBackstreetIconSquare(square: SquareInfo): boolean {
  return square.type === "BACKSTREET";
}

function isDoorwayIconSquare(square: SquareInfo): boolean {
  return square.type === "DOORWAY";
}

function isSwitchIconSquare(square: SquareInfo): boolean {
  return square.type === "SWITCH";
}

function isSuitYourselfIconSquare(square: SquareInfo): boolean {
  return square.type === "SUIT_YOURSELF";
}

function isStockbrokerIconSquare(square: SquareInfo): boolean {
  return square.type === "STOCKBROKER";
}

function isMinimapIconSquare(square: SquareInfo): boolean {
  return (
    isSuitIconSquare(square) ||
    isBankIconSquare(square) ||
    isVentureIconSquare(square) ||
    isBoonIconSquare(square) ||
    isBoomIconSquare(square) ||
    isTakeABreakIconSquare(square) ||
    isArcadeIconSquare(square) ||
    isRollOnIconSquare(square) ||
    isCannonIconSquare(square) ||
    isBackstreetIconSquare(square) ||
    isDoorwayIconSquare(square) ||
    isSwitchIconSquare(square) ||
    isSuitYourselfIconSquare(square) ||
    isStockbrokerIconSquare(square)
  );
}

function isMinimapShopLikeSquare(square: SquareInfo): boolean {
  return ["SHOP", "VACANT_PLOT", "VP_CHECKPOINT", "VP_TAX_OFFICE"].includes(square.type);
}

function MinimapSquareIcon({ square, x, y }: { square: SquareInfo; x: number; y: number }) {
  if (isSuitIconSquare(square)) {
    return (
      <g className="minimap-square-icon" transform={`translate(${x} ${y})`} aria-hidden="true">
        <SuitShape suit={square.suit} scale={1.05} />
      </g>
    );
  }
  if (isBankIconSquare(square)) {
    return (
      <g className="minimap-square-icon" transform={`translate(${x} ${y}) scale(0.027) translate(-50 -52)`} aria-hidden="true">
        <BankShape />
      </g>
    );
  }
  if (isStockbrokerIconSquare(square)) {
    return (
      <g className="minimap-square-icon" transform={`translate(${x} ${y}) scale(0.027) translate(-50 -52)`} aria-hidden="true">
        <StockbrokerShape />
      </g>
    );
  }
  if (isVentureIconSquare(square)) {
    return (
      <g className="minimap-square-icon" transform={`translate(${x} ${y}) scale(0.026) translate(-50 -51)`} aria-hidden="true">
        <VentureShape />
      </g>
    );
  }
  if (isBoonIconSquare(square)) {
    return (
      <g className="minimap-square-icon" transform={`translate(${x} ${y}) scale(0.027) translate(-50 -50)`} aria-hidden="true">
        <BoonShape />
      </g>
    );
  }
  if (isBoomIconSquare(square)) {
    return (
      <g className="minimap-square-icon" transform={`translate(${x} ${y}) scale(0.0255) translate(-50 -50)`} aria-hidden="true">
        <BoomShape />
      </g>
    );
  }
  if (isTakeABreakIconSquare(square)) {
    return (
      <g className="minimap-square-icon" transform={`translate(${x} ${y}) scale(0.027) translate(-50 -50)`} aria-hidden="true">
        <TakeABreakShape />
      </g>
    );
  }
  if (isRollOnIconSquare(square)) {
    return (
      <g className="minimap-square-icon" transform={`translate(${x} ${y}) scale(0.024) translate(-50 -52)`} aria-hidden="true">
        <RollOnShape />
      </g>
    );
  }
  if (isCannonIconSquare(square)) {
    return (
      <g className="minimap-square-icon" transform={`translate(${x} ${y}) scale(0.024) translate(-60 -50)`} aria-hidden="true">
        <CannonShape />
      </g>
    );
  }
  if (isArcadeIconSquare(square)) {
    return (
      <g className="minimap-square-icon" transform={`translate(${x} ${y}) scale(0.027) translate(-50 -50)`} aria-hidden="true">
        <ArcadeShape />
      </g>
    );
  }
  if (isBackstreetIconSquare(square)) {
    return (
      <g className="minimap-square-icon" transform={`translate(${x} ${y}) scale(0.022)`} aria-hidden="true">
        <BackstreetShape color={getBackstreetColor(square)} />
      </g>
    );
  }
  if (isDoorwayIconSquare(square)) {
    return (
      <g className="minimap-square-icon" transform={`translate(${x} ${y}) scale(0.026) translate(-50 -50)`} aria-hidden="true">
        <DoorwayShape color={getDoorwayColor(square)} />
      </g>
    );
  }
  if (isSwitchIconSquare(square)) {
    return (
      <g className="minimap-square-icon" transform={`translate(${x} ${y}) scale(0.03) translate(-50 -50)`} aria-hidden="true">
        <SwitchShape />
      </g>
    );
  }
  if (isSuitYourselfIconSquare(square)) {
    return (
      <g className="minimap-square-icon" transform={`translate(${x} ${y}) scale(0.034) translate(-50 -50)`} aria-hidden="true">
        <SuitYourselfShape />
      </g>
    );
  }
  return null;
}

function rentMultiplier(numOwned: number, numTotal: number): number {
  if (numOwned <= 0) {
    return 0;
  }
  return RENT_MULTIPLIERS[`${numOwned}:${numTotal}`] ?? 1;
}

function countDistrictShops(state: GameState, districtId: number): number {
  return state.board.squares.filter(
    (square) => square.type === "SHOP" && square.property_district === districtId,
  ).length;
}

function countOwnedDistrictShops(state: GameState, districtId: number, ownerId: number): number {
  return state.board.squares.filter(
    (square) =>
      square.type === "SHOP" &&
      square.property_district === districtId &&
      square.property_owner === ownerId,
  ).length;
}

function currentShopRent(state: GameState, square: SquareInfo): number {
  if (square.property_owner === null) {
    return square.shop_base_rent ?? 0;
  }
  if (
    square.shop_base_rent === null ||
    square.shop_base_value === null ||
    square.shop_current_value === null ||
    square.property_district === null
  ) {
    return 0;
  }

  const numTotal = countDistrictShops(state, square.property_district);
  const numOwned = countOwnedDistrictShops(state, square.property_district, square.property_owner);
  const multiplier = rentMultiplier(numOwned, numTotal);
  return Math.floor(
    (multiplier * square.shop_base_rent * (2 * square.shop_current_value - square.shop_base_value)) /
      square.shop_base_value,
  );
}

function remainingShopCapital(state: GameState, square: SquareInfo): number {
  if (
    square.property_owner === null ||
    square.shop_base_value === null ||
    square.shop_current_value === null ||
    square.property_district === null
  ) {
    return 0;
  }
  const numTotal = countDistrictShops(state, square.property_district);
  const numOwned = countOwnedDistrictShops(
    state,
    square.property_district,
    square.property_owner,
  );
  const multiplier = MAX_CAP_MULTIPLIERS[`${numOwned}:${numTotal}`] ?? 1;
  return Math.max(0, Math.floor(multiplier * square.shop_base_value - square.shop_current_value));
}

function rawGold(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return String(Math.round(value));
}

function ShopTile({
  square,
  state,
  x,
  y,
  closedTurns,
}: {
  square: SquareInfo;
  state: GameState;
  x: number;
  y: number;
  closedTurns: number | null;
}) {
  const value = square.shop_current_value ?? square.shop_base_value;
  const rent = currentShopRent(state, square);

  if (square.property_owner === null) {
    return (
      <g className="shop-tile shop-tile-unowned" aria-hidden="true">
        <text className="shop-tile-price" x={x} y={y}>
          {rawGold(value)}G
        </text>
      </g>
    );
  }

  const left = x - BOARD_TILE_RADIUS + BOARD_TILE_STROKE_INSET;
  const right = x + BOARD_TILE_RADIUS - BOARD_TILE_STROKE_INSET;
  const top = y + 0.35;
  const bottom = y + BOARD_TILE_RADIUS - BOARD_TILE_STROKE_INSET;
  const topRadius = 0.18;
  const bottomRadius = 0.32;
  const rentBarPath = [
    `M ${left + topRadius} ${top}`,
    `Q ${left} ${top} ${left} ${top + topRadius}`,
    `L ${left} ${bottom - bottomRadius}`,
    `Q ${left} ${bottom} ${left + bottomRadius} ${bottom}`,
    `L ${right - bottomRadius} ${bottom}`,
    `Q ${right} ${bottom} ${right} ${bottom - bottomRadius}`,
    `L ${right} ${top + topRadius}`,
    `Q ${right} ${top} ${right - topRadius} ${top}`,
    "Z",
  ].join(" ");

  return (
    <g className="shop-tile shop-tile-owned" aria-hidden="true">
      {closedTurns !== null && (
        <g className="closed-shop-indicator">
          <g transform={`translate(${x - 0.42} ${y - 0.72}) scale(0.014) translate(-50 -50)`}>
            <TakeABreakShape />
          </g>
          <text className="closed-shop-turn-count" x={x + 0.56} y={y - 0.86}>
            {closedTurns}
          </text>
          <text className="closed-shop-turn-label" x={x + 0.56} y={y - 0.28}>
            {closedTurns === 1 ? "TURN" : "TURNS"}
          </text>
        </g>
      )}
      <path className="shop-tile-rent-bar" d={rentBarPath} />
      <text
        className={`shop-tile-price shop-tile-rent ${closedTurns === null ? "" : "is-closed"}`}
        x={x}
        y={y + 1.17}
      >
        {rawGold(rent)}G
      </text>
    </g>
  );
}

function getSuitColor(suit: string | null): string {
  if (!suit) {
    return "#f7f7f2";
  }
  return SUIT_COLORS[suit] ?? "#f7f7f2";
}

function suitLabel(suit: string | null): string {
  if (!suit) {
    return "SPADE";
  }
  return readableType(suit).toUpperCase();
}

function SuitShape({
  suit,
  scale = 1,
  fill,
}: {
  suit: string | null;
  scale?: number;
  fill?: string;
}) {
  const shapeFill = fill ?? getSuitColor(suit);
  const normalized = suit ?? "SPADE";

  return (
    <g transform={`scale(${scale})`}>
      {normalized === "HEART" && (
        <path
          className="suit-icon-shape"
          d="M0 1.12 C-0.22 0.8 -1.3 0.22 -1.3 -0.48 C-1.3 -0.94 -0.96 -1.18 -0.58 -1.18 C-0.32 -1.18 -0.12 -1.02 0 -0.82 C0.12 -1.02 0.32 -1.18 0.58 -1.18 C0.96 -1.18 1.3 -0.94 1.3 -0.48 C1.3 0.22 0.22 0.8 0 1.12 Z"
          fill={shapeFill}
        />
      )}
      {normalized === "DIAMOND" && (
        <path className="suit-icon-shape" d="M0 -1.22 L1.02 0 L0 1.22 L-1.02 0 Z" fill={shapeFill} />
      )}
      {normalized === "CLUB" && (
        <path
          className="suit-icon-shape"
          d="M0 -1.16 C0.34 -1.16 0.57 -0.88 0.53 -0.54 C0.51 -0.4 0.45 -0.28 0.35 -0.18 C0.48 -0.28 0.62 -0.33 0.76 -0.29 C1.04 -0.21 1.2 0.09 1.1 0.39 C1 0.69 0.7 0.83 0.46 0.68 C0.38 0.62 0.32 0.55 0.28 0.46 C0.28 0.81 0.46 1.04 0.74 1.13 H-0.74 C-0.46 1.04 -0.28 0.81 -0.28 0.46 C-0.32 0.55 -0.38 0.62 -0.46 0.68 C-0.7 0.83 -1 0.69 -1.1 0.39 C-1.2 0.09 -1.04 -0.21 -0.76 -0.29 C-0.62 -0.33 -0.48 -0.28 -0.35 -0.18 C-0.45 -0.28 -0.51 -0.4 -0.53 -0.54 C-0.57 -0.88 -0.34 -1.16 0 -1.16 Z"
          fill={shapeFill}
        />
      )}
      {normalized !== "HEART" && normalized !== "DIAMOND" && normalized !== "CLUB" && (
        <path
          className="suit-icon-shape"
          d="M0 -1.22 C-0.82 -0.54 -1.16 -0.08 -1.02 0.38 C-0.9 0.78 -0.48 0.94 -0.14 0.62 C-0.18 0.88 -0.42 1.06 -0.72 1.12 H0.72 C0.42 1.06 0.18 0.88 0.14 0.62 C0.48 0.94 0.9 0.78 1.02 0.38 C1.16 -0.08 0.82 -0.54 0 -1.22 Z"
          fill={shapeFill}
        />
      )}
    </g>
  );
}

function SquareIconLabel({
  className = "",
  label,
  x,
  y,
}: {
  className?: string;
  label: string;
  x: number;
  y: number;
}) {
  return (
    <text className={`square-icon-label ${className}`.trim()} x={x} y={y - 1.22}>
      {label}
    </text>
  );
}

function SuitIcon({
  suit,
  squareType,
  x,
  y,
}: {
  suit: string | null;
  squareType: string;
  x: number;
  y: number;
}) {
  const isChangeOfSuit = squareType === "CHANGE_OF_SUIT";

  return (
    <g className={`suit-icon ${isChangeOfSuit ? "change-of-suit" : "standard-suit"}`} aria-hidden="true">
      <SquareIconLabel label={suitLabel(suit)} x={x} y={y} />
      <g transform={`translate(${x} ${y + (isChangeOfSuit ? -0.08 : 0.28)})`}>
        <SuitShape suit={suit} scale={isChangeOfSuit ? 0.62 : 0.72} />
      </g>
      {isChangeOfSuit && (
        <g className="suit-mini-row" transform={`translate(${x} ${y + 1.15})`}>
          {SUIT_ORDER.map((miniSuit, index) => (
            <g key={miniSuit} transform={`translate(${(index - 1.5) * 0.5} 0)`}>
              <SuitShape suit={miniSuit} scale={0.15} />
            </g>
          ))}
        </g>
      )}
    </g>
  );
}

function BankShape({ fill = "#ffd166" }: { fill?: string }) {
  return (
    <g className="bank-icon-shape" fill={fill}>
      <path d="M8 35 50 8l42 27v7H8z" />
      <rect x="13" y="46" width="74" height="7" rx="2" />
      <rect x="18" y="55" width="11" height="27" rx="2" />
      <rect x="36" y="55" width="10" height="27" rx="2" />
      <rect x="54" y="55" width="10" height="27" rx="2" />
      <rect x="71" y="55" width="11" height="27" rx="2" />
      <rect x="11" y="84" width="78" height="6" rx="2" />
      <rect x="6" y="92" width="88" height="5" rx="2.5" />
    </g>
  );
}

function BankIcon({ x, y }: { x: number; y: number }) {
  return (
    <g className="bank-icon" aria-hidden="true">
      <SquareIconLabel label="BANK" x={x} y={y} />
      <g transform={`translate(${x} ${y + 0.35}) scale(0.0235) translate(-50 -52.5)`}>
        <BankShape />
      </g>
    </g>
  );
}

function StockbrokerShape({ fill = STOCKBROKER_ICON_COLOR }: { fill?: string }) {
  return (
    <g className="stockbroker-icon-shape">
      <path fill={fill} d="M5 38 50 9l45 29v7H5zM8 49h84v10H8zM8 86h84v6H8zM3 95h94v5H3z" />
      <path fill={fill} d="M13 58h9v28h-9zM26 58h9v28h-9zM39 58h9v28h-9zM52 58h9v28h-9zM65 58h9v28h-9zM78 58h9v28h-9z" />
      <path fill="#080a0e" d="m31 38 10-8 8 4 13-12 10 6-3 5-7-4-12 12-9-5-6 6z" />
    </g>
  );
}

function StockbrokerIcon({ x, y }: { x: number; y: number }) {
  return (
    <g className="stockbroker-icon" aria-hidden="true">
      <SquareIconLabel className="stockbroker-icon-label" label="STOCKBROKER" x={x} y={y} />
      <g transform={`translate(${x} ${y + 0.38}) scale(0.0235) translate(-50 -52)`}>
        <StockbrokerShape />
      </g>
    </g>
  );
}

function VentureShape({ fill = "#ff6aae" }: { fill?: string }) {
  return (
    <g className="venture-icon-shape" color={fill}>
      <path
        fill="none"
        stroke="currentColor"
        strokeWidth="17"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M25 30C25 18 35 11 50 11 65 11 75 19 75 31c0 12-9 17-18 22-7 4-10 9-10 15"
      />
      <circle fill="currentColor" cx="47" cy="92" r="8" />
    </g>
  );
}

function VentureIcon({ x, y }: { x: number; y: number }) {
  return (
    <g className="venture-icon" aria-hidden="true">
      <SquareIconLabel label="VENTURE" x={x} y={y} />
      <g transform={`translate(${x} ${y + 0.34}) scale(0.02025) translate(-50 -51)`}>
        <VentureShape />
      </g>
    </g>
  );
}

const REGULAR_STAR_CENTER = 50;
const REGULAR_STAR_OUTER_RADIUS = 44;
const REGULAR_STAR_INNER_RADIUS =
  REGULAR_STAR_OUTER_RADIUS * (Math.sin(Math.PI / 10) / Math.sin((3 * Math.PI) / 10));
const REGULAR_STAR_POINTS = Array.from({ length: 10 }, (_, index) => {
  const angle = -Math.PI / 2 + index * (Math.PI / 5);
  const radius = index % 2 === 0 ? REGULAR_STAR_OUTER_RADIUS : REGULAR_STAR_INNER_RADIUS;
  const x = REGULAR_STAR_CENTER + radius * Math.cos(angle);
  const y = REGULAR_STAR_CENTER + radius * Math.sin(angle);
  return `${x},${y}`;
}).join(" ");

function BoonShape({ fill = BOON_ICON_COLOR }: { fill?: string }) {
  return (
    <polygon
      fill={fill}
      points={REGULAR_STAR_POINTS}
    />
  );
}

function BoonIcon({ x, y }: { x: number; y: number }) {
  return (
    <g className="boon-icon" aria-hidden="true">
      <SquareIconLabel label="BOON" x={x} y={y} />
      <g transform={`translate(${x} ${y + 0.42}) scale(0.024) translate(-50 -46.5)`}>
        <BoonShape />
      </g>
    </g>
  );
}

function BoomShape() {
  return (
    <g className="boom-icon-shape">
      <g transform="rotate(180 50 50)">
        <BoonShape fill={BOOM_ICON_COLOR} />
      </g>
      <BoonShape />
    </g>
  );
}

function BoomIcon({ x, y }: { x: number; y: number }) {
  return (
    <g className="boom-icon" aria-hidden="true">
      <SquareIconLabel label="BOOM" x={x} y={y} />
      <g transform={`translate(${x} ${y + 0.42}) scale(0.023) translate(-50 -50)`}>
        <BoomShape />
      </g>
    </g>
  );
}

function TakeABreakShape({ fill = TAKE_A_BREAK_ICON_COLOR }: { fill?: string }) {
  return (
    <path
      fill={fill}
      d="M65 8A42 42 0 1 0 92 75A34 34 0 0 1 65 8Z"
    />
  );
}

function TakeABreakIcon({ x, y }: { x: number; y: number }) {
  return (
    <g className="take-a-break-icon" aria-hidden="true">
      <SquareIconLabel className="take-a-break-icon-label" label="TAKE A BREAK" x={x} y={y} />
      <g transform={`translate(${x} ${y + 0.44}) scale(0.024) translate(-50 -50)`}>
        <TakeABreakShape />
      </g>
    </g>
  );
}

function RollOnShape() {
  return (
    <g className="roll-on-icon-shape">
      <polygon points="50,6 90,29 50,52 10,29" fill="#f7f7f2" />
      <polygon points="10,29 50,52 50,98 10,75" fill="#d5d9da" />
      <polygon points="50,52 90,29 90,75 50,98" fill="#b8bec0" />
      <g fill="#080a0e">
        <g transform="matrix(40 23 -40 23 50 6)">
          <circle cx=".5" cy=".5" r=".082" />
        </g>
        <g transform="matrix(40 23 0 46 10 29)">
          <circle cx=".28" cy=".25" r=".075" />
          <circle cx=".72" cy=".75" r=".075" />
        </g>
        <g transform="matrix(40 -23 0 46 50 52)">
          <circle cx=".25" cy=".24" r=".075" />
          <circle cx=".5" cy=".5" r=".075" />
          <circle cx=".75" cy=".76" r=".075" />
        </g>
      </g>
      <path
        d="M50 6 90 29v46L50 98 10 75V29L50 6Z M10 29l40 23 40-23M50 52v46"
        fill="none"
        stroke="#080a0e"
        strokeWidth="3.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </g>
  );
}

function RollOnIcon({ x, y }: { x: number; y: number }) {
  return (
    <g className="roll-on-icon" aria-hidden="true">
      <SquareIconLabel label="ROLL ON" x={x} y={y} />
      <g transform={`translate(${x} ${y + 0.4}) scale(0.022) translate(-50 -52)`}>
        <RollOnShape />
      </g>
    </g>
  );
}

function CannonShape() {
  return (
    <g className="cannon-icon-shape">
      <g transform="rotate(-15 60 38)">
        <rect x="22" y="26" width="70" height="25" rx="12" fill="#62ad68" />
        <rect x="86" y="23" width="12" height="31" rx="4" fill="#c9ced0" />
      </g>
      <path d="M43 54h39l10 20H33Z" fill="#aeb5b7" />
      <circle cx="42" cy="76" r="13" fill="#f2c94c" />
      <circle cx="83" cy="76" r="13" fill="#f2c94c" />
      <circle cx="42" cy="76" r="5" fill="#080a0e" />
      <circle cx="83" cy="76" r="5" fill="#080a0e" />
    </g>
  );
}

function CannonIcon({ x, y }: { x: number; y: number }) {
  return (
    <g className="cannon-icon" aria-hidden="true">
      <SquareIconLabel label="CANNON" x={x} y={y} />
      <g transform={`translate(${x} ${y + 0.43}) scale(0.022) translate(-60 -50)`}>
        <CannonShape />
      </g>
    </g>
  );
}

function DottedFireworkShape({ color }: { color: string }) {
  return (
    <g color={color}>
      <g fill="currentColor">
        <circle r="8" />
        <circle cx="0" cy="-40" r="5" />
        <circle cx="28" cy="-28" r="5" />
        <circle cx="40" cy="0" r="5" />
        <circle cx="28" cy="28" r="5" />
        <circle cx="0" cy="40" r="5" />
        <circle cx="-28" cy="28" r="5" />
        <circle cx="-40" cy="0" r="5" />
        <circle cx="-28" cy="-28" r="5" />
      </g>
      <g fill="none" stroke="currentColor" strokeWidth="5" strokeLinecap="round">
        <path d="M0-24V-15M17-17l-7 7M24 0h-9M17 17l-7-7M0 24v-9M-17 17l7-7M-24 0h9M-17-17l7 7" />
      </g>
    </g>
  );
}

function ArcadeShape() {
  return (
    <g className="arcade-icon-shape">
      <g transform="translate(27 47) scale(0.58)">
        <DottedFireworkShape color="#58c8ff" />
      </g>
      <g transform="translate(67 63) scale(0.52)">
        <DottedFireworkShape color="#ff5aa5" />
      </g>
      <g transform="translate(80 29) scale(0.33)">
        <DottedFireworkShape color="#ffb703" />
      </g>
    </g>
  );
}

function ArcadeIcon({ x, y }: { x: number; y: number }) {
  return (
    <g className="arcade-icon" aria-hidden="true">
      <SquareIconLabel label="ARCADE" x={x} y={y} />
      <g transform={`translate(${x} ${y + 0.43}) scale(0.026) translate(-50 -50)`}>
        <ArcadeShape />
      </g>
    </g>
  );
}

function BackstreetArm() {
  return <path d="M8 2C18 5 29 3 38-4 44-9 48-16 49-24" />;
}

function BackstreetShape({ color }: { color: string }) {
  return (
    <g
      className="backstreet-icon-shape"
      fill="none"
      stroke={color}
      strokeWidth="8.5"
      strokeLinecap="round"
    >
      {Array.from({ length: 8 }, (_, index) => (
        <g key={index} transform={`rotate(${index * 45})`}>
          <BackstreetArm />
        </g>
      ))}
    </g>
  );
}

function BackstreetIcon({ square, x, y }: { square: SquareInfo; x: number; y: number }) {
  return (
    <g className="backstreet-icon" aria-hidden="true">
      <SquareIconLabel className="backstreet-icon-label" label="BACKSTREET" x={x} y={y} />
      <g transform={`translate(${x} ${y + 0.36}) scale(0.01935)`}>
        <BackstreetShape color={getBackstreetColor(square)} />
      </g>
    </g>
  );
}

function DoorwayShape({ color }: { color: string }) {
  return (
    <g className="doorway-icon-shape">
      <path
        d="M19 92V54C19 35 31 20 50 9C69 20 81 35 81 54V92Z"
        fill="none"
        stroke="#f7f7f2"
        strokeWidth="7"
        strokeLinecap="round"
        strokeLinejoin="miter"
      />
      <g transform="translate(50 41) scale(0.15)">
        <BackstreetShape color={color} />
      </g>
      <g transform="translate(37 68) scale(0.15)">
        <BackstreetShape color={color} />
      </g>
      <g transform="translate(63 68) scale(0.15)">
        <BackstreetShape color={color} />
      </g>
    </g>
  );
}

function DoorwayIcon({ square, x, y }: { square: SquareInfo; x: number; y: number }) {
  return (
    <g className="doorway-icon" aria-hidden="true">
      <SquareIconLabel label="DOORWAY" x={x} y={y} />
      <g transform={`translate(${x} ${y + 0.36}) scale(0.024) translate(-50 -50)`}>
        <DoorwayShape color={getDoorwayColor(square)} />
      </g>
    </g>
  );
}

function SwitchShape() {
  return (
    <g className="switch-icon-shape">
      <circle cx="50" cy="50" r="42" fill="#aeb5b7" />
      <circle cx="50" cy="50" r="36.75" fill="#080a0e" />
      <circle cx="50" cy="50" r="34.6" fill="#ffd84d" />
    </g>
  );
}

function SwitchIcon({ x, y }: { x: number; y: number }) {
  return (
    <g className="switch-icon" aria-hidden="true">
      <SquareIconLabel label="SWITCH" x={x} y={y} />
      <g transform={`translate(${x} ${y + 0.42}) scale(0.0255) translate(-50 -50)`}>
        <SwitchShape />
      </g>
    </g>
  );
}

function SuitYourselfShape() {
  const panels = [
    { suit: "SPADE", x: 20, y: 20, offsetX: -1.5, offsetY: -1.5 },
    { suit: "HEART", x: 52, y: 20, offsetX: 1.5, offsetY: -1.5 },
    { suit: "DIAMOND", x: 20, y: 52, offsetX: -1.5, offsetY: 1.5 },
    { suit: "CLUB", x: 52, y: 52, offsetX: 1.5, offsetY: 1.5 },
  ] as const;

  return (
    <g className="suit-yourself-icon-shape" transform="rotate(-12 50 50)">
      <rect x="16" y="16" width="68" height="68" rx="5" fill="#f7f7f2" />
      {panels.map(({ suit, x, y, offsetX, offsetY }) => (
        <g key={suit} transform={`translate(${offsetX} ${offsetY})`}>
          <rect x={x} y={y} width="28" height="28" rx="2" fill={SUIT_COLORS[suit]} />
          <g transform={`translate(${x + 14} ${y + 14})`}>
            <SuitShape suit={suit} scale={6.7} fill="#f7f7f2" />
          </g>
        </g>
      ))}
    </g>
  );
}

function SuitYourselfIcon({ x, y }: { x: number; y: number }) {
  return (
    <g className="suit-yourself-icon" aria-hidden="true">
      <SquareIconLabel className="suit-yourself-icon-label" label="SUIT YOURSELF" x={x} y={y} />
      <g transform={`translate(${x} ${y + 0.42}) scale(0.029) translate(-50 -50)`}>
        <SuitYourselfShape />
      </g>
    </g>
  );
}

function HudSuitSlots({ player }: { player: PlayerState }) {
  const ownedSuits = SUIT_ORDER.filter((suit) => (player.suits[suit] ?? 0) > 0);
  const accessibleLabel = SUIT_ORDER.map(
    (suit) => `${readableType(suit)} ${ownedSuits.includes(suit) ? "owned" : "missing"}`,
  ).join(", ");

  return (
    <span className="hud-suit-slots" role="img" aria-label={accessibleLabel}>
      {SUIT_ORDER.map((suit) => {
        const isOwned = ownedSuits.includes(suit);
        return (
          <span
            key={suit}
            className={`hud-suit-slot ${isOwned ? "owned" : "missing"}`}
            title={`${readableType(suit)}: ${isOwned ? "owned" : "missing"}`}
            aria-hidden="true"
          >
            <svg viewBox="-1.5 -1.5 3 3" focusable="false">
              <SuitShape suit={suit} scale={0.92} fill={isOwned ? undefined : "#f7f7f2"} />
            </svg>
          </span>
        );
      })}
    </span>
  );
}

function labelForSquare(square: SquareInfo): string {
  if (square.type === "BANK") {
    return "Bank";
  }
  if (square.type === "SHOP") {
    return square.property_owner === null ? "Shop" : `P${square.property_owner}`;
  }
  if (square.type === "VP_CHECKPOINT") {
    return "Toll";
  }
  if (square.type === "VP_TAX_OFFICE") {
    return "Tax";
  }
  if (square.suit) {
    return square.suit;
  }
  return readableType(square.type);
}

function valueLabelForSquare(square: SquareInfo, state: GameState): string | null {
  if (square.type === "VP_CHECKPOINT") {
    return shortGold(square.checkpoint_toll);
  }
  if (square.type === "VP_TAX_OFFICE") {
    const currentPlayer = state.players[state.current_player_index];
    if (!currentPlayer) {
      return null;
    }
    return shortGold(Math.floor(netWorth(state, currentPlayer) * 0.04));
  }
  if (square.shop_current_value !== null) {
    return shortGold(square.shop_current_value);
  }
  return null;
}

function displayTypeForSquare(square: SquareInfo): string {
  if (square.type === "SUIT" && square.suit) {
    return `${readableType(square.suit)} Suit`;
  }
  if (square.type === "CHANGE_OF_SUIT" && square.suit) {
    return `Change of Suit (${readableType(square.suit)})`;
  }
  if (square.type === "VP_CHECKPOINT") {
    return "Checkpoint";
  }
  if (square.type === "VP_TAX_OFFICE") {
    return "Tax Office";
  }
  return readableType(square.type);
}

function PlayerCommissionIndicators({
  statuses,
}: {
  statuses: PlayerState["statuses"];
}) {
  const indicators = commissionStatusIndicators(statuses);
  if (indicators.length === 0) {
    return null;
  }

  const accessibleLabel = indicators
    .map(
      (indicator) =>
        `${indicator.kind === "boom" ? "Boom" : "Boon"} ${indicator.percent}% commission, ${indicator.remainingTurns} ${indicator.remainingTurns === 1 ? "turn" : "turns"} remaining`,
    )
    .join("; ");

  return (
    <span className="player-commission-indicators" role="img" aria-label={accessibleLabel}>
      {indicators.map((indicator, index) => (
        <svg
          key={`${indicator.kind}:${indicator.remainingTurns}:${index}`}
          className={`player-commission-star is-${indicator.kind}`}
          viewBox="0 0 100 100"
          aria-hidden="true"
          focusable="false"
        >
          <BoonShape fill={commissionIndicatorColor(indicator.kind)} />
        </svg>
      ))}
    </span>
  );
}

function PlayerHud({
  state,
  assignedPlayerId,
  cashDeltas,
}: {
  state: GameState | null;
  assignedPlayerId: number | null;
  cashDeltas: ReadonlyMap<number, number> | null;
}) {
  if (!state) {
    return null;
  }

  return (
    <section
      className={`player-hud ${cashDeltas ? "has-cash-deltas" : ""}`}
      aria-label="Players"
    >
      {state.players.map((player) => {
        const isCurrent = state.players[state.current_player_index]?.player_id === player.player_id;
        const isAssigned = assignedPlayerId === player.player_id;
        const cashDelta = cashDeltas?.get(player.player_id) ?? 0;
        return (
          <article
            key={player.player_id}
            className={`hud-player-card ${isCurrent ? "current" : ""} ${isAssigned ? "assigned" : ""}`}
            style={{ borderColor: getPlayerColor(player.player_id) }}
          >
            {cashDelta !== 0 && (
              <span
                className={`hud-cash-delta ${cashDelta > 0 ? "is-positive" : "is-negative"}`}
                aria-label={`Ready cash ${cashDelta > 0 ? "increases" : "decreases"} by ${formatGold(Math.abs(cashDelta))}`}
              >
                {cashDelta > 0 ? "+" : "−"}{formatGold(Math.abs(cashDelta))}
              </span>
            )}
            <div className="hud-player-title">
              <span className="player-token large" style={{ backgroundColor: getPlayerColor(player.player_id) }}>
                {player.player_id}
              </span>
              <div>
                <div className="hud-player-name-row">
                  <strong>Player {player.player_id}</strong>
                  <PlayerCommissionIndicators statuses={player.statuses} />
                </div>
                <span>{isAssigned ? "You" : isCurrent ? "Turn" : `Square #${player.position}`}</span>
              </div>
            </div>
            <dl>
              <div>
                <dt>Cash</dt>
                <dd>{formatGold(player.ready_cash)}</dd>
              </div>
              <div>
                <dt>Worth</dt>
                <dd>{formatGold(netWorth(state, player))}</dd>
              </div>
              <div>
                <dt>Level</dt>
                <dd>{player.level}</dd>
              </div>
              <div>
                <dt>Suits</dt>
                <dd className="hud-suit-value">
                  <HudSuitSlots player={player} />
                </dd>
              </div>
            </dl>
          </article>
        );
      })}
    </section>
  );
}

function TurnPanel({
  state,
  assignedPlayer,
  currentPlayer,
  request,
  dice,
  latestEvent,
  gameOverWinner,
}: {
  state: GameState;
  assignedPlayer: PlayerState | null;
  currentPlayer: PlayerState | null;
  request: InputRequest | null;
  dice: { value: number; remaining: number } | null;
  latestEvent: string | null;
  gameOverWinner: number | null | undefined;
}) {
  const isYourPrompt = request && assignedPlayer?.player_id === request.player_id;
  const turnLabel = currentPlayer ? `Player ${currentPlayer.player_id}` : "Player -";
  return (
    <section className="panel turn-panel">
      <header className="panel-header">
        <div>
          <p className="eyebrow">Now</p>
          <h2>{gameOverWinner !== undefined ? "Game Finished" : isYourPrompt ? "Your Decision" : `${turnLabel}'s Turn`}</h2>
        </div>
        {dice && <div className="dice-chip">d{dice.value} / {dice.remaining}</div>}
      </header>
      <dl className="turn-stats">
        <div>
          <dt>Your Cash</dt>
          <dd>{assignedPlayer ? formatGold(assignedPlayer.ready_cash) : "-"}</dd>
        </div>
        <div>
          <dt>Your Worth</dt>
          <dd>{assignedPlayer ? formatGold(netWorth(state, assignedPlayer)) : "-"}</dd>
        </div>
        <div>
          <dt>Target</dt>
          <dd>{formatGold(state.board.target_networth)}</dd>
        </div>
        <div>
          <dt>Prompt</dt>
          <dd>{request ? readableType(request.type) : "-"}</dd>
        </div>
      </dl>
      <div className="event-ticker">
        <span>Latest</span>
        <p>{latestEvent ?? "The match is ready."}</p>
      </div>
    </section>
  );
}

function SquarePanel({ square, state }: { square: SquareInfo | null; state: GameState | null }) {
  return (
    <section className="panel square-panel">
      <header className="panel-header">
        <h2>Square</h2>
      </header>
      {!square ? (
        <p className="muted">Select a board square for details.</p>
      ) : (
        <dl className="detail-list">
          <div>
            <dt>ID</dt>
            <dd>#{square.id}</dd>
          </div>
          <div>
            <dt>Type</dt>
            <dd>{displayTypeForSquare(square)}</dd>
          </div>
          <div>
            <dt>Owner</dt>
            <dd>{square.property_owner === null ? "-" : `Player ${square.property_owner}`}</dd>
          </div>
          <div>
            <dt>District</dt>
            <dd>{square.property_district ?? "-"}</dd>
          </div>
          <div>
            <dt>Value</dt>
            <dd>{formatGold(square.shop_current_value)}</dd>
          </div>
          {square.type === "VP_CHECKPOINT" && (
            <div>
              <dt>Toll</dt>
              <dd>{formatGold(square.checkpoint_toll)}</dd>
            </div>
          )}
          {square.type === "VP_TAX_OFFICE" && (
            <div>
              <dt>Current tax</dt>
              <dd>{state ? valueLabelForSquare(square, state) : "-"}</dd>
            </div>
          )}
          <div>
            <dt>Base rent</dt>
            <dd>{formatGold(square.shop_base_rent)}</dd>
          </div>
          <div>
            <dt>Stock price</dt>
            <dd>
              {state && square.property_district !== null
                ? formatGold(stockPrice(state.stock.stocks[square.property_district]))
                : "-"}
            </dd>
          </div>
        </dl>
      )}
    </section>
  );
}

function LiquidationChoiceWidget({
  request,
  hasStock,
  hasShops,
  onChoose,
}: {
  request: InputRequest;
  hasStock: boolean;
  hasShops: boolean;
  onChoose: (mode: LiquidationAssetMode) => void;
}) {
  const cash = asNumber(request.data.cash);
  return (
    <section className="panel action-panel liquidation-choice-widget" aria-label="Choose an asset to sell">
      <header className="panel-header prompt-header">
        <div>
          <p className="eyebrow">Negative Ready Cash</p>
          <h2>Choose What to Sell</h2>
          <p>
            Ready cash is {formatGold(cash)}. Sell assets until it is nonnegative.
          </p>
        </div>
      </header>
      <div className="liquidation-asset-options">
        <button type="button" disabled={!hasStock} onClick={() => onChoose("stock")}>
          <strong>Sell Stock</strong>
          <span>{hasStock ? "Open the stock exchange" : "No stock available"}</span>
        </button>
        <button type="button" disabled={!hasShops} onClick={() => onChoose("shop")}>
          <strong>Sell a Shop</strong>
          <span>{hasShops ? "Choose a shop on the board" : "No shops available"}</span>
        </button>
      </div>
    </section>
  );
}

function LiquidationShopWidget({
  request,
  choices,
  selectedSquareId,
  responsePending,
  onConfirm,
  onBack,
}: {
  request: InputRequest;
  choices: LiquidationShopChoice[];
  selectedSquareId: number | null;
  responsePending: boolean;
  onConfirm: (squareId: number) => void;
  onBack: () => void;
}) {
  const selected = choices.find((choice) => choice.squareId === selectedSquareId) ?? null;
  return (
    <section
      className={`panel action-panel investment-widget is-selecting liquidation-shop-widget ${responsePending ? "is-resolving" : ""}`}
      aria-label="Choose a shop to sell"
      aria-busy={responsePending}
    >
      <header className="panel-header prompt-header">
        <div>
          <p className="eyebrow">Sell a Shop</p>
          <h2>Choose on the Board</h2>
          <p>
            Shops available for sale remain clear. Click to inspect; double-click to sell.
          </p>
        </div>
      </header>
      {selected ? (
        <div className="investment-selected-shop">
          <span>Selected shop</span>
          <strong>Square #{selected.squareId}</strong>
          <p>Bank sale value: {formatGold(selected.sellValue)}</p>
          <button
            type="button"
            disabled={responsePending}
            onClick={() => onConfirm(selected.squareId)}
          >
            Sell for {formatGold(selected.sellValue)}
          </button>
        </div>
      ) : (
        <p className="investment-selection-hint">Choose one of the clear shops.</p>
      )}
      <button type="button" className="secondary" disabled={responsePending} onClick={onBack}>
        Back to Asset Choice
      </button>
      <small>Ready cash: {formatGold(asNumber(request.data.cash))}</small>
    </section>
  );
}

function VentureGridOverlay({
  request,
  responsePending,
  onSubmit,
}: {
  request: InputRequest;
  responsePending: boolean;
  onSubmit: (value: unknown) => void;
}) {
  const cells = useMemo(() => getVentureCells(request), [request]);
  const [cursor, setCursor] = useState<VentureCursor>(() => findFirstUnclaimedVentureCell(cells));
  const [usingKeyboardNavigation, setUsingKeyboardNavigation] = useState(false);
  const submittedRef = useRef(false);
  const overlayRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    setCursor(findFirstUnclaimedVentureCell(cells));
    setUsingKeyboardNavigation(false);
    submittedRef.current = false;
    window.requestAnimationFrame(() => overlayRef.current?.focus());
  }, [cells]);

  const selectedOwner = cells[cursor[0]]?.[cursor[1]];
  const canClaim = selectedOwner === null && !responsePending && !submittedRef.current;
  const linePreview = useMemo(
    () => getVentureLinePreview(cells, cursor[0], cursor[1], request.player_id),
    [cells, cursor, request.player_id],
  );
  const availableCount = cells.reduce(
    (count, row) => count + row.filter((owner) => owner === null).length,
    0,
  );
  const playerIds = useMemo(() => {
    const ids = new Set<number>([request.player_id]);
    cells.forEach((row) => row.forEach((owner) => owner !== null && ids.add(owner)));
    return [...ids].sort((left, right) => left - right);
  }, [cells, request.player_id]);
  const columnCount = Math.max(1, ...cells.map((row) => row.length));

  function selectCell(row: number, col: number) {
    setUsingKeyboardNavigation(false);
    setCursor([row, col]);
  }

  function claimCell(row: number, col: number) {
    if (cells[row]?.[col] !== null || responsePending || submittedRef.current) {
      return;
    }
    submittedRef.current = true;
    setCursor([row, col]);
    onSubmit([row, col]);
  }

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.altKey || event.ctrlKey || event.metaKey || isTypingTarget(event.target)) {
        return;
      }

      const key = event.key.toLowerCase();
      const movement: Record<string, readonly [number, number]> = {
        w: [-1, 0],
        arrowup: [-1, 0],
        s: [1, 0],
        arrowdown: [1, 0],
        a: [0, -1],
        arrowleft: [0, -1],
        d: [0, 1],
        arrowright: [0, 1],
      };

      if (movement[key]) {
        event.preventDefault();
        event.stopPropagation();
        setUsingKeyboardNavigation(true);
        if (
          document.activeElement instanceof HTMLElement &&
          document.activeElement.closest(".venture-grid-board")
        ) {
          document.activeElement.blur();
        }
        const [rowDelta, colDelta] = movement[key];
        setCursor(([row, col]) => {
          const nextRow = Math.max(0, Math.min(cells.length - 1, row + rowDelta));
          const nextRowWidth = cells[nextRow]?.length ?? 0;
          const nextCol = Math.max(0, Math.min(nextRowWidth - 1, col + colDelta));
          return nextRowWidth > 0 ? [nextRow, nextCol] : [row, col];
        });
        return;
      }

      if ((key === " " || key === "enter") && !event.repeat) {
        event.preventDefault();
        event.stopPropagation();
        claimCell(cursor[0], cursor[1]);
      }
    }

    window.addEventListener("keydown", handleKeyDown, true);
    return () => window.removeEventListener("keydown", handleKeyDown, true);
  }, [cells, cursor, responsePending, onSubmit]);

  return (
    <section
      ref={overlayRef}
      className={`venture-grid-overlay ${usingKeyboardNavigation ? "is-keyboard-navigation" : ""} ${responsePending ? "is-resolving" : ""}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby="venture-grid-title"
      tabIndex={-1}
    >
      <div className="venture-grid-shell">
        <div className="venture-grid-panel">
          <header className="venture-grid-header">
            <div>
              <p className="eyebrow">Venture Card</p>
              <h2 id="venture-grid-title">Claim a Venture Square</h2>
            </div>
            <span className="venture-grid-available">{availableCount} open</span>
          </header>

          {cells.length > 0 ? (
            <div
              className="venture-grid-board"
              style={{ "--venture-grid-size": columnCount } as CSSProperties}
              role="grid"
              aria-label="Shared venture grid"
              onPointerMove={() => setUsingKeyboardNavigation(false)}
            >
              {cells.flatMap((row, rowIndex) =>
                row.map((owner, colIndex) => {
                  const selected = cursor[0] === rowIndex && cursor[1] === colIndex;
                  const coordinate = ventureCoordinateLabel(rowIndex, colIndex);
                  const classes = [
                    "venture-grid-cell",
                    owner === null ? "is-open" : "is-claimed",
                    selected ? "is-selected" : "",
                    linePreview.cells.has(`${rowIndex}:${colIndex}`) ? "is-line-preview" : "",
                  ]
                    .filter(Boolean)
                    .join(" ");
                  const style =
                    owner === null
                      ? undefined
                      : ({ "--venture-owner-color": getPlayerColor(owner) } as CSSProperties);

                  return (
                    <button
                      key={`${rowIndex}:${colIndex}`}
                      type="button"
                      className={classes}
                      style={style}
                      role="gridcell"
                      aria-selected={selected}
                      aria-label={`${coordinate}, ${owner === null ? "unclaimed" : `claimed by Player ${owner}`}`}
                      onClick={() => selectCell(rowIndex, colIndex)}
                      onDoubleClick={(event) => {
                        event.preventDefault();
                        claimCell(rowIndex, colIndex);
                      }}
                    >
                      <span className="venture-cell-coordinate">{coordinate}</span>
                      <span className="venture-cell-owner">{owner === null ? "·" : `P${owner}`}</span>
                    </button>
                  );
                }),
              )}
            </div>
          ) : (
            <p className="venture-grid-empty">No Venture Grid data was provided.</p>
          )}
        </div>

        <aside className="venture-grid-sidebar" aria-label="Venture selection details">
          <div className="venture-selection-card">
            <span>Selected</span>
            <strong>{ventureCoordinateLabel(cursor[0], cursor[1])}</strong>
            <p>
              {selectedOwner === null
                ? linePreview.bonus > 0
                  ? `Completes lines worth ${formatGold(linePreview.bonus)}`
                  : "Unclaimed square"
                : selectedOwner === undefined
                  ? "Unavailable"
                  : `Claimed by Player ${selectedOwner}`}
            </p>
          </div>

          <button
            type="button"
            className="venture-claim-button"
            disabled={!canClaim}
            onClick={() => claimCell(cursor[0], cursor[1])}
          >
            {responsePending || submittedRef.current ? "Claiming..." : "Claim Square"}
          </button>

          <div className="venture-grid-instructions">
            <p><strong>Click</strong> to move the cursor</p>
            <p><strong>Double-click</strong> to claim immediately</p>
            <p><strong>WASD / Arrows</strong> to move</p>
            <p><strong>Space / Enter</strong> to claim</p>
          </div>

          <div className="venture-grid-legend" aria-label="Player colors">
            {playerIds.map((playerId) => (
              <span key={playerId}>
                <i style={{ background: getPlayerColor(playerId) }} />
                Player {playerId}{playerId === request.player_id ? " (you)" : ""}
              </span>
            ))}
          </div>
        </aside>
      </div>
    </section>
  );
}

function StockOverlay({
  request,
  state,
  responsePending,
  onSubmit,
  onBack,
}: {
  request: InputRequest;
  state: GameState;
  responsePending: boolean;
  onSubmit: (value: unknown) => void;
  onBack: (() => void) | null;
}) {
  const mode: StockOverlayMode =
    request.type === "BUY_STOCK"
      ? "buy"
      : request.type === "SELL_STOCK"
        ? "sell"
        : "liquidate";
  const player = state.players.find((candidate) => candidate.player_id === request.player_id) ?? null;
  const liquidationOptions = asRecord(request.data.options);
  const liquidationStocks = asRecord(liquidationOptions.stock);
  const buyStocks = asArray(request.data.stocks).map(asRecord);
  const sellHoldings = asRecord(request.data.holdings);
  const promptPriceByDistrict = new Map<number, number>();
  const maximumByDistrict = new Map<number, number>();
  const cash = asNumber(request.data.cash, player?.ready_cash ?? 0);
  const cashDeficit = asNumber(liquidationOptions.cash_deficit, Math.max(0, -cash));

  if (mode === "buy") {
    buyStocks.forEach((stock) => {
      const districtId = asNumber(stock.district_id, -1);
      const price = asNumber(stock.price);
      if (districtId >= 0) {
        promptPriceByDistrict.set(districtId, price);
        maximumByDistrict.set(districtId, maxBuyQuantity(cash, price));
      }
    });
  } else if (mode === "sell") {
    Object.entries(sellHoldings).forEach(([districtKey, rawHolding]) => {
      const districtId = Number(districtKey);
      const holding = asRecord(rawHolding);
      promptPriceByDistrict.set(districtId, asNumber(holding.price));
      maximumByDistrict.set(districtId, asNumber(holding.quantity));
    });
  } else {
    Object.entries(liquidationStocks).forEach(([districtKey, rawHolding]) => {
      const districtId = Number(districtKey);
      const holding = asRecord(rawHolding);
      promptPriceByDistrict.set(districtId, asNumber(holding.price_per_share));
      maximumByDistrict.set(districtId, asNumber(holding.quantity));
    });
  }

  const districts = [...state.stock.stocks].sort(
    (left, right) => left.district_id - right.district_id,
  );
  const firstDistrictId =
    districts.find((stock) => (maximumByDistrict.get(stock.district_id) ?? 0) > 0)?.district_id ??
    districts[0]?.district_id ??
    0;
  const requestKey = `${request.type}:${request.player_id}:${[...maximumByDistrict.entries()].map(([id, maximum]) => `${id}-${maximum}`).join("|")}`;
  const [selectedDistrictId, setSelectedDistrictId] = useState(firstDistrictId);
  const [quantity, setQuantity] = useState(1);
  const [usingKeyboardNavigation, setUsingKeyboardNavigation] = useState(false);
  const submittedRef = useRef(false);
  const overlayRef = useRef<HTMLElement | null>(null);

  const selectedStock =
    districts.find((stock) => stock.district_id === selectedDistrictId) ?? districts[0] ?? null;
  const selectedPrice = selectedStock
    ? (promptPriceByDistrict.get(selectedStock.district_id) ?? stockPrice(selectedStock))
    : 0;
  const selectedMaximum = selectedStock
    ? (maximumByDistrict.get(selectedStock.district_id) ?? 0)
    : 0;
  const normalizedQuantity = clampStockQuantity(quantity, selectedMaximum);
  const transactionTotal = selectedPrice * normalizedQuantity;
  const cashAfter = mode === "buy" ? cash - transactionTotal : cash + transactionTotal;
  const deficitAfter = Math.max(0, cashDeficit - transactionTotal);
  const selectedProjectedPrice = selectedStock
    ? projectedStockPrice(
        selectedPrice,
        selectedStock.pending_fluctuation ?? 0,
        mode,
        normalizedQuantity,
      )
    : selectedPrice;
  const selectedShops = state.board.squares.filter(
    (square) =>
      square.type === "SHOP" && square.property_district === selectedStock?.district_id,
  );
  const selectedHolding = player?.owned_stock[String(selectedStock?.district_id ?? -1)] ?? 0;
  const canSubmitStock =
    selectedStock !== null &&
    selectedMaximum > 0 &&
    normalizedQuantity > 0 &&
    !responsePending &&
    !submittedRef.current;

  function selectDistrict(districtId: number, inputMode: "pointer" | "keyboard" = "pointer") {
    const stock = districts.find((candidate) => candidate.district_id === districtId);
    if (!stock) {
      return;
    }
    const price = promptPriceByDistrict.get(districtId) ?? stockPrice(stock);
    const maximum = maximumByDistrict.get(districtId) ?? 0;
    setUsingKeyboardNavigation(inputMode === "keyboard");
    setSelectedDistrictId(districtId);
    setQuantity(defaultStockQuantity(mode, maximum, price, cashDeficit));
  }

  function submitStock() {
    if (!canSubmitStock || selectedStock === null) {
      return;
    }
    submittedRef.current = true;
    onSubmit(
      mode === "liquidate"
        ? ["stock", selectedStock.district_id, normalizedQuantity]
        : [selectedStock.district_id, normalizedQuantity],
    );
  }

  function cancel() {
    if (responsePending || submittedRef.current) {
      return;
    }
    if (mode === "liquidate") {
      onBack?.();
      return;
    }
    submittedRef.current = true;
    onSubmit(null);
  }

  useEffect(() => {
    submittedRef.current = false;
    setUsingKeyboardNavigation(false);
    setSelectedDistrictId(firstDistrictId);
    const firstStock = districts.find((stock) => stock.district_id === firstDistrictId);
    const price = firstStock
      ? (promptPriceByDistrict.get(firstDistrictId) ?? stockPrice(firstStock))
      : 0;
    setQuantity(
      defaultStockQuantity(
        mode,
        maximumByDistrict.get(firstDistrictId) ?? 0,
        price,
        cashDeficit,
      ),
    );
    window.requestAnimationFrame(() => overlayRef.current?.focus());
  }, [requestKey]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (
        event.altKey ||
        event.ctrlKey ||
        event.metaKey ||
        responsePending ||
        submittedRef.current ||
        isTypingTarget(event.target)
      ) {
        return;
      }
      const key = event.key.toLowerCase();
      const currentIndex = districts.findIndex(
        (stock) => stock.district_id === selectedDistrictId,
      );
      if (["w", "arrowup", "s", "arrowdown"].includes(key) && districts.length > 0) {
        event.preventDefault();
        event.stopPropagation();
        setUsingKeyboardNavigation(true);
        if (
          document.activeElement instanceof HTMLElement &&
          document.activeElement.closest(".stock-district-table")
        ) {
          document.activeElement.blur();
        }
        const direction = key === "w" || key === "arrowup" ? -1 : 1;
        const nextIndex = (currentIndex + direction + districts.length) % districts.length;
        selectDistrict(districts[nextIndex].district_id, "keyboard");
        return;
      }
      if (["a", "arrowleft", "d", "arrowright"].includes(key)) {
        event.preventDefault();
        event.stopPropagation();
        setUsingKeyboardNavigation(true);
        if (
          document.activeElement instanceof HTMLElement &&
          document.activeElement.closest(".stock-district-table")
        ) {
          document.activeElement.blur();
        }
        const direction = key === "a" || key === "arrowleft" ? -1 : 1;
        setQuantity((current) => clampStockQuantity(current + direction, selectedMaximum));
        return;
      }
      if ((key === "enter" || key === " ") && !event.repeat) {
        event.preventDefault();
        event.stopPropagation();
        submitStock();
        return;
      }
      if (key === "escape" && (mode !== "liquidate" || onBack)) {
        event.preventDefault();
        event.stopPropagation();
        cancel();
      }
    }

    window.addEventListener("keydown", handleKeyDown, true);
    return () => window.removeEventListener("keydown", handleKeyDown, true);
  }, [
    districts,
    mode,
    responsePending,
    selectedDistrictId,
    selectedMaximum,
    normalizedQuantity,
    onBack,
  ]);

  const title = mode === "buy" ? "Buy Stock" : mode === "sell" ? "Sell Stock" : "Raise Cash";
  const instruction =
    mode === "buy"
      ? "Choose a district and purchase amount."
      : mode === "sell"
        ? "Choose a district and the shares to sell."
        : `Choose stock to sell. ${formatGold(cashDeficit)} still needed.`;
  const primaryLabel =
    mode === "buy"
      ? `Buy ${normalizedQuantity}`
      : mode === "sell"
        ? `Sell ${normalizedQuantity}`
        : `Sell ${normalizedQuantity} shares`;

  return (
    <section
      ref={overlayRef}
      className={`stock-overlay stock-mode-${mode} ${usingKeyboardNavigation ? "is-keyboard-navigation" : ""} ${responsePending ? "is-resolving" : ""}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby="stock-overlay-title"
      aria-busy={responsePending}
      tabIndex={-1}
      onPointerMove={() => setUsingKeyboardNavigation(false)}
    >
      <div className="stock-overlay-shell">
        <header className="stock-overlay-header">
          <div>
            <p className="eyebrow">Stock Exchange</p>
            <h2 id="stock-overlay-title">{title}</h2>
            <p>{instruction}</p>
          </div>
          <div className="stock-player-summary">
            <span className="player-token large" style={{ background: getPlayerColor(request.player_id) }}>
              {request.player_id}
            </span>
            <dl>
              <div><dt>Stocks</dt><dd>{Object.values(player?.owned_stock ?? {}).reduce((sum, held) => sum + held, 0)}</dd></div>
              <div><dt>Ready cash</dt><dd>{formatGold(cash)}</dd></div>
            </dl>
          </div>
        </header>

        <div className="stock-overlay-main">
          <div className="stock-market-panel">
            <div
              className="stock-district-table"
              style={{ "--stock-player-count": Math.max(1, state.players.length) } as CSSProperties}
              role="table"
              aria-label="District stock market"
            >
              <div className="stock-district-header" role="row">
                <span>District</span>
                <span>Price</span>
                {state.players.map((marketPlayer) => (
                  <span key={marketPlayer.player_id} style={{ color: getPlayerColor(marketPlayer.player_id) }}>
                    P{marketPlayer.player_id}
                  </span>
                ))}
                <span>Shop value</span>
              </div>
              {districts.map((stock) => {
                const districtId = stock.district_id;
                const maximum = maximumByDistrict.get(districtId) ?? 0;
                const selected = districtId === selectedStock?.district_id;
                const shops = state.board.squares.filter(
                  (square) => square.type === "SHOP" && square.property_district === districtId,
                );
                const shopValue = shops.reduce(
                  (sum, shop) => sum + (shop.shop_current_value ?? shop.shop_base_value ?? 0),
                  0,
                );
                return (
                  <button
                    key={districtId}
                    type="button"
                    className={`stock-district-row ${selected ? "is-selected" : ""} ${maximum <= 0 ? "is-unavailable" : ""}`}
                    style={{ "--district-color": getDistrictColor(districtId) } as CSSProperties}
                    role="row"
                    aria-selected={selected}
                    onClick={() => selectDistrict(districtId)}
                  >
                    <strong>{districtLabel(districtId)}</strong>
                    <span>{formatGold(promptPriceByDistrict.get(districtId) ?? stockPrice(stock))}</span>
                    {state.players.map((marketPlayer) => {
                      const held = marketPlayer.owned_stock[String(districtId)] ?? 0;
                      return <span key={marketPlayer.player_id}>{held > 0 ? held : "—"}</span>;
                    })}
                    <span>{formatGold(shopValue)}</span>
                  </button>
                );
              })}
            </div>

            <section className="stock-shop-section" aria-label="Selected district shops">
              <header>
                <div>
                  <p className="eyebrow">Selected district</p>
                  <h3>{selectedStock ? districtLabel(selectedStock.district_id) : "No district"}</h3>
                </div>
                <span>{selectedShops.length} shops</span>
              </header>
              <div className="stock-shop-strip">
                {selectedShops.map((shop) => {
                  const ownerColor =
                    shop.property_owner === null ? "#70747d" : getPlayerColor(shop.property_owner);
                  return (
                    <article
                      key={shop.id}
                      className="stock-shop-card"
                      style={{ "--shop-owner-color": ownerColor } as CSSProperties}
                    >
                      <div className="stock-shop-owner">
                        <span>Shop #{shop.id}</span>
                        <strong>{shop.property_owner === null ? "Unowned" : `Player ${shop.property_owner}`}</strong>
                      </div>
                      <dl>
                        <div><dt>Value</dt><dd>{formatGold(shop.shop_current_value ?? shop.shop_base_value)}</dd></div>
                        <div><dt>Rent</dt><dd>{formatGold(currentShopRent(state, shop))}</dd></div>
                        <div>
                          <dt>Max capital</dt>
                          <dd>
                            {shop.property_owner === null
                              ? "—"
                              : formatGold(remainingShopCapital(state, shop))}
                          </dd>
                        </div>
                      </dl>
                    </article>
                  );
                })}
                {selectedShops.length === 0 && <p className="muted">This district has no shops.</p>}
              </div>
            </section>
          </div>

          <aside className="stock-transaction-panel">
            <div className="stock-selection-summary">
              <span>Selected</span>
              <strong>{selectedStock ? districtLabel(selectedStock.district_id) : "—"}</strong>
              <p>{formatGold(selectedPrice)} per share · You hold {selectedHolding}</p>
            </div>

            <div className="stock-quantity-control">
              <span>{mode === "buy" ? "Purchase amount" : "Sale amount"}</span>
              <div>
                <button
                  type="button"
                  aria-label="Decrease stock quantity"
                  disabled={selectedMaximum <= 0}
                  onClick={() => setQuantity((current) => clampStockQuantity(current - 1, selectedMaximum))}
                >−</button>
                <input
                  aria-label="Stock quantity"
                  type="number"
                  min={selectedMaximum > 0 ? 1 : 0}
                  max={selectedMaximum}
                  step="1"
                  value={normalizedQuantity}
                  onChange={(event) =>
                    setQuantity(clampStockQuantity(Number(event.target.value), selectedMaximum))
                  }
                />
                <button
                  type="button"
                  aria-label="Increase stock quantity"
                  disabled={selectedMaximum <= 0}
                  onClick={() => setQuantity((current) => clampStockQuantity(current + 1, selectedMaximum))}
                >+</button>
              </div>
              <button
                type="button"
                className="secondary stock-max-button"
                disabled={selectedMaximum <= 0}
                onClick={() => setQuantity(selectedMaximum)}
              >
                Max {selectedMaximum}
              </button>
            </div>

            <dl className="stock-transaction-math">
              <div>
                <dt>Stock price</dt>
                <dd>
                  {formatGold(selectedPrice)}
                  {selectedProjectedPrice !== selectedPrice && (
                    <> → <strong>{formatGold(selectedProjectedPrice)}</strong></>
                  )}
                </dd>
              </div>
              <div><dt>{mode === "buy" ? "Purchase total" : "Sale proceeds"}</dt><dd>{formatGold(transactionTotal)}</dd></div>
              <div><dt>Ready cash</dt><dd>{formatGold(cash)} → <strong>{formatGold(cashAfter)}</strong></dd></div>
              {mode === "liquidate" && (
                <div className={deficitAfter === 0 ? "is-covered" : "is-deficit"}>
                  <dt>Still needed</dt><dd>{formatGold(deficitAfter)}</dd>
                </div>
              )}
            </dl>

            <button
              type="button"
              className="stock-confirm-button"
              disabled={!canSubmitStock}
              onClick={submitStock}
            >
              {responsePending || submittedRef.current ? "Resolving..." : primaryLabel}
            </button>
            {(mode !== "liquidate" || onBack) && (
              <button type="button" className="secondary" onClick={cancel}>
                {mode === "liquidate" ? "Back to Asset Choice" : "Cancel"}
              </button>
            )}
            <div className="stock-keyboard-help">
              <p><strong>W/S or ↑/↓</strong> district</p>
              <p><strong>A/D or ←/→</strong> quantity</p>
              <p>
                <strong>Enter</strong> confirm
                {mode === "liquidate" ? " · Esc back" : " · Esc cancel"}
              </p>
            </div>
          </aside>
        </div>
      </div>
    </section>
  );
}

function VentureCardReveal({
  presentation,
  assignedPlayerId,
  onContinue,
}: {
  presentation: PresentationState;
  assignedPlayerId: number | null;
  onContinue: () => void;
}) {
  const name = String(presentation.data.name ?? "Venture Card");
  const description = String(presentation.data.description ?? "");
  const isOwner = !presentation.requiresAcknowledgment || presentation.playerId === assignedPlayerId;
  const canContinue = isOwner && !presentation.acknowledgmentPending;

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (
        ["Escape", "Enter", " "].includes(event.key) ||
        WASD_KEYS.has(event.key.toLowerCase()) ||
        event.key.startsWith("Arrow")
      ) {
        event.preventDefault();
        event.stopPropagation();
        if (canContinue && ["Enter", " "].includes(event.key)) {
          onContinue();
        }
      }
    }
    window.addEventListener("keydown", handleKeyDown, true);
    return () => window.removeEventListener("keydown", handleKeyDown, true);
  }, [canContinue, onContinue]);

  return (
    <div className="venture-card-reveal" role="dialog" aria-modal="true" aria-labelledby="venture-card-title">
      <button
        type="button"
        className="venture-card"
        autoFocus={isOwner}
        disabled={!canContinue}
        onClick={onContinue}
        aria-label={isOwner ? "Continue from Venture Card" : `Waiting for Player ${presentation.playerId}`}
      >
        <span className="venture-card-kicker">Venture Card</span>
        <strong id="venture-card-title">{name}</strong>
        {description && <span className="venture-card-description">{description}</span>}
        <small>
          {presentation.acknowledgmentPending
            ? "Continuing..."
            : isOwner
              ? "Click or press Enter to continue"
              : `Waiting for Player ${presentation.playerId}...`}
        </small>
      </button>
    </div>
  );
}

function GenericPresentation({
  presentation,
  assignedPlayerId,
  onContinue,
}: {
  presentation: PresentationState;
  assignedPlayerId: number | null;
  onContinue: () => void;
}) {
  const isOwner = !presentation.requiresAcknowledgment || presentation.playerId === assignedPlayerId;
  const canContinue = isOwner && !presentation.acknowledgmentPending;

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      event.preventDefault();
      event.stopPropagation();
      if (canContinue && ["Enter", " "].includes(event.key)) {
        onContinue();
      }
    }
    window.addEventListener("keydown", handleKeyDown, true);
    return () => window.removeEventListener("keydown", handleKeyDown, true);
  }, [canContinue, onContinue]);

  return (
    <div className="venture-card-reveal" role="dialog" aria-modal="true" aria-labelledby="presentation-title">
      <button
        type="button"
        className="venture-card"
        autoFocus={isOwner}
        disabled={!canContinue}
        onClick={onContinue}
      >
        <span className="venture-card-kicker">Game Event</span>
        <strong id="presentation-title">{readableType(presentation.type)}</strong>
        <small>
          {presentation.acknowledgmentPending
            ? "Continuing..."
            : isOwner
              ? "Click or press Enter to continue"
              : `Waiting for Player ${presentation.playerId}...`}
        </small>
      </button>
    </div>
  );
}

function RentPaymentOverlay({
  presentation,
  state,
  assignedPlayerId,
  onContinue,
}: {
  presentation: PresentationState;
  state: GameState | null;
  assignedPlayerId: number | null;
  onContinue: () => void;
}) {
  const payment = rentPaymentFacts(presentation.data, presentation.playerId);
  const dividendByPlayer = new Map(
    payment.dividends.map((payout) => [payout.playerId, payout.amount]),
  );
  const hasDividends = payment.dividends.length > 0;
  const players = state?.players ?? [];
  const isOwner = !presentation.requiresAcknowledgment || presentation.playerId === assignedPlayerId;
  const canContinue = isOwner && !presentation.acknowledgmentPending;
  const districtName =
    payment.districtId === null ? "District" : districtLabel(payment.districtId);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (
        ["Escape", "Enter", " "].includes(event.key) ||
        WASD_KEYS.has(event.key.toLowerCase()) ||
        event.key.startsWith("Arrow")
      ) {
        event.preventDefault();
        event.stopPropagation();
        if (canContinue && ["Enter", " "].includes(event.key)) {
          onContinue();
        }
      }
    }
    window.addEventListener("keydown", handleKeyDown, true);
    return () => window.removeEventListener("keydown", handleKeyDown, true);
  }, [canContinue, onContinue]);

  return (
    <div
      className="payment-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="payment-title"
    >
      <section className="payment-stack">
        <div className="payment-card">
          <div className="payment-route" id="payment-title">
            <span className="payment-player" style={{ "--payment-player-color": getPlayerColor(payment.payerId) } as CSSProperties}>
              <span className="payment-player-token">{payment.payerId}</span>
              <strong>Player {payment.payerId}</strong>
            </span>
            <span className="payment-arrow" aria-label="pays">→</span>
            <span className="payment-player" style={{ "--payment-player-color": getPlayerColor(payment.ownerId) } as CSSProperties}>
              <span className="payment-player-token">{payment.ownerId}</span>
              <strong>Player {payment.ownerId}</strong>
            </span>
          </div>
          <strong className="payment-amount">{formatGold(payment.rentAmount)}</strong>
          <span className="payment-context">Shop payment · Square #{payment.squareId}</span>
        </div>

        {hasDividends && (
          <section className="payment-dividends" aria-labelledby="payment-dividend-title">
            <header>
              <span>Stock dividends</span>
              <h3 id="payment-dividend-title">{districtName}</h3>
            </header>
            <div className="payment-dividend-grid">
              {players.map((player) => {
                const amount = dividendByPlayer.get(player.player_id) ?? 0;
                return (
                  <article
                    key={player.player_id}
                    className={amount > 0 ? "has-payout" : ""}
                    style={{ "--payment-player-color": getPlayerColor(player.player_id) } as CSSProperties}
                  >
                    <span className="payment-player-token">{player.player_id}</span>
                    <span>Player {player.player_id}</span>
                    <strong>{amount > 0 ? "+" : ""}{formatGold(amount)}</strong>
                  </article>
                );
              })}
            </div>
          </section>
        )}

        <button
          type="button"
          className="payment-continue"
          autoFocus={isOwner}
          disabled={!canContinue}
          onClick={onContinue}
        >
          {presentation.acknowledgmentPending
            ? "Continuing..."
            : isOwner
              ? "Continue"
              : `Waiting for Player ${presentation.playerId}...`}
        </button>
      </section>
    </div>
  );
}

function StockPriceChangeOverlay({
  presentation,
  state,
  assignedPlayerId,
  onContinue,
}: {
  presentation: PresentationState;
  state: GameState | null;
  assignedPlayerId: number | null;
  onContinue: () => void;
}) {
  const change = stockPriceChangeFacts(presentation.data, presentation.playerId);
  const impactByPlayer = new Map(
    change.holdings.map((holding) => [holding.playerId, holding]),
  );
  const playerIds =
    state?.players.map((player) => player.player_id) ??
    change.holdings.map((holding) => holding.playerId);
  const isRise = change.delta > 0;
  const isOwner = !presentation.requiresAcknowledgment || presentation.playerId === assignedPlayerId;
  const canContinue = isOwner && !presentation.acknowledgmentPending;
  const title = `${districtLabel(change.districtId)} stock price ${isRise ? "rises" : "falls"}!`;

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (
        ["Escape", "Enter", " "].includes(event.key) ||
        WASD_KEYS.has(event.key.toLowerCase()) ||
        event.key.startsWith("Arrow")
      ) {
        event.preventDefault();
        event.stopPropagation();
        if (canContinue && ["Enter", " "].includes(event.key)) {
          onContinue();
        }
      }
    }
    window.addEventListener("keydown", handleKeyDown, true);
    return () => window.removeEventListener("keydown", handleKeyDown, true);
  }, [canContinue, onContinue]);

  return (
    <div
      className={`stock-price-change-overlay ${isRise ? "is-rise" : "is-fall"}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby="stock-price-change-title"
    >
      <section className="stock-price-change-card">
        <header>
          <span>Market update</span>
          <h2 id="stock-price-change-title">{title}</h2>
        </header>

        <div className="stock-price-transition" aria-label={`${change.oldPrice}G to ${change.newPrice}G`}>
          <strong>{formatGold(change.oldPrice)}</strong>
          <span aria-hidden="true">→</span>
          <strong>{formatGold(change.newPrice)}</strong>
        </div>

        <div className="stock-price-impact-grid" aria-label="Player stock value changes">
          {playerIds.map((playerId) => {
            const holding = impactByPlayer.get(playerId) ?? {
              playerId,
              quantity: 0,
              valueChange: 0,
            };
            const sign = holding.valueChange > 0 ? "+" : "";
            return (
              <article
                key={playerId}
                className={holding.valueChange !== 0 ? "has-impact" : ""}
                style={{ "--stock-player-color": getPlayerColor(playerId) } as CSSProperties}
              >
                <span className="stock-price-player-token">{playerId}</span>
                <span>Player {playerId}</span>
                <strong>{holding.quantity}</strong>
                <small>shares</small>
                <em>{sign}{formatGold(holding.valueChange)}</em>
              </article>
            );
          })}
        </div>

        <button
          type="button"
          className="stock-price-continue"
          autoFocus={isOwner}
          disabled={!canContinue}
          onClick={onContinue}
        >
          {presentation.acknowledgmentPending
            ? "Continuing..."
            : isOwner
              ? "Continue"
              : `Waiting for Player ${presentation.playerId}...`}
        </button>
      </section>
    </div>
  );
}

function PromotionCeremony({
  presentation,
  assignedPlayerId,
  onContinue,
}: {
  presentation: PresentationState;
  assignedPlayerId: number | null;
  onContinue: () => void;
}) {
  const playerId = asNumber(presentation.data.player_id, presentation.playerId);
  const previousLevel = asNumber(presentation.data.previous_level, 1);
  const nextLevel = asNumber(presentation.data.next_level, previousLevel + 1);
  const totalBonus = asNumber(presentation.data.total_bonus);
  const readyCashAfter = asNumber(presentation.data.ready_cash_after);
  const isAssignedPlayer = playerId === assignedPlayerId;
  const isOwner = !presentation.requiresAcknowledgment || presentation.playerId === assignedPlayerId;
  const canContinue = isOwner && !presentation.acknowledgmentPending;
  const salaryRows = [
    ["Base salary", asNumber(presentation.data.base_bonus)],
    ["Level bonus", asNumber(presentation.data.level_bonus)],
    ["Shop value bonus", asNumber(presentation.data.shop_bonus)],
    ["Comeback bonus", asNumber(presentation.data.comeback_bonus)],
  ] as const;

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (
        ["Escape", "Enter", " "].includes(event.key) ||
        WASD_KEYS.has(event.key.toLowerCase()) ||
        event.key.startsWith("Arrow")
      ) {
        event.preventDefault();
        event.stopPropagation();
        if (canContinue && ["Enter", " "].includes(event.key)) {
          onContinue();
        }
      }
    }
    window.addEventListener("keydown", handleKeyDown, true);
    return () => window.removeEventListener("keydown", handleKeyDown, true);
  }, [canContinue, onContinue]);

  return (
    <div
      className="promotion-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="promotion-title"
      style={{ "--promotion-player-color": getPlayerColor(playerId) } as CSSProperties}
    >
      <section className="promotion-ceremony">
        <header className="promotion-header">
          <span className="promotion-eyebrow">Bank Promotion</span>
          <h2 id="promotion-title">{isAssignedPlayer ? "You Promoted!" : `Player ${playerId} Promoted!`}</h2>
        </header>

        <div className="promotion-suits" role="img" aria-label="Spade, Heart, Diamond, and Club complete">
          {SUIT_ORDER.map((suit, index) => (
            <span
              key={suit}
              className="promotion-suit"
              style={
                {
                  "--promotion-suit-color": getSuitColor(suit),
                  "--promotion-suit-delay": `${index * 90}ms`,
                } as CSSProperties
              }
              aria-hidden="true"
            >
              <svg viewBox="-1.5 -1.5 3 3" focusable="false">
                <SuitShape suit={suit} scale={0.92} />
              </svg>
              <small>{readableType(suit)}</small>
            </span>
          ))}
        </div>

        <div className="promotion-details">
          <section className="promotion-level-card" aria-label={`Level ${previousLevel} to Level ${nextLevel}`}>
            <span className="promotion-detail-label">Level Up</span>
            <div className="promotion-level-transition">
              <span className="promotion-level previous">
                <small>Level</small>
                <strong>{previousLevel}</strong>
              </span>
              <span className="promotion-level-arrow" aria-hidden="true">→</span>
              <span className="promotion-level next">
                <small>Level</small>
                <strong>{nextLevel}</strong>
              </span>
            </div>
          </section>

          <section className="promotion-salary-card" aria-label="Promotion salary breakdown">
            <span className="promotion-detail-label">Salary Breakdown</span>
            <dl>
              {salaryRows.map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>+{formatGold(value)}</dd>
                </div>
              ))}
              <div className="promotion-salary-total">
                <dt>Total promotion salary</dt>
                <dd>+{formatGold(totalBonus)}</dd>
              </div>
            </dl>
            <p>Ready cash after promotion: <strong>{formatGold(readyCashAfter)}</strong></p>
          </section>
        </div>

        <button
          type="button"
          className="promotion-continue"
          autoFocus={isOwner}
          disabled={!canContinue}
          onClick={onContinue}
        >
          {presentation.acknowledgmentPending
            ? "Continuing..."
            : isOwner
              ? "Continue"
              : `Waiting for Player ${presentation.playerId}...`}
        </button>
      </section>
    </div>
  );
}

function SquareChoiceWidget({
  request,
  selectedSquareId,
  eligibleSquareIds,
  responsePending,
  onConfirmSquare,
  onCancel,
}: {
  request: InputRequest;
  selectedSquareId: number | null;
  eligibleSquareIds: ReadonlySet<number>;
  responsePending: boolean;
  onConfirmSquare: (squareId: number) => void;
  onCancel: (() => void) | null;
}) {
  const selectedIsEligible =
    selectedSquareId !== null && eligibleSquareIds.has(selectedSquareId);
  const isAuction = request.type === "CHOOSE_SHOP_AUCTION";
  const prompt = String(
    request.data.prompt ??
      (isAuction
        ? "Choose one of your shops to put up for auction."
        : "Choose a square on the board."),
  );

  return (
    <section
      className={`panel action-panel investment-widget is-selecting ${responsePending ? "is-resolving" : ""}`}
      aria-label={isAuction ? "Choose a shop to auction" : "Choose a square"}
      aria-busy={responsePending}
    >
      <header className="panel-header prompt-header">
        <div>
          <p className="eyebrow">{isAuction ? "Auction" : "Choose Square"}</p>
          <h2>{isAuction ? "Choose a Shop" : "Choose a Square"}</h2>
          <p>{prompt} Click to inspect; double-click to choose.</p>
        </div>
      </header>
      {selectedSquareId !== null && selectedIsEligible ? (
        <div className="investment-selected-shop">
          <span>Selected</span>
          <strong>{isAuction ? "Shop" : "Square"} #{selectedSquareId}</strong>
          <button
            type="button"
            disabled={responsePending}
            onClick={() => onConfirmSquare(selectedSquareId)}
          >
            Choose This {isAuction ? "Shop" : "Square"}
          </button>
        </div>
      ) : (
        <p className="investment-selection-hint">Pan and zoom freely, then choose an untinted square.</p>
      )}
      {onCancel && (
        <button type="button" className="secondary investment-cancel" disabled={responsePending} onClick={onCancel}>
          Cancel
        </button>
      )}
    </section>
  );
}

function InvestmentWidget({
  request,
  choices,
  selectedSquareId,
  confirmedSquareId,
  responsePending,
  onConfirmSquare,
  onChangeSquare,
  onSubmit,
}: {
  request: InputRequest;
  choices: InvestmentSquareChoice[];
  selectedSquareId: number | null;
  confirmedSquareId: number | null;
  responsePending: boolean;
  onConfirmSquare: (squareId: number) => void;
  onChangeSquare: () => void;
  onSubmit: (value: unknown) => void;
}) {
  const selectedChoice =
    choices.find((choice) => choice.squareId === selectedSquareId) ?? null;
  const confirmedChoice =
    choices.find((choice) => choice.squareId === confirmedSquareId) ?? null;
  const readyCash = asNumber(request.data.cash);
  const spendableCash = asNumber(request.data.spendable_cash, readyCash);
  const maximum = confirmedChoice ? maximumInvestment(confirmedChoice, spendableCash) : 0;
  const [amount, setAmount] = useState("1");
  const normalizedAmount = clampInvestmentAmount(Number(amount), maximum);

  useEffect(() => {
    if (confirmedChoice) {
      setAmount(String(maximumInvestment(confirmedChoice, spendableCash)));
    }
  }, [confirmedChoice?.squareId, maximum, spendableCash]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape" || responsePending || isTypingTarget(event.target)) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      if (confirmedChoice) {
        onChangeSquare();
      } else {
        onSubmit(null);
      }
    }
    window.addEventListener("keydown", handleKeyDown, true);
    return () => window.removeEventListener("keydown", handleKeyDown, true);
  }, [confirmedChoice, onChangeSquare, onSubmit, responsePending]);

  function submitInvestment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!confirmedChoice || normalizedAmount <= 0 || responsePending) {
      return;
    }
    onSubmit([confirmedChoice.squareId, normalizedAmount]);
  }

  if (!confirmedChoice) {
    return (
      <section className="panel action-panel investment-widget is-selecting" aria-label="Choose a shop to invest in">
        <header className="panel-header prompt-header">
          <div>
            <p className="eyebrow">Invest</p>
            <h2>Choose a Shop</h2>
            <p>Your available shops stay clear; other squares are tinted. Click to inspect; double-click to choose.</p>
          </div>
        </header>
        {selectedChoice ? (
          <div className="investment-selected-shop">
            <span>Selected shop</span>
            <strong>Shop #{selectedChoice.squareId}</strong>
            <small>
              {formatGold(selectedChoice.currentValue)} value · {formatGold(selectedChoice.maxCapital)} max capital
            </small>
            <button type="button" onClick={() => onConfirmSquare(selectedChoice.squareId)}>
              Choose This Shop
            </button>
          </div>
        ) : (
          <p className="investment-selection-hint">Pan and zoom freely, then choose one of the untinted shops.</p>
        )}
        <button type="button" className="secondary investment-cancel" onClick={() => onSubmit(null)}>
          Skip Investment
        </button>
      </section>
    );
  }

  return (
    <section
      className={`panel action-panel investment-widget is-amount ${responsePending ? "is-resolving" : ""}`}
      aria-busy={responsePending}
    >
      <header className="panel-header prompt-header">
        <div>
          <p className="eyebrow">Invest · Shop #{confirmedChoice.squareId}</p>
          <h2>Choose Amount</h2>
          <p>Enter how much capital to add to this shop.</p>
        </div>
      </header>
      <form onSubmit={submitInvestment}>
        <dl className="investment-summary">
          <div>
            <dt>Shop value</dt>
            <dd>
              {formatGold(confirmedChoice.currentValue)} → {formatGold(confirmedChoice.currentValue + normalizedAmount)}
            </dd>
          </div>
          <div>
            <dt>Available</dt>
            <dd>{formatGold(maximum)}</dd>
          </div>
          <div>
            <dt>Ready cash</dt>
            <dd>{formatGold(readyCash)}</dd>
          </div>
        </dl>
        <label className="investment-amount-input">
          Investment amount
          <span>
            <button
              type="button"
              aria-label="Decrease investment"
              disabled={responsePending || normalizedAmount <= 1}
              onClick={() => setAmount(String(clampInvestmentAmount(normalizedAmount - 1, maximum)))}
            >
              −
            </button>
            <input
              type="number"
              min="1"
              max={maximum}
              step="1"
              value={normalizedAmount}
              disabled={responsePending}
              onChange={(event) => setAmount(event.target.value)}
              autoFocus
            />
            <button
              type="button"
              aria-label="Increase investment"
              disabled={responsePending || normalizedAmount >= maximum}
              onClick={() => setAmount(String(clampInvestmentAmount(normalizedAmount + 1, maximum)))}
            >
              +
            </button>
          </span>
        </label>
        <div className="investment-amount-actions">
          <button type="button" className="secondary" disabled={responsePending} onClick={() => setAmount(String(maximum))}>
            Max {formatGold(maximum)}
          </button>
          <button type="submit" disabled={responsePending || normalizedAmount <= 0}>
            {responsePending ? "Investing..." : `Invest ${formatGold(normalizedAmount)}`}
          </button>
        </div>
        <div className="investment-secondary-actions">
          <button type="button" className="secondary" disabled={responsePending} onClick={onChangeSquare}>
            Change Shop
          </button>
          <button type="button" className="secondary" disabled={responsePending} onClick={() => onSubmit(null)}>
            Cancel
          </button>
        </div>
      </form>
    </section>
  );
}

function BuyShopOfferWidget({
  request,
  choices,
  selectedSquareId,
  confirmedSquareId,
  responsePending,
  onConfirmSquare,
  onChangeSquare,
  onSubmit,
}: {
  request: InputRequest;
  choices: BuyShopChoice[];
  selectedSquareId: number | null;
  confirmedSquareId: number | null;
  responsePending: boolean;
  onConfirmSquare: (squareId: number) => void;
  onChangeSquare: () => void;
  onSubmit: (value: unknown) => void;
}) {
  const selectedChoice = choices.find((choice) => choice.squareId === selectedSquareId) ?? null;
  const confirmedChoice = choices.find((choice) => choice.squareId === confirmedSquareId) ?? null;
  const readyCash = asNumber(request.data.cash);
  const [amount, setAmount] = useState("1");
  const normalizedAmount = normalizePositiveOfferPrice(Number(amount));

  useEffect(() => {
    if (confirmedChoice) {
      setAmount(String(Math.max(1, confirmedChoice.currentValue)));
    }
  }, [confirmedChoice?.squareId, confirmedChoice?.currentValue]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape" || responsePending || isTypingTarget(event.target)) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      if (confirmedChoice) {
        onChangeSquare();
      } else {
        onSubmit(null);
      }
    }
    window.addEventListener("keydown", handleKeyDown, true);
    return () => window.removeEventListener("keydown", handleKeyDown, true);
  }, [confirmedChoice, onChangeSquare, onSubmit, responsePending]);

  function submitOffer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!confirmedChoice || normalizedAmount <= 0 || responsePending) {
      return;
    }
    onSubmit([confirmedChoice.ownerId, confirmedChoice.squareId, normalizedAmount]);
  }

  if (!confirmedChoice) {
    return (
      <section className="panel action-panel investment-widget shop-negotiation-widget is-selecting" aria-label="Choose a property to buy">
        <header className="panel-header prompt-header">
          <div>
            <p className="eyebrow">Buy Shop</p>
            <h2>Choose a Property</h2>
            <p>Opponent-owned properties stay clear. Click to inspect; double-click to make an offer.</p>
          </div>
        </header>
        {selectedChoice ? (
          <div className="investment-selected-shop">
            <span>Owned by Player {selectedChoice.ownerId}</span>
            <strong>{readableType(selectedChoice.squareType)} #{selectedChoice.squareId}</strong>
            <small>
              {formatGold(selectedChoice.currentValue)} current value
              {selectedChoice.districtId === null ? "" : ` · District ${selectedChoice.districtId}`}
            </small>
            <button
              type="button"
              disabled={responsePending}
              onClick={() => onConfirmSquare(selectedChoice.squareId)}
            >
              Make an Offer
            </button>
          </div>
        ) : (
          <p className="investment-selection-hint">
            {choices.length > 0
              ? "Pan and zoom freely, then choose one of the untinted properties."
              : "No opponent-owned properties are available to buy."}
          </p>
        )}
        <button
          type="button"
          className="secondary investment-cancel"
          disabled={responsePending}
          onClick={() => onSubmit(null)}
        >
          Cancel
        </button>
      </section>
    );
  }

  return (
    <section
      className={`panel action-panel investment-widget shop-negotiation-widget is-amount ${responsePending ? "is-resolving" : ""}`}
      aria-busy={responsePending}
    >
      <header className="panel-header prompt-header">
        <div>
          <p className="eyebrow">Buy · {readableType(confirmedChoice.squareType)} #{confirmedChoice.squareId}</p>
          <h2>Make Your Offer</h2>
          <p>Player {confirmedChoice.ownerId} can accept, counter, or reject this amount.</p>
        </div>
      </header>
      <form onSubmit={submitOffer}>
        <dl className="investment-summary">
          <div>
            <dt>Current value</dt>
            <dd>{formatGold(confirmedChoice.currentValue)}</dd>
          </div>
          <div>
            <dt>Ready cash</dt>
            <dd>{formatGold(readyCash)}</dd>
          </div>
          <div>
            <dt>Cash if accepted</dt>
            <dd>{formatGold(readyCash - normalizedAmount)}</dd>
          </div>
        </dl>
        <label className="investment-amount-input">
          Offer price
          <span>
            <button
              type="button"
              aria-label="Decrease offer"
              disabled={responsePending || normalizedAmount <= 1}
              onClick={() => setAmount(String(Math.max(1, normalizedAmount - 1)))}
            >
              −
            </button>
            <input
              type="number"
              min="1"
              step="1"
              value={amount}
              disabled={responsePending}
              onChange={(event) => setAmount(event.target.value)}
              autoFocus
            />
            <button
              type="button"
              aria-label="Increase offer"
              disabled={responsePending}
              onClick={() => setAmount(String(Math.max(1, normalizedAmount + 1)))}
            >
              +
            </button>
          </span>
        </label>
        <div className="investment-amount-actions">
          <button
            type="button"
            className="secondary"
            disabled={responsePending}
            onClick={() => setAmount(String(Math.max(1, confirmedChoice.currentValue)))}
          >
            Match {formatGold(confirmedChoice.currentValue)}
          </button>
          <button type="submit" disabled={responsePending || normalizedAmount <= 0}>
            {responsePending ? "Sending..." : `Offer ${formatGold(normalizedAmount)}`}
          </button>
        </div>
        <div className="investment-secondary-actions">
          <button type="button" className="secondary" disabled={responsePending} onClick={onChangeSquare}>
            Change Property
          </button>
          <button type="button" className="secondary" disabled={responsePending} onClick={() => onSubmit(null)}>
            Cancel
          </button>
        </div>
      </form>
    </section>
  );
}

function SellShopOfferWidget({
  request,
  choices,
  targets,
  selectedSquareId,
  confirmedSquareId,
  responsePending,
  onConfirmSquare,
  onChangeSquare,
  onSubmit,
}: {
  request: InputRequest;
  choices: BuyShopChoice[];
  targets: NegotiationPlayerChoice[];
  selectedSquareId: number | null;
  confirmedSquareId: number | null;
  responsePending: boolean;
  onConfirmSquare: (squareId: number) => void;
  onChangeSquare: () => void;
  onSubmit: (value: unknown) => void;
}) {
  const selectedChoice = choices.find((choice) => choice.squareId === selectedSquareId) ?? null;
  const confirmedChoice = choices.find((choice) => choice.squareId === confirmedSquareId) ?? null;
  const [targetPlayerId, setTargetPlayerId] = useState<number | null>(null);
  const targetPlayer = targets.find((player) => player.playerId === targetPlayerId) ?? null;
  const [amount, setAmount] = useState("1");
  const normalizedAmount = normalizePositiveOfferPrice(Number(amount));

  useEffect(() => {
    setTargetPlayerId(null);
    if (confirmedChoice) {
      setAmount(String(Math.max(1, confirmedChoice.currentValue)));
    }
  }, [confirmedChoice?.squareId, confirmedChoice?.currentValue]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape" || responsePending || isTypingTarget(event.target)) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      if (!confirmedChoice) {
        onSubmit(null);
      } else if (targetPlayer) {
        setTargetPlayerId(null);
      } else {
        onChangeSquare();
      }
    }
    window.addEventListener("keydown", handleKeyDown, true);
    return () => window.removeEventListener("keydown", handleKeyDown, true);
  }, [confirmedChoice, onChangeSquare, onSubmit, responsePending, targetPlayer]);

  if (!confirmedChoice) {
    return (
      <section className="panel action-panel investment-widget sell-shop-widget is-selecting" aria-label="Choose a property to sell">
        <header className="panel-header prompt-header">
          <div>
            <p className="eyebrow">Sell Shop · 1 of 3</p>
            <h2>Choose Your Property</h2>
            <p>Your sellable properties stay clear. Click to inspect; double-click to continue.</p>
          </div>
        </header>
        {selectedChoice ? (
          <div className="investment-selected-shop">
            <span>Selected property</span>
            <strong>{readableType(selectedChoice.squareType)} #{selectedChoice.squareId}</strong>
            <small>
              {formatGold(selectedChoice.currentValue)} current value
              {selectedChoice.districtId === null ? "" : ` · District ${selectedChoice.districtId}`}
            </small>
            <button
              type="button"
              disabled={responsePending}
              onClick={() => onConfirmSquare(selectedChoice.squareId)}
            >
              Sell This Property
            </button>
          </div>
        ) : (
          <p className="investment-selection-hint">
            {choices.length > 0
              ? "Pan and zoom freely, then choose one of the untinted properties."
              : "You have no properties available to sell."}
          </p>
        )}
        <button
          type="button"
          className="secondary investment-cancel"
          disabled={responsePending}
          onClick={() => onSubmit(null)}
        >
          Cancel
        </button>
      </section>
    );
  }

  if (!targetPlayer) {
    return (
      <section className="panel action-panel investment-widget sell-shop-widget" aria-label="Choose a buyer">
        <header className="panel-header prompt-header">
          <div>
            <p className="eyebrow">Sell Shop · 2 of 3</p>
            <h2>Choose a Buyer</h2>
            <p>Choose who should receive {readableType(confirmedChoice.squareType)} #{confirmedChoice.squareId} if they accept.</p>
          </div>
        </header>
        <div className="investment-selected-shop sell-shop-summary">
          <span>Property for sale</span>
          <strong>{readableType(confirmedChoice.squareType)} #{confirmedChoice.squareId}</strong>
          <small>{formatGold(confirmedChoice.currentValue)} current value</small>
        </div>
        <div className="trade-player-options">
          {targets.map((player) => (
            <button
              key={player.playerId}
              type="button"
              className="secondary"
              disabled={responsePending}
              onClick={() => setTargetPlayerId(player.playerId)}
            >
              <strong>Player {player.playerId}</strong>
              <span>{formatGold(player.readyCash)} ready cash</span>
            </button>
          ))}
        </div>
        {targets.length === 0 && (
          <p className="investment-selection-hint">No other non-bankrupt player is available.</p>
        )}
        <div className="investment-secondary-actions">
          <button type="button" className="secondary" disabled={responsePending} onClick={onChangeSquare}>
            Change Property
          </button>
          <button type="button" className="secondary" disabled={responsePending} onClick={() => onSubmit(null)}>
            Cancel
          </button>
        </div>
      </section>
    );
  }

  function submitSaleOffer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!confirmedChoice || !targetPlayer || normalizedAmount <= 0 || responsePending) {
      return;
    }
    onSubmit([targetPlayer.playerId, confirmedChoice.squareId, normalizedAmount]);
  }

  return (
    <section
      className={`panel action-panel investment-widget sell-shop-widget is-amount ${responsePending ? "is-resolving" : ""}`}
      aria-busy={responsePending}
    >
      <header className="panel-header prompt-header">
        <div>
          <p className="eyebrow">Sell Shop · 3 of 3</p>
          <h2>Set Asking Price</h2>
          <p>Player {targetPlayer.playerId} can accept, counter, or reject these terms.</p>
        </div>
      </header>
      <form onSubmit={submitSaleOffer}>
        <dl className="investment-summary">
          <div>
            <dt>Property</dt>
            <dd>{readableType(confirmedChoice.squareType)} #{confirmedChoice.squareId}</dd>
          </div>
          <div>
            <dt>Current value</dt>
            <dd>{formatGold(confirmedChoice.currentValue)}</dd>
          </div>
          <div>
            <dt>Buyer ready cash</dt>
            <dd>{formatGold(targetPlayer.readyCash)}</dd>
          </div>
          <div>
            <dt>Buyer cash if accepted</dt>
            <dd>{formatGold(targetPlayer.readyCash - normalizedAmount)}</dd>
          </div>
        </dl>
        <label className="investment-amount-input">
          Asking price
          <span>
            <button
              type="button"
              aria-label="Decrease asking price"
              disabled={responsePending || normalizedAmount <= 1}
              onClick={() => setAmount(String(Math.max(1, normalizedAmount - 1)))}
            >
              −
            </button>
            <input
              type="number"
              min="1"
              step="1"
              value={amount}
              disabled={responsePending}
              onChange={(event) => setAmount(event.target.value)}
              autoFocus
            />
            <button
              type="button"
              aria-label="Increase asking price"
              disabled={responsePending}
              onClick={() => setAmount(String(Math.max(1, normalizedAmount + 1)))}
            >
              +
            </button>
          </span>
        </label>
        <div className="investment-amount-actions">
          <button
            type="button"
            className="secondary"
            disabled={responsePending}
            onClick={() => setAmount(String(Math.max(1, confirmedChoice.currentValue)))}
          >
            Match {formatGold(confirmedChoice.currentValue)}
          </button>
          <button type="submit" disabled={responsePending || normalizedAmount <= 0}>
            {responsePending ? "Sending..." : `Ask ${formatGold(normalizedAmount)}`}
          </button>
        </div>
        <div className="investment-secondary-actions">
          <button
            type="button"
            className="secondary"
            disabled={responsePending}
            onClick={() => setTargetPlayerId(null)}
          >
            Change Buyer
          </button>
          <button type="button" className="secondary" disabled={responsePending} onClick={() => onSubmit(null)}>
            Cancel
          </button>
        </div>
      </form>
    </section>
  );
}

function TradeExchangeWidget({
  request,
  phase,
  players,
  proposerProperties,
  targetPlayer,
  selectedSquareId,
  offeredSquareIds,
  requestedSquareIds,
  responsePending,
  onChooseTarget,
  onToggleSquare,
  onPhaseChange,
  onSubmit,
}: {
  request: InputRequest;
  phase: TradePhase;
  players: TradePlayerChoice[];
  proposerProperties: BuyShopChoice[];
  targetPlayer: TradePlayerChoice | null;
  selectedSquareId: number | null;
  offeredSquareIds: number[];
  requestedSquareIds: number[];
  responsePending: boolean;
  onChooseTarget: (playerId: number) => void;
  onToggleSquare: (squareId: number) => void;
  onPhaseChange: (phase: TradePhase) => void;
  onSubmit: (value: unknown) => void;
}) {
  const [goldMode, setGoldMode] = useState<"none" | "offer" | "request">("none");
  const [goldAmount, setGoldAmount] = useState("0");
  const phaseProperties = phase === "offer" ? proposerProperties : (targetPlayer?.properties ?? []);
  const chosenSquareIds = phase === "offer" ? offeredSquareIds : requestedSquareIds;
  const selectedChoice =
    phaseProperties.find((choice) => choice.squareId === selectedSquareId) ?? null;
  const offeredChoices = proposerProperties.filter((choice) => offeredSquareIds.includes(choice.squareId));
  const requestedChoices = (targetPlayer?.properties ?? []).filter((choice) =>
    requestedSquareIds.includes(choice.squareId),
  );
  const normalizedGoldAmount = normalizePositiveOfferPrice(Number(goldAmount));
  const goldOffer =
    goldMode === "offer"
      ? normalizedGoldAmount
      : goldMode === "request"
        ? -normalizedGoldAmount
        : 0;
  const proposalComplete = isCompleteShopExchange(offeredSquareIds, requestedSquareIds);

  useEffect(() => {
    if (phase === "target") {
      setGoldMode("none");
      setGoldAmount("0");
    }
  }, [phase]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape" || responsePending || isTypingTarget(event.target)) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      if (phase === "target") {
        onSubmit(null);
      } else if (phase === "offer") {
        onPhaseChange("target");
      } else if (phase === "request") {
        onPhaseChange("offer");
      } else {
        onPhaseChange("request");
      }
    }
    window.addEventListener("keydown", handleKeyDown, true);
    return () => window.removeEventListener("keydown", handleKeyDown, true);
  }, [onPhaseChange, onSubmit, phase, responsePending]);

  if (phase === "target") {
    return (
      <section className="panel action-panel investment-widget trade-exchange-widget" aria-label="Choose a shop exchange partner">
        <header className="panel-header prompt-header">
          <div>
            <p className="eyebrow">Shop Exchange · 1 of 4</p>
            <h2>Choose a Player</h2>
            <p>Select the player whose properties you want to include in the exchange.</p>
          </div>
        </header>
        <div className="trade-player-options">
          {players.map((player) => (
            <button
              key={player.playerId}
              type="button"
              className="secondary"
              disabled={responsePending}
              onClick={() => onChooseTarget(player.playerId)}
            >
              <strong>Player {player.playerId}</strong>
              <span>{player.properties.length} properties · {formatGold(player.readyCash)} cash</span>
            </button>
          ))}
        </div>
        {players.length === 0 && (
          <p className="investment-selection-hint">No other player has properties available to exchange.</p>
        )}
        <button
          type="button"
          className="secondary investment-cancel"
          disabled={responsePending}
          onClick={() => onSubmit(null)}
        >
          Cancel
        </button>
      </section>
    );
  }

  if (phase === "offer" || phase === "request") {
    const choosingOwn = phase === "offer";
    const selectedIsChosen = selectedChoice
      ? chosenSquareIds.includes(selectedChoice.squareId)
      : false;
    const canContinue = chosenSquareIds.length >= 1 && chosenSquareIds.length <= 2;
    return (
      <section className="panel action-panel investment-widget trade-exchange-widget is-selecting" aria-label={choosingOwn ? "Choose your offered properties" : "Choose requested properties"}>
        <header className="panel-header prompt-header">
          <div>
            <p className="eyebrow">Shop Exchange · {choosingOwn ? "2" : "3"} of 4</p>
            <h2>{choosingOwn ? "Choose What You Offer" : `Choose From Player ${targetPlayer?.playerId ?? ""}`}</h2>
            <p>Select one or two properties. Double-click toggles a property immediately.</p>
          </div>
        </header>
        <TradePropertySelection
          choices={phaseProperties}
          chosenSquareIds={chosenSquareIds}
          onToggleSquare={onToggleSquare}
        />
        {selectedChoice && (
          <div className="investment-selected-shop trade-focused-property">
            <span>{selectedIsChosen ? "Included in exchange" : "Selected property"}</span>
            <strong>{readableType(selectedChoice.squareType)} #{selectedChoice.squareId}</strong>
            <small>
              {formatGold(selectedChoice.currentValue)} current value
              {selectedChoice.districtId === null ? "" : ` · District ${selectedChoice.districtId}`}
            </small>
            <button
              type="button"
              className={selectedIsChosen ? "secondary" : ""}
              disabled={responsePending || (!selectedIsChosen && chosenSquareIds.length >= 2)}
              onClick={() => onToggleSquare(selectedChoice.squareId)}
            >
              {selectedIsChosen ? "Remove Property" : "Include Property"}
            </button>
          </div>
        )}
        {!selectedChoice && (
          <p className="investment-selection-hint">Choose an untinted property on the board.</p>
        )}
        <div className="trade-navigation-actions">
          <button
            type="button"
            className="secondary"
            disabled={responsePending}
            onClick={() => onPhaseChange(choosingOwn ? "target" : "offer")}
          >
            Back
          </button>
          <button
            type="button"
            disabled={responsePending || !canContinue}
            onClick={() => onPhaseChange(choosingOwn ? "request" : "terms")}
          >
            Continue with {chosenSquareIds.length}
          </button>
        </div>
        <button
          type="button"
          className="secondary investment-cancel"
          disabled={responsePending}
          onClick={() => onSubmit(null)}
        >
          Cancel Exchange
        </button>
      </section>
    );
  }

  const proposerCash = asNumber(request.data.cash);
  const targetCash = targetPlayer?.readyCash ?? 0;
  const goldAmountIsValid = goldMode === "none" || normalizedGoldAmount > 0;
  return (
    <section
      className={`panel action-panel investment-widget trade-exchange-widget is-terms ${responsePending ? "is-resolving" : ""}`}
      aria-busy={responsePending}
    >
      <header className="panel-header prompt-header">
        <div>
          <p className="eyebrow">Shop Exchange · 4 of 4</p>
          <h2>Review Exchange</h2>
          <p>Set optional gold terms, then send the complete proposal to Player {targetPlayer?.playerId ?? ""}.</p>
        </div>
      </header>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (!targetPlayer || !proposalComplete || !goldAmountIsValid || responsePending) {
            return;
          }
          onSubmit({
            target_player_id: targetPlayer.playerId,
            offer_shops: offeredSquareIds,
            request_shops: requestedSquareIds,
            gold_offer: goldOffer,
          });
        }}
      >
        <TradeProposalSummary
          proposerId={request.player_id}
          targetId={targetPlayer?.playerId ?? null}
          offeredChoices={offeredChoices}
          requestedChoices={requestedChoices}
          goldOffer={goldOffer}
        />
        <fieldset className="trade-gold-terms">
          <legend>Gold terms</legend>
          <div>
            {(["none", "offer", "request"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                className={goldMode === mode ? "is-selected" : "secondary"}
                disabled={responsePending}
                onClick={() => {
                  setGoldMode(mode);
                  if (mode !== "none" && normalizedGoldAmount <= 0) {
                    setGoldAmount("1");
                  }
                }}
              >
                {mode === "none" ? "No Gold" : mode === "offer" ? "You Add Gold" : "You Request Gold"}
              </button>
            ))}
          </div>
          {goldMode !== "none" && (
            <label className="investment-amount-input">
              {goldMode === "offer" ? "Gold you give" : "Gold you receive"}
              <input
                type="number"
                min="1"
                step="1"
                value={goldAmount}
                disabled={responsePending}
                onChange={(event) => setGoldAmount(event.target.value)}
              />
            </label>
          )}
        </fieldset>
        <dl className="investment-summary trade-cash-preview">
          <div>
            <dt>Your cash if accepted</dt>
            <dd>{formatGold(proposerCash - goldOffer)}</dd>
          </div>
          <div>
            <dt>Player {targetPlayer?.playerId ?? ""} cash if accepted</dt>
            <dd>{formatGold(targetCash + goldOffer)}</dd>
          </div>
        </dl>
        <div className="trade-navigation-actions">
          <button
            type="button"
            className="secondary"
            disabled={responsePending}
            onClick={() => onPhaseChange("request")}
          >
            Back
          </button>
          <button
            type="submit"
            disabled={responsePending || !targetPlayer || !proposalComplete || !goldAmountIsValid}
          >
            {responsePending ? "Sending..." : "Send Exchange"}
          </button>
        </div>
        <button
          type="button"
          className="secondary investment-cancel"
          disabled={responsePending}
          onClick={() => onSubmit(null)}
        >
          Cancel Exchange
        </button>
      </form>
    </section>
  );
}

function TradePropertySelection({
  choices,
  chosenSquareIds,
  onToggleSquare,
}: {
  choices: BuyShopChoice[];
  chosenSquareIds: number[];
  onToggleSquare: (squareId: number) => void;
}) {
  const chosen = choices.filter((choice) => chosenSquareIds.includes(choice.squareId));
  if (chosen.length === 0) {
    return <p className="trade-selection-count">0 of 2 properties included</p>;
  }
  return (
    <div className="trade-property-chips" aria-label={`${chosen.length} of 2 properties included`}>
      {chosen.map((choice) => (
        <button
          key={choice.squareId}
          type="button"
          className="secondary"
          onClick={() => onToggleSquare(choice.squareId)}
          aria-label={`Remove property ${choice.squareId}`}
        >
          #{choice.squareId} · {formatGold(choice.currentValue)} <span aria-hidden="true">×</span>
        </button>
      ))}
    </div>
  );
}

function TradeProposalSummary({
  proposerId,
  targetId,
  offeredChoices,
  requestedChoices,
  goldOffer,
}: {
  proposerId: number;
  targetId: number | null;
  offeredChoices: BuyShopChoice[];
  requestedChoices: BuyShopChoice[];
  goldOffer: number;
}) {
  return (
    <div className="trade-proposal-summary">
      <section>
        <span>Player {proposerId} gives</span>
        <strong>{formatTradeProperties(offeredChoices)}</strong>
        <small>{goldOffer > 0 ? `+ ${formatGold(goldOffer)}` : "No gold"}</small>
      </section>
      <span className="trade-exchange-arrow" aria-hidden="true">⇄</span>
      <section>
        <span>Player {targetId ?? "?"} gives</span>
        <strong>{formatTradeProperties(requestedChoices)}</strong>
        <small>{goldOffer < 0 ? `+ ${formatGold(-goldOffer)}` : "No gold"}</small>
      </section>
    </div>
  );
}

function formatTradeProperties(choices: BuyShopChoice[]): string {
  return choices.length > 0
    ? choices.map((choice) => `#${choice.squareId} (${formatGold(choice.currentValue)})`).join(", ")
    : "No properties";
}

function OfferResponseWidget({
  request,
  state,
  onSubmit,
}: {
  request: InputRequest;
  state: GameState | null;
  onSubmit: (value: unknown) => void;
}) {
  const facts = negotiationOfferFacts(request.data.offer);
  return (
    <div className="offer-response-widget">
      <NegotiationOfferSummary facts={facts} state={state} />
      <div className="offer-response-actions">
        <button type="button" className="offer-accept" onClick={() => onSubmit("accept")}>
          <span className="keycap">D</span>
          Accept
        </button>
        <button type="button" className="secondary" onClick={() => onSubmit("counter")}>
          <span className="keycap">S</span>
          Counter
        </button>
        <button type="button" className="secondary offer-reject" onClick={() => onSubmit("reject")}>
          <span className="keycap">A</span>
          Reject
        </button>
      </div>
    </div>
  );
}

function CounterOfferWidget({
  request,
  state,
  onSubmit,
}: {
  request: InputRequest;
  state: GameState | null;
  onSubmit: (value: unknown) => void;
}) {
  const facts = negotiationOfferFacts(request.data.offer);
  const originalPrice = asNumber(request.data.original_price);
  const [amount, setAmount] = useState(String(originalPrice));
  const numericAmount = Number(amount);
  const isTrade = facts?.type === "trade";
  const normalizedAmount = Number.isFinite(numericAmount)
    ? isTrade
      ? Math.floor(numericAmount)
      : normalizePositiveOfferPrice(numericAmount)
    : 0;
  const valid = Number.isFinite(numericAmount) && (isTrade || normalizedAmount > 0);

  useEffect(() => setAmount(String(originalPrice)), [request, originalPrice]);

  return (
    <form
      className="counter-offer-widget"
      onSubmit={(event) => {
        event.preventDefault();
        if (valid) {
          onSubmit(normalizedAmount);
        }
      }}
    >
      <NegotiationOfferSummary facts={facts} state={state} />
      <label className="investment-amount-input">
        {isTrade ? "Counter gold adjustment" : "Counter price"}
        <input
          type="number"
          min={isTrade ? undefined : 1}
          step="1"
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
          autoFocus
        />
        {isTrade && facts && (
          <small>
            Positive means Player {facts.proposerId ?? "?"} gives gold to Player {facts.targetId ?? "?"}; negative reverses it.
          </small>
        )}
      </label>
      <div className="counter-offer-actions">
        <button type="submit" disabled={!valid}>
          Send {formatGold(normalizedAmount)}
        </button>
      </div>
    </form>
  );
}

function NegotiationOfferSummary({
  facts,
  state,
}: {
  facts: NegotiationOfferFacts | null;
  state: GameState | null;
}) {
  if (!facts) {
    return <p className="muted">Review the offer before responding.</p>;
  }
  if (facts.type === "trade") {
    return (
      <dl className="investment-summary negotiation-summary">
        <div>
          <dt>Players</dt>
          <dd>P{facts.proposerId ?? "?"} ↔ P{facts.targetId ?? "?"}</dd>
        </div>
        <div>
          <dt>Offered properties</dt>
          <dd>{formatSquareList(facts.offerShopIds, state)}</dd>
        </div>
        <div>
          <dt>Requested properties</dt>
          <dd>{formatSquareList(facts.requestShopIds, state)}</dd>
        </div>
        <div>
          <dt>Gold terms</dt>
          <dd>{formatTradeGoldTerms(facts)}</dd>
        </div>
      </dl>
    );
  }

  const square = state?.board.squares.find((candidate) => candidate.id === facts.squareId) ?? null;
  return (
    <dl className="investment-summary negotiation-summary">
      <div>
        <dt>Deal</dt>
        <dd>P{facts.buyerId ?? "?"} buys from P{facts.sellerId ?? "?"}</dd>
      </div>
      <div>
        <dt>Property</dt>
        <dd>{square ? readableType(square.type) : "Square"} #{facts.squareId ?? "?"}</dd>
      </div>
      {square?.shop_current_value !== null && square?.shop_current_value !== undefined && (
        <div>
          <dt>Current value</dt>
          <dd>{formatGold(square.shop_current_value)}</dd>
        </div>
      )}
      <div>
        <dt>Offer</dt>
        <dd>{formatGold(facts.price ?? 0)}</dd>
      </div>
    </dl>
  );
}

function formatSquareList(squareIds: number[], state: GameState | null = null): string {
  return squareIds.length > 0
    ? squareIds
        .map((squareId) => {
          const value = state?.board.squares.find((square) => square.id === squareId)?.shop_current_value;
          return value === null || value === undefined
            ? `#${squareId}`
            : `#${squareId} (${formatGold(value)})`;
        })
        .join(", ")
    : "None";
}

function formatTradeGoldTerms(facts: NegotiationOfferFacts): string {
  const goldOffer = facts.goldOffer ?? 0;
  if (goldOffer > 0) {
    return `P${facts.proposerId ?? "?"} gives P${facts.targetId ?? "?"} ${formatGold(goldOffer)}`;
  }
  if (goldOffer < 0) {
    return `P${facts.targetId ?? "?"} gives P${facts.proposerId ?? "?"} ${formatGold(-goldOffer)}`;
  }
  return "No gold";
}

function PromptPanel({
  request,
  state,
  onSubmit,
  connected,
  responsePending,
}: {
  request: InputRequest | null;
  state: GameState | null;
  onSubmit: (value: unknown) => void;
  connected: boolean;
  responsePending: boolean;
}) {
  const [amount, setAmount] = useState("1");

  const amountNumber = Math.max(0, Math.floor(Number(amount) || 0));

  return (
    <section
      className={`panel action-panel ${request?.type === "CONFIRM_STOP" ? "stop-confirmation-panel" : ""} ${responsePending ? "is-resolving" : ""}`}
      aria-busy={responsePending}
    >
      <header className="panel-header prompt-header">
        <div>
          <p className="eyebrow">Action</p>
          <h2>{request ? getPromptTitle(request) : "Watching the Board"}</h2>
          <p>{request ? getPromptHelp(request) : "No decision is needed from you right now."}</p>
        </div>
      </header>
      {request ? (
        <PromptControls
          request={request}
          state={state}
          amount={amount}
          amountNumber={amountNumber}
          onAmountChange={setAmount}
          onSubmit={onSubmit}
        />
      ) : (
        <div className="idle-action">
          <span className="pulse-dot" />
          <p>{connected ? "Follow the board and wait for your next turn." : "Join a local match to begin."}</p>
        </div>
      )}
    </section>
  );
}

function PromptControls({
  request,
  state,
  amount,
  amountNumber,
  onAmountChange,
  onSubmit,
}: {
  request: InputRequest;
  state: GameState | null;
  amount: string;
  amountNumber: number;
  onAmountChange: (value: string) => void;
  onSubmit: (value: unknown) => void;
}) {
  const data = request.data;

  if (request.type === "PRE_ROLL") {
    return (
      <div className="action-grid">
        <button type="button" onClick={() => onSubmit("roll")}>
          Roll
        </button>
        <button type="button" className="secondary" onClick={() => onSubmit("sell_stock")}>
          Sell Stock
        </button>
        <button type="button" className="secondary" onClick={() => onSubmit("buy_shop")}>
          Buy Shop
        </button>
        <button type="button" className="secondary" onClick={() => onSubmit("sell_shop")}>
          Sell Shop
        </button>
        <button type="button" className="secondary" onClick={() => onSubmit("trade")}>
          Trade
        </button>
        <button type="button" className="secondary" onClick={() => onSubmit("auction")}>
          Auction
        </button>
      </div>
    );
  }

  if (request.type === "CHOOSE_PATH") {
    return <KeyActionList actions={getPathKeyActions(request)} onSubmit={onSubmit} />;
  }

  if (request.type === "CONFIRM_STOP") {
    return <StopConfirmationControls request={request} onSubmit={onSubmit} />;
  }

  if (["BUY_SHOP", "FORCED_BUYOUT"].includes(request.type)) {
    return <KeyActionList actions={getSimpleKeyActions(request)} onSubmit={onSubmit} />;
  }

  if (request.type === "BUY_STOCK") {
    const stocks = asArray(data.stocks).map(asRecord);
    return (
      <div className="choice-table">
        <AmountInput label="Quantity" value={amount} onChange={onAmountChange} />
        {stocks.map((stock) => {
          const districtId = asNumber(stock.district_id);
          return (
            <button key={districtId} type="button" onClick={() => onSubmit([districtId, amountNumber])}>
              Buy {amountNumber} in District {districtId} at {formatGold(asNumber(stock.price))}
            </button>
          );
        })}
        <button type="button" className="secondary" onClick={() => onSubmit(null)}>
          Skip
        </button>
      </div>
    );
  }

  if (request.type === "SELL_STOCK") {
    const holdings = Object.entries(asRecord(data.holdings));
    return (
      <div className="choice-table">
        <AmountInput label="Quantity" value={amount} onChange={onAmountChange} />
        {holdings.map(([districtId, holding]) => {
          const record = asRecord(holding);
          return (
            <button key={districtId} type="button" onClick={() => onSubmit([Number(districtId), amountNumber])}>
              Sell {amountNumber} of {asNumber(record.quantity)} in District {districtId}
            </button>
          );
        })}
        <button type="button" className="secondary" onClick={() => onSubmit(null)}>
          Skip
        </button>
      </div>
    );
  }

  if (request.type === "INVEST") {
    const investable = asArray(data.investable).map(asRecord);
    return (
      <div className="choice-table">
        <AmountInput label="Amount" value={amount} onChange={onAmountChange} />
        {investable.map((shop) => {
          const squareId = asNumber(shop.square_id);
          return (
            <button key={squareId} type="button" onClick={() => onSubmit([squareId, amountNumber])}>
              Invest {formatGold(amountNumber)} in #{squareId}
            </button>
          );
        })}
        <button type="button" className="secondary" onClick={() => onSubmit(null)}>
          Skip
        </button>
      </div>
    );
  }

  if (["CANNON_TARGET", "CHOOSE_ANY_SQUARE", "CHOOSE_SHOP_AUCTION"].includes(request.type)) {
    const key = request.type === "CANNON_TARGET" ? "targets" : request.type === "CHOOSE_ANY_SQUARE" ? "squares" : "shops";
    const options = asArray(data[key]).map(asRecord);
    return (
      <div className="action-list">
        {options.map((option, index) => {
          const value = asNumber(option.square_id, asNumber(option.player_id, index));
          return (
            <button key={`${value}:${index}`} type="button" onClick={() => onSubmit(value)}>
              Choose {option.square_id !== undefined ? `Square #${value}` : `Player ${value}`}
            </button>
          );
        })}
        <button type="button" className="secondary" onClick={() => onSubmit(null)}>
          Skip
        </button>
      </div>
    );
  }

  if (["VACANT_PLOT_TYPE", "RENOVATE"].includes(request.type)) {
    const options = asArray(data.options);
    return (
      <div className="action-list">
        {options.map((option) => (
          <button key={String(option)} type="button" onClick={() => onSubmit(option)}>
            {readableType(String(option))}
          </button>
        ))}
        {request.type === "RENOVATE" && (
          <button type="button" className="secondary" onClick={() => onSubmit(null)}>
            Skip
          </button>
        )}
      </div>
    );
  }

  if (request.type === "AUCTION_BID") {
    return (
      <div className="choice-table">
        <AmountInput label="Gold" value={amount} onChange={onAmountChange} />
        <button type="button" onClick={() => onSubmit(amountNumber)}>
          Send {formatGold(amountNumber)}
        </button>
        <button type="button" className="secondary" onClick={() => onSubmit(null)}>
          Skip
        </button>
      </div>
    );
  }

  if (request.type === "COUNTER_PRICE") {
    return <CounterOfferWidget request={request} state={state} onSubmit={onSubmit} />;
  }

  if (request.type === "ACCEPT_OFFER") {
    return <OfferResponseWidget request={request} state={state} onSubmit={onSubmit} />;
  }

  if (request.type === "SCRIPT_DECISION") {
    const options = scriptDecisionOptions(request.data.options);
    return (
      <div className="script-decision-options" role="group" aria-label="Event choices">
        {options.map((option, index) => (
          <button
            key={`${index}:${option.label}`}
            type="button"
            onClick={() => onSubmit(option.value)}
          >
            <span>{option.label}</span>
          </button>
        ))}
        {options.length === 0 && (
          <p className="muted">This event did not provide any choices.</p>
        )}
      </div>
    );
  }

  if (request.type === "CHOOSE_VENTURE_CELL") {
    return (
      <div className="idle-action">
        <span className="pulse-dot" />
        <p>Choosing a venture grid cell...</p>
      </div>
    );
  }

  return (
    <div className="request-data">
      <p className="muted">This decision needs a temporary manual control. Open Tools to respond.</p>
    </div>
  );
}

function KeyActionList({
  actions,
  onSubmit,
}: {
  actions: Array<{ key: string; value: unknown; label: string; squareType?: string }>;
  onSubmit: (value: unknown) => void;
}) {
  return (
    <div className="key-action-list">
      {actions.map((action) => (
        <button
          key={`${action.key}:${String(action.value)}`}
          type="button"
          className="key-action-card"
          onClick={() => onSubmit(action.value)}
        >
          <span className="keycap">{formatWasdKey(action.key)}</span>
          <span>
            {action.label}
            {action.squareType ? <small>{readableType(action.squareType)}</small> : null}
          </span>
        </button>
      ))}
    </div>
  );
}

function StopConfirmationControls({
  request,
  onSubmit,
}: {
  request: InputRequest;
  onSubmit: (value: unknown) => void;
}) {
  const squareId = asNumber(request.data.square_id);
  const actions = getSimpleKeyActions(request).sort((left, right) =>
    left.value === true ? -1 : right.value === true ? 1 : 0,
  );

  return (
    <div className="stop-action-list">
      {actions.map((action) => {
        const isStop = action.value === true;
        return (
          <button
            key={`${action.key}:${String(action.value)}`}
            type="button"
            className={`stop-action-card ${isStop ? "is-stop" : "secondary is-undo"}`}
            onClick={() => onSubmit(action.value)}
          >
            <span className="keycap">{formatWasdKey(action.key)}</span>
            <span>
              <strong>{action.label}</strong>
              <small>{isStop ? `End your move on Square #${squareId}` : "Return to your previous square"}</small>
            </span>
          </button>
        );
      })}
    </div>
  );
}

function AmountInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="amount-input">
      {label}
      <input type="number" min="0" step="1" value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function DevPanel({
  open,
  uri,
  status,
  playerId,
  gameId,
  request,
  logs,
  onUriChange,
  onConnect,
  onDisconnect,
  onSave,
  onSync,
  onSubmitRaw,
}: {
  open: boolean;
  uri: string;
  status: string;
  playerId: number | null;
  gameId: string | null;
  request: InputRequest | null;
  logs: string[];
  onUriChange: (value: string) => void;
  onConnect: (event: FormEvent<HTMLFormElement>) => void;
  onDisconnect: () => void;
  onSave: () => void;
  onSync: () => void;
  onSubmitRaw: (value: unknown) => void;
}) {
  const [rawValue, setRawValue] = useState("");

  function submitRaw(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmitRaw(parseResponseInput(rawValue));
    setRawValue("");
  }

  if (!open) {
    return null;
  }

  return (
    <aside className="dev-panel" aria-label="Developer tools">
      <header className="dev-panel-header">
        <div>
          <p className="eyebrow">Tools</p>
          <h2>Local Client Controls</h2>
        </div>
        <span className={`connection-dot ${status}`} title={`Connection ${status}`} />
      </header>

      <form className="dev-connect-form" onSubmit={onConnect}>
        <label>
          Local game address
          <input value={uri} onChange={(event) => onUriChange(event.target.value)} />
        </label>
        {status === "connected" ? (
          <button type="button" className="secondary" onClick={onDisconnect}>
            Disconnect
          </button>
        ) : (
          <button type="submit">{status === "connecting" ? "Joining" : "Join"}</button>
        )}
      </form>

      <section className="dev-status-grid">
        <StatusPill label="Status" value={status} tone={status as "connected" | "connecting" | "disconnected"} />
        <StatusPill label="Player" value={playerId === null ? "-" : `P${playerId}`} />
        <StatusPill label="Game" value={gameId ?? "-"} />
      </section>

      <section className="dev-tool-row">
        <button type="button" className="secondary" disabled={status !== "connected"} onClick={onSave}>
          Save
        </button>
        <button type="button" className="secondary" disabled={status !== "connected"} onClick={onSync}>
          Sync
        </button>
      </section>

      <form className="raw-response" onSubmit={submitRaw}>
        <label>
          Raw response fallback
          <input
            value={rawValue}
            disabled={!request}
            onChange={(event) => setRawValue(event.target.value)}
            placeholder={'Example: "roll", true, null, [1, 20]'}
          />
        </label>
        <button type="submit" disabled={!request}>
          Send
        </button>
      </form>

      <section className="request-data">
        <header className="mini-header">
          <h3>Pending Request</h3>
        </header>
        <pre>{request ? JSON.stringify(request, null, 2) : "No pending request."}</pre>
      </section>

      <LogPanel logs={logs} />
    </aside>
  );
}

function LogPanel({ logs }: { logs: string[] }) {
  return (
    <section className="panel log-panel">
      <header className="panel-header">
        <h2>Log</h2>
      </header>
      <div className="log-scroll">
        {logs.length === 0 ? (
          <p className="muted">Server messages will appear here.</p>
        ) : (
          logs.map((line, index) => <p key={`${index}:${line}`}>{line}</p>)
        )}
      </div>
    </section>
  );
}

export default App;
