import { FormEvent, useMemo, useState } from "react";
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

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function App() {
  const { clientState, connect, disconnect, submitResponse, saveGame, requestSync } =
    useGameClient(DEFAULT_URI);
  const [uri, setUri] = useState(DEFAULT_URI);
  const [selectedSquareId, setSelectedSquareId] = useState<number | null>(null);

  const selectedSquare = useMemo(() => {
    if (!clientState.gameState || selectedSquareId === null) {
      return null;
    }
    return clientState.gameState.board.squares.find((square) => square.id === selectedSquareId) ?? null;
  }, [clientState.gameState, selectedSquareId]);

  function handleConnect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    connect(uri);
  }

  return (
    <main className="app-shell">
      <section className="top-bar">
        <div>
          <p className="eyebrow">Road to Riches</p>
          <h1>Web Client Preview</h1>
        </div>
        <form className="connect-form" onSubmit={handleConnect}>
          <label>
            Server
            <input value={uri} onChange={(event) => setUri(event.target.value)} />
          </label>
          {clientState.status === "connected" ? (
            <button type="button" className="secondary" onClick={disconnect}>
              Disconnect
            </button>
          ) : (
            <button type="submit">{clientState.status === "connecting" ? "Connecting" : "Connect"}</button>
          )}
        </form>
      </section>

      <section className="status-strip">
        <StatusPill label="Status" value={clientState.status} tone={clientState.status} />
        <StatusPill label="Player" value={clientState.playerId === null ? "-" : `P${clientState.playerId}`} />
        <StatusPill label="Game" value={clientState.gameId ?? "-"} />
        <StatusPill
          label="Target"
          value={clientState.gameState ? formatGold(clientState.gameState.board.target_networth) : "-"}
        />
        <StatusPill
          label="Dice"
          value={clientState.dice ? `${clientState.dice.value} rolled, ${clientState.dice.remaining} left` : "-"}
        />
      </section>

      {clientState.error && <div className="error-banner">{clientState.error}</div>}

      <section className="play-layout">
        <BoardPanel
          state={clientState.gameState}
          selectedSquare={selectedSquare}
          onSelectSquare={setSelectedSquareId}
        />
        <aside className="side-panel">
          <PlayerPanel state={clientState.gameState} assignedPlayerId={clientState.playerId} />
          <SquarePanel square={selectedSquare} state={clientState.gameState} />
        </aside>
      </section>

      <section className="bottom-panels">
        <PromptPanel
          request={clientState.pendingRequest}
          onSubmit={submitResponse}
          onSave={() => saveGame()}
          onSync={requestSync}
          connected={clientState.status === "connected"}
        />
        <LogPanel logs={clientState.logs} />
      </section>

      {clientState.gameOverWinner !== undefined && (
        <div className="game-over-banner">Game over. Winner: Player {clientState.gameOverWinner ?? "none"}</div>
      )}
    </main>
  );
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
          <h2>Connect to a local game server</h2>
          <p>Start the Python server, then connect here to see the live board.</p>
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
      <div className="board-canvas" aria-label="Game board">
        <svg className="board-lines" viewBox={`${bounds.minX} ${bounds.minY} ${bounds.width} ${bounds.height}`}>
          {lines.map((line) => (
            <line
              key={line.key}
              x1={line.from.position[0]}
              y1={line.from.position[1]}
              x2={line.to.position[0]}
              y2={line.to.position[1]}
            />
          ))}
        </svg>
        {state.board.squares.map((square) => {
          const x = ((square.position[0] - bounds.minX) / bounds.width) * 100;
          const y = ((square.position[1] - bounds.minY) / bounds.height) * 100;
          const players = playerGroups.get(square.id) ?? [];
          const isSelected = selectedSquare?.id === square.id;
          const ownerColor =
            square.property_owner === null ? "rgba(255,255,255,0.78)" : getPlayerColor(square.property_owner);
          return (
            <button
              key={square.id}
              type="button"
              className={`board-square ${isSelected ? "selected" : ""}`}
              style={{
                left: `${x}%`,
                top: `${y}%`,
                borderColor: getDistrictColor(square.property_district),
                color: ownerColor,
              }}
              onClick={() => onSelectSquare(square.id)}
            >
              <span className="square-type">{labelForSquare(square)}</span>
              {square.shop_current_value !== null && (
                <span className="square-value">{formatGold(square.shop_current_value)}</span>
              )}
              <span className="square-id">#{square.id}</span>
              <span className="player-stack">
                {players.map((player) => (
                  <span
                    key={player.player_id}
                    className="player-token"
                    style={{ backgroundColor: getPlayerColor(player.player_id) }}
                    title={`Player ${player.player_id}`}
                  >
                    {player.player_id}
                  </span>
                ))}
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function getBoardBounds(state: GameState) {
  const xs = state.board.squares.map((square) => square.position[0]);
  const ys = state.board.squares.map((square) => square.position[1]);
  const minX = Math.min(...xs) - 4;
  const maxX = Math.max(...xs) + 4;
  const minY = Math.min(...ys) - 4;
  const maxY = Math.max(...ys) + 4;
  return {
    minX,
    minY,
    width: Math.max(1, maxX - minX),
    height: Math.max(1, maxY - minY),
  };
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

function PlayerPanel({
  state,
  assignedPlayerId,
}: {
  state: GameState | null;
  assignedPlayerId: number | null;
}) {
  return (
    <section className="panel">
      <header className="panel-header">
        <h2>Players</h2>
      </header>
      {!state ? (
        <p className="muted">Waiting for state sync.</p>
      ) : (
        <div className="player-list">
          {state.players.map((player) => (
            <article
              key={player.player_id}
              className={`player-card ${assignedPlayerId === player.player_id ? "assigned" : ""}`}
              style={{ borderColor: getPlayerColor(player.player_id) }}
            >
              <div className="player-card-title">
                <span className="player-token large" style={{ backgroundColor: getPlayerColor(player.player_id) }}>
                  {player.player_id}
                </span>
                <strong>Player {player.player_id}</strong>
              </div>
              <dl>
                <div>
                  <dt>Cash</dt>
                  <dd>{formatGold(player.ready_cash)}</dd>
                </div>
                <div>
                  <dt>Net worth</dt>
                  <dd>{formatGold(netWorth(state, player))}</dd>
                </div>
                <div>
                  <dt>Level</dt>
                  <dd>{player.level}</dd>
                </div>
                <div>
                  <dt>Square</dt>
                  <dd>#{player.position}</dd>
                </div>
              </dl>
              <p className="suits">{formatSuits(player)}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function formatSuits(player: PlayerState): string {
  const suits = Object.entries(player.suits)
    .filter(([, count]) => count > 0)
    .map(([suit, count]) => `${suit}${count > 1 ? ` x${count}` : ""}`);
  return suits.length ? suits.join(", ") : "No suits";
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
  onSave,
  onSync,
  connected,
}: {
  request: InputRequest | null;
  onSubmit: (value: unknown) => void;
  onSave: () => void;
  onSync: () => void;
  connected: boolean;
}) {
  const [rawValue, setRawValue] = useState("");
  const [amount, setAmount] = useState("1");

  function submitRaw(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit(parseResponseInput(rawValue));
    setRawValue("");
  }

  const amountNumber = Math.max(0, Math.floor(Number(amount) || 0));

  return (
    <section className="panel prompt-panel">
      <header className="panel-header prompt-header">
        <div>
          <h2>Action</h2>
          <p>{request ? `${readableType(request.type)} for Player ${request.player_id}` : "No pending prompt"}</p>
        </div>
        <div className="prompt-tools">
          <button type="button" className="secondary" disabled={!connected} onClick={onSave}>
            Save
          </button>
          <button type="button" className="secondary" disabled={!connected} onClick={onSync}>
            Sync
          </button>
        </div>
      </header>
      {request ? (
        <>
          <PromptControls
            request={request}
            amount={amount}
            amountNumber={amountNumber}
            onAmountChange={setAmount}
            onSubmit={onSubmit}
          />
          <form className="raw-response" onSubmit={submitRaw}>
            <label>
              Raw response fallback
              <input
                value={rawValue}
                onChange={(event) => setRawValue(event.target.value)}
                placeholder={'Example: "roll", true, null, [1, 20]'}
              />
            </label>
            <button type="submit">Send</button>
          </form>
        </>
      ) : (
        <p className="muted">When the server asks for your decision, controls will appear here.</p>
      )}
    </section>
  );
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
    const choices = asArray(data.choices).map(asRecord);
    return (
      <div className="action-list">
        {choices.map((choice) => {
          const squareId = asNumber(choice.square_id);
          return (
            <button key={squareId} type="button" onClick={() => onSubmit(squareId)}>
              Move to #{squareId} {choice.type ? `(${readableType(asString(choice.type))})` : ""}
            </button>
          );
        })}
        {data.can_undo === true && (
          <button type="button" className="secondary" onClick={() => onSubmit("undo")}>
            Undo Step
          </button>
        )}
      </div>
    );
  }

  if (request.type === "CONFIRM_STOP") {
    return (
      <div className="action-grid">
        <button type="button" onClick={() => onSubmit(true)}>
          Stop Here
        </button>
        {data.can_undo === true && (
          <button type="button" className="secondary" onClick={() => onSubmit(false)}>
            Undo Step
          </button>
        )}
      </div>
    );
  }

  if (["BUY_SHOP", "FORCED_BUYOUT"].includes(request.type)) {
    return (
      <div className="action-grid">
        <button type="button" onClick={() => onSubmit(true)}>
          Confirm
        </button>
        <button type="button" className="secondary" onClick={() => onSubmit(false)}>
          Decline
        </button>
      </div>
    );
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
    return (
      <div className="action-grid">
        <button type="button" onClick={() => onSubmit("accept")}>
          Accept
        </button>
        <button type="button" className="secondary" onClick={() => onSubmit("reject")}>
          Reject
        </button>
        <button type="button" className="secondary" onClick={() => onSubmit("counter")}>
          Counter
        </button>
      </div>
    );
  }

  return (
    <div className="request-data">
      <p className="muted">This prompt is available through the raw response fallback for now.</p>
      <pre>{JSON.stringify(request.data, null, 2)}</pre>
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
