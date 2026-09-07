import { createContext, useCallback, useEffect, useRef, useState } from "react";
import type { PresentationState } from "./presentationQueue";
import { automaticBeat, beatTiming, presentedState } from "./presentationTiming";

export const PresentationMotionContext = createContext<{
  beat: PresentationState | null; complete: (part: string, requestId?: string) => void;
}>({ beat: null, complete: () => {} });

export function usePresentationDirector(beat: PresentationState | null, playerId: number | null,
  finish: (requestId: string) => void, acknowledge: (requestId: string) => void) {
  const latest = useRef({ beat, finish, acknowledge });
  latest.current = { beat, finish, acknowledge };
  const clock = useRef({ id: "", elapsed: 0, readableAt: -1, exitAt: -1, done: false, motion: new Set<string>() });
  const [frame, setFrame] = useState({ id: "", elapsed: 0, readableAt: -1, exitAt: -1, done: false });
  const complete = useCallback((part: string, requestId?: string) => {
    if (!requestId || requestId === clock.current.id) clock.current.motion.add(part);
  }, []);

  useEffect(() => {
    if (!beat?.coordinated) return;
    const c = { id: beat.requestId, elapsed: 0, readableAt: -1, exitAt: -1, done: false, motion: new Set<string>() };
    clock.current = c;
    const timing = beatTiming(beat);
    let previous = performance.now(), painted = -Infinity, raf = 0;
    const trace = (phase: string) => {
      if (new URLSearchParams(location.search).has("pacingTrace")) {
        window.dispatchEvent(new CustomEvent("rtr:pacing", { detail: { id: c.id, type: beat.type, phase, elapsed: c.elapsed, revision: beat.revision } }));
        console.debug("[pacing]", beat.type, phase, Math.round(c.elapsed));
      }
    };
    trace("enter");
    const tick = (now: number) => {
      if (document.visibilityState !== "hidden") c.elapsed += Math.min(100, now - previous);
      previous = now;
      const current = latest.current.beat;
      const owner = beat.playerId === playerId;
      // Motion comes from rendered components, with a bounded recovery for a lost renderer.
      const motionDone = timing.motion.every((part) => c.motion.has(part)) || c.elapsed >= timing.reveal + 4000;
      if (c.readableAt < 0 && c.elapsed >= timing.reveal && motionDone) {
        c.readableAt = c.elapsed; trace("readable");
      }
      const auto = automaticBeat(beat);
      const readHold = auto ? timing.auto : owner ? timing.human : timing.auto;
      const readable = c.readableAt >= 0 && c.elapsed >= c.readableAt + readHold;
      if (c.exitAt < 0 && readable && (auto || !owner || current?.acknowledgmentPending)) {
        c.exitAt = c.elapsed; trace("exit");
      }
      if (c.exitAt >= 0 && c.elapsed >= c.exitAt + timing.exit && !c.done) {
        c.done = true; trace("complete");
        if (auto && beat.requiresAcknowledgment && owner) latest.current.acknowledge(c.id);
        latest.current.finish(c.id);
      }
      if (now - painted >= 40 || c.done) {
        setFrame({ ...c }); painted = now;
      }
      if (!c.done) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [beat?.requestId, beat?.coordinated, playerId]);

  if (!beat?.coordinated) return { beat, displayState: undefined, motion: { beat: null, complete } };
  const f = frame.id === beat.requestId ? frame : { elapsed: 0, readableAt: -1, exitAt: -1, done: false };
  const canContinue = f.readableAt >= 0 && f.elapsed >= f.readableAt + beatTiming(beat).human && f.exitAt < 0;
  const phase = f.done ? "complete" : f.exitAt >= 0 ? "exit" : f.readableAt >= 0 ? "readable" : "enter";
  const presented: PresentationState = { ...beat, elapsed: f.elapsed, canContinue, phase };
  return { beat: presented, displayState: presentedState(beat, f.elapsed), motion: { beat: presented, complete } };
}
