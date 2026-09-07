import assert from "node:assert/strict";
import test from "node:test";
import { presentedState, beatTiming } from "../src/presentationTiming.ts";
import { completePresentation, enqueuePresentation, resolvePresentation, type PresentationState } from "../src/presentationQueue.ts";
import type { GameState } from "../src/protocol.ts";

const before = {
  current_player_index: 0,
  players: [0, 1, 2].map((player_id) => ({ player_id, ready_cash: 1000, position: 0, suits: {}, owned_properties: [], owned_stock: {} })),
  board: { squares: [] }, stock: { stocks: [] },
} as unknown as GameState;
const after = { ...before, players: before.players.map((p, i) => ({ ...p, ready_cash: [918, 1094, 1003][i] })) };
const beat: PresentationState = { requestId: "rent", type: "rent_payment", playerId: 0,
  coordinated: true, requiresAcknowledgment: true, acknowledgmentPending: false, before, after,
  data: { rent_cash: { 0: 911, 1: 1089, 2: 1000 }, dividends: [{ player_id: 0, amount: 7 }] } };

test("rent shows original balances, then actual rent, then dividend endpoints", () => {
  const cash = (time: number) => presentedState(beat, time)!.players.map((p) => p.ready_cash);
  assert.deepEqual(cash(0), [1000, 1000, 1000]);
  assert.deepEqual(cash(1450), [911, 1089, 1000]);
  assert.deepEqual(cash(2350), [918, 1094, 1003]);
  assert.deepEqual(before.players.map((p) => p.ready_cash), [1000, 1000, 1000]);
});

test("network resolution cannot remove a still-rendering result", () => {
  const resolved = resolvePresentation([beat], "rent");
  assert.equal(resolved.length, 1);
  assert.equal(resolved[0].serverResolved, true);
  assert.deepEqual(completePresentation(resolved, "rent"), []);
  assert.deepEqual(resolvePresentation(completePresentation([beat], "rent"), "rent"), []);
});

test("coordinated card cannot discard the suit preceding it", () => {
  const suit = { ...beat, requestId: "suit", type: "suit_collected", requiresAcknowledgment: false };
  const card = { ...beat, requestId: "card", type: "venture_card_revealed" };
  assert.deepEqual(enqueuePresentation([suit], card).map((p) => p.requestId), ["suit", "card"]);
  assert.deepEqual(resolvePresentation([suit, card], "stale"), [suit, card]);
});

test("ordinary steps have no extra reading hold; arrival has a distinct settle", () => {
  const step = beatTiming({ ...beat, type: "piece_moved", data: { remaining: 2 } });
  const arrival = beatTiming({ ...beat, type: "piece_moved", data: { remaining: 0 } });
  assert.equal(step.auto, 0);
  assert.equal(step.exit, 0);
  assert(arrival.reveal > step.reveal);
  assert.deepEqual(step.motion, ["piece", "camera"]);
});


test("older suit beats release immediately with no animation or extra hold", () => {
  const pickup = { ...beat, type: "suit_collected", requiresAcknowledgment: false };
  assert.equal(presentedState(pickup, 0), after);
  assert.deepEqual(beatTiming(pickup), { reveal: 0, human: 0, auto: 0, exit: 0, motion: [] });
});
