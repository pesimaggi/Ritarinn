/**
 * The review step for generated text.
 *
 * The invariant these protect: generated text never reaches the document
 * without an explicit acceptance.
 */

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { GenerationPanel } from "./GenerationPanel";
import type { GenerationResponse, ModelsStatusResponse, WritingIssue } from "../lib/types";

const READY_MODELS: ModelsStatusResponse = {
  correctionEngines: [
    { name: "greynir", label: "GreynirCorrect", available: true, localOnly: true },
  ],
  llmProviders: [
    {
      name: "ollama",
      label: "Ollama",
      available: true,
      models: [],
      selectedModel: "prófunarlíkan",
      localOnly: true,
      canGenerate: true,
    },
  ],
  proofreadingReady: true,
  generationReady: true,
};

function result(overrides: Partial<GenerationResponse> = {}): GenerationResponse {
  return {
    text: "Stutt samantekt á íslensku.",
    model: "prófunarlíkan",
    chunks: 1,
    passes: 1,
    elapsedMs: 1234,
    issues: [],
    offsetUnit: "utf16",
    truncated: false,
    ...overrides,
  };
}

function renderPanel(overrides: Partial<Parameters<typeof GenerationPanel>[0]> = {}) {
  const props = {
    heading: "Samantekt",
    controls: null,
    original: "Upprunalegur texti sem á að draga saman.",
    result: null as GenerationResponse | null,
    busy: false,
    error: null as string | null,
    models: READY_MODELS,
    proofreadOutput: true,
    onProofreadOutputChange: vi.fn(),
    compareMode: "sideBySide" as const,
    onRun: vi.fn(),
    onCancel: vi.fn(),
    onAccept: vi.fn(),
    onDiscard: vi.fn(),
    ...overrides,
  };
  render(<GenerationPanel {...props} />);
  return props;
}

describe("GenerationPanel", () => {
  it("runs when asked", () => {
    const props = renderPanel();
    fireEvent.click(screen.getByRole("button", { name: "Búa til" }));
    expect(props.onRun).toHaveBeenCalled();
  });

  it("offers cancellation while running", () => {
    const props = renderPanel({ busy: true });
    fireEvent.click(screen.getByRole("button", { name: "Hætta við" }));
    expect(props.onCancel).toHaveBeenCalled();
  });

  it("shows the generated text with the model that produced it", () => {
    renderPanel({ result: result() });
    // Appears twice by design: once as the result, once in the comparison.
    expect(screen.getAllByText("Stutt samantekt á íslensku.")).toHaveLength(2);
    expect(screen.getByText(/prófunarlíkan/)).toBeDefined();
  });

  it("offers Samþykkja, Afrita and Hafna", () => {
    renderPanel({ result: result() });
    expect(screen.getByRole("button", { name: "Samþykkja" })).toBeDefined();
    expect(screen.getByRole("button", { name: "Afrita" })).toBeDefined();
    expect(screen.getByRole("button", { name: "Hafna" })).toBeDefined();
  });

  it("applies nothing until Samþykkja is clicked", () => {
    const props = renderPanel({ result: result() });
    expect(props.onAccept).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Samþykkja" }));
    expect(props.onAccept).toHaveBeenCalledTimes(1);
  });

  it("discards on Hafna without applying anything", () => {
    const props = renderPanel({ result: result() });
    fireEvent.click(screen.getByRole("button", { name: "Hafna" }));
    expect(props.onDiscard).toHaveBeenCalled();
    expect(props.onAccept).not.toHaveBeenCalled();
  });

  it("shows the original alongside the proposal", () => {
    renderPanel({ result: result() });
    expect(screen.getByText("Upprunalegur texti sem á að draga saman.")).toBeDefined();
  });

  it("says how a long document was divided", () => {
    renderPanel({ result: result({ chunks: 4, passes: 2 }) });
    expect(screen.getByText(/skipt í 4 hluta/)).toBeDefined();
  });

  it("warns when the model hit its output cap", () => {
    renderPanel({ result: result({ truncated: true }) });
    expect(screen.getByText(/ófullgerð/)).toBeDefined();
  });

  it("reports issues found in the generated text and says it was not altered", () => {
    const issue: WritingIssue = {
      id: "greynir-0",
      source: "greynir",
      category: "spelling",
      code: "S004",
      family: "Stafsetning",
      scope: "span",
      startChar: 0,
      endChar: 7,
      original: "Þinngið",
      replacement: "Þingið",
      alternatives: [],
      title: "Orðið 'Þinngið' var leiðrétt í 'Þingið'",
      severity: "error",
      references: [],
    };
    renderPanel({ result: result({ issues: [issue] }) });

    expect(screen.getByText(/1 ábending fannst í útkomunni/)).toBeDefined();
    expect(screen.getByText("Þinngið")).toBeDefined();
    expect(screen.getByText(/hefur ekki verið breytt/)).toBeDefined();
  });

  it("says so when the generated text has no issues", () => {
    renderPanel({ result: result() });
    expect(screen.getByText(/Engar ábendingar fundust/)).toBeDefined();
  });

  it("blocks running when no local model is selected", () => {
    renderPanel({
      models: {
        ...READY_MODELS,
        llmProviders: [
          { ...READY_MODELS.llmProviders[0]!, selectedModel: null, canGenerate: false },
        ],
      },
    });
    expect(screen.getByRole("button", { name: "Búa til" })).toHaveProperty("disabled", true);
    expect(screen.getByText(/Ekkert staðbundið líkan/)).toBeDefined();
  });

  it("blocks running when the local runtime is not found", () => {
    renderPanel({
      models: {
        ...READY_MODELS,
        llmProviders: [
          { ...READY_MODELS.llmProviders[0]!, available: false, canGenerate: false },
        ],
      },
    });
    expect(screen.getByRole("button", { name: "Búa til" })).toHaveProperty("disabled", true);
    expect(screen.getByText(/Ollama fannst ekki/)).toBeDefined();
  });

  it("blocks running with no text", () => {
    renderPanel({ original: "   " });
    expect(screen.getByRole("button", { name: "Búa til" })).toHaveProperty("disabled", true);
  });

  it("shows an error without offering the result", () => {
    renderPanel({ error: "Textagerð mistókst." });
    expect(screen.getByRole("alert").textContent).toContain("Textagerð mistókst.");
    expect(screen.queryByRole("button", { name: "Samþykkja" })).toBeNull();
  });
});
