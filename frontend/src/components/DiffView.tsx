/**
 * Comparison of the author's text with a generated proposal.
 *
 * Generated text is never applied automatically, so the user has to be able to
 * see what would change. Two views serve different questions: the inline diff
 * answers "what exactly is different?", and the side-by-side answers "does the
 * new version read well?". Rewrites need both, which is why the toggle exists.
 */

import { useMemo, useState } from "react";

import { is } from "../i18n/is";
import { diffWords, unchangedRatio } from "../lib/diff";

export interface DiffViewProps {
  original: string;
  proposal: string;
  /** Summaries are new artifacts, not edits, so a word diff is meaningless. */
  mode?: "diff" | "sideBySide";
}

export function DiffView({ original, proposal, mode }: DiffViewProps) {
  const [showDiff, setShowDiff] = useState(mode !== "sideBySide");
  const parts = useMemo(
    () => (showDiff ? diffWords(original, proposal) : []),
    [original, proposal, showDiff],
  );
  const unchanged = useMemo(
    () => (parts.length > 0 ? Math.round(unchangedRatio(parts) * 100) : null),
    [parts],
  );

  const toggleable = mode !== "sideBySide";

  return (
    <section className="ritarinn-compare">
      <header className="ritarinn-compare__header">
        <h3>{is.generation.comparisonHeading}</h3>
        {toggleable && (
          <button
            type="button"
            className="ritarinn-button ritarinn-button--subtle"
            onClick={() => setShowDiff((value) => !value)}
          >
            {showDiff ? is.generation.showSideBySide : is.generation.showDiff}
          </button>
        )}
        {showDiff && unchanged !== null && (
          <span className="ritarinn-compare__ratio">
            {is.generation.unchangedRatio(unchanged)}
          </span>
        )}
      </header>

      {showDiff ? (
        <p className="ritarinn-diffview" lang="is">
          {parts.map((part, index) => (
            <span
              key={index}
              className={
                part.kind === "added"
                  ? "ritarinn-diffview__added"
                  : part.kind === "removed"
                    ? "ritarinn-diffview__removed"
                    : undefined
              }
            >
              {part.text}
            </span>
          ))}
        </p>
      ) : (
        <div className="ritarinn-compare__columns">
          <div>
            <h4>{is.panel.original}</h4>
            <p className="ritarinn-compare__text" lang="is">
              {original}
            </p>
          </div>
          <div>
            <h4>{is.generation.resultHeading}</h4>
            <p className="ritarinn-compare__text" lang="is">
              {proposal}
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
