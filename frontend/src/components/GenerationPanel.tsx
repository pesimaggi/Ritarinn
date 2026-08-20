/**
 * Shared shell for Samantekt and Á mannamáli.
 *
 * Both features have the same shape: pick options, run a local model, review a
 * proposal beside the original, then accept, copy or discard it. Only the
 * options and the prompts differ, so the surrounding machinery lives here and
 * each tab supplies its own controls.
 *
 * Nothing here writes to the document. Acceptance is handed back to the caller,
 * which applies it as an ordinary undoable edit.
 */

import { useState, type ReactNode } from "react";

import { is } from "../i18n/is";
import type { GenerationResponse, ModelsStatusResponse } from "../lib/types";
import { DiffView } from "./DiffView";

export interface GenerationPanelProps {
  heading: string;
  /** The option controls for this feature. */
  controls: ReactNode;
  original: string;
  result: GenerationResponse | null;
  busy: boolean;
  error: string | null;
  models: ModelsStatusResponse | null;
  proofreadOutput: boolean;
  onProofreadOutputChange: (value: boolean) => void;
  compareMode: "diff" | "sideBySide";
  onRun: () => void;
  onCancel: () => void;
  onAccept: () => void;
  onDiscard: () => void;
}

export function GenerationPanel({
  heading,
  controls,
  original,
  result,
  busy,
  error,
  models,
  proofreadOutput,
  onProofreadOutputChange,
  compareMode,
  onRun,
  onCancel,
  onAccept,
  onDiscard,
}: GenerationPanelProps) {
  const [copied, setCopied] = useState(false);

  const provider = models?.llmProviders[0];
  const runtimeMissing = models !== null && provider?.available !== true;
  const modelMissing = models !== null && !provider?.selectedModel;
  const hasText = original.trim() !== "";
  const blocked = runtimeMissing || modelMissing || !hasText;

  async function copy() {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result.text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard access can be refused; the text is on screen and selectable,
      // so failing quietly is better than an alarming error.
    }
  }

  return (
    <section className="ritarinn-generation">
      <h2 className="ritarinn-generation__heading">{heading}</h2>

      <div className="ritarinn-generation__controls">{controls}</div>

      <label className="ritarinn-checkbox">
        <input
          type="checkbox"
          checked={proofreadOutput}
          onChange={(event) => onProofreadOutputChange(event.target.checked)}
        />
        <span>
          {is.generation.proofreadOutput}
          <small>{is.generation.proofreadOutputHint}</small>
        </span>
      </label>

      <div className="ritarinn-generation__actions">
        <button
          type="button"
          className="ritarinn-button ritarinn-button--primary"
          onClick={onRun}
          disabled={busy || blocked}
        >
          {busy ? is.generation.running : result ? is.generation.rerun : is.generation.run}
        </button>
        {busy && (
          <button type="button" className="ritarinn-button" onClick={onCancel}>
            {is.generation.cancel}
          </button>
        )}
      </div>

      {!hasText && <p className="ritarinn-generation__note">{is.generation.emptyText}</p>}
      {hasText && runtimeMissing && (
        <p className="ritarinn-generation__note">
          {is.generation.noRuntime} {is.generation.setupHint}
        </p>
      )}
      {hasText && !runtimeMissing && modelMissing && (
        <p className="ritarinn-generation__note">
          {is.generation.noModel} {is.generation.setupHint}
        </p>
      )}

      {error && (
        <div className="ritarinn-error" role="alert">
          <span>{error}</span>
        </div>
      )}

      {result && (
        <>
          <section className="ritarinn-result">
            <header className="ritarinn-result__header">
              <h3>{is.generation.resultHeading}</h3>
              <span className="ritarinn-result__meta">
                {is.generation.modelLabel}: {result.model} ·{" "}
                {is.generation.elapsedLabel(result.elapsedMs)}
              </span>
            </header>

            <p className="ritarinn-result__text" lang="is">
              {result.text}
            </p>

            <p className="ritarinn-result__provenance">
              {is.generation.chunksLabel(result.chunks, result.passes)}
            </p>

            {result.truncated && (
              <p className="ritarinn-result__warning">{is.generation.truncatedWarning}</p>
            )}

            {proofreadOutput && (
              <div className="ritarinn-result__issues">
                <p>
                  {result.issues.length === 0
                    ? is.generation.noIssuesInOutput
                    : is.generation.issuesInOutput(result.issues.length)}
                </p>
                {result.issues.length > 0 && (
                  <ul>
                    {result.issues.slice(0, 8).map((issue) => (
                      <li key={issue.id}>
                        <span className="ritarinn-result__issue-original">{issue.original}</span>
                        {issue.replacement && (
                          <>
                            {" → "}
                            <span className="ritarinn-result__issue-replacement">
                              {issue.replacement}
                            </span>
                          </>
                        )}
                        <span className="ritarinn-result__issue-title"> — {issue.title}</span>
                      </li>
                    ))}
                  </ul>
                )}
                <p className="ritarinn-result__note">{is.generation.outputNotAltered}</p>
              </div>
            )}

            <div className="ritarinn-result__actions">
              <button
                type="button"
                className="ritarinn-button ritarinn-button--primary"
                onClick={onAccept}
                title={is.generation.acceptReplaces}
              >
                {is.actions.accept}
              </button>
              <button type="button" className="ritarinn-button" onClick={copy}>
                {copied ? is.actions.copied : is.actions.copy}
              </button>
              <button type="button" className="ritarinn-button" onClick={onDiscard}>
                {is.actions.reject}
              </button>
              <span className="ritarinn-result__hint">{is.generation.acceptReplaces}</span>
            </div>
          </section>

          <DiffView original={original} proposal={result.text} mode={compareMode} />
        </>
      )}
    </section>
  );
}
