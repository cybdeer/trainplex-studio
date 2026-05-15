/**
 * Tests for Step 3 — Assign Trainers.
 * Phase 1 Step 4.2-2.
 *
 * Covers: filter chips toggle the trainer table contents, checkbox-select
 * round-trips through `onSelectionChange`, and the bilingual filter labels
 * resolve through the mocked `t()`.
 */

/* eslint-disable @typescript-eslint/no-var-requires */

import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";

jest.mock("@humansignal/app-common", () => ({
  useTranslation: () => ({
    t: (key: string, opts?: any) =>
      opts && typeof opts.count === "number" ? `${key}:${opts.count}` : key,
    i18n: { language: "en" },
  }),
}));

import { Step3Assign, MOCK_TRAINERS } from "../Step3_Assign";

describe("Step3_Assign", () => {
  it("renders one row per mock trainer", () => {
    render(<Step3Assign selectedIds={[]} onSelectionChange={() => {}} />);
    expect(screen.getByTestId("trainer-table")).toBeInTheDocument();
    MOCK_TRAINERS.forEach((tr) => {
      expect(screen.getByTestId(`trainer-row-${tr.id}`)).toBeInTheDocument();
    });
  });

  it("renders all four filter groups (state, tier, language, cert)", () => {
    render(<Step3Assign selectedIds={[]} onSelectionChange={() => {}} />);
    expect(screen.getByTestId("filter-state-group")).toBeInTheDocument();
    expect(screen.getByTestId("filter-tier-group")).toBeInTheDocument();
    expect(screen.getByTestId("filter-language-group")).toBeInTheDocument();
    expect(screen.getByTestId("filter-cert-group")).toBeInTheDocument();
  });

  it("filters the table when a state chip is toggled on", () => {
    render(<Step3Assign selectedIds={[]} onSelectionChange={() => {}} />);
    // Rajasthan is "Geeta P." only (id=5) in the mock roster.
    fireEvent.click(screen.getByTestId("filter-state-Rajasthan"));
    expect(screen.getByTestId("trainer-row-5")).toBeInTheDocument();
    // Anil K. (Bihar, id=12) should no longer be in the DOM.
    expect(screen.queryByTestId("trainer-row-12")).not.toBeInTheDocument();
  });

  it("combines tier and state filters with AND semantics", () => {
    render(<Step3Assign selectedIds={[]} onSelectionChange={() => {}} />);
    fireEvent.click(screen.getByTestId("filter-state-Rajasthan"));
    fireEvent.click(screen.getByTestId("filter-tier-silver"));
    // Geeta is gold-tier in Rajasthan, so silver+Rajasthan should be empty.
    expect(screen.getByTestId("trainer-empty")).toBeInTheDocument();
  });

  it("filters by language overlap", () => {
    render(<Step3Assign selectedIds={[]} onSelectionChange={() => {}} />);
    fireEvent.click(screen.getByTestId("filter-language-Tamil"));
    // Karthik R. (id=42, Tamil Nadu) should remain.
    expect(screen.getByTestId("trainer-row-42")).toBeInTheDocument();
    // Geeta (id=5, Hindi only) should be filtered out.
    expect(screen.queryByTestId("trainer-row-5")).not.toBeInTheDocument();
  });

  it("calls onSelectionChange with the toggled id when checkbox clicked", () => {
    const handler = jest.fn();
    render(<Step3Assign selectedIds={[]} onSelectionChange={handler} />);
    fireEvent.click(screen.getByTestId("trainer-checkbox-7"));
    expect(handler).toHaveBeenCalledWith([7]);
  });

  it("deselects when an already-selected checkbox is clicked", () => {
    const handler = jest.fn();
    render(<Step3Assign selectedIds={[5, 7]} onSelectionChange={handler} />);
    fireEvent.click(screen.getByTestId("trainer-checkbox-5"));
    expect(handler).toHaveBeenCalledWith([7]);
  });

  it("renders the selected-count summary including the count value", () => {
    render(<Step3Assign selectedIds={[5, 7, 12]} onSelectionChange={() => {}} />);
    expect(screen.getByTestId("wizard-selected-summary")).toHaveTextContent("3");
  });
});
