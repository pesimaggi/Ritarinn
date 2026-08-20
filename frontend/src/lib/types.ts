/**
 * Types mirroring the backend's JSON schemas (backend/ritarinn/models/).
 *
 * Character offsets are UTF-16 code units, matching JavaScript's
 * `String.length` and CodeMirror's document positions. The backend converts
 * from Python's code-point indexing before serialising, and states the unit in
 * `offsetUnit` so a mismatch is detectable rather than silent.
 */

export type IssueSource = "greynir" | "byt5" | "local-llm" | "style";
export type IssueCategory = "spelling" | "grammar" | "punctuation" | "style" | "unknown";
export type IssueSeverity = "error" | "warning";
/** Whether the span delimits the problem, or the sentence containing it. */
export type IssueScope = "span" | "sentence";

export interface WritingIssue {
  id: string;
  source: IssueSource;
  category: IssueCategory;
  code?: string | null;
  /** Icelandic label for the code's group, e.g. "Samsett orð". */
  family?: string | null;
  startChar: number;
  endChar: number;
  scope: IssueScope;
  original: string;
  replacement?: string | null;
  alternatives: string[];
  title: string;
  explanation?: string | null;
  severity: IssueSeverity;
  references: string[];
  /** Only set when an engine reports a genuine score. Greynir never does. */
  confidence?: number | null;
}

export interface ProofreadResponse {
  issues: WritingIssue[];
  offsetUnit: "utf16";
  engines: string[];
  stats: Record<string, number | string>;
}

export interface HealthResponse {
  status: "ok";
  version: string;
  proofreadingReady: boolean;
}

export interface EngineStatus {
  name: string;
  label: string;
  available: boolean;
  version?: string | null;
  detail?: string | null;
  localOnly: boolean;
  provenance?: string | null;
}

export interface ModelInfo {
  name: string;
  sizeBytes?: number | null;
  family?: string | null;
  details: Record<string, string>;
}

export interface ProviderStatus {
  name: string;
  label: string;
  available: boolean;
  endpoint?: string | null;
  version?: string | null;
  models: ModelInfo[];
  selectedModel?: string | null;
  detail?: string | null;
  localOnly: boolean;
  canGenerate: boolean;
}

export interface ModelsStatusResponse {
  correctionEngines: EngineStatus[];
  llmProviders: ProviderStatus[];
  proofreadingReady: boolean;
  generationReady: boolean;
}

export interface PrivacyStatusResponse {
  localOnly: boolean;
  bindHost: string;
  bindsToLoopbackOnly: boolean;
  allowedOrigins: string[];
  wildcardCors: boolean;
  remoteProviderConfigured: boolean;
  telemetryEnabled: boolean;
  outboundEndpoints: string[];
  summary: string;
}
