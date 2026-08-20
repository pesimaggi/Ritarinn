/**
 * Rendering of a single suggestion.
 */

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { IssueCard, stripMarkup } from "./IssueCard";
import type { WritingIssue } from "../lib/types";

const ISSUE: WritingIssue = {
  id: "greynir-0",
  source: "greynir",
  category: "grammar",
  code: "P_WRONG_CASE_þgf_þf",
  family: "Málfræði",
  scope: "span",
  startChar: 0,
  endChar: 17,
  original: "Páli, vini mínum,",
  replacement: "Pál, vin minn",
  alternatives: [],
  title: "Á líklega að vera 'Pál, vin minn'",
  explanation: "Sögnin 'að langa' er ópersónuleg.",
  severity: "error",
  references: [],
};

describe("IssueCard", () => {
  it("shows the original text, the suggestion and the explanation", () => {
    render(
      <IssueCard issue={ISSUE} selected={false} onSelect={() => {}} onAccept={() => {}} onIgnore={() => {}} />,
    );
    expect(screen.getByText("Páli, vini mínum,")).toBeDefined();
    expect(screen.getByText("Pál, vin minn")).toBeDefined();
    expect(screen.getByText(/ópersónuleg/)).toBeDefined();
  });

  it("offers Samþykkja and Hunsa in Icelandic", () => {
    render(
      <IssueCard issue={ISSUE} selected={false} onSelect={() => {}} onAccept={() => {}} onIgnore={() => {}} />,
    );
    expect(screen.getByRole("button", { name: "Samþykkja" })).toBeDefined();
    expect(screen.getByRole("button", { name: "Hunsa" })).toBeDefined();
  });

  it("reports acceptance and ignoring by issue id", () => {
    const onAccept = vi.fn();
    const onIgnore = vi.fn();
    render(
      <IssueCard issue={ISSUE} selected={false} onSelect={() => {}} onAccept={onAccept} onIgnore={onIgnore} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Samþykkja" }));
    fireEvent.click(screen.getByRole("button", { name: "Hunsa" }));

    expect(onAccept).toHaveBeenCalledWith(ISSUE.id);
    expect(onIgnore).toHaveBeenCalledWith(ISSUE.id);
  });

  it("disables acceptance when there is nothing to apply", () => {
    render(
      <IssueCard
        issue={{ ...ISSUE, replacement: null }}
        selected={false}
        onSelect={() => {}}
        onAccept={() => {}}
        onIgnore={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: "Samþykkja" })).toHaveProperty("disabled", true);
    expect(screen.getByText("Engin sjálfvirk tillaga í boði.")).toBeDefined();
  });

  it("shows the engine's own error code", () => {
    render(
      <IssueCard issue={ISSUE} selected={false} onSelect={() => {}} onAccept={() => {}} onIgnore={() => {}} />,
    );
    expect(screen.getByText("P_WRONG_CASE_þgf_þf")).toBeDefined();
  });
});

describe("stripMarkup", () => {
  it("removes the anchor tags GreynirCorrect embeds in explanations", () => {
    expect(stripMarkup('Sjá <a href="#">ritreglur</a> um þetta.')).toBe("Sjá ritreglur um þetta.");
  });

  it("leaves plain Icelandic untouched", () => {
    expect(stripMarkup("Sögnin 'að langa' er ópersónuleg.")).toBe(
      "Sögnin 'að langa' er ópersónuleg.",
    );
  });

  it("neutralises markup rather than rendering it", () => {
    expect(stripMarkup("<script>alert(1)</script>")).toBe("alert(1)");
  });
});
