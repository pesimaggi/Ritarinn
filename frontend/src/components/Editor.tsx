/**
 * The CodeMirror 6 editor.
 *
 * CodeMirror was chosen over a hand-built contentEditable because it already
 * provides everything issue review depends on: stable document positions that
 * survive edits, range decorations, a real undo history, and correct handling
 * of paste and IME input. v0.1 needs plain Icelandic text only, so no language
 * mode or rich formatting is loaded.
 */

import { useEffect, useRef } from "react";
import { history } from "@codemirror/commands";
import { EditorState, type Extension } from "@codemirror/state";
import { EditorView, drawSelection, placeholder } from "@codemirror/view";

import { is } from "../i18n/is";
import { ritarinnKeymap } from "../lib/editorKeymap";
import {
  issueAt,
  issueDecorations,
  issueField,
  selectIssueEffect,
  selectedIssueField,
  setIssuesEffect,
} from "../lib/issueDecorations";
import type { WritingIssue } from "../lib/types";

export interface EditorProps {
  initialText: string;
  issues: readonly WritingIssue[];
  onTextChange: (text: string) => void;
  onIssueClick: (issueId: string) => void;
  onProofreadShortcut: () => void;
  /** Receives the view so the parent can accept/ignore/reveal issues. */
  onReady: (view: EditorView) => void;
}

const editorTheme = EditorView.theme({
  "&": { height: "100%", fontSize: "16px" },
  ".cm-scroller": {
    fontFamily: "var(--ritarinn-font-body)",
    lineHeight: "1.7",
    padding: "1.5rem 1.75rem",
  },
  ".cm-content": { maxWidth: "70ch", caretColor: "var(--ritarinn-text)" },
  "&.cm-focused": { outline: "none" },
  ".cm-line": { padding: "0" },
});

export function Editor({
  initialText,
  issues,
  onTextChange,
  onIssueClick,
  onProofreadShortcut,
  onReady,
}: EditorProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const viewRef = useRef<EditorView | null>(null);

  // Callbacks are read through a ref so the editor is created once. Rebuilding
  // it on every render would throw away the undo history and the cursor.
  const handlers = useRef({ onTextChange, onIssueClick, onProofreadShortcut });
  handlers.current = { onTextChange, onIssueClick, onProofreadShortcut };

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    const extensions: Extension[] = [
      history(),
      drawSelection(),
      EditorView.lineWrapping,
      placeholder(is.editor.placeholder),
      issueField,
      selectedIssueField,
      issueDecorations,
      ritarinnKeymap({ onProofread: () => handlers.current.onProofreadShortcut() }),
      EditorView.updateListener.of((update) => {
        if (update.docChanged) {
          handlers.current.onTextChange(update.state.doc.toString());
        }
      }),
      EditorView.domEventHandlers({
        mousedown(event, view) {
          const pos = view.posAtCoords({ x: event.clientX, y: event.clientY });
          if (pos === null) return false;
          const hit = issueAt(view.state, pos);
          if (!hit) {
            view.dispatch({ effects: selectIssueEffect.of(null) });
            return false;
          }
          handlers.current.onIssueClick(hit.issue.id);
          view.dispatch({ effects: selectIssueEffect.of(hit.issue.id) });
          // Let CodeMirror place the caret as usual; selecting an issue should
          // not stop the user from clicking into the word to edit it.
          return false;
        },
      }),
      EditorView.contentAttributes.of({
        "aria-label": is.editor.label,
        lang: "is",
        spellcheck: "false",
      }),
      editorTheme,
    ];

    const view = new EditorView({
      state: EditorState.create({ doc: initialText, extensions }),
      parent: host,
    });
    viewRef.current = view;
    onReady(view);

    return () => {
      view.destroy();
      viewRef.current = null;
    };
    // Created once for the lifetime of the component; see the ref above.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Push new issue sets into editor state. This is an effect rather than a
  // prop-driven re-render because the underlines live in CodeMirror's state,
  // not React's.
  useEffect(() => {
    const view = viewRef.current;
    if (!view) return;
    view.dispatch({ effects: setIssuesEffect.of([...issues]) });
  }, [issues]);

  return <div className="ritarinn-editor" ref={hostRef} />;
}
