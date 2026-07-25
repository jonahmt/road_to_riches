import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

test("promotion suit row shows symbols only while retaining its accessible name", async (context) => {
  const vite = await createServer({
    appType: "custom",
    server: { middlewareMode: true },
  });
  context.after(() => vite.close());

  const {
    PROMOTION_SUITS_ACCESSIBLE_LABEL,
    PromotionSuitRow,
  } = await vite.ssrLoadModule("/src/PromotionSuitRow.tsx");
  const markup = renderToStaticMarkup(
    React.createElement(PromotionSuitRow, {
      getSuitColor: (suit) => `color-${suit.toLowerCase()}`,
      renderSuitIcon: (suit) => React.createElement("svg", { "data-suit": suit }),
    }),
  );

  assert.match(
    markup,
    new RegExp(`aria-label="${PROMOTION_SUITS_ACCESSIBLE_LABEL}"`),
  );
  assert.equal((markup.match(/data-suit=/g) ?? []).length, 4);
  assert.match(markup, /data-suit="SPADE"/);
  assert.match(markup, /data-suit="HEART"/);
  assert.match(markup, /data-suit="DIAMOND"/);
  assert.match(markup, /data-suit="CLUB"/);
  assert.doesNotMatch(markup, /<small/);
  assert.doesNotMatch(markup, />Spade</);
  assert.doesNotMatch(markup, />Heart</);
  assert.doesNotMatch(markup, />Diamond</);
  assert.doesNotMatch(markup, />Club</);
});
