import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import {
  getStopConfirmationActions,
  StopConfirmationControls,
} from "../src/StopConfirmationControls.tsx";
import { type InputRequest } from "../src/protocol.ts";

function request(canUndo: boolean): InputRequest {
  return {
    type: "CONFIRM_STOP",
    player_id: 0,
    data: { square_id: 9, can_undo: canUndo },
  };
}

test("stop confirmation exposes explicit pointer actions without key hints", () => {
  assert.deepEqual(getStopConfirmationActions(request(true)), [
    {
      label: "Stop Here",
      description: "End your move on Square #9",
      value: true,
    },
    {
      label: "Undo Step",
      description: "Return to your previous square",
      value: false,
    },
  ]);

  const markup = renderToStaticMarkup(
    <StopConfirmationControls
      request={request(true)}
      responsePending={false}
      onSubmit={() => undefined}
    />,
  );

  assert.match(markup, />Stop Here</);
  assert.match(markup, />Undo Step</);
  assert.match(markup, /aria-label="Stop Here\. End your move on Square #9"/);
  assert.match(markup, /aria-label="Undo Step\. Return to your previous square"/);
  assert.doesNotMatch(markup, /keycap/);
});

test("stop confirmation omits unavailable undo and disables controls while resolving", () => {
  const markup = renderToStaticMarkup(
    <StopConfirmationControls
      request={request(false)}
      responsePending={true}
      onSubmit={() => undefined}
    />,
  );

  assert.match(markup, />Stop Here</);
  assert.doesNotMatch(markup, />Undo Step</);
  assert.match(markup, /disabled=""/);
});
