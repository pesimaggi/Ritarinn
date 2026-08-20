/**
 * The scheduler's ordering guarantees.
 *
 * These are the tests that stop a stale response from painting the wrong
 * underlines — the failure mode is subtle in a browser and obvious here.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProofreadScheduler } from "./proofreadScheduler";
import type { ProofreadResponse } from "./types";

function response(marker: string): ProofreadResponse {
  return {
    issues: [
      {
        id: marker,
        source: "greynir",
        category: "spelling",
        code: "S004",
        family: "Stafsetning",
        startChar: 0,
        endChar: 1,
        scope: "span",
        original: marker,
        replacement: marker,
        alternatives: [],
        title: marker,
        severity: "error",
        references: [],
      },
    ],
    offsetUnit: "utf16",
    engines: ["greynir"],
    stats: {},
  };
}

/** A run function whose individual calls can be resolved in any order. */
function controllable() {
  const pending: { text: string; resolve: (value: ProofreadResponse) => void; signal: AbortSignal }[] =
    [];
  const run = (text: string, signal: AbortSignal) =>
    new Promise<ProofreadResponse>((resolve) => {
      pending.push({ text, resolve, signal });
    });
  return { pending, run };
}

describe("ProofreadScheduler", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("waits for the debounce interval before running", async () => {
    const run = vi.fn(async () => response("a"));
    const scheduler = new ProofreadScheduler({ debounceMs: 800, run, onChange: () => {} });

    scheduler.schedule("Þinngið");
    expect(run).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(799);
    expect(run).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1);
    expect(run).toHaveBeenCalledTimes(1);
  });

  it("collapses rapid typing into a single run", async () => {
    const run = vi.fn(async () => response("a"));
    const scheduler = new ProofreadScheduler({ debounceMs: 800, run, onChange: () => {} });

    for (const text of ["Þ", "Þi", "Þin", "Þinn"]) {
      scheduler.schedule(text);
      await vi.advanceTimersByTimeAsync(100);
    }
    await vi.advanceTimersByTimeAsync(800);

    expect(run).toHaveBeenCalledTimes(1);
    expect(run.mock.calls[0]?.[0]).toBe("Þinn");
  });

  it("ignores a slow response for older text", async () => {
    // The core guarantee: a request that started first but finished last must
    // not overwrite results for text the user has since typed.
    const { pending, run } = controllable();
    const states: string[] = [];
    const scheduler = new ProofreadScheduler({
      debounceMs: 0,
      run,
      onChange: (state) => {
        if (state.status === "done") states.push(state.analysedText);
      },
    });

    // Started first, but deliberately left in flight.
    const firstRun = scheduler.runNow("gamli textinn");
    const firstCall = pending[0]!;

    const secondRun = scheduler.runNow("nýi textinn");
    const secondCall = pending[1]!;

    // The newer request finishes first, then the older one arrives late.
    secondCall.resolve(response("new"));
    await secondRun;
    firstCall.resolve(response("old"));
    await firstRun;

    expect(states).toEqual(["nýi textinn"]);
  });

  it("aborts a request that has been superseded", async () => {
    const { pending, run } = controllable();
    const scheduler = new ProofreadScheduler({ debounceMs: 0, run, onChange: () => {} });

    void scheduler.runNow("fyrsti");
    const first = pending[0]!;
    expect(first.signal.aborted).toBe(false);

    void scheduler.runNow("annar");
    expect(first.signal.aborted).toBe(true);
  });

  it("publishes an empty result for empty text instead of leaving stale issues", async () => {
    const run = vi.fn(async () => response("a"));
    const seen: (string | null)[] = [];
    const scheduler = new ProofreadScheduler({
      debounceMs: 0,
      run,
      onChange: (state) => seen.push(state.result === null ? null : "issues"),
    });

    await scheduler.runNow("Þinngið");
    await scheduler.runNow("   ");

    expect(run).toHaveBeenCalledTimes(1);
    expect(seen.at(-1)).toBeNull();
  });

  it("reports an error without discarding the previous analysed text", async () => {
    const run = vi.fn(async () => {
      throw new Error("boom");
    });
    let last: string | null = null;
    const scheduler = new ProofreadScheduler({
      debounceMs: 0,
      run,
      onChange: (state) => {
        if (state.status === "error") last = "error";
      },
    });

    await scheduler.runNow("Þinngið");
    expect(last).toBe("error");
  });

  it("swallows abort errors rather than reporting them as failures", async () => {
    const run = vi.fn(async (_text: string, signal: AbortSignal) => {
      await new Promise((resolve) => setTimeout(resolve, 10));
      if (signal.aborted) {
        const error = new Error("aborted");
        error.name = "AbortError";
        throw error;
      }
      return response("a");
    });
    const statuses: string[] = [];
    const scheduler = new ProofreadScheduler({
      debounceMs: 0,
      run,
      onChange: (state) => statuses.push(state.status),
    });

    const first = scheduler.runNow("fyrsti");
    void scheduler.runNow("annar");
    await vi.advanceTimersByTimeAsync(20);
    await first;

    expect(statuses).not.toContain("error");
  });

  it("stops pending work when disposed", async () => {
    const run = vi.fn(async () => response("a"));
    const scheduler = new ProofreadScheduler({ debounceMs: 800, run, onChange: () => {} });

    scheduler.schedule("Þinngið");
    scheduler.dispose();
    await vi.advanceTimersByTimeAsync(2000);

    expect(run).not.toHaveBeenCalled();
  });
});
