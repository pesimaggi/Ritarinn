/**
 * Ritarinn's application shell.
 *
 * Holds the document, orchestrates proofreading, and keeps the editor's
 * underlines and the sidebar showing the same set of issues. The editor owns
 * the text; React state mirrors it so the scheduler and word count can react.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { EditorView } from "@codemirror/view";

import { Editor } from "./components/Editor";
import { FeaturePlaceholder } from "./components/FeaturePlaceholder";
import { IssuePanel } from "./components/IssuePanel";
import { PrivacyIndicator } from "./components/PrivacyIndicator";
import { SetupStatus } from "./components/SetupStatus";
import { is } from "./i18n/is";
import { ApiError, getModelsStatus, getPrivacyStatus, proofread } from "./lib/api";
import { acceptIssue, ignoreIssue, revealIssue } from "./lib/issueDecorations";
import { ProofreadScheduler, type ProofreadState } from "./lib/proofreadScheduler";
import { countWords } from "./lib/text";
import type { ModelsStatusResponse, PrivacyStatusResponse, WritingIssue } from "./lib/types";

type Tab = "proofread" | "summary" | "plainLanguage" | "settings";

export function App() {
  const [text, setText] = useState("");
  const [tab, setTab] = useState<Tab>("proofread");
  const [issues, setIssues] = useState<WritingIssue[]>([]);
  const [ignoredIds, setIgnoredIds] = useState<ReadonlySet<string>>(new Set());
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [privacy, setPrivacy] = useState<PrivacyStatusResponse | null>(null);
  const [models, setModels] = useState<ModelsStatusResponse | null>(null);

  const viewRef = useRef<EditorView | null>(null);
  const textRef = useRef(text);
  textRef.current = text;

  // -- backend status --------------------------------------------------------

  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      try {
        const [privacyStatus, modelsStatus] = await Promise.all([
          getPrivacyStatus(controller.signal),
          getModelsStatus(controller.signal),
        ]);
        setPrivacy(privacyStatus);
        setModels(modelsStatus);
      } catch (cause) {
        if (cause instanceof ApiError && cause.status === 0) {
          setError(is.errors.backendUnreachable);
        }
      }
    })();
    return () => controller.abort();
  }, []);

  // -- proofreading ----------------------------------------------------------

  const handleSchedulerChange = useCallback((state: ProofreadState) => {
    setBusy(state.status === "pending");
    if (state.status === "error") {
      const cause = state.error;
      setError(
        cause instanceof ApiError && cause.status === 0
          ? is.errors.backendUnreachable
          : cause instanceof ApiError && cause.status === 413
            ? is.errors.textTooLong
            : is.errors.proofreadFailed,
      );
      return;
    }
    if (state.status === "pending") return;

    setError(null);
    setIssues(state.result?.issues ?? []);
  }, []);

  const scheduler = useMemo(
    () =>
      new ProofreadScheduler({
        run: (value, signal) => proofread(value, { signal }),
        onChange: handleSchedulerChange,
      }),
    [handleSchedulerChange],
  );

  useEffect(() => () => scheduler.dispose(), [scheduler]);

  const handleTextChange = useCallback(
    (value: string) => {
      setText(value);
      scheduler.schedule(value);
    },
    [scheduler],
  );

  const runProofread = useCallback(() => {
    void scheduler.runNow(textRef.current);
  }, [scheduler]);

  // Issues the user has ignored stay hidden until they ask for them back.
  const visibleIssues = useMemo(
    () => issues.filter((issue) => !ignoredIds.has(issue.id)),
    [issues, ignoredIds],
  );

  // -- issue actions ---------------------------------------------------------

  const handleSelect = useCallback((issueId: string) => {
    setSelectedId(issueId);
    const view = viewRef.current;
    if (view) revealIssue(view, issueId);
  }, []);

  const handleAccept = useCallback(
    (issueId: string) => {
      const view = viewRef.current;
      if (!view) return;
      if (!acceptIssue(view, issueId)) return;
      // Drop it from the sidebar immediately; the editor has already removed
      // the underline, and the next run re-analyses the changed sentence.
      setIssues((current) => current.filter((issue) => issue.id !== issueId));
      setSelectedId(null);
      scheduler.schedule(view.state.doc.toString());
    },
    [scheduler],
  );

  const handleIgnore = useCallback((issueId: string) => {
    const view = viewRef.current;
    if (view) ignoreIssue(view, issueId);
    setIgnoredIds((current) => new Set(current).add(issueId));
    setSelectedId(null);
  }, []);

  const handleAcceptAll = useCallback(() => {
    const view = viewRef.current;
    if (!view) return;
    // Applied one at a time, back to front, so each replacement's offsets stay
    // valid — and so each lands in the undo history as its own step.
    const ordered = [...visibleIssues]
      .filter((issue) => issue.replacement !== null && issue.replacement !== undefined)
      .sort((a, b) => b.startChar - a.startChar);
    for (const issue of ordered) acceptIssue(view, issue.id);
    setIssues((current) =>
      current.filter((issue) => !ordered.some((applied) => applied.id === issue.id)),
    );
    setSelectedId(null);
    scheduler.schedule(view.state.doc.toString());
  }, [scheduler, visibleIssues]);

  const handleRestoreIgnored = useCallback(() => {
    setIgnoredIds(new Set());
    // Re-running is the only way to get the underlines back: the editor
    // discarded them when they were ignored.
    runProofread();
  }, [runProofread]);

  // -- render ----------------------------------------------------------------

  const wordCount = useMemo(() => countWords(text), [text]);

  return (
    <div className="ritarinn-app">
      <header className="ritarinn-header">
        <h1 className="ritarinn-brand">{is.appName}</h1>
        <PrivacyIndicator privacy={privacy} models={models} />
      </header>

      <nav className="ritarinn-tabs" aria-label={is.appName}>
        {(["proofread", "summary", "plainLanguage", "settings"] as const).map((key) => (
          <button
            key={key}
            type="button"
            className={`ritarinn-tab${tab === key ? " is-active" : ""}`}
            onClick={() => setTab(key)}
            aria-current={tab === key}
          >
            {is.tabs[key]}
          </button>
        ))}
      </nav>

      {error && (
        <div className="ritarinn-error" role="alert">
          <span>{error}</span>
          <button type="button" className="ritarinn-button" onClick={runProofread}>
            {is.errors.retry}
          </button>
        </div>
      )}

      <main className="ritarinn-main">
        {/* The editor is never unmounted: switching tabs must not throw away
            the user's document or its undo history. */}
        <div className={`ritarinn-workspace${tab === "proofread" ? "" : " is-hidden"}`}>
          <div className="ritarinn-editor-column">
            <div className="ritarinn-toolbar">
              <button
                type="button"
                className="ritarinn-button ritarinn-button--primary"
                onClick={runProofread}
                disabled={busy || text.trim() === ""}
              >
                {busy ? is.actions.proofreading : is.actions.proofread}
              </button>
            </div>
            <Editor
              initialText=""
              issues={visibleIssues}
              onTextChange={handleTextChange}
              onIssueClick={setSelectedId}
              onProofreadShortcut={runProofread}
              onReady={(view) => {
                viewRef.current = view;
              }}
            />
          </div>

          <IssuePanel
            issues={visibleIssues}
            ignoredCount={ignoredIds.size}
            selectedId={selectedId}
            busy={busy}
            hasText={text.trim() !== ""}
            onSelect={handleSelect}
            onAccept={handleAccept}
            onIgnore={handleIgnore}
            onAcceptAll={handleAcceptAll}
            onRestoreIgnored={handleRestoreIgnored}
          />
        </div>

        {tab === "summary" && (
          <FeaturePlaceholder
            title={is.tabs.summary}
            description={is.features.summaryUnavailable}
          />
        )}

        {tab === "plainLanguage" && (
          <FeaturePlaceholder
            title={is.tabs.plainLanguage}
            description={is.features.plainLanguageUnavailable}
          />
        )}

        {tab === "settings" && (
          <section className="ritarinn-settings">
            <SetupStatus models={models} />
            <section className="ritarinn-attribution">
              <h3>{is.attribution.heading}</h3>
              <p>{is.attribution.body}</p>
            </section>
          </section>
        )}
      </main>

      <footer className="ritarinn-statusbar">
        <span>{is.status.words(wordCount)}</span>
        <span>{is.status.issues(visibleIssues.length)}</span>
        <span className="ritarinn-statusbar__right">
          {busy ? is.status.analysing : is.status.processedLocally}
        </span>
      </footer>
    </div>
  );
}
