/**
 * Ordering and cancellation for local generation.
 *
 * Local generation is slow enough that a user will re-run or cancel while a
 * request is in flight. Neither may result in a stale proposal appearing —
 * accepting one would put text into the document that the user never asked for.
 */

import { describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";

import { ApiError } from "./api";
import { useGeneration } from "./useGeneration";
import type { GenerationResponse } from "./types";

function response(text: string): GenerationResponse {
  return {
    text,
    model: "prófunarlíkan",
    chunks: 1,
    passes: 1,
    elapsedMs: 10,
    issues: [],
    offsetUnit: "utf16",
    truncated: false,
  };
}

/** A call whose resolution is controlled by the test. */
function deferred() {
  let resolve!: (value: GenerationResponse) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<GenerationResponse>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("useGeneration", () => {
  it("publishes a result", async () => {
    const { result } = renderHook(() => useGeneration());
    await act(async () => {
      await result.current.run(async () => response("Samantekt."));
    });
    expect(result.current.result?.text).toBe("Samantekt.");
    expect(result.current.busy).toBe(false);
  });

  it("reports busy while running", async () => {
    const { result } = renderHook(() => useGeneration());
    const first = deferred();

    act(() => {
      void result.current.run(() => first.promise);
    });
    await waitFor(() => expect(result.current.busy).toBe(true));

    await act(async () => {
      first.resolve(response("Samantekt."));
      await first.promise;
    });
    await waitFor(() => expect(result.current.busy).toBe(false));
  });

  it("ignores a result that arrives after cancellation", async () => {
    const { result } = renderHook(() => useGeneration());
    const call = deferred();

    act(() => {
      void result.current.run(() => call.promise);
    });
    await waitFor(() => expect(result.current.busy).toBe(true));

    act(() => result.current.cancel());
    await act(async () => {
      call.resolve(response("of seint"));
      await call.promise;
    });

    expect(result.current.result).toBeNull();
    expect(result.current.busy).toBe(false);
  });

  it("aborts the in-flight request when cancelled", async () => {
    const { result } = renderHook(() => useGeneration());
    let signal: AbortSignal | null = null;

    act(() => {
      void result.current.run((s) => {
        signal = s;
        return deferred().promise;
      });
    });
    await waitFor(() => expect(signal).not.toBeNull());

    act(() => result.current.cancel());
    expect(signal!.aborted).toBe(true);
  });

  it("keeps only the newest result when a run is superseded", async () => {
    const { result } = renderHook(() => useGeneration());
    const first = deferred();
    const second = deferred();

    act(() => {
      void result.current.run(() => first.promise);
    });
    act(() => {
      void result.current.run(() => second.promise);
    });

    await act(async () => {
      second.resolve(response("nýrri"));
      await second.promise;
      first.resolve(response("eldri"));
      await first.promise;
    });

    expect(result.current.result?.text).toBe("nýrri");
  });

  it("surfaces the backend's Icelandic explanation for a 503", async () => {
    // The backend says what to do — start Ollama, choose a model — which is
    // more useful than a generic failure message.
    const { result } = renderHook(() => useGeneration());
    await act(async () => {
      await result.current.run(async () => {
        throw new ApiError("Ekkert staðbundið líkan er valið.", 503);
      });
    });
    expect(result.current.error).toBe("Ekkert staðbundið líkan er valið.");
  });

  it("reports an unreachable backend in Icelandic", async () => {
    const { result } = renderHook(() => useGeneration());
    await act(async () => {
      await result.current.run(async () => {
        throw new ApiError("backend-unreachable", 0);
      });
    });
    expect(result.current.error).toMatch(/bakenda/);
  });

  it("does not report an aborted request as a failure", async () => {
    const { result } = renderHook(() => useGeneration());
    await act(async () => {
      await result.current.run(async () => {
        const error = new Error("aborted");
        error.name = "AbortError";
        throw error;
      });
    });
    expect(result.current.error).toBeNull();
  });

  it("discards a result without running anything", async () => {
    const run = vi.fn(async () => response("Samantekt."));
    const { result } = renderHook(() => useGeneration());
    await act(async () => {
      await result.current.run(run);
    });
    act(() => result.current.discard());

    expect(result.current.result).toBeNull();
    expect(run).toHaveBeenCalledTimes(1);
  });
});
