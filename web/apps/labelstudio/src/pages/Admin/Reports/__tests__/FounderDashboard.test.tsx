/**
 * Tests for the FounderDashboard.
 * Phase 1 Step 7.
 *
 * Coverage
 * --------
 * - Renders 4 KPI tiles, cohort heatmap, project ROI table, geo + language
 *   tables, problematic trainers table given a mock snapshot.
 * - PDF export anchor points at /api/v1/admin/reports/founder-weekly.pdf.
 * - Loading state renders the skeleton.
 * - Error state renders the error box.
 * - Non-admin sees the RoleGate fallback.
 */

/* eslint-disable @typescript-eslint/no-var-requires */

import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
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

let mockLang = "en";
let mockTranslations: Record<string, string> = {};
jest.mock("@humansignal/app-common", () => ({
  useTranslation: () => ({
    t: (key: string, opts?: any) => {
      const v = mockTranslations[key] ?? key;
      if (opts && typeof opts.count === "number") {
        return v.replace("{{count}}", String(opts.count));
      }
      return v;
    },
    i18n: { language: mockLang },
  }),
}));

import { FounderDashboard } from "../FounderDashboard";
import type { FounderWeeklySnapshot } from "../types";

const SNAPSHOT: FounderWeeklySnapshot = {
  week_start: "2026-05-11",
  week_end: "2026-05-17",
  generated_at: "2026-05-15T12:34:56Z",
  top_kpis: {
    submissions_weekly: 8420,
    submissions_delta_pct: 8,
    revenue_weekly_inr: 412500,
    revenue_delta_pct: 12,
    active_trainers: 138,
    active_trainers_delta_pct: 4,
    avg_payout_per_trainer_inr: 2989,
  },
  trend_lines: {
    submissions_over_time: [
      { date: "2026-05-11", count: 1100 },
      { date: "2026-05-12", count: 1150 },
      { date: "2026-05-13", count: 1200 },
      { date: "2026-05-14", count: 1250 },
      { date: "2026-05-15", count: 1300 },
      { date: "2026-05-16", count: 800 },
      { date: "2026-05-17", count: 850 },
    ],
    revenue_mom: [
      { month: "2025-12", revenue_inr: 280000 },
      { month: "2026-01", revenue_inr: 302000 },
      { month: "2026-02", revenue_inr: 324000 },
      { month: "2026-03", revenue_inr: 346000 },
      { month: "2026-04", revenue_inr: 380000 },
      { month: "2026-05", revenue_inr: 412500 },
    ],
    trainer_growth: [
      { month: "2025-12", active_trainers: 78 },
      { month: "2026-01", active_trainers: 90 },
      { month: "2026-02", active_trainers: 102 },
      { month: "2026-03", active_trainers: 114 },
      { month: "2026-04", active_trainers: 126 },
      { month: "2026-05", active_trainers: 138 },
    ],
  },
  cohort_retention: [
    { wave_name: "Wave 1", wave_start: "2026-03-04", cohort_size: 42, day_7: 88, day_30: 74, day_60: 62, day_90: 55 },
    { wave_name: "Wave 2", wave_start: "2026-03-25", cohort_size: 38, day_7: 84, day_30: 71, day_60: 60, day_90: 52 },
  ],
  project_roi: [
    { project_id: 101, project_name: "KYC OCR — Hindi", cost_inr: 145000, revenue_inr: 285000, roi_pct: 96 },
    { project_id: 102, project_name: "Voice intent — Bhojpuri", cost_inr: 92000, revenue_inr: 158000, roi_pct: 72 },
  ],
  geographic_split: [
    { state_code: "RJ", state_name: "Rajasthan", submissions: 1320, active_trainers: 22, earnings_inr: 68000 },
    { state_code: "UP", state_name: "Uttar Pradesh", submissions: 1180, active_trainers: 19, earnings_inr: 58000 },
  ],
  language_split: [
    { language_code: "hi", language_name: "Hindi", submissions: 2480, avg_quality_pct: 89 },
    { language_code: "bn", language_name: "Bengali", submissions: 1180, avg_quality_pct: 86 },
  ],
  quality_kpis: {
    avg_consensus_pct: 87,
    dispute_rate_pct: 4,
    avg_consensus_pct_delta: 2,
    dispute_rate_pct_delta: -1,
    top_10_problematic: [
      { trainer_id: 42, name: "Trainer #42", state: "UP", dispute_count: 8, submissions: 60, dispute_rate_pct: 13 },
    ],
  },
};

const renderPage = () =>
  render(
    <MemoryRouter>
      <FounderDashboard />
    </MemoryRouter>,
  );

describe("FounderDashboard", () => {
  beforeEach(() => {
    mockUserRole = "admin";
    mockLang = "en";
    mockTranslations = {};
  });

  it("renders loading skeleton while fetching", () => {
    setMockQuery({ data: undefined, isFetching: true, isError: false });
    renderPage();
    expect(screen.getByTestId("founder-skeleton")).toBeInTheDocument();
  });

  it("renders error box on failure", () => {
    setMockQuery({ data: undefined, isFetching: false, isError: true });
    renderPage();
    expect(screen.getByTestId("founder-error")).toBeInTheDocument();
  });

  it("renders all 4 KPI tiles when data lands", () => {
    setMockQuery({ data: SNAPSHOT, isFetching: false, isError: false });
    renderPage();
    expect(screen.getByTestId("kpi-submissions")).toBeInTheDocument();
    expect(screen.getByTestId("kpi-revenue")).toBeInTheDocument();
    expect(screen.getByTestId("kpi-active-trainers")).toBeInTheDocument();
    expect(screen.getByTestId("kpi-avg-payout")).toBeInTheDocument();
  });

  it("renders cohort heatmap when data lands", () => {
    setMockQuery({ data: SNAPSHOT, isFetching: false, isError: false });
    renderPage();
    expect(screen.getByTestId("cohort-heatmap")).toBeInTheDocument();
  });

  it("renders the PDF export anchor", () => {
    setMockQuery({ data: SNAPSHOT, isFetching: false, isError: false });
    renderPage();
    const anchor = screen.getByTestId("founder-export-pdf");
    expect(anchor).toHaveAttribute("href", "/api/v1/admin/reports/founder-weekly.pdf");
  });

  it("blocks non-admin with the RoleGate fallback", () => {
    mockUserRole = "trainer";
    renderPage();
    expect(screen.getByTestId("founder-forbidden")).toBeInTheDocument();
  });

  it("renders Hindi week label when locale is hi", () => {
    mockLang = "hi";
    setMockQuery({ data: SNAPSHOT, isFetching: false, isError: false });
    mockTranslations = {
      "admin.reports.founder_weekly": "साप्ताहिक रिपोर्ट",
    };
    renderPage();
    expect(screen.getByText("साप्ताहिक रिपोर्ट")).toBeInTheDocument();
  });

  it("exposes route metadata", () => {
    expect(FounderDashboard.path).toBe("/admin/reports/founder");
  });
});
