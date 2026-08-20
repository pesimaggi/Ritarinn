/**
 * First-run status: what is installed, what is optional, what is missing.
 *
 * Ritarinn never downloads a model on the user's behalf. This panel exists so
 * the absence of an LLM reads as a deliberate, documented state rather than as
 * something broken — proofreading works without one.
 */

import { is } from "../i18n/is";
import type { ModelsStatusResponse } from "../lib/types";

export interface SetupStatusProps {
  models: ModelsStatusResponse | null;
}

function Indicator({ ok }: { ok: boolean }) {
  return (
    <span className={`ritarinn-indicator${ok ? " is-ok" : ""}`} aria-hidden="true">
      {ok ? "✓" : "○"}
    </span>
  );
}

export function SetupStatus({ models }: SetupStatusProps) {
  if (!models) return null;

  const greynir = models.correctionEngines.find((e) => e.name === "greynir");
  const byt5 = models.correctionEngines.find((e) => e.name === "byt5");
  const ollama = models.llmProviders.find((p) => p.name === "ollama");

  return (
    <section className="ritarinn-setup">
      <div className="ritarinn-setup__group">
        <h3>{is.setup.heading}</h3>
        <p>
          <Indicator ok={Boolean(greynir?.available)} />
          {greynir?.label ?? "GreynirCorrect"}{" "}
          {greynir?.available ? is.setup.ready : is.setup.notInstalled}
        </p>
      </div>

      <div className="ritarinn-setup__group">
        <h3>{is.setup.llmHeading}</h3>
        <p>
          <Indicator ok={Boolean(ollama?.available)} />
          Ollama {ollama?.available ? is.setup.found : is.setup.notFound}
        </p>
        <p>
          <Indicator ok={Boolean(ollama?.selectedModel)} />
          {ollama?.selectedModel ?? is.setup.noModelSelected}
        </p>
        {ollama?.available && ollama.models.length > 0 && (
          <p className="ritarinn-setup__hint">{is.setup.modelsAvailable(ollama.models.length)}</p>
        )}
      </div>

      <div className="ritarinn-setup__group">
        <h3>{is.setup.neuralHeading}</h3>
        <p>
          <Indicator ok={Boolean(byt5?.available)} />
          ByT5 {byt5?.available ? is.setup.ready : is.setup.notInstalled}
        </p>
      </div>
    </section>
  );
}
