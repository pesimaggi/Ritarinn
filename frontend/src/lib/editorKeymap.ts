/**
 * Ritarinn's editor key bindings.
 *
 * Kept in its own module so the bindings can be tested directly.
 *
 * Undo and redo are not hand-written here beyond one addition: `historyKeymap`
 * already binds them, and re-binding `Mod-z` locally risks shadowing the
 * platform-specific entries that follow it. Upstream binds:
 *
 *     Mod-z                      undo   (all platforms)
 *     Mod-y                      redo   (Windows/Linux)
 *     Mod-Shift-z                redo   (macOS only)
 *     Ctrl-Shift-z               redo   (Linux only)
 *
 * That leaves Ctrl+Shift+Z unbound on Windows, where it is a thoroughly
 * conventional redo shortcut — so it is added explicitly. It is placed ahead of
 * `historyKeymap` so the shift-specific binding is matched before anything
 * else, and no unshifted `Mod-z` is written here that could take precedence.
 *
 * Covered by `editorKeymap.test.ts`.
 */

import { defaultKeymap, historyKeymap, redo } from "@codemirror/commands";
import type { Extension } from "@codemirror/state";
import { keymap } from "@codemirror/view";

export interface KeymapOptions {
  /** Run proofreading immediately, bound to Mod-Enter. */
  onProofread: () => void;
}

export function ritarinnKeymap({ onProofread }: KeymapOptions): Extension {
  return keymap.of([
    {
      key: "Mod-Enter",
      run: () => {
        onProofread();
        return true;
      },
      preventDefault: true,
    },
    // Redo on Ctrl/Cmd+Shift+Z everywhere, not only macOS and Linux.
    { key: "Mod-Shift-z", run: redo, preventDefault: true },
    ...historyKeymap,
    ...defaultKeymap,
  ]);
}
