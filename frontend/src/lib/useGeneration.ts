/**
 * Running a local model from the UI.
 *
 * Local generation takes seconds to minutes, so two things matter beyond just
 * calling the endpoint: the user must be able to cancel, and a result that
 * arrives after they cancelled or re-ran must not appear. The sequence guard
 * here is the same idea as the proofreading scheduler's — aborting alone is not
 * enough, because a request can be past cancellation when it is superseded.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "./api";
import { is } from "../i18n/is";
import type { GenerationResponse } from "./types";

export interface GenerationState {
  result: GenerationResponse | null;
  busy: boolean;
  error: string | null;
}

export interface UseGeneration extends GenerationState {
  run: (call: (signal: AbortSignal) => Promise<GenerationResponse>) => Promise<void>;
  cancel: () => void;
  discard: () => void;
}

export function useGeneration(): UseGeneration {
  const [result, setResult] = useState<GenerationResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const controllerRef = useRef<AbortController | null>(null);
  const sequenceRef = useRef(0);

  const cancel = useCallback(() => {
    controllerRef.current?.abort();
    controllerRef.current = null;
    // Bump the sequence so an in-flight response can no longer publish.
    sequenceRef.current += 1;
    setBusy(false);
  }, []);

  const discard = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  const run = useCallback(
    async (call: (signal: AbortSignal) => Promise<GenerationResponse>) => {
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;
      const runId = ++sequenceRef.current;

      setBusy(true);
      setError(null);

      try {
        const response = await call(controller.signal);
        if (runId !== sequenceRef.current) return;
        setResult(response);
      } catch (cause) {
        if (runId !== sequenceRef.current) return;
        if (isAbort(cause)) return;
        setError(describe(cause));
      } finally {
        if (runId === sequenceRef.current) setBusy(false);
        if (controllerRef.current === controller) controllerRef.current = null;
      }
    },
    [],
  );

  useEffect(() => () => controllerRef.current?.abort(), []);

  return { result, busy, error, run, cancel, discard };
}

function isAbort(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "name" in error &&
    (error as { name: unknown }).name === "AbortError"
  );
}

function describe(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 0) return is.errors.backendUnreachable;
    if (error.status === 413) return is.errors.textTooLong;
    // 503 carries an Icelandic, user-facing explanation from the backend —
    // "start Ollama", "pick a model" — which is more useful than a generic
    // failure message.
    if (error.status === 503) return error.message;
  }
  return is.errors.generationFailed;
}
