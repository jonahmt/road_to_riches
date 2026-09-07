import { useEffect, useRef } from "react";
import { getWasdResponseMap } from "./controls";
import { projectMovementRequest, type BoardProjector } from "./board3d/geometry";
import { MovementInput } from "./movementInput";
import type { InputRequest } from "./protocol";
import type { PresentationState } from "./presentationQueue";

export function useMovementControls(request: InputRequest | null, beat: PresentationState | null,
  responsePending: boolean, suspended: boolean, playerId: number | null,
  submit: (value: unknown) => boolean, projector: { current: BoardProjector | null }) {
  const buffer = useRef(new MovementInput());
  const session = useRef(false);
  const consumed = useRef<InputRequest | null>(null);
  const chordTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latest = useRef({ request, beat, responsePending, suspended, playerId, submit });
  latest.current = { request, beat, responsePending, suspended, playerId, submit };

  function clearInput() {
    buffer.current.clear();
    if (chordTimer.current !== null) clearTimeout(chordTimer.current);
    chordTimer.current = null;
  }
  function reset() { clearInput(); session.current = false; }
  function drain() {
    const state = latest.current;
    if (!session.current || state.suspended || state.beat || state.responsePending || chordTimer.current !== null
      || state.request?.type !== "CHOOSE_PATH" || consumed.current === state.request) return;
    const value = buffer.current.next(getWasdResponseMap(projectMovementRequest(state.request, projector.current)));
    if (value !== undefined && state.submit(value)) consumed.current = state.request;
  }

  useEffect(() => {
    if (suspended || (request && (request.type !== "CHOOSE_PATH" || request.player_id !== playerId))
      || (beat && (beat.type !== "piece_moved" || beat.playerId !== playerId || beat.data.remaining === 0))) reset();
    else if (request?.type === "CHOOSE_PATH") session.current = true;
    drain();
  }, [request, beat?.requestId, responsePending, suspended, playerId]);

  useEffect(() => {
    function keyDown(event: KeyboardEvent) {
      const key = event.key.toLowerCase();
      if (!session.current || latest.current.suspended || !"wasd".includes(key) || key.length !== 1
        || event.repeat || event.altKey || event.ctrlKey || event.metaKey) return;
      const target = event.target;
      if (document.body.dataset.gameplayHotkeysSuppressed === "true" ||
        (target instanceof HTMLElement && (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)))) {
        clearInput(); return;
      }
      event.preventDefault();
      buffer.current.press(key);
      if (chordTimer.current !== null) { clearTimeout(chordTimer.current); chordTimer.current = null; drain(); return; }
      const current = latest.current.request;
      const mapping = current ? getWasdResponseMap(projectMovementRequest(current, projector.current)) : {};
      if (!latest.current.responsePending && !latest.current.beat &&
        Object.keys(mapping).some((candidate) => candidate.length > 1 && candidate.includes(key))) {
        chordTimer.current = setTimeout(() => { chordTimer.current = null; drain(); }, 180);
      } else drain();
    }
    function keyUp(event: KeyboardEvent) { buffer.current.release(event.key.toLowerCase()); }
    function visibility() { if (document.hidden) clearInput(); }
    window.addEventListener("keydown", keyDown);
    window.addEventListener("keyup", keyUp);
    window.addEventListener("blur", clearInput);
    document.addEventListener("visibilitychange", visibility);
    return () => {
      reset(); window.removeEventListener("keydown", keyDown); window.removeEventListener("keyup", keyUp);
      window.removeEventListener("blur", clearInput); document.removeEventListener("visibilitychange", visibility);
    };
  }, []);
}
