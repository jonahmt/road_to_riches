import { useCallback, useEffect, useRef, useState } from "react";
import {
  PLAYER_CONTROL_REPLACED_CLOSE_CODE,
  playerControlReplacementReason,
  slowClientCloseReason,
} from "./connectionClose";
import { type GameState, type InputRequest, decode, encode } from "./protocol";
import {
  dismissNonblockingPresentation,
  enqueuePresentation,
  markPresentationAcknowledging,
  resolvePresentation,
  type PresentationState,
} from "./presentationQueue";

export type { PresentationState } from "./presentationQueue";

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
  presentations: PresentationState[];
  gameOverWinner: number | null | undefined;
  responsePending: boolean;
  error: string | null;
}

const MAX_LOGS = 240;
const LOCAL_DEFAULT_GAME_ID = "default";
const LOCAL_DEFAULT_PLAYER_ID = 0;

function appendLog(logs: string[], message: string): string[] {
  return [...logs, message].slice(-MAX_LOGS);
}

function shouldClaimLocalDefaultPlayer(uri: string): boolean {
  try {
    const parsed = new URL(uri);
    return ["localhost", "127.0.0.1", "::1", "[::1]"].includes(parsed.hostname);
  } catch {
    return uri.includes("localhost") || uri.includes("127.0.0.1");
  }
}

function closeSocket(socket: WebSocket | null): Promise<void> {
  if (!socket || socket.readyState === WebSocket.CLOSED) {
    return Promise.resolve();
  }

  return new Promise((resolve) => {
    let timeoutId: number | null = null;
    const finish = () => {
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
      socket.removeEventListener("close", finish);
      resolve();
    };

    socket.addEventListener("close", finish, { once: true });
    timeoutId = window.setTimeout(finish, 750);

    if (socket.readyState !== WebSocket.CLOSING) {
      socket.close();
    }
  });
}

