import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const styles = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");

function rules(selector: string): string[] {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const matches = [...styles.matchAll(new RegExp(`^${escaped}\\s*\\{`, "gm"))];
  assert.ok(matches.length > 0, `missing CSS rule for ${selector}`);
  return matches.map((match) => {
    const bodyStart = styles.indexOf("{", match.index) + 1;
    const bodyEnd = styles.indexOf("}", bodyStart);
    return styles.slice(bodyStart, bodyEnd);
  });
}

function hasDeclaration(selector: string, property: string, value: string): void {
  const escapedProperty = property.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const escapedValue = value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const declaration = new RegExp(`${escapedProperty}\\s*:\\s*${escapedValue}\\s*;`);
  assert.ok(
    rules(selector).some((body) => declaration.test(body)),
    `${selector} should declare ${property}: ${value}`,
  );
}

test("stock exchange uses the readable 1280x720 typography contract", () => {
  hasDeclaration(".stock-district-header", "font-size", "13px");
  hasDeclaration(".stock-district-row strong", "font-size", "16px");
  hasDeclaration(".stock-district-row span", "font-size", "16px");

  hasDeclaration(".stock-shop-owner span", "font-size", "13px");
  hasDeclaration(".stock-shop-owner strong", "font-size", "15px");
  hasDeclaration(".stock-shop-card dt", "font-size", "13px");
  hasDeclaration(".stock-shop-card dd", "font-size", "15px");

  hasDeclaration(".stock-transaction-math dt", "font-size", "14px");
  hasDeclaration(".stock-transaction-math dd", "font-size", "16px");
  hasDeclaration(".stock-transaction-math > div:first-child dd", "font-size", "18px");
  hasDeclaration(".stock-keyboard-help p", "font-size", "13px");
});

test("stock typography changes preserve the fixed layout footprint", () => {
  hasDeclaration(".stock-overlay-shell", "width", "min(1120px, 100%)");
  hasDeclaration(".stock-overlay-main", "grid-template-columns", "minmax(0, 1fr) 270px");
  hasDeclaration(".stock-district-row", "min-height", "43px");
  hasDeclaration(
    ".stock-shop-strip",
    "grid-template-columns",
    "repeat(auto-fit, minmax(138px, 1fr))",
  );
});
