/**
 * ConsensusBadge unit tests — TrainPlex Phase 1 Step 6.
 *
 * Covers the four consensus statuses + the pending state + a non-default
 * total_reviewers panel size. Verifies aria-label so screen-reader users
 * get a meaningful summary of "agreed N of T".
 */

import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { ConsensusBadge } from "../ConsensusBadge";

describe("ConsensusBadge", () => {
  it("renders 3 dots by default (panel size 3)", () => {
    render(<ConsensusBadge status="approved" agreedCount={3} />);
    expect(screen.getByTestId("consensus-badge-dot-0")).toBeInTheDocument();
    expect(screen.getByTestId("consensus-badge-dot-1")).toBeInTheDocument();
    expect(screen.getByTestId("consensus-badge-dot-2")).toBeInTheDocument();
  });

  it("approved → all 3 dots are green", () => {
    render(<ConsensusBadge status="approved" agreedCount={3} totalReviewers={3} />);
    [0, 1, 2].forEach((i) => {
      const dot = screen.getByTestId(`consensus-badge-dot-${i}`);
      expect(dot).toHaveStyle({ "background-color": "#2BB673" });
    });
  });

  it("rejected → all 3 dots are red", () => {
    render(<ConsensusBadge status="rejected" agreedCount={0} totalReviewers={3} />);
    [0, 1, 2].forEach((i) => {
      const dot = screen.getByTestId(`consensus-badge-dot-${i}`);
      expect(dot).toHaveStyle({ "background-color": "#E54848" });
    });
  });

  it("flagged 2/3 → 2 green dots, 1 red dot", () => {
    render(<ConsensusBadge status="flagged" agreedCount={2} totalReviewers={3} />);
    expect(screen.getByTestId("consensus-badge-dot-0")).toHaveStyle({
      "background-color": "#2BB673",
    });
    expect(screen.getByTestId("consensus-badge-dot-1")).toHaveStyle({
      "background-color": "#2BB673",
    });
    expect(screen.getByTestId("consensus-badge-dot-2")).toHaveStyle({
      "background-color": "#E54848",
    });
  });

  it("dispute 1/3 → 1 green dot, 2 red dots", () => {
    render(<ConsensusBadge status="dispute" agreedCount={1} totalReviewers={3} />);
    expect(screen.getByTestId("consensus-badge-dot-0")).toHaveStyle({
      "background-color": "#2BB673",
    });
    expect(screen.getByTestId("consensus-badge-dot-1")).toHaveStyle({
      "background-color": "#E54848",
    });
    expect(screen.getByTestId("consensus-badge-dot-2")).toHaveStyle({
      "background-color": "#E54848",
    });
  });

  it("pending → all dots are grey", () => {
    render(<ConsensusBadge status="pending" />);
    [0, 1, 2].forEach((i) => {
      const dot = screen.getByTestId(`consensus-badge-dot-${i}`);
      expect(dot).toHaveStyle({ "background-color": "#C7C9D9" });
    });
  });

  it("null / undefined status → all dots are grey", () => {
    render(<ConsensusBadge status={null} agreedCount={0} />);
    expect(screen.getByTestId("consensus-badge-dot-0")).toHaveStyle({
      "background-color": "#C7C9D9",
    });
  });

  it("respects custom totalReviewers", () => {
    render(<ConsensusBadge status="flagged" agreedCount={3} totalReviewers={5} />);
    // 5 dots, first 3 green, last 2 red.
    expect(screen.getByTestId("consensus-badge-dot-4")).toBeInTheDocument();
    expect(screen.queryByTestId("consensus-badge-dot-5")).not.toBeInTheDocument();
    expect(screen.getByTestId("consensus-badge-dot-2")).toHaveStyle({
      "background-color": "#2BB673",
    });
    expect(screen.getByTestId("consensus-badge-dot-3")).toHaveStyle({
      "background-color": "#E54848",
    });
  });

  it("auto-generates aria-label summarising agreement", () => {
    render(<ConsensusBadge status="flagged" agreedCount={2} totalReviewers={3} />);
    const badge = screen.getByTestId("consensus-badge");
    expect(badge).toHaveAttribute("aria-label", "Agreed 2 of 3 (flagged)");
  });

  it("accepts a custom ariaLabel override", () => {
    render(
      <ConsensusBadge
        status="approved"
        agreedCount={3}
        ariaLabel="Custom screen-reader label"
      />,
    );
    expect(screen.getByTestId("consensus-badge")).toHaveAttribute(
      "aria-label",
      "Custom screen-reader label",
    );
  });

  it("clamps agreedCount above totalReviewers without overflow", () => {
    render(<ConsensusBadge status="approved" agreedCount={99} totalReviewers={3} />);
    // Still renders exactly 3 dots, all green.
    expect(screen.queryByTestId("consensus-badge-dot-3")).not.toBeInTheDocument();
    [0, 1, 2].forEach((i) => {
      const dot = screen.getByTestId(`consensus-badge-dot-${i}`);
      expect(dot).toHaveStyle({ "background-color": "#2BB673" });
    });
  });

  it("clamps negative agreedCount to 0", () => {
    render(<ConsensusBadge status="rejected" agreedCount={-5} totalReviewers={3} />);
    [0, 1, 2].forEach((i) => {
      const dot = screen.getByTestId(`consensus-badge-dot-${i}`);
      expect(dot).toHaveStyle({ "background-color": "#E54848" });
    });
  });

  it("uses a custom testId prefix", () => {
    render(
      <ConsensusBadge
        status="approved"
        agreedCount={3}
        testId="my-prefix"
      />,
    );
    expect(screen.getByTestId("my-prefix")).toBeInTheDocument();
    expect(screen.getByTestId("my-prefix-dot-0")).toBeInTheDocument();
  });
});
