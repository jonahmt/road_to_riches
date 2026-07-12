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
import { getPathKeyActions, getWasdResponseMap, type WasdResponseMap } from "./controls";
import { formatGold, netWorth, readableType } from "./format";
import {
  type GameState,
  type InputRequest,
  type PlayerState,
  type SquareInfo,
  stockPrice,
} from "./protocol";
import { type DiceState, type PresentationState, useGameClient } from "./useGameClient";

const DEFAULT_URI = "ws://localhost:8765";
const LAYOUT_STORAGE_KEY = "road-to-riches-layout";

const PLAYER_COLORS = ["#54d6ff", "#ff7ab6", "#ffd166", "#77dd77", "#c792ea", "#ff9f1c"];
const DISTRICT_COLORS = ["#54d6ff", "#ff7ab6", "#ffd166", "#77dd77", "#c792ea", "#ff9f1c"];
const SUIT_COLORS: Record<string, string> = {
  SPADE: "#56cfff",
  HEART: "#ff6aae",
  DIAMOND: "#ffd84d",
  CLUB: "#74df67",
};
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
const BOARD_TILE_SIZE = 4;
const BOARD_TILE_RADIUS = BOARD_TILE_SIZE / 2;
const BOARD_TILE_STROKE_WIDTH = 0.14;
const BOARD_TILE_STROKE_INSET = BOARD_TILE_STROKE_WIDTH / 2;
const BOARD_TILE_DRAW_SIZE = BOARD_TILE_SIZE - BOARD_TILE_STROKE_WIDTH;
const BOARD_TILE_SELECTION_INSET = 0.34;
const BOARD_TILE_SELECTION_STROKE_WIDTH = 0.12;
const BOARD_TILE_SELECTION_SIZE = BOARD_TILE_SIZE - BOARD_TILE_SELECTION_INSET * 2;
const WASD_KEYS = new Set(["w", "a", "s", "d"]);
const CHORD_TIMEOUT_MS = 180;
const MIN_BOARD_ZOOM = 0.5;
const MAX_BOARD_ZOOM = 3;
const FOLLOW_BOARD_ZOOM = 1.75;
const FOLLOW_CAMERA_ANIMATION_MS = 360;
const ADJACENT_STEP_ANIMATION_MS = 100;
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
type GameLayoutMode = "immersive" | "classic";
type VentureCellOwner = number | null;
type VentureCursor = readonly [number, number];

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
    return hexToRgba(getPlayerColor(ownerId), 0.34);
  }
  return "rgba(8, 10, 14, 0.92)";
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

