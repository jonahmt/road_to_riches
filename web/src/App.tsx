import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { getPathKeyActions, getWasdResponseMap, type WasdResponseMap } from "./controls";
import { formatGold, netWorth, readableType } from "./format";
import {
  type GameState,
  type InputRequest,
  type PlayerState,
  type SquareInfo,
  stockPrice,
} from "./protocol";
import { useGameClient } from "./useGameClient";

const DEFAULT_URI = "ws://localhost:8765";

const PLAYER_COLORS = ["#54d6ff", "#ff7ab6", "#ffd166", "#77dd77", "#c792ea", "#ff9f1c"];
const DISTRICT_COLORS = ["#54d6ff", "#ff7ab6", "#ffd166", "#77dd77", "#c792ea", "#ff9f1c"];
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

function getPlayerColor(playerId: number): string {
  return PLAYER_COLORS[playerId % PLAYER_COLORS.length];
}

function getDistrictColor(districtId: number | null): string {
  if (districtId === null) {
    return "#ffffff";
  }
  return DISTRICT_COLORS[districtId % DISTRICT_COLORS.length];
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
  const { clientState, connect, disconnect, submitResponse, saveGame, requestSync } =
    useGameClient(DEFAULT_URI);
  const [uri, setUri] = useState(DEFAULT_URI);
  const [devPanelOpen, setDevPanelOpen] = useState(false);
  const [selectedSquareId, setSelectedSquareId] = useState<number | null>(null);
  useWasdPromptControls(clientState.pendingRequest, submitResponse);

  const currentPlayer = clientState.gameState
    ? clientState.gameState.players[clientState.gameState.current_player_index]
    : null;
  const assignedPlayer = clientState.gameState
    ? clientState.gameState.players.find((player) => player.player_id === clientState.playerId) ?? null
    : null;
  const latestEvent = getLatestGameLog(clientState.logs);

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
    <main className={`app-shell ${clientState.gameState ? "is-playing" : "is-starting"}`}>
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
        <button
          type="button"
          className="secondary dev-toggle"
          onClick={() => setDevPanelOpen((open) => !open)}
        >
          {devPanelOpen ? "Hide Tools" : "Tools"}
        </button>
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
              />
              <SquarePanel square={focusSquare} state={clientState.gameState} />
            </aside>
          </section>
        </>
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
  selectedSquare,
  onSelectSquare,
}: {
  state: GameState | null;
  selectedSquare: SquareInfo | null;
  onSelectSquare: (squareId: number) => void;
}) {
  if (!state) {
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

  const bounds = getBoardBounds(state);
  const playerGroups = groupPlayersBySquare(state.players);
  const lines = getBoardLines(state);

  return (
    <section className="board-panel">
      <div className="location-backdrop" />
      <div className="board-canvas">
        <svg
          className="board-svg"
          viewBox={`${bounds.minX} ${bounds.minY} ${bounds.width} ${bounds.height}`}
          preserveAspectRatio="xMidYMid meet"
          aria-label="Game board"
          role="img"
        >
          <g className="board-lines">
            {lines.map((line) => (
              <line
                key={line.key}
                x1={line.from.position[0]}
                y1={line.from.position[1]}
                x2={line.to.position[0]}
                y2={line.to.position[1]}
              />
            ))}
          </g>
          {state.board.squares.map((square) => {
            const players = playerGroups.get(square.id) ?? [];
            const isSelected = selectedSquare?.id === square.id;
            const ownerColor =
              square.property_owner === null ? "rgba(255,255,255,0.78)" : getPlayerColor(square.property_owner);
            const label = labelForSquare(square);
            return (
              <g
                key={square.id}
                className={`board-square-group ${isSelected ? "selected" : ""}`}
                role="button"
                tabIndex={0}
                aria-label={`Square ${square.id}: ${readableType(square.type)}`}
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
                    stroke: getDistrictColor(square.property_district),
                    fill: "rgba(8, 10, 14, 0.92)",
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
                <text
                  className="square-type"
                  x={square.position[0]}
                  y={square.position[1] - 0.55}
                  fill={ownerColor}
                >
                  {fitLabel(label, 8)}
                </text>
                {square.shop_current_value !== null && (
                  <text className="square-value" x={square.position[0]} y={square.position[1] + 0.38}>
                    {shortGold(square.shop_current_value)}
                  </text>
                )}
                <text className="square-id" x={square.position[0] + 1.55} y={square.position[1] + 1.48}>
                  #{square.id}
                </text>
                {players.map((player, index) => (
                  <g key={player.player_id} className="player-token-svg">
                    <circle
                      cx={square.position[0] - 1.45 + index * 0.58}
                      cy={square.position[1] + 1.35}
                      r="0.34"
                      fill={getPlayerColor(player.player_id)}
                    />
                    <text x={square.position[0] - 1.45 + index * 0.58} y={square.position[1] + 1.47}>
                      {player.player_id}
                    </text>
                  </g>
                ))}
              </g>
            );
          })}
        </svg>
      </div>
    </section>
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

function getBoardLines(state: GameState) {
  const squares = new Map(state.board.squares.map((square) => [square.id, square]));
  const seen = new Set<string>();
  const lines: Array<{ key: string; from: SquareInfo; to: SquareInfo }> = [];
  for (const square of state.board.squares) {
    for (const waypoint of square.waypoints) {
      for (const toId of waypoint.to_ids) {
        const to = squares.get(toId);
        if (!to) {
          continue;
        }
        const key = [Math.min(square.id, to.id), Math.max(square.id, to.id)].join(":");
        if (seen.has(key)) {
          continue;
        }
        seen.add(key);
        lines.push({ key, from: square, to });
      }
    }
  }
  return lines;
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

function labelForSquare(square: SquareInfo): string {
  if (square.type === "BANK") {
    return "Bank";
  }
  if (square.type === "SHOP") {
    return square.property_owner === null ? "Shop" : `P${square.property_owner}`;
  }
  if (square.suit) {
    return square.suit;
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
                <dd>{formatSuitCount(player)}</dd>
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

function formatSuitCount(player: PlayerState): string {
  const count = Object.values(player.suits).filter((value) => value > 0).length;
  return `${count}/4`;
}

function SquarePanel({ square, state }: { square: SquareInfo | null; state: GameState | null }) {
  return (
    <section className="panel">
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
            <dd>{readableType(square.type)}</dd>
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

function PromptPanel({
  request,
  onSubmit,
  connected,
}: {
  request: InputRequest | null;
  onSubmit: (value: unknown) => void;
  connected: boolean;
}) {
  const [amount, setAmount] = useState("1");

  const amountNumber = Math.max(0, Math.floor(Number(amount) || 0));

  return (
    <section className="panel action-panel">
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
    return "Stop or Keep Moving";
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
    return "Commit to this square, or undo the last step if allowed.";
  }
  if (request.type === "BUY_STOCK" || request.type === "SELL_STOCK") {
    return "Set a quantity, then choose a district.";
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
    return <KeyActionList actions={getSimpleKeyActions(request)} onSubmit={onSubmit} />;
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
