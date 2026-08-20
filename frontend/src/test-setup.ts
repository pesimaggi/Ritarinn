/**
 * Vitest setup.
 *
 * jsdom does not implement the layout APIs CodeMirror uses for measurement.
 * The stubs below let the editor mount and run its state logic in tests; they
 * do not affect the browser build.
 */

import "@testing-library/dom";

if (!("Range" in globalThis)) {
  // Nothing to patch in this environment.
} else {
  Range.prototype.getBoundingClientRect =
    Range.prototype.getBoundingClientRect ??
    (() => ({ top: 0, left: 0, bottom: 0, right: 0, width: 0, height: 0 }) as DOMRect);
  Range.prototype.getClientRects =
    Range.prototype.getClientRects ??
    (() => Object.assign([], { item: () => null }) as unknown as DOMRectList);
}