function getInitialLayoutMode(): GameLayoutMode {
  const requested = new URLSearchParams(window.location.search).get("layout");
  if (requested === "classic" || requested === "immersive") {
    return requested;
  }
  try {
    const stored = window.localStorage.getItem(LAYOUT_STORAGE_KEY);
    return stored === "classic" || stored === "immersive" ? stored : "immersive";
  } catch {
    return "immersive";
  }
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
  const [layoutMode, setLayoutMode] = useState<GameLayoutMode>(getInitialLayoutMode);
  const ventureRequest =
    clientState.pendingRequest?.type === "CHOOSE_VENTURE_CELL" ? clientState.pendingRequest : null;
  const activePresentation = clientState.presentations[0] ?? null;
  const blockingPresentationActive = activePresentation !== null;
  const standardKeyboardRequest = ventureRequest || blockingPresentationActive ? null : clientState.pendingRequest;
  useWasdPromptControls(clientState.responsePending ? null : standardKeyboardRequest, submitResponse);

  useEffect(() => {
    try {
      window.localStorage.setItem(LAYOUT_STORAGE_KEY, layoutMode);
    } catch {
      // The layout still works when storage is unavailable.
    }
  }, [layoutMode]);

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
      className={`app-shell layout-${layoutMode} ${clientState.gameState ? "is-playing" : "is-starting"} ${isRollingOrMoving ? "is-roll-active" : ""} ${stopConfirmationActive ? "is-stop-confirmation" : ""} ${rollActionPromptActive ? "is-roll-action-prompt" : ""} ${ventureRequest ? "has-venture-grid" : ""}`}
      data-layout={layoutMode}
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
            className="secondary layout-toggle"
            onClick={() => setLayoutMode((mode) => (mode === "immersive" ? "classic" : "immersive"))}
          >
            {layoutMode === "immersive" ? "Classic UI" : "Immersive UI"}
          </button>
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
          <PlayerHud state={clientState.gameState} assignedPlayerId={clientState.playerId} />
          <section className="game-layout">
            <BoardPanel
              state={clientState.gameState}
              dice={clientState.dice}
              showDice={layoutMode === "classic" || isRollingOrMoving}
              selectedSquare={selectedSquare}
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
              <PromptPanel
                request={clientState.pendingRequest}
                onSubmit={submitResponse}
                connected={clientState.status === "connected"}
                responsePending={clientState.responsePending}
              />
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

      {activePresentation &&
        !["venture_card_revealed", "promotion_completed"].includes(activePresentation.type) && (
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
  dice,
  showDice,
  selectedSquare,
  onSelectSquare,
}: {
  state: GameState | null;
  dice: DiceState | null;
  showDice: boolean;
  selectedSquare: SquareInfo | null;
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
  const activePlayerFrameRef = useRef<ActivePlayerFrame | null>(null);
  const tokenElementsRef = useRef(new Map<number, SVGGElement>());
  const tokenVisualsRef = useRef(new Map<number, BoardTokenVisual>());
  const tokenAnimationFrameRef = useRef<number | null>(null);
  const [cameraMode, setCameraMode] = useState<BoardCameraMode>("follow");
  const [isDragging, setIsDragging] = useState(false);
  const boardBounds = state ? getBoardBounds(state) : null;
  const activePlayer = state?.players[state.current_player_index] ?? null;
  const activeSquare =
    state && activePlayer
      ? state.board.squares.find((square) => square.id === activePlayer.position) ?? null
      : null;
  const activePositionKey = activeSquare ? `${activeSquare.position[0]}:${activeSquare.position[1]}` : "";
  const automaticAnimation = useMemo(() => {
    const previous = activePlayerFrameRef.current;
    const isAdjacentActiveMove = Boolean(
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
      duration: isAdjacentActiveMove ? ADJACENT_STEP_ANIMATION_MS : FOLLOW_CAMERA_ANIMATION_MS,
    };
  }, [activePlayer?.player_id, activeSquare?.id]);
  const automaticAnimationCurve = automaticAnimation.curve;
  const automaticAnimationDuration = automaticAnimation.duration;
  const playerTokens = useMemo(() => getBoardPlayerTokens(state), [state]);
  const playerTokenKey = playerTokens
    .map((token) => `${token.player.player_id}:${token.x}:${token.y}:${token.radius}`)
    .join("|");
  const boundsKey = boardBounds
    ? `${boardBounds.minX}:${boardBounds.minY}:${boardBounds.width}:${boardBounds.height}`
    : "";

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
    }
    svg.dataset.cameraMode = cameraMode;
    if (cameraMode === "follow") {
      const center = activeSquare
        ? { x: activeSquare.position[0], y: activeSquare.position[1] }
        : { x: boardBounds.minX + boardBounds.width / 2, y: boardBounds.minY + boardBounds.height / 2 };
      const target = centeredBoardCamera(boardBounds, FOLLOW_BOARD_ZOOM, center);
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
  }, [activePositionKey, boundsKey, cameraMode, automaticAnimationCurve, automaticAnimationDuration]);

  useEffect(() => {
    const canvas = boardCanvasRef.current;
    const svg = boardSvgRef.current;
    if (!canvas || !svg || !boardBounds || cameraMode !== "free") {
      return;
    }
    const activeSvg = svg;
    const activeBounds = boardBounds;

    function handleWheel(event: WheelEvent) {
      event.preventDefault();
      const point = svgPointAt(activeSvg, event.clientX, event.clientY);
      if (!point) {
        return;
      }
      const factor = Math.exp(-event.deltaY * BOARD_WHEEL_ZOOM_SPEED);
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
  }, [boundsKey, cameraMode]);

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

  function zoomFromCenter(delta: number) {
    const svg = boardSvgRef.current;
    if (!svg) {
      return;
    }
    const camera = cameraRef.current;
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
    boardDragRef.current = null;
    setIsDragging(false);
    setCameraMode("follow");
  }

  function handlePointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    if (cameraMode !== "free" || event.button !== 0) {
      return;
    }
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    didDragRef.current = false;
    boardDragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      lastX: event.clientX,
      lastY: event.clientY,
    };
    setIsDragging(true);
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
    didDragRef.current = true;
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
        className={`board-canvas ${cameraMode === "free" ? "is-free-camera" : "is-follow-camera"} ${isDragging ? "is-dragging" : ""}`}
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
            const isSelected = selectedSquare?.id === square.id;
            const ownerColor =
              square.property_owner === null ? "rgba(255,255,255,0.78)" : getPlayerColor(square.property_owner);
            const label = labelForSquare(square);
            const valueLabel = valueLabelForSquare(square, state);
            const shouldRenderSuitIcon = isSuitIconSquare(square);
            const shouldRenderShopTile = isShopSquare(square);
            const shouldRenderDefaultText = !shouldRenderSuitIcon && !shouldRenderShopTile;
            return (
              <g
                key={square.id}
                className={`board-square-group ${isSelected ? "selected" : ""}`}
                role="button"
                tabIndex={0}
                aria-label={`Square ${square.id}: ${displayTypeForSquare(square)}`}
                onClick={() => onSelectSquare(square.id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelectSquare(square.id);
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
                  strokeWidth={BOARD_TILE_STROKE_WIDTH}
                  style={{
                    stroke: shouldRenderSuitIcon ? "#f7f7f2" : getDistrictColor(square.property_district),
                    fill: getSquareFill(square),
                  }}
                />
                {isSelected && (
                  <rect
                    className="board-square-selection"
                    x={square.position[0] - BOARD_TILE_RADIUS + BOARD_TILE_SELECTION_INSET}
                    y={square.position[1] - BOARD_TILE_RADIUS + BOARD_TILE_SELECTION_INSET}
                    width={BOARD_TILE_SELECTION_SIZE}
                    height={BOARD_TILE_SELECTION_SIZE}
                    rx="0.24"
                    ry="0.24"
                    strokeWidth={BOARD_TILE_SELECTION_STROKE_WIDTH}
                  />
                )}
                {shouldRenderSuitIcon ? (
                  <SuitIcon suit={square.suit} squareType={square.type} x={square.position[0]} y={square.position[1]} />
                ) : shouldRenderShopTile ? (
                  <ShopTile square={square} state={state} x={square.position[0]} y={square.position[1]} />
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
                {!shouldRenderShopTile && (
                  <text className="square-id" x={square.position[0] + 1.55} y={square.position[1] + 1.48}>
                    #{square.id}
                  </text>
                )}
              </g>
            );
          })}
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
      {showDice && <BoardDice dice={dice} />}
      <div className="board-camera-controls" aria-label="Board zoom controls">
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
          <>
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
            <button
              type="button"
              className="board-camera-mode"
              aria-label="Follow active player"
              title="Follow active player"
              onClick={enableFollowCamera}
            >
              Follow
            </button>
          </>
        )}
      </div>
    </section>
  );
}

