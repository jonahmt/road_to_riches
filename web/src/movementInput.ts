import type { WasdResponseMap } from "./controls.ts";

/** Buffer directions, never square IDs: each hop uses the next server prompt. */
export class MovementInput {
  private taps: string[] = [];
  private held = new Set<string>();

  press(key: string) {
    if (this.held.has(key)) return;
    this.held.add(key);
    if (this.taps.length < 9) this.taps.push(key);
  }

  release(key: string) { this.held.delete(key); }

  clear() { this.taps = []; this.held.clear(); }

  next(mapping: WasdResponseMap): number | "undo" | undefined {
    const explicit = this.taps.length > 0;
    let key = this.taps.shift();
    if (key && this.taps.length) {
      const pair = key + this.taps[0];
      const combo = [pair, [...pair].reverse().join("")].find((candidate) => candidate in mapping);
      if (combo) { key = combo; this.taps.shift(); }
    }
    if (!key) key = Object.keys(mapping).sort((a, b) => b.length - a.length)
      .find((candidate) => [...candidate].every((part) => this.held.has(part)));
    const value = key ? mapping[key] : undefined;
    // Holding a direction must never turn into an accidental undo after a bend.
    if (typeof value !== "number" && !(explicit && value === "undo")) {
      this.clear();
      return undefined;
    }
    if (value === "undo") this.clear();
    return value;
  }
}
