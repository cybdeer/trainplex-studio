/**
 * Tests for the CohortAnalysis page.
 * Phase 1 Step 7.
 *
 * Coverage
 * --------
 * - Overview heatmap renders one row per cohort with day 7/30/60/90 cells.
 * - Cohort definition pills switch the active state.
 * - Per-cohort detail sections render drop-off + earnings tables.
 * - Loading + error states.
 * - Non-admin sees RoleGate fallback.
 */

/* eslint-disable @typescript-eslint/no-var-requires */

import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import React from "react";

jest.mock("../../../../providers/ApiProvider", () => ({
  useAPI: () => ({ callApi: jest.fn() }),
  ApiContext: { Provider: ({ children }: any) => children },
}));

let mockUserRole: string | null = "admin";
jest.mock("@humansignal/core/providers/AuthProvider", () => ({
  useAuth: () => ({ user: { role: mockUserRole } }),
}));

let mockQueryState: any = { data: undefined, isFetching: true, isError: false };
const setMockQuery = (state: any) => {
  mockQueryState = state;
};
jest.mock("@tanstack/react-query", () => ({
  useQuery: () => mockQueryState,
}));

jest.mock("@humansignal/app-common", () => ({
  useTranslation: () => ({
    t: (key: string, opts?: any) => {
      if (opts && typeof opts.count === "number") return `${key}:${opts.count}`;
      return key;
    },
    i18n: { language: "en" },
  }),
}));

import { CohortAnalysis } from "../CohortAnalysis";
import type { CohortsPayload } from "../types";

const PAYLOAD: CohortsPayload = {
  cohort_definition: "signup_wave",
  cohorts: [
    {
      cohort_id: "wave-1-mar-2026",
      cohort_name: "Wave 1",
      cohort_start: "2026-03-04",
      cohort_size: 42,
      retention_curve: [
        { day: 7, retention_pct: 88 },
        { day: 30, retention_pct: 74 },
        { day: 60, retention_pct: 62 },
        { day: 90, retention_pct: 55 },
      ],
      productivity_curve: [
        { week: 1, avg_tasks_per_day: 4 },
        { week: 2, avg_tasks_per_day: 5 },
      ],
      earnings_curve: [
        { week: 1, cumulative_earnings_inr: 1800 },
        { week: 2, cumulative_earnings_inr: 3600 },
      ],
      drop_off_analysis: [
        { stage: "signed_up", trainers_remaining: 42, drop_pct: 0 },
        { stage: "completed_kyc", trainers_remaining: 38, drop_pct: 10 },
      ],
    },
  ],
};

const renderPage = () =>
  render(
    <MemoryRouter>
      <CohortAnalysis />
    </MemoryRouter>,
  );

describe("CohortAnalysis", () => {
  beforeEach(() => {
    mockUserRole = "admin";
  });

  it("renders the overview heatmap with retention cells", () => {
    setMockQuery({ data: PAYLOAD, isFetching: false, isError: false });
    renderPage();
    const grid = screen.getByTestId("cohort-overview-heatmap");
    expect(grid).toBeInTheDocument();
    expect(screen.getByTestId("cohort-wave-1-mar-2026-d7")).toHaveTextContent("88%");
    expect(screen.getByTestId("cohort-wave-1-mar-2026-d30")).toHaveTextContent("74%");
    expect(screen.getByTestId("cohort-wave-1-mar-2026-d60")).toHaveTextContent("62%");
    expect(screen.getByTestId("cohort-wave-1-mar-2026-d90")).toHaveTextContent("55%");
  });

  it("renders 3 definition pills and the default active state", () => {
    setMockQuery({ data: PAYLOAD, isFetching: false, isError: false });
    renderPage();
    expect(screen.getByTestId("cohort-def-signup_wave")).toBeInTheDocument();
    expect(screen.getByTestId("cohort-def-registration_week")).toBeInTheDocument();
    expect(screen.getByTestId("cohort-def-tier_promotion_month")).toBeInTheDocument();
    expect(screen.getByTestId("cohort-def-signup_wave")).toHaveAttribute("aria-pressed", "true");
  });

  it("clicking a definition pill updates aria-pressed", () => {
    setMockQuery({ data: PAYLOAD, isFetching: false, isError: false });
    renderPage();
    fireEvent.click(screen.getByTestId("cohort-def-registration_week"));
    expect(screen.getByTestId("cohort-def-registration_week")).toHaveAttribute("aria-pressed", "true");
  });

  it("renders per-cohort detail section", () => {
    setMockQuery({ data: PAYLOAD, isFetching: false, isError: false });
    renderPage();
    expect(screen.getByTestId("cohort-detail-wave-1-mar-2026")).toBeInTheDocument();
  });

  it("renders loading skeleton during fetch", () => {
    setMockQuery({ data: undefined, isFetching: true, isError: false });
    renderPage();
    expect(screen.getByTestId("cohorts-skeleton")).toBeInTheDocument();
  });

  it("renders error box on failure", () => {
    setMockQuery({ data: undefined, isFetching: false, isError: true });
    renderPage();
    expect(screen.getByTestId("cohorts-error")).toBeInTheDocument();
  });

  it("blocks non-admin", () => {
    mockUserRole = "trainer";
    renderPage();
    expect(screen.getByTestId("cohorts-forbidden")).toBeInTheDocument();
  });

  it("exposes route metadata", () => {
    expect(CohortAnalysis.path).toBe("/admin/reports/cohorts");
  });
});