function BoardDice({ dice }: { dice: DiceState | null }) {
  const roll = dice?.value ?? 0;
  const remaining = dice?.remaining ?? 0;
  const faceValue = remaining > 0 ? remaining : 0;
  const activePips = new Set(DIE_PIPS[faceValue] ?? DIE_PIPS[0]);
  const description = roll > 0 ? `Rolled ${roll}; ${remaining} moves remaining` : "No active roll";

  return (
    <div className="board-dice" role="img" aria-label={description}>
      <div className="board-die-face" aria-hidden="true">
        {Array.from({ length: 9 }, (_, index) => {
          const position = index + 1;
          return (
            <span
              key={position}
              className={`board-die-pip ${activePips.has(position) ? "is-visible" : ""}`}
            />
          );
        })}
      </div>
      <span className={`board-die-roll ${roll > 0 ? "" : "is-empty"}`}>Roll {roll || "-"}</span>
    </div>
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
}: {
  square: SquareInfo;
  state: GameState;
  x: number;
  y: number;
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

  return (
    <g className="shop-tile shop-tile-owned" aria-hidden="true">
      <text className="shop-tile-price" x={x} y={y}>
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
      <text className="suit-icon-label" x={x} y={y - 1.22}>
        {suitLabel(suit)}
      </text>
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

function PlayerHud({
  state,
  assignedPlayerId,
}: {
  state: GameState | null;
  assignedPlayerId: number | null;
}) {
  if (!state) {
    return null;
  }

  return (
    <section className="player-hud" aria-label="Players">
      {state.players.map((player) => {
        const isCurrent = state.players[state.current_player_index]?.player_id === player.player_id;
        const isAssigned = assignedPlayerId === player.player_id;
        return (
          <article
            key={player.player_id}
            className={`hud-player-card ${isCurrent ? "current" : ""} ${isAssigned ? "assigned" : ""}`}
            style={{ borderColor: getPlayerColor(player.player_id) }}
          >
            <div className="hud-player-title">
              <span className="player-token large" style={{ backgroundColor: getPlayerColor(player.player_id) }}>
                {player.player_id}
              </span>
              <div>
                <strong>Player {player.player_id}</strong>
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
      <div className="promotion-radiance" aria-hidden="true" />
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

function PromptPanel({
  request,
  onSubmit,
  connected,
  responsePending,
}: {
  request: InputRequest | null;
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

function getPromptTitle(request: InputRequest): string {
  if (request.type === "PRE_ROLL") {
    return "Choose Your Move";
  }
  if (request.type === "CHOOSE_PATH") {
    return "Choose a Path";
  }
  if (request.type === "CONFIRM_STOP") {
    return "Stop on This Square?";
  }
  if (request.type === "BUY_SHOP") {
    return "Buy This Shop?";
  }
  if (request.type === "BUY_STOCK") {
    return "Buy Stock";
  }
  if (request.type === "SELL_STOCK") {
    return "Sell Stock";
  }
  if (request.type === "INVEST") {
    return "Invest in a Shop";
  }
  if (request.type === "CHOOSE_VENTURE_CELL") {
    return "Choosing Venture Cell";
  }
  return readableType(request.type);
}

function getPromptHelp(request: InputRequest): string {
  if (request.type === "PRE_ROLL") {
    return "Take any pre-roll actions, or roll the die to start moving.";
  }
  if (request.type === "CHOOSE_PATH") {
    return "Pick where your piece should move next.";
  }
  if (request.type === "CONFIRM_STOP") {
    return request.data.can_undo === true
      ? "Choose Stop Here to end your move, or undo the last step."
      : "Choose Stop Here to end your move on this square.";
  }
  if (request.type === "BUY_STOCK" || request.type === "SELL_STOCK") {
    return "Set a quantity, then choose a district.";
  }
  if (request.type === "CHOOSE_VENTURE_CELL") {
    return "The web client is choosing a random unclaimed venture grid cell.";
  }
  return `Decision for Player ${request.player_id}.`;
}

function PromptControls({
  request,
  amount,
  amountNumber,
  onAmountChange,
  onSubmit,
}: {
  request: InputRequest;
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

  if (request.type === "AUCTION_BID" || request.type === "COUNTER_PRICE") {
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

  if (request.type === "ACCEPT_OFFER") {
    return <KeyActionList actions={getSimpleKeyActions(request)} onSubmit={onSubmit} />;
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
