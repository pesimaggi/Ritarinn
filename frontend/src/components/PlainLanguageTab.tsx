/**
 * Á mannamáli — rewrite the document for a chosen audience and style.
 */

import { useState } from "react";

import { is } from "../i18n/is";
import { simplify } from "../lib/api";
import { useGeneration } from "../lib/useGeneration";
import type { Audience, ModelsStatusResponse, SimplifyStyle } from "../lib/types";
import { GenerationPanel } from "./GenerationPanel";
import { OptionGroup } from "./OptionGroup";

const AUDIENCES: readonly { value: Audience; label: string }[] = [
  { value: "general", label: is.generation.audience.general },
  { value: "experts", label: is.generation.audience.experts },
  { value: "managers", label: is.generation.audience.managers },
  { value: "customers", label: is.generation.audience.customers },
  { value: "youth", label: is.generation.audience.youth },
];

const STYLES: readonly { value: SimplifyStyle; label: string }[] = [
  { value: "plain", label: is.generation.style.plain },
  { value: "concise", label: is.generation.style.concise },
  { value: "formal", label: is.generation.style.formal },
  { value: "neutral", label: is.generation.style.neutral },
  { value: "friendly", label: is.generation.style.friendly },
];

export interface PlainLanguageTabProps {
  text: string;
  models: ModelsStatusResponse | null;
  onAccept: (text: string) => void;
}

export function PlainLanguageTab({ text, models, onAccept }: PlainLanguageTabProps) {
  const [audience, setAudience] = useState<Audience>("general");
  // Plain language is the emphasis: it is what bureaucratic, legal, scientific
  // and technical writing most needs.
  const [style, setStyle] = useState<SimplifyStyle>("plain");
  const [proofreadOutput, setProofreadOutput] = useState(true);
  const generation = useGeneration();

  return (
    <GenerationPanel
      heading={is.generation.plainLanguageHeading}
      controls={
        <>
          <OptionGroup
            label={is.generation.audienceLabel}
            name="simplify-audience"
            value={audience}
            options={AUDIENCES}
            onChange={setAudience}
            disabled={generation.busy}
          />
          <OptionGroup
            label={is.generation.styleLabel}
            name="simplify-style"
            value={style}
            options={STYLES}
            onChange={setStyle}
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
      // A rewrite replaces the source, so the user needs to see exactly what
      // changed before accepting it.
      compareMode="diff"
      onRun={() =>
        void generation.run((signal) =>
          simplify(text, { audience, style, proofread: proofreadOutput, signal }),
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
