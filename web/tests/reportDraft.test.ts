import assert from "node:assert/strict";
import test from "node:test";

import {
  MAX_REPORT_IMAGE_BYTES,
  attachmentFromDataUrl,
  canSubmitReport,
  validateReportImage,
} from "../src/reportDraft.ts";
import { decode, encode } from "../src/protocol.ts";
import { reportResultState } from "../src/reportSubmission.ts";

test("report image validation accepts supported images within the size limit", () => {
  assert.equal(
    validateReportImage({ name: "turn.webp", size: MAX_REPORT_IMAGE_BYTES, type: "image/webp" }),
    null,
  );
  assert.match(
    validateReportImage({ name: "turn.svg", size: 100, type: "image/svg+xml" }) ?? "",
    /PNG, JPEG, or WebP/,
  );
  assert.match(
    validateReportImage({ name: "huge.png", size: MAX_REPORT_IMAGE_BYTES + 1, type: "image/png" }) ?? "",
    /10 MiB/,
  );
});

test("the report form requires meaningful copy and cannot double-submit", () => {
  assert.equal(canSubmitReport("Summary", "Description", "idle"), true);
  assert.equal(canSubmitReport("   ", "Description", "idle"), false);
  assert.equal(canSubmitReport("Summary", "   ", "idle"), false);
  assert.equal(canSubmitReport("Summary", "Description", "submitting"), false);
});

test("data URL conversion strips the prefix and rejects mismatched MIME types", () => {
  assert.deepEqual(
    attachmentFromDataUrl(
      { name: "board.png", size: 3, type: "image/png" },
      "data:image/png;base64,YWJj",
    ),
    {
      filename: "board.png",
      mime_type: "image/png",
      data_base64: "YWJj",
    },
  );
  assert.equal(
    attachmentFromDataUrl(
      { name: "board.png", size: 3, type: "image/png" },
      "data:image/jpeg;base64,YWJj",
    ),
    null,
  );
});

test("report protocol preserves optional evidence and server result identifiers", () => {
  assert.deepEqual(
    JSON.parse(
      encode({
        msg: "submit_report",
        category: "bug",
        priority: 1,
        summary: "Board is stuck",
        description: "The movement prompt never clears.",
        include_game_state: true,
        restart_requested: false,
        game_id: "default",
      }),
    ),
    {
      msg: "submit_report",
      category: "bug",
      priority: 1,
      summary: "Board is stuck",
      description: "The movement prompt never clears.",
      include_game_state: true,
      restart_requested: false,
      game_id: "default",
    },
  );
  assert.deepEqual(decode('{"msg":"report_result","success":true,"issue_id":"rtr-123"}'), {
    msg: "report_result",
    success: true,
    issue_id: "rtr-123",
  });
});

test("report submission result keeps a useful hook state for success and failure", () => {
  assert.deepEqual(reportResultState({ success: true, issue_id: "rtr-123" }), {
    status: "success",
    issueId: "rtr-123",
  });
  assert.deepEqual(reportResultState({ success: false, error: "Beads unavailable" }), {
    status: "error",
    error: "Beads unavailable",
  });
});
