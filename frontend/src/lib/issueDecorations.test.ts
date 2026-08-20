/**
 * Issue anchoring, acceptance and position maintenance in the editor.
 *
 * These exercise real CodeMirror state rather than a mock, because the things
 * that break — offsets drifting after an edit, undo losing an accepted
 * correction — are properties of the editor's own change mapping.
 */

import { describe, expect, it } from "vitest";
import { redo, undo } from "@codemirror/commands";
import { history } from "@codemirror/commands";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";

import {
  acceptIssue,
  anchorIssues,
  dismissIssueEffect,
  ignoreIssue,
  issueAt,
  issueDecorations,
  issueField,
  selectedIssueField,
  setIssuesEffect,
} from "./issueDecorations";
import type { IssueScope, WritingIssue } from "./types";

function issue(
  overrides: Partial<WritingIssue> & Pick<WritingIssue, "id" | "startChar" | "endChar" | "original">,
): WritingIssue {
  return {
    source: "greynir",
    category: "spelling",
    code: "S004",
    family: "Stafsetning",
    scope: "span" as IssueScope,
    replacement: null,
    alternatives: [],
    title: "Villa",
    severity: "error",
    references: [],
    ...overrides,
  };
}

function makeView(doc: string): EditorView {
  return new EditorView({
    state: EditorState.create({
      doc,
      extensions: [history(), issueField, selectedIssueField, issueDecorations],
    }),
  });
}

function decoratedRanges(view: EditorView): [number, number][] {
  const set = view.state.facet(EditorView.decorations);
  const ranges: [number, number][] = [];
  for (const source of set) {
    const decorations = typeof source === "function" ? source(view) : source;
    const iter = decorations.iter();
    while (iter.value) {
      ranges.push([iter.from, iter.to]);
      iter.next();
    }
  }
  return ranges;
}

const SENTENCE = "Þinngið samþikkti tilöguna.";
const SPELLING_ISSUES = [
  issue({ id: "a", startChar: 0, endChar: 7, original: "Þinngið", replacement: "Þingið" }),
  issue({ id: "b", startChar: 8, endChar: 17, original: "samþikkti", replacement: "samþykkti" }),
  issue({ id: "c", startChar: 18, endChar: 26, original: "tilöguna", replacement: "tillöguna" }),
];

describe("anchorIssues", () => {
  it("keeps issues that fit the document", () => {
    expect(anchorIssues(SPELLING_ISSUES, SENTENCE.length)).toHaveLength(3);
  });

  it("discards issues that fall outside the document", () => {
    // A mismatch between client and server text is a bug; rendering a
    // misplaced underline would hide it behind a plausible-looking result.
    const anchored = anchorIssues(
      [issue({ id: "x", startChar: 0, endChar: 500, original: "…" })],
      SENTENCE.length,
    );
    expect(anchored).toHaveLength(0);
  });

  it("discards empty spans", () => {
    expect(
      anchorIssues([issue({ id: "x", startChar: 4, endChar: 4, original: "" })], 20),
    ).toHaveLength(0);
  });

  it("sorts by position", () => {
    const shuffled = [SPELLING_ISSUES[2]!, SPELLING_ISSUES[0]!, SPELLING_ISSUES[1]!];
    expect(anchorIssues(shuffled, SENTENCE.length).map((a) => a.issue.id)).toEqual(["a", "b", "c"]);
  });
});

describe("highlighting", () => {
  it("decorates each issue span", () => {
    const view = makeView(SENTENCE);
    view.dispatch({ effects: setIssuesEffect.of(SPELLING_ISSUES) });
    expect(decoratedRanges(view)).toEqual([
      [0, 7],
      [8, 17],
      [18, 26],
    ]);
  });

  it("does not underline sentence-scope issues", () => {
    // An unparseable-sentence note covers the whole sentence; underlining it
    // would bury the word-level issues inside it.
    const view = makeView(SENTENCE);
    view.dispatch({
      effects: setIssuesEffect.of([
        issue({ id: "s", startChar: 0, endChar: 27, original: SENTENCE, scope: "sentence" }),
        SPELLING_ISSUES[0]!,
      ]),
    });
    expect(decoratedRanges(view)).toEqual([[0, 7]]);
    // It is still tracked, so the sidebar can select it.
    expect(view.state.field(issueField)).toHaveLength(2);
  });

  it("handles nested spans without throwing", () => {
    const view = makeView(SENTENCE);
    view.dispatch({
      effects: setIssuesEffect.of([
        issue({ id: "outer", startChar: 0, endChar: 17, original: "Þinngið samþikkti" }),
        SPELLING_ISSUES[0]!,
      ]),
    });
    expect(decoratedRanges(view)).toHaveLength(2);
  });
});

describe("issueAt", () => {
  it("finds the issue under a position", () => {
    const view = makeView(SENTENCE);
    view.dispatch({ effects: setIssuesEffect.of(SPELLING_ISSUES) });
    expect(issueAt(view.state, 3)?.issue.id).toBe("a");
    expect(issueAt(view.state, 12)?.issue.id).toBe("b");
  });

  it("returns null outside every issue", () => {
    const view = makeView(SENTENCE);
    view.dispatch({ effects: setIssuesEffect.of([SPELLING_ISSUES[0]!]) });
    expect(issueAt(view.state, 20)).toBeNull();
  });

  it("prefers the tightest span when issues nest", () => {
    const view = makeView(SENTENCE);
    view.dispatch({
      effects: setIssuesEffect.of([
        issue({ id: "outer", startChar: 0, endChar: 17, original: "Þinngið samþikkti" }),
        SPELLING_ISSUES[0]!,
      ]),
    });
    expect(issueAt(view.state, 3)?.issue.id).toBe("a");
  });
});

