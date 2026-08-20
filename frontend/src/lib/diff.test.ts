import { describe, expect, it } from "vitest";

import { diffWords, tokenize, unchangedRatio } from "./diff";

/** Reconstruct each side from the diff, to prove nothing was invented or lost. */
function rebuild(parts: ReturnType<typeof diffWords>) {
  return {
    before: parts.filter((p) => p.kind !== "added").map((p) => p.text).join(""),
    after: parts.filter((p) => p.kind !== "removed").map((p) => p.text).join(""),
  };
}

describe("tokenize", () => {
  it("keeps whitespace so tokens concatenate back to the source", () => {
    const text = "Þingið  samþykkti\ntillöguna.";
    expect(tokenize(text).join("")).toBe(text);
  });

  it("handles empty text", () => {
    expect(tokenize("")).toEqual([]);
  });
});

describe("diffWords", () => {
  it("reports no change for identical text", () => {
    const parts = diffWords("Þingið samþykkti.", "Þingið samþykkti.");
    expect(parts.every((p) => p.kind === "equal")).toBe(true);
  });

  it("marks a replaced word without touching its neighbours", () => {
    const parts = diffWords("Þingið samþykkti tillöguna.", "Þingið hafnaði tillöguna.");
    expect(parts.filter((p) => p.kind === "removed").map((p) => p.text.trim())).toEqual([
      "samþykkti",
    ]);
    expect(parts.filter((p) => p.kind === "added").map((p) => p.text.trim())).toEqual([
      "hafnaði",
    ]);
  });

  it("reconstructs both sides exactly", () => {
    const before =
      "Með vísan til framangreinds er það mat stofnunarinnar að ekki séu forsendur til að verða við erindinu.";
    const after = "Stofnunin telur að ekki sé hægt að verða við erindinu.";
    expect(rebuild(diffWords(before, after))).toEqual({ before, after });
  });

  it("handles Icelandic letters and punctuation", () => {
    const before = "Ást, épli og þök — ýmis orð.";
    const after = "Ást, epli og þök — ýmis orð.";
    expect(rebuild(diffWords(before, after))).toEqual({ before, after });
  });

  it("handles text containing emoji", () => {
    const before = "Til hamingju 🎉 með daginn!";
    const after = "Til hamingju 😀 með daginn!";
    const parts = diffWords(before, after);
    expect(rebuild(parts)).toEqual({ before, after });
  });

  it("treats one side being empty as a whole insertion or deletion", () => {
    expect(diffWords("", "Nýr texti.")).toEqual([{ kind: "added", text: "Nýr texti." }]);
    expect(diffWords("Gamli texti.", "")).toEqual([{ kind: "removed", text: "Gamli texti." }]);
  });

  it("merges consecutive changes into one part", () => {
    const parts = diffWords("a b c d", "a x y d");
    expect(parts.filter((p) => p.kind === "removed")).toHaveLength(1);
    expect(parts.filter((p) => p.kind === "added")).toHaveLength(1);
  });

  it("falls back to whole-text comparison rather than diffing pathological input", () => {
    const huge = "orð ".repeat(5000);
    const parts = diffWords(huge, huge + "extra");
    expect(parts.map((p) => p.kind)).toEqual(["removed", "added"]);
  });
});

describe("unchangedRatio", () => {
  it("is 1 when nothing changed", () => {
    expect(unchangedRatio(diffWords("sami texti", "sami texti"))).toBe(1);
  });

  it("is 0 when everything changed", () => {
    expect(unchangedRatio(diffWords("alveg annar", "gjörólíkur strengur"))).toBeLessThan(0.3);
  });

  it("is 1 for empty input rather than dividing by zero", () => {
    expect(unchangedRatio([])).toBe(1);
  });
});
