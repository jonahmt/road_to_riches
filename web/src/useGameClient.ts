import { useCallback, useEffect, useRef, useState } from "react";
import { type GameState, type InputRequest, decode, encode } from "./protocol";

export type ConnectionStatus = "disconnected" | "connecting" | "connected";

export interface DiceState {
  value: number;
  remaining: number;
}

export interface GameClientState {
  status: ConnectionStatus;
  uri: string;
  playerId: number | null;
  gameId: string | null;
  gameState: GameState | null;
  pendingRequest: InputRequest | null;
  logs: string[];
  dice: DiceState | null;
  gameOverWinner: number | null | undefined;
  error: string | null;
}

const MAX_LOGS = 240;

function appendLog(logs: string[], message: string): string[] {
  return [...logs, message].slice(-MAX_LOGS);
}

export function useGameClient(defaultUri: string) {
  const socketRef = useRef<WebSocket | null>(null);
  const playerIdRef = useRef<number | null>(null);
  const gameIdRef = useRef<string | null>(null);
  const [clientState, setClientState] = useState<GameClientState>({
    status: "disconnected",
    uri: defaultUri,
    playerId: null,
    gameId: null,
    gameState: null,
    pendingRequest: null,
    logs: [],
    dice: null,
    gameOverWinner: undefined,
    error: null,
  });

  const disconnect = useCallback(() => {
    socketRef.current?.close();
    socketRef.current = null;
    playerIdRef.current = null;
    gameIdRef.current = null;
    setClientState((current) => ({
      ...current,
      status: "disconnected",
      playerId: null,
      gameId: null,
      pendingRequest: null,
    }));
  }, []);

  const send = useCallback((message: Parameters<typeof encode>[0]) => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setClientState((current) => ({
        ...current,
        error: "WebSocket is not connected.",
      }));
      return;
    }
    socket.send(encode(message));
  }, []);

  const connect = useCallback(
    (uri: string) => {
      disconnect();
      setClientState((current) => ({
        ...current,
        uri,
        status: "connecting",
        playerId: null,
        gameId: null,
        gameState: null,
        pendingRequest: null,
        logs: [],
        dice: null,
        gameOverWinner: undefined,
        error: null,
      }));

      const socket = new WebSocket(uri);
      socketRef.current = socket;

      socket.addEventListener("open", () => {
        setClientState((current) => ({
          ...current,
          status: "connected",
          logs: appendLog(current.logs, `Connected to ${uri}`),
        }));
      });

      socket.addEventListener("message", (event) => {
        const message = decode(String(event.data));
        setClientState((current) => {
          switch (message.msg) {
            case "assign_player": {
              playerIdRef.current = message.player_id;
              gameIdRef.current = message.game_id ?? null;
              return {
                ...current,
                playerId: message.player_id,
                gameId: message.game_id ?? null,
                logs: appendLog(
                  current.logs,
                  `Assigned Player ${message.player_id}${message.game_id ? ` in ${message.game_id}` : ""}`,
                ),
              };
            }
            case "state_sync":
              return {
                ...current,
                gameId: message.game_id ?? current.gameId,
                gameState: message.state,
              };
            case "input_request": {
              const request: InputRequest = {
                type: message.type,
                player_id: message.player_id,
                data: message.data ?? {},
              };
              return {
                ...current,
                pendingRequest:
                  playerIdRef.current === null || playerIdRef.current === message.player_id
                    ? request
                    : current.pendingRequest,
              };
            }
            case "log":
              return {
                ...current,
                logs: appendLog(current.logs, message.text),
              };
            case "log_retract":
              return {
                ...current,
                logs: current.logs.slice(0, Math.max(0, current.logs.length - message.count)),
              };
            case "ui_notification":
              return current;
            case "dice":
              return {
                ...current,
                dice: { value: message.value, remaining: message.remaining },
              };
            case "game_over":
              return {
                ...current,
                gameOverWinner: message.winner,
                pendingRequest: null,
                logs: appendLog(current.logs, `Game over. Winner: Player ${message.winner ?? "none"}`),
              };
            case "save_result":
              return {
                ...current,
                logs: appendLog(
                  current.logs,
                  message.success
                    ? `Game saved to ${message.path ?? "server save path"}`
                    : `Save failed: ${message.error ?? "unknown error"}`,
                ),
              };
            case "error":
              return {
                ...current,
                error: message.error,
                logs: appendLog(current.logs, `Error: ${message.error}`),
              };
            case "game_created":
            case "joined_game":
            case "games_list":
            case "game_starting":
              return current;
          }
        });
      });

      socket.addEventListener("close", () => {
        socketRef.current = null;
        setClientState((current) => ({
          ...current,
          status: "disconnected",
          pendingRequest: null,
          logs: appendLog(current.logs, "Disconnected from server"),
        }));
      });

      socket.addEventListener("error", () => {
        setClientState((current) => ({
          ...current,
          error: "WebSocket connection error.",
          logs: appendLog(current.logs, "WebSocket connection error."),
        }));
      });
    },
    [disconnect],
  );

  const submitResponse = useCallback(
    (value: unknown) => {
      send({
        msg: "input_response",
        value,
        player_id: playerIdRef.current ?? undefined,
        game_id: gameIdRef.current ?? undefined,
      });
      setClientState((current) => ({
        ...current,
        pendingRequest: null,
      }));
    },
    [send],
  );

  const saveGame = useCallback(
    (saveName?: string) => {
      send({
        msg: "save_game",
        player_id: playerIdRef.current ?? undefined,
        save_name: saveName,
        game_id: gameIdRef.current ?? undefined,
      });
    },
    [send],
  );

  const requestSync = useCallback(() => {
    send({
      msg: "sync_request",
      game_id: gameIdRef.current ?? undefined,
    });
  }, [send]);

  useEffect(() => disconnect, [disconnect]);

  return {
    clientState,
    connect,
    disconnect,
    submitResponse,
    saveGame,
    requestSync,
  };
}
