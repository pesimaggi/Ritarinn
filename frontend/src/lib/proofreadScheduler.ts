/**
 * Debounced proofreading with strict ordering guarantees.
 *
 * Two things go wrong in a naive implementation, and both put wrong underlines
 * on the user's screen:
 *
 * 1. a request fired for text the user has since changed, and
 * 2. a slow response for old text arriving after a fast response for new text.
 *
 * The scheduler solves (1) by aborting superseded requests and (2) by tagging
 * every run with an increasing sequence number and discarding any result that
 * is not the newest. Aborting alone is not enough for (2): a request can
 * already be past the point of cancellation when it is superseded.
 *
 * The class is deliberately free of React so it can be tested directly.
 */

import type { ProofreadResponse } from "./types";

export type ProofreadStatus = "idle" | "pending" | "done" | "error";

export interface ProofreadState {
  status: ProofreadStatus;
  /** The text the current `result` describes. Empty until a run completes. */
  analysedText: string;
  result: ProofreadResponse | null;
  error: unknown;
}

export interface SchedulerOptions {
  /** Milliseconds of quiet typing before a run starts. */
  debounceMs?: number;
  run: (text: string, signal: AbortSignal) => Promise<ProofreadResponse>;
  onChange: (state: ProofreadState) => void;
}

/** Matches the product brief's 700–1000 ms window. */
export const DEFAULT_DEBOUNCE_MS = 800;

export class ProofreadScheduler {
  private readonly debounceMs: number;
  private readonly run: SchedulerOptions["run"];
  private readonly onChange: SchedulerOptions["onChange"];

  private timer: ReturnType<typeof setTimeout> | null = null;
  private controller: AbortController | null = null;
  /** Incremented per run; only the newest run may publish a result. */
  private sequence = 0;
  private state: ProofreadState = {
    status: "idle",
    analysedText: "",
    result: null,
    error: null,
  };

  constructor(options: SchedulerOptions) {
    this.debounceMs = options.debounceMs ?? DEFAULT_DEBOUNCE_MS;
    this.run = options.run;
    this.onChange = options.onChange;
  }

  getState(): ProofreadState {
    return this.state;
  }

  /** Queue a run after the debounce interval, replacing any pending one. */
  schedule(text: string): void {
    this.clearTimer();
    this.timer = setTimeout(() => {
      this.timer = null;
      void this.execute(text);
    }, this.debounceMs);
  }

  /** Run immediately, cancelling any debounce or in-flight request. */
  runNow(text: string): Promise<void> {
    this.clearTimer();
    return this.execute(text);
  }

  /** Stop everything. Called when the component unmounts. */
  dispose(): void {
    this.clearTimer();
    this.abortInFlight();
  }

  private clearTimer(): void {
    if (this.timer !== null) {
      clearTimeout(this.timer);
      this.timer = null;
    }
  }

  private abortInFlight(): void {
    this.controller?.abort();
    this.controller = null;
  }

  private emit(next: Partial<ProofreadState>): void {
    this.state = { ...this.state, ...next };
    this.onChange(this.state);
  }

  private async execute(text: string): Promise<void> {
    this.abortInFlight();

    if (text.trim() === "") {
      // Nothing to analyse. Publish an empty result so stale underlines from a
      // previous document do not linger.
      this.sequence += 1;
      this.emit({ status: "idle", analysedText: text, result: null, error: null });
      return;
    }

    const controller = new AbortController();
    this.controller = controller;
    const runId = ++this.sequence;

    this.emit({ status: "pending", error: null });

    try {
      const result = await this.run(text, controller.signal);
      if (runId !== this.sequence) {
        // A newer run started while this one was in flight. Its result is the
        // one the user is waiting for; this one describes text that no longer
        // exists in the editor.
        return;
      }
      this.emit({ status: "done", analysedText: text, result, error: null });
    } catch (error) {
      if (runId !== this.sequence) return;
      if (isAbort(error)) return;
      this.emit({ status: "error", error });
    } finally {
      if (this.controller === controller) this.controller = null;
    }
  }
}

function isAbort(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "name" in error &&
    (error as { name: unknown }).name === "AbortError"
  );
}
