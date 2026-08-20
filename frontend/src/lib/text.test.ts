/**
 * Offset handling on the JavaScript side of the boundary.
 *
 * The backend publishes UTF-16 offsets precisely so these operations are
 * correct without conversion. `tests/backend/test_offsets.py` checks the same
 * property from Python; together they pin both ends of the contract.
 */

import { describe, expect, it } from "vitest";

import { applyReplacement, countWords } from "./text";

describe("countWords", () => {
  it("counts Icelandic words", () => {
    expect(countWords("Þingið samþykkti tillöguna.")).toBe(3);
  });

  it("treats every Icelandic letter as an ordinary word character", () => {
    expect(countWords("ást épli ís ól úr ýmis þök æði öl ðið")).toBe(10);
  });

  it("ignores surrounding and repeated whitespace", () => {
    expect(countWords("  Þingið   samþykkti \n\n tillöguna  ")).toBe(3);
  });

  it("returns zero for empty and whitespace-only text", () => {
    expect(countWords("")).toBe(0);
    expect(countWords("   \n ")).toBe(0);
  });

  it("counts a hyphenated compound as one word", () => {
    expect(countWords("Vestur-Íslendingur kom heim")).toBe(3);
  });
});

describe("applyReplacement", () => {
  it("replaces exactly the given range", () => {
    expect(applyReplacement("Þinngið samþikkti.", 0, 7, "Þingið")).toBe("Þingið samþikkti.");
  });

  it("is correct after an astral-plane character", () => {
    // "🎉" is two UTF-16 units. Backend offsets already account for that, so
    // slicing must not need any adjustment here.
    const text = "🎉 Þinngið";
    const start = text.indexOf("Þinngið");
    expect(start).toBe(3);
    expect(applyReplacement(text, start, text.length, "Þingið")).toBe("🎉 Þingið");
  });

  it("agrees with the offsets the backend computes for Icelandic letters", () => {
    const text = "Ást, épli, ýmis og þök.";
    // Every Icelandic letter is one UTF-16 unit, so JS offsets equal code-point
    // offsets here — the case the backend's identity fast path relies on.
    expect([...text].length).toBe(text.length);
  });
});
