/**
 * The "Ábendingar" sidebar: every issue found, grouped by category.
 */

import { is } from "../i18n/is";
import type { IssueCategory, WritingIssue } from "../lib/types";
import { IssueCard } from "./IssueCard";

export interface IssuePanelProps {
  issues: readonly WritingIssue[];
  ignoredCount: number;
  selectedId: string | null;
  busy: boolean;
  hasText: boolean;
  onSelect: (issueId: string) => void;
  onAccept: (issueId: string) => void;
  onIgnore: (issueId: string) => void;
  onAcceptAll: () => void;
  onRestoreIgnored: () => void;
}

// Fixed order so the panel does not reshuffle between runs.
const CATEGORY_ORDER: IssueCategory[] = [
  "spelling",
  "grammar",
  "punctuation",
  "style",
  "unknown",
];

export function IssuePanel({
  issues,
  ignoredCount,
  selectedId,
  busy,
  hasText,
  onSelect,
  onAccept,
  onIgnore,
  onAcceptAll,
  onRestoreIgnored,
}: IssuePanelProps) {
  const grouped = CATEGORY_ORDER.map((category) => ({
    category,
    items: issues.filter((issue) => issue.category === category),
  })).filter((group) => group.items.length > 0);

  const acceptableCount = issues.filter(
    (issue) => issue.replacement !== null && issue.replacement !== undefined,
  ).length;

  return (
    <aside className="ritarinn-panel" aria-label={is.panel.title}>
      <div className="ritarinn-panel__header">
        <h2 className="ritarinn-panel__title">{is.panel.title}</h2>
        {acceptableCount > 1 && (
          // Bulk acceptance is available but deliberately secondary: reviewing
          // changes one at a time is the workflow this tool is built around.
          <button type="button" className="ritarinn-button ritarinn-button--subtle" onClick={onAcceptAll}>
            {is.actions.acceptAll}
          </button>
        )}
      </div>

      {issues.length === 0 && (
        <p className="ritarinn-panel__empty">
          {!hasText ? is.panel.emptyHint : busy ? is.status.analysing : is.panel.noneFound}
        </p>
      )}

      {grouped.map((group) => (
        <section key={group.category} className="ritarinn-panel__group">
          <h3 className="ritarinn-panel__group-title">{is.categories[group.category]}</h3>
          <ul className="ritarinn-panel__list">
            {group.items.map((issue) => (
              <IssueCard
                key={issue.id}
                issue={issue}
                selected={issue.id === selectedId}
                onSelect={onSelect}
                onAccept={onAccept}
                onIgnore={onIgnore}
              />
            ))}
          </ul>
        </section>
      ))}

      {ignoredCount > 0 && (
        <div className="ritarinn-panel__ignored">
          <span>{is.panel.ignoredCount(ignoredCount)}</span>
          <button type="button" className="ritarinn-button ritarinn-button--subtle" onClick={onRestoreIgnored}>
            {is.actions.restore}
          </button>
        </div>
      )}
    </aside>
  );
}
