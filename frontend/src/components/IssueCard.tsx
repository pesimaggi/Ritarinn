/**
 * One reviewable issue in the sidebar.
 *
 * Shows what the engine found, what it proposes, and why — then lets the author
 * decide. Ritarinn never applies a change without this step.
 */

import { is } from "../i18n/is";
import type { WritingIssue } from "../lib/types";

export interface IssueCardProps {
  issue: WritingIssue;
  selected: boolean;
  onSelect: (issueId: string) => void;
  onAccept: (issueId: string) => void;
  onIgnore: (issueId: string) => void;
}

export function IssueCard({ issue, selected, onSelect, onAccept, onIgnore }: IssueCardProps) {
  const canAccept = issue.replacement !== null && issue.replacement !== undefined;

  return (
    <li
      className={`ritarinn-issue-card${selected ? " is-selected" : ""}`}
      data-category={issue.category}
      data-testid={`issue-${issue.id}`}
    >
      <button
        type="button"
        className="ritarinn-issue-card__header"
        onClick={() => onSelect(issue.id)}
        aria-expanded={selected}
      >
        <span className={`ritarinn-tag ritarinn-tag--${issue.category}`}>
          {issue.family ?? is.categories[issue.category]}
        </span>
        {issue.severity === "warning" && (
          <span className="ritarinn-tag ritarinn-tag--warning">{is.severity.warning}</span>
        )}
        <span className="ritarinn-issue-card__title">{issue.title}</span>
      </button>

      <div className="ritarinn-issue-card__body">
        <div className="ritarinn-diff">
          <span className="ritarinn-diff__original" lang="is">
            {issue.original}
          </span>
          {canAccept && (
            <>
              <span className="ritarinn-diff__arrow" aria-hidden="true">
                →
              </span>
              <span className="ritarinn-diff__replacement" lang="is">
                {issue.replacement}
              </span>
            </>
          )}
        </div>

        {!canAccept && <p className="ritarinn-issue-card__note">{is.panel.noSuggestion}</p>}

        {issue.explanation && (
          // The explanation comes from GreynirCorrect and may contain <a> tags.
          // It is rendered as text, never as HTML: the backend is local, but
          // "local" is not a reason to hand markup straight to the DOM.
          <p className="ritarinn-issue-card__explanation" lang="is">
            {stripMarkup(issue.explanation)}
          </p>
        )}

        {issue.alternatives.length > 0 && (
          <p className="ritarinn-issue-card__alternatives">
            <span className="ritarinn-issue-card__label">{is.panel.alternatives}:</span>{" "}
            {issue.alternatives.join(", ")}
          </p>
        )}

        <div className="ritarinn-issue-card__actions">
          <button
            type="button"
            className="ritarinn-button ritarinn-button--primary"
            onClick={() => onAccept(issue.id)}
            disabled={!canAccept}
          >
            {is.actions.accept}
          </button>
          <button
            type="button"
            className="ritarinn-button"
            onClick={() => onIgnore(issue.id)}
          >
            {is.actions.ignore}
          </button>
          {issue.code && (
            <span className="ritarinn-issue-card__code" title={is.panel.errorCode}>
              {issue.code}
            </span>
          )}
        </div>
      </div>
    </li>
  );
}

/**
 * Remove the anchor tags GreynirCorrect embeds in some explanations.
 *
 * Upstream writes reference links as `<a href="...">text</a>`. Ritarinn keeps
 * the wording and drops the markup rather than rendering it, so no engine
 * output can ever reach the DOM as HTML.
 */
export function stripMarkup(text: string): string {
  return text.replace(/<[^>]*>/g, "").replace(/\s+/g, " ").trim();
}
