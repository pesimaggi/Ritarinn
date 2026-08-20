/**
 * CodeMirror state for issue underlines.
 *
 * Issues arrive from the backend as offsets into a snapshot of the document.
 * The user keeps typing while a request is in flight, so those offsets have to
 * be maintained against subsequent edits, or an underline drifts onto the wrong
 * word. This module anchors each issue in editor state and maps it through
 * every change.
 *
 * When an edit actually touches an issue's range, the issue is dropped rather
 * than stretched: the text it described no longer exists, and the next
 * proofreading run will report whatever is there now. A missing underline for
 * 800 ms is a much smaller problem than a confidently wrong one.
 */

import { EditorState, StateEffect, StateField, type Range } from "@codemirror/state";
import { Decoration, EditorView, type DecorationSet } from "@codemirror/view";

import type { WritingIssue } from "./types";

/** An issue positioned in the *current* document. */
export interface AnchoredIssue {
  issue: WritingIssue;
  from: number;
  to: number;
}

/** Replace the whole issue set, e.g. when a proofreading run completes. */
export const setIssuesEffect = StateEffect.define<WritingIssue[]>();

/** Remove a single issue by id, e.g. when the user ignores it. */
export const dismissIssueEffect = StateEffect.define<string>();

/** Highlight one issue as selected, or `null` for none. */
export const selectIssueEffect = StateEffect.define<string | null>();

/**
 * Anchor backend issues in a document, discarding any that do not fit.
 *
 * An out-of-range offset means the client and server disagree about the text —
 * a bug worth failing quietly on rather than rendering a misplaced underline.
 */
export function anchorIssues(issues: readonly WritingIssue[], docLength: number): AnchoredIssue[] {
  const anchored: AnchoredIssue[] = [];
  for (const issue of issues) {
    const { startChar: from, endChar: to } = issue;
    if (from < 0 || to > docLength || from >= to) continue;
    anchored.push({ issue, from, to });
  }
  anchored.sort((a, b) => a.from - b.from || a.to - b.to);
  return anchored;
}

export const issueField = StateField.define<AnchoredIssue[]>({
  create: () => [],

  update(value, tr) {
    let next = value;

    for (const effect of tr.effects) {
      if (effect.is(setIssuesEffect)) {
        next = anchorIssues(effect.value, tr.newDoc.length);
      } else if (effect.is(dismissIssueEffect)) {
        next = next.filter((a) => a.issue.id !== effect.value);
      }
    }

    if (!tr.docChanged) return next;

    // Only map issues the change left alone; anything the edit reached into is
    // no longer described by its issue.
    const mapped: AnchoredIssue[] = [];
    for (const anchored of next) {
      if (tr.changes.touchesRange(anchored.from, anchored.to)) continue;
      mapped.push({
        issue: anchored.issue,
        from: tr.changes.mapPos(anchored.from, 1),
        to: tr.changes.mapPos(anchored.to, -1),
      });
    }
    return mapped;
  },
});

export const selectedIssueField = StateField.define<string | null>({
  create: () => null,
  update(value, tr) {
    for (const effect of tr.effects) {
      if (effect.is(selectIssueEffect)) return effect.value;
      // A replaced issue set invalidates the selection it referred to.
      if (effect.is(setIssuesEffect)) return null;
    }
    return value;
  },
});

const CATEGORY_CLASS: Record<string, string> = {
  spelling: "ritarinn-issue--spelling",
  grammar: "ritarinn-issue--grammar",
  punctuation: "ritarinn-issue--punctuation",
  style: "ritarinn-issue--style",
  unknown: "ritarinn-issue--unknown",
};

function buildDecorations(state: EditorState): DecorationSet {
  const selected = state.field(selectedIssueField);
  const ranges: Range<Decoration>[] = [];

  for (const { issue, from, to } of state.field(issueField)) {
    // A sentence-scope annotation (unparseable sentence, very long sentence)
    // spans the whole sentence. Underlining that would draw a line under a
    // paragraph and hide the word-level issues inside it, so these appear in
    // the sidebar only.
    if (issue.scope === "sentence") continue;

    const classes = [
      "ritarinn-issue",
      CATEGORY_CLASS[issue.category] ?? CATEGORY_CLASS.unknown,
      issue.severity === "warning" ? "ritarinn-issue--warning" : "",
      issue.id === selected ? "ritarinn-issue--selected" : "",
    ]
      .filter(Boolean)
      .join(" ");

    ranges.push(
      Decoration.mark({
        class: classes,
        attributes: { "data-issue-id": issue.id },
      }).range(from, to),
    );
  }

  // Decoration.set sorts for us, which matters because issue spans can nest.
  return Decoration.set(ranges, true);
}

export const issueDecorations = EditorView.decorations.compute(
  [issueField, selectedIssueField],
  buildDecorations,
);

/** The issue whose range contains `pos`, if any. */
export function issueAt(state: EditorState, pos: number): AnchoredIssue | null {
  let best: AnchoredIssue | null = null;
  for (const anchored of state.field(issueField)) {
    if (anchored.issue.scope === "sentence") continue;
    if (pos < anchored.from || pos > anchored.to) continue;
    // Spans can nest; the tightest one is what the user pointed at.
    if (best === null || anchored.to - anchored.from < best.to - best.from) {
      best = anchored;
    }
  }
  return best;
}

/**
 * Apply an issue's suggested replacement.
 *
 * The change is dispatched as a normal transaction, so it joins the editor's
 * undo history: the user can undo an accepted correction with Ctrl/Cmd+Z like
 * any other edit. Only the issue's own range is touched — the rest of the
 * document, and every other issue, is left alone.
 */
export function acceptIssue(view: EditorView, issueId: string): boolean {
  const anchored = view.state.field(issueField).find((a) => a.issue.id === issueId);
  if (!anchored) return false;

  const replacement = anchored.issue.replacement;
  if (replacement === null || replacement === undefined) return false;

  view.dispatch({
    changes: { from: anchored.from, to: anchored.to, insert: replacement },
    // Leave the caret after the replacement so typing continues naturally.
    selection: { anchor: anchored.from + replacement.length },
    scrollIntoView: true,
    effects: selectIssueEffect.of(null),
    userEvent: "input.accept",
  });
  return true;
}

/** Remove an issue's underline without touching the document. */
export function ignoreIssue(view: EditorView, issueId: string): void {
  view.dispatch({ effects: [dismissIssueEffect.of(issueId), selectIssueEffect.of(null)] });
}

/** Move the viewport and selection to an issue. */
export function revealIssue(view: EditorView, issueId: string): void {
  const anchored = view.state.field(issueField).find((a) => a.issue.id === issueId);
  if (!anchored) return;
  view.dispatch({
    selection: { anchor: anchored.from, head: anchored.to },
    effects: [selectIssueEffect.of(issueId), EditorView.scrollIntoView(anchored.from, { y: "center" })],
  });
  view.focus();
}