export function useGameClient(defaultUri: string) {
  const socketRef = useRef<WebSocket | null>(null);
  const connectionIdRef = useRef(0);
  const playerIdRef = useRef<number | null>(null);
  const gameIdRef = useRef<string | null>(null);
  const responsePendingRef = useRef(false);
  const notificationIdRef = useRef(0);
  const presentationAckPendingRef = useRef(new Set<string>());
  const [clientState, setClientState] = useState<GameClientState>({
    status: "disconnected",
    uri: defaultUri,
    playerId: null,
    gameId: null,
    gameState: null,
    pendingRequest: null,
    logs: [],
    dice: null,
    presentations: [],
    gameOverWinner: undefined,
    responsePending: false,
    error: null,
  });

  const disconnect = useCallback(() => {
    connectionIdRef.current += 1;
    void closeSocket(socketRef.current);
    socketRef.current = null;
    playerIdRef.current = null;
    gameIdRef.current = null;
    responsePendingRef.current = false;
    presentationAckPendingRef.current.clear();
    setClientState((current) => ({
      ...current,
      status: "disconnected",
      playerId: null,
      gameId: null,
      gameState: null,
      pendingRequest: null,
      dice: null,
      presentations: [],
      gameOverWinner: undefined,
      responsePending: false,
    }));
  }, []);

  const send = useCallback((message: Parameters<typeof encode>[0]) => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setClientState((current) => ({
        ...current,
        error: "WebSocket is not connected.",
      }));
      return false;
    }
    socket.send(encode(message));
    return true;
  }, []);

  const connect = useCallback(
    async (uri: string) => {
      const connectionId = connectionIdRef.current + 1;
      connectionIdRef.current = connectionId;
      const previousSocket = socketRef.current;
      socketRef.current = null;
      playerIdRef.current = null;
      gameIdRef.current = null;
      responsePendingRef.current = false;
      presentationAckPendingRef.current.clear();
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
        presentations: [],
        gameOverWinner: undefined,
        responsePending: false,
        error: null,
      }));

      await closeSocket(previousSocket);
      if (connectionIdRef.current !== connectionId) {
        return;
      }

      const socket = new WebSocket(uri);
      socketRef.current = socket;
      const isCurrentSocket = () => socketRef.current === socket && connectionIdRef.current === connectionId;

      socket.addEventListener("open", () => {
        if (!isCurrentSocket()) {
          return;
        }
        setClientState((current) => ({
          ...current,
          status: "connected",
          logs: appendLog(current.logs, `Connected to ${uri}`),
        }));
        if (shouldClaimLocalDefaultPlayer(uri)) {
          socket.send(
            encode({
              msg: "claim_player",
              player_id: LOCAL_DEFAULT_PLAYER_ID,
              game_id: LOCAL_DEFAULT_GAME_ID,
              force: true,
            }),
          );
        }
      });

      socket.addEventListener("message", (event) => {
        if (!isCurrentSocket()) {
          return;
        }
        const message = decode(String(event.data));
        if (message.msg === "input_rejected" && message.ownership_lost) {
          const reason = message.error || "This browser no longer controls the active player.";
          playerIdRef.current = null;
          gameIdRef.current = null;
          responsePendingRef.current = false;
          presentationAckPendingRef.current.clear();
          setClientState((current) => ({
            ...current,
            status: "disconnected",
            playerId: null,
            gameId: null,
            gameState: null,
            pendingRequest: null,
            dice: null,
            presentations: [],
            gameOverWinner: undefined,
            responsePending: false,
            error: reason,
            logs: appendLog(current.logs, `Control lost: ${reason}`),
          }));
          if (socket.readyState === WebSocket.OPEN) {
            socket.close(PLAYER_CONTROL_REPLACED_CLOSE_CODE, reason);
          }
          return;
        }
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
              responsePendingRef.current = false;
              const request: InputRequest = {
                type: message.type,
                player_id: message.player_id,
                data: message.data ?? {},
              };
              const isAssignedPrompt = playerIdRef.current === null || playerIdRef.current === message.player_id;
              return {
                ...current,
                pendingRequest: isAssignedPrompt ? request : null,
                responsePending: false,
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
            case "ui_notification": {
              notificationIdRef.current += 1;
              const requestId = `notification:${notificationIdRef.current}`;
              return {
                ...current,
                presentations: enqueuePresentation(current.presentations, {
                  requestId,
                  playerId: Number(message.data?.player_id ?? -1),
                  acknowledgmentPending: false,
                  requiresAcknowledgment: false,
                  type: message.type,
                  data: message.data ?? {},
                }),
              };
            }
            case "presentation_request": {
              return {
                ...current,
                presentations: enqueuePresentation(current.presentations, {
                  requestId: message.request_id,
                  playerId: message.player_id,
                  acknowledgmentPending: presentationAckPendingRef.current.has(message.request_id),
                  requiresAcknowledgment: true,
                  type: message.type,
                  data: message.data ?? {},
                }),
              };
            }
            case "presentation_resolved": {
              presentationAckPendingRef.current.delete(message.request_id);
              return {
                ...current,
                presentations: resolvePresentation(current.presentations, message.request_id),
              };
            }
            case "dice":
              return {
                ...current,
                dice: { value: message.value, remaining: message.remaining },
              };
            case "game_over":
              responsePendingRef.current = false;
              return {
                ...current,
                gameOverWinner: message.winner,
                pendingRequest: null,
                responsePending: false,
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
            case "input_rejected":
              responsePendingRef.current = false;
              return {
                ...current,
                error: message.error,
                responsePending: false,
                logs: appendLog(current.logs, `Response rejected: ${message.error}`),
              };
            case "error":
              responsePendingRef.current = false;
              return {
                ...current,
                error: message.error,
                responsePending: false,
                logs: appendLog(current.logs, `Error: ${message.error}`),
              };
            case "game_created":
              gameIdRef.current = message.game_id;
              return {
                ...current,
                gameId: message.game_id,
                logs: appendLog(current.logs, `Created game ${message.game_id}`),
              };
            case "joined_game":
              playerIdRef.current = message.player_id;
              gameIdRef.current = message.game_id;
              return {
                ...current,
                playerId: message.player_id,
                gameId: message.game_id,
                logs: appendLog(current.logs, `Joined game ${message.game_id} as Player ${message.player_id}`),
              };
            case "games_list":
              return {
                ...current,
                logs: appendLog(current.logs, `Found ${message.games.length} open game${message.games.length === 1 ? "" : "s"}`),
              };
            case "game_starting":
              return {
                ...current,
                gameId: message.game_id,
                logs: appendLog(current.logs, `Game ${message.game_id} is starting`),
              };
          }
        });
      });

      socket.addEventListener("close", (event) => {
        if (!isCurrentSocket()) {
          return;
        }
        const replacementReason = playerControlReplacementReason(event.code, event.reason);
        const slowClientReason = slowClientCloseReason(event.code, event.reason);
        const closeReason = replacementReason ?? slowClientReason;
        socketRef.current = null;
        playerIdRef.current = null;
        gameIdRef.current = null;
        responsePendingRef.current = false;
        presentationAckPendingRef.current.clear();
        setClientState((current) => ({
          ...current,
          status: "disconnected",
          playerId: null,
          gameId: null,
          gameState: null,
          pendingRequest: null,
          dice: null,
          presentations: [],
          gameOverWinner: undefined,
          responsePending: false,
          error: closeReason ?? current.error,
          logs: appendLog(
            current.logs,
            replacementReason
              ? `Control moved: ${replacementReason}`
              : slowClientReason
                ? `Disconnected: ${slowClientReason}`
                : "Disconnected from server",
          ),
        }));
      });

      socket.addEventListener("error", () => {
        if (!isCurrentSocket()) {
          return;
        }
        setClientState((current) => ({
          ...current,
          error: "WebSocket connection error.",
          logs: appendLog(current.logs, "WebSocket connection error."),
        }));
      });
    },
    [],
  );

  const submitResponse = useCallback(
    (value: unknown) => {
      if (responsePendingRef.current) {
        return;
      }
      const sent = send({
        msg: "input_response",
        value,
        player_id: playerIdRef.current ?? undefined,
        game_id: gameIdRef.current ?? undefined,
      });
      if (!sent) {
        return;
      }
      responsePendingRef.current = true;
      setClientState((current) => ({
        ...current,
        responsePending: true,
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

  const acknowledgePresentation = useCallback((requestId: string) => {
    if (presentationAckPendingRef.current.has(requestId)) {
      return;
    }
    const sent = send({
      msg: "presentation_ack",
      request_id: requestId,
      player_id: playerIdRef.current ?? undefined,
      game_id: gameIdRef.current ?? undefined,
    });
    if (!sent) {
      return;
    }
    presentationAckPendingRef.current.add(requestId);
    setClientState((current) => {
      return {
        ...current,
        presentations: markPresentationAcknowledging(current.presentations, requestId),
      };
    });
  }, [send]);

  const dismissPresentation = useCallback((requestId: string) => {
    setClientState((current) => ({
      ...current,
      presentations: dismissNonblockingPresentation(current.presentations, requestId),
    }));
  }, []);

  useEffect(() => disconnect, [disconnect]);

  return {
    clientState,
    connect,
    disconnect,
    submitResponse,
    saveGame,
    requestSync,
    acknowledgePresentation,
    dismissPresentation,
  };
}