describe("accepting a correction", () => {
  it("replaces only the issue's own range", () => {
    const view = makeView(SENTENCE);
    view.dispatch({ effects: setIssuesEffect.of(SPELLING_ISSUES) });

    expect(acceptIssue(view, "a")).toBe(true);
    expect(view.state.doc.toString()).toBe("Þingið samþikkti tilöguna.");
  });

  it("leaves other issues correctly positioned afterwards", () => {
    // "Þinngið" → "Þingið" removes one character, so every later issue shifts.
    const view = makeView(SENTENCE);
    view.dispatch({ effects: setIssuesEffect.of(SPELLING_ISSUES) });
    acceptIssue(view, "a");

    const doc = view.state.doc.toString();
    for (const anchored of view.state.field(issueField)) {
      expect(doc.slice(anchored.from, anchored.to)).toBe(anchored.issue.original);
    }
  });

  it("removes the accepted issue's own underline", () => {
    const view = makeView(SENTENCE);
    view.dispatch({ effects: setIssuesEffect.of(SPELLING_ISSUES) });
    acceptIssue(view, "a");
    expect(view.state.field(issueField).map((a) => a.issue.id)).toEqual(["b", "c"]);
  });

  it("can be undone, restoring the original text", () => {
    const view = makeView(SENTENCE);
    view.dispatch({ effects: setIssuesEffect.of(SPELLING_ISSUES) });
    acceptIssue(view, "a");
    expect(view.state.doc.toString()).toBe("Þingið samþikkti tilöguna.");

    undo(view);
    expect(view.state.doc.toString()).toBe(SENTENCE);

    redo(view);
    expect(view.state.doc.toString()).toBe("Þingið samþikkti tilöguna.");
  });

  it("applies every correction when accepted back to front", () => {
    const view = makeView(SENTENCE);
    view.dispatch({ effects: setIssuesEffect.of(SPELLING_ISSUES) });
    for (const id of ["c", "b", "a"]) acceptIssue(view, id);
    expect(view.state.doc.toString()).toBe("Þingið samþykkti tillöguna.");
  });

  it("refuses an issue with no replacement", () => {
    const view = makeView(SENTENCE);
    view.dispatch({
      effects: setIssuesEffect.of([issue({ id: "n", startChar: 0, endChar: 7, original: "Þinngið" })]),
    });
    expect(acceptIssue(view, "n")).toBe(false);
    expect(view.state.doc.toString()).toBe(SENTENCE);
  });

  it("refuses an unknown issue id", () => {
    const view = makeView(SENTENCE);
    expect(acceptIssue(view, "missing")).toBe(false);
  });
});

describe("ignoring an issue", () => {
  it("removes the underline without touching the document", () => {
    const view = makeView(SENTENCE);
    view.dispatch({ effects: setIssuesEffect.of(SPELLING_ISSUES) });
    ignoreIssue(view, "b");

    expect(view.state.doc.toString()).toBe(SENTENCE);
    expect(view.state.field(issueField).map((a) => a.issue.id)).toEqual(["a", "c"]);
  });

  it("is expressed as an effect, so it is not an undoable edit", () => {
    const view = makeView(SENTENCE);
    view.dispatch({ effects: setIssuesEffect.of(SPELLING_ISSUES) });
    ignoreIssue(view, "b");
    undo(view);
    expect(view.state.doc.toString()).toBe(SENTENCE);
  });
});

describe("positions after editing", () => {
  it("shifts issues when text is inserted before them", () => {
    const view = makeView(SENTENCE);
    view.dispatch({ effects: setIssuesEffect.of(SPELLING_ISSUES) });
    view.dispatch({ changes: { from: 0, insert: "Já. " } });

    const doc = view.state.doc.toString();
    for (const anchored of view.state.field(issueField)) {
      expect(doc.slice(anchored.from, anchored.to)).toBe(anchored.issue.original);
    }
  });

  it("drops an issue the user has edited into", () => {
    // Its text no longer exists; the next run will report whatever is there now.
    const view = makeView(SENTENCE);
    view.dispatch({ effects: setIssuesEffect.of(SPELLING_ISSUES) });
    view.dispatch({ changes: { from: 3, to: 4, insert: "x" } });

    expect(view.state.field(issueField).map((a) => a.issue.id)).toEqual(["b", "c"]);
  });

  it("keeps issues correct when an emoji is typed before them", () => {
    // An emoji is two UTF-16 units, so a naive +1 shift would misplace every
    // later underline by one character.
    const view = makeView(SENTENCE);
    view.dispatch({ effects: setIssuesEffect.of(SPELLING_ISSUES) });
    view.dispatch({ changes: { from: 0, insert: "😀 " } });

    const doc = view.state.doc.toString();
    for (const anchored of view.state.field(issueField)) {
      expect(doc.slice(anchored.from, anchored.to)).toBe(anchored.issue.original);
    }
  });

  it("clears the selection when a new issue set arrives", () => {
    const view = makeView(SENTENCE);
    view.dispatch({ effects: setIssuesEffect.of(SPELLING_ISSUES) });
    view.dispatch({ effects: dismissIssueEffect.of("a") });
    view.dispatch({ effects: setIssuesEffect.of(SPELLING_ISSUES) });
    expect(view.state.field(selectedIssueField)).toBeNull();
    expect(view.state.field(issueField)).toHaveLength(3);
  });
});
