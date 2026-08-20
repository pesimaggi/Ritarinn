/**
 * Key binding regression tests.
 *
 * Redo has to work on all three platforms, and upstream's `historyKeymap`
 * leaves Ctrl+Shift+Z unbound on Windows. These tests pin the bindings and,
 * in particular, that Ctrl+Shift+Z never performs a second undo — the failure
 * mode if an unshifted `Mod-z` binding is ever written ahead of it.
 */

import { describe, expect, it, vi } from "vitest";
import { history, isolateHistory } from "@codemirror/commands";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";

import { ritarinnKeymap } from "./editorKeymap";

function makeView(onProofread = () => {}): EditorView {
  const view = new EditorView({
    state: EditorState.create({ doc: "", extensions: [history(), ritarinnKeymap({ onProofread })] }),
    parent: document.body,
  });
  view.focus();
  return view;
}

/**
 * Dispatch a keystroke the way a real browser reports it.
 *
 * `keyCode` matters: CodeMirror uses it to recover the unshifted key name, and
 * a synthetic event that omits it (jsdom defaults to 0) silently matches no
 * binding at all. Shift is applied to `key` here for the same reason a real
 * keyboard does — Ctrl+Shift+Z reports `key: "Z"`, never `"z"`.
 */
function press(view: EditorView, letter: string, mods: { ctrl?: boolean; shift?: boolean } = {}) {
  const shift = mods.shift ?? false;
  const event = new KeyboardEvent("keydown", {
    key: shift ? letter.toUpperCase() : letter.toLowerCase(),
    code: `Key${letter.toUpperCase()}`,
    keyCode: letter.toUpperCase().charCodeAt(0),
    ctrlKey: mods.ctrl ?? false,
    shiftKey: shift,
    bubbles: true,
    cancelable: true,
  });
  view.contentDOM.dispatchEvent(event);
}

/** Append text as its own undo step. */
function typeText(view: EditorView, text: string) {
  view.dispatch({
    changes: { from: view.state.doc.length, insert: text },
    userEvent: "input.type",
    annotations: isolateHistory.of("before"),
  });
}

describe("ritarinnKeymap", () => {
  it("undoes with Ctrl+Z", () => {
    const view = makeView();
    typeText(view, "Þinngið");
    press(view, "z", { ctrl: true });
    expect(view.state.doc.toString()).toBe("");
    view.destroy();
  });

  it("redoes on Ctrl+Shift+Z, and never undoes a second time", () => {
    // Note: a real browser reports `key: "Z"` (uppercase) when Shift is held.
    // Synthesising `key: "z"` with shiftKey set describes a keystroke no
    // keyboard produces, and CodeMirror resolves it to plain Ctrl+Z.
    const view = makeView();
    typeText(view, "Þinngið");
    typeText(view, " samþikkti");

    press(view, "z", { ctrl: true });
    expect(view.state.doc.toString()).toBe("Þinngið");

    press(view, "z", { ctrl: true, shift: true });
    expect(view.state.doc.toString()).toBe("Þinngið samþikkti");
    view.destroy();
  });

  it("redoes with Ctrl+Y, which is bound on every platform", () => {
    const view = makeView();
    typeText(view, "Þinngið");
    press(view, "z", { ctrl: true });
    expect(view.state.doc.toString()).toBe("");

    press(view, "y", { ctrl: true });
    expect(view.state.doc.toString()).toBe("Þinngið");
    view.destroy();
  });

  it("undoes one step at a time", () => {
    const view = makeView();
    typeText(view, "Þinngið");
    typeText(view, " samþikkti");

    press(view, "z", { ctrl: true });
    expect(view.state.doc.toString()).toBe("Þinngið");

    press(view, "z", { ctrl: true });
    expect(view.state.doc.toString()).toBe("");
    view.destroy();
  });

  it("runs proofreading on Ctrl+Enter", () => {
    const onProofread = vi.fn();
    const view = makeView(onProofread);
    const event = new KeyboardEvent("keydown", {
      key: "Enter",
      code: "Enter",
      ctrlKey: true,
      bubbles: true,
      cancelable: true,
    });
    view.contentDOM.dispatchEvent(event);
    expect(onProofread).toHaveBeenCalledTimes(1);
    view.destroy();
  });
});
