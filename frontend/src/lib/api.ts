/**
 * Typed client for the local backend.
 *
 * All requests are same-origin: in development Vite proxies `/api` to the
 * backend on loopback, and a production build is served next to it. Nothing
 * here can be pointed at a remote host.
 */

import type {
  HealthResponse,
  ModelsStatusResponse,
  PrivacyStatusResponse,
  ProofreadResponse,
} from "./types";

const API_BASE = "/api";

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch (cause) {
    // A network-level failure here means the local backend is not running;
    // there is no remote fallback to try.
    throw new ApiError("backend-unreachable", 0);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail =
      body && typeof body === "object" && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : response.statusText;
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>("/health", { signal });
}

export function getModelsStatus(signal?: AbortSignal): Promise<ModelsStatusResponse> {
  return request<ModelsStatusResponse>("/models/status", { signal });
}

export function getPrivacyStatus(signal?: AbortSignal): Promise<PrivacyStatusResponse> {
  return request<PrivacyStatusResponse>("/privacy/status", { signal });
}

export interface ProofreadOptions {
  engines?: string[];
  ignoreCodes?: string[];
  signal?: AbortSignal;
}

export function proofread(
  text: string,
  options: ProofreadOptions = {},
): Promise<ProofreadResponse> {
  return request<ProofreadResponse>("/proofread", {
    method: "POST",
    body: JSON.stringify({
      text,
      engines: options.engines ?? null,
      ignoreCodes: options.ignoreCodes ?? [],
    }),
    signal: options.signal,
  });
}
