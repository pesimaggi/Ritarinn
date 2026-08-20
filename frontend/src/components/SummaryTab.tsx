/**
 * Samantekt — summarize the document with the local model.
 */

import { is } from "../i18n/is";
import { summarize } from "../lib/api";
import { useGeneration } from "../lib/useGeneration";
import type { ModelsStatusResponse, SummaryForm, SummaryLength } from "../lib/types";
import { GenerationPanel } from "./GenerationPanel";
import { OptionGroup } from "./OptionGroup";
import { useState } from "react";

const LENGTHS: readonly { value: SummaryLength; label: string }[] = [
  { value: "very_short", label: is.generation.length.very_short },
  { value: "short", label: is.generation.length.short },
  { value: "medium", label: is.generation.length.medium },
  { value: "detailed", label: is.generation.length.detailed },
];

const FORMS: readonly { value: SummaryForm; label: string }[] = [
  { value: "prose", label: is.generation.form.prose },
  { value: "bullets", label: is.generation.form.bullets },
];

export interface SummaryTabProps {
  text: string;
  models: ModelsStatusResponse | null;
  onAccept: (text: string) => void;
}

export function SummaryTab({ text, models, onAccept }: SummaryTabProps) {
  const [length, setLength] = useState<SummaryLength>("medium");
  const [form, setForm] = useState<SummaryForm>("prose");
  const [proofreadOutput, setProofreadOutput] = useState(true);
  const generation = useGeneration();

  return (
    <GenerationPanel
      heading={is.generation.summaryHeading}
      controls={
        <>
          <OptionGroup
            label={is.generation.lengthLabel}
            name="summary-length"
            value={length}
            options={LENGTHS}
            onChange={setLength}
            disabled={generation.busy}
          />
          <OptionGroup
            label={is.generation.formLabel}
            name="summary-form"
            value={form}
            options={FORMS}
            onChange={setForm}
            disabled={generation.busy}
          />
        </>
      }
      original={text}
      result={generation.result}
      busy={generation.busy}
      error={generation.error}
      models={models}
      proofreadOutput={proofreadOutput}
      onProofreadOutputChange={setProofreadOutput}
      // A summary is a new artifact rather than an edit of the source, so a
      // word-level diff against the original would be noise.
      compareMode="sideBySide"
      onRun={() =>
        void generation.run((signal) =>
          summarize(text, { length, form, proofread: proofreadOutput, signal }),
        )
      }
      onCancel={generation.cancel}
      onAccept={() => {
        if (generation.result) onAccept(generation.result.text);
      }}
      onDiscard={generation.discard}
    />
  );
}
