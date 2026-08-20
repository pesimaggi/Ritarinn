/**
 * Word-level diff for reviewing generated text.
 *
 * The user has to be able to see what a rewrite changed before accepting it.
 * A character diff is too noisy for prose — changing "stofnunarinnar" to
 * "stofnunin" would light up half the word — so this compares whole words and
 * keeps the whitespace between them attached, which means the diff can be
 * rendered directly without reconstructing spacing.
 *
 * The algorithm is a straightforward longest-common-subsequence over tokens.
 * Documents here are a few thousand words at most, so the O(n·m) table is
 * cheap, and an exact diff is worth more than a fast approximate one when the
 * user is deciding whether meaning changed.
 */

export type DiffKind = "equal" | "added" | "removed";

export interface DiffPart {
  kind: DiffKind;
  text: string;
}

/**
 * Split into words with their trailing whitespace, so parts concatenate back
 * into the original text exactly.
 */
export function tokenize(text: string): string[] {
  return text.match(/\S+\s*|\s+/gu) ?? [];
}

/** Guard against the quadratic table on pathological input. */
const MAX_TOKENS = 4000;

export function diffWords(before: string, after: string): DiffPart[] {
  if (before === after) {
    return before === "" ? [] : [{ kind: "equal", text: before }];
  }

  const a = tokenize(before);
  const b = tokenize(after);

  if (a.length > MAX_TOKENS || b.length > MAX_TOKENS) {
    // Too large to diff exactly. Showing the two texts whole is honest;
    // showing a wrong diff would not be.
    return [
      { kind: "removed", text: before },
      { kind: "added", text: after },
    ];
  }

  const lcs = buildLcsTable(a, b);
  const parts: DiffPart[] = [];
  let i = 0;
  let j = 0;

  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      push(parts, "equal", a[i]!);
      i += 1;
      j += 1;
    } else if ((lcs[i + 1]?.[j] ?? 0) >= (lcs[i]?.[j + 1] ?? 0)) {
      push(parts, "removed", a[i]!);
      i += 1;
    } else {
      push(parts, "added", b[j]!);
      j += 1;
    }
  }
  while (i < a.length) push(parts, "removed", a[i++]!);
  while (j < b.length) push(parts, "added", b[j++]!);

  return parts;
}

/** Merge into the previous part when the kind matches, to keep runs contiguous. */
function push(parts: DiffPart[], kind: DiffKind, text: string): void {
  const last = parts[parts.length - 1];
  if (last && last.kind === kind) {
    last.text += text;
    return;
  }
  parts.push({ kind, text });
}

function buildLcsTable(a: string[], b: string[]): number[][] {
  // lcs[i][j] = length of the longest common subsequence of a[i:] and b[j:].
  const lcs: number[][] = Array.from({ length: a.length + 1 }, () =>
    new Array<number>(b.length + 1).fill(0),
  );
  for (let i = a.length - 1; i >= 0; i -= 1) {
    for (let j = b.length - 1; j >= 0; j -= 1) {
      lcs[i]![j] =
        a[i] === b[j] ? (lcs[i + 1]![j + 1] ?? 0) + 1 : Math.max(lcs[i + 1]![j] ?? 0, lcs[i]![j + 1] ?? 0);
    }
  }
  return lcs;
}

/** How much of the text the rewrite left alone, as a fraction from 0 to 1. */
export function unchangedRatio(parts: readonly DiffPart[]): number {
  let equal = 0;
  let total = 0;
  for (const part of parts) {
    total += part.text.length;
    if (part.kind === "equal") equal += part.text.length;
  }
  return total === 0 ? 1 : equal / total;
}
