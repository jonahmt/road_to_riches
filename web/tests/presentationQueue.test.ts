import assert from "node:assert/strict";
import test from "node:test";

import {
  dismissNonblockingPresentation,
  enqueuePresentation,
  markPresentationAcknowledging,
  resolvePresentation,
  type PresentationState,
} from "../src/presentationQueue.ts";

function presentation(
  requestId: string,
  requiresAcknowledgment = true,
): PresentationState {
  return {
    requestId,
    type: "venture_card_revealed",
    playerId: 0,
    data: {},
    acknowledgmentPending: false,
    requiresAcknowledgment,
  };
}

test("presentation queue is FIFO and deduplicates reconnect replay", () => {
  const first = presentation("one");
  const second = presentation("two");
  const queue = enqueuePresentation(enqueuePresentation([], first), second);

  assert.deepEqual(enqueuePresentation(queue, first), queue);
  assert.deepEqual(queue.map((item) => item.requestId), ["one", "two"]);
});

test("acknowledgment stays mounted until server resolution", () => {
  const queue = markPresentationAcknowledging([presentation("one")], "one");

  assert.equal(queue[0].acknowledgmentPending, true);
  assert.deepEqual(dismissNonblockingPresentation(queue, "one"), queue);
  assert.deepEqual(resolvePresentation(queue, "one"), []);
});

test("legacy nonblocking presentations can be dismissed locally", () => {
  assert.deepEqual(
    dismissNonblockingPresentation([presentation("legacy", false)], "legacy"),
    [],
  );
});
