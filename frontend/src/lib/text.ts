/**
 * Small text helpers.
 */

/**
 * Count words in Icelandic text.
 *
 * Splits on Unicode whitespace only. Hyphenated compounds ("Vestur-Íslendingur")
 * count as one word, which matches how the count is read in an Icelandic
 * editor, and the Icelandic letters á é í ó ú ý þ æ ö ð need no special case
 * because nothing here inspects individual characters.
 */
export function countWords(text: string): number {
  const trimmed = text.trim();
  if (trimmed === "") return 0;
  return trimmed.split(/\s+/u).length;
}

/**
 * Replace a range using UTF-16 offsets, the same coordinates the backend emits.
 *
 * Used by tests and by any code path that needs to apply a correction outside
 * the editor. `String.prototype.slice` is already UTF-16 indexed, so this is a
 * thin wrapper — its value is that it names the convention.
 */
export function applyReplacement(
  text: string,
  startChar: number,
  endChar: number,
  replacement: string,
): string {
  return text.slice(0, startChar) + replacement + text.slice(endChar);
}
