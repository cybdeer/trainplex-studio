/**
 * Tests for the ProjectROI page.
 * Phase 1 Step 7.
 *
 * Coverage
 * --------
 * - Overview table renders one row per project.
 * - Clicking a row opens the detail panel for that project.
 * - Detail panel renders the PDF export anchor pointing to the per-project
 *   .pdf endpoint.
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
    t: (key: string) => key,
    i18n: { language: "en" },
  }),
}));

import { ProjectROI } from "../ProjectROI";
import type { ProjectROIList } from "../types";

const PAYLOAD: ProjectROIList = {
  results: [
    {
      project_id: 101,
      project_name: "KYC OCR — Hindi",
      project_type: "ocr",
      language: "hi",
      tasks_created: 5000,
      tasks_completed: 4825,
      trainer_payout_inr: 96500,
      reviewer_payout_inr: 28500,
      infra_cost_inr: 20000,
      total_cost_inr: 145000,
      external_revenue_inr: 285000,
      profit_inr: 140000,
      roi_pct: 96,
      cost_per_quality_task_inr: 33,
      time_to_complete_days: 18,
      quality_score_pct: 92,
    },
    {
      project_id: 102,
      project_name: "Voice intent — Bhojpuri",
      project_type: "voice",
      language: "bho",
      tasks_created: 3200,
      tasks_completed: 3040,
      trainer_payout_inr: 64000,
      reviewer_payout_inr: 18500,
      infra_cost_inr: 9500,
      total_cost_inr: 92000,
      external_revenue_inr: 158000,
      profit_inr: 66000,
      roi_pct: 72,
      cost_per_quality_task_inr: 35,
      time_to_complete_days: 22,
      quality_score_pct: 87,
    },
  ],
};

const renderPage = () =>
  render(
    <MemoryRouter>
      <ProjectROI />
    </MemoryRouter>,
  );

describe("ProjectROI", () => {
  beforeEach(() => {
    mockUserRole = "admin";
  });

  it("renders the overview table for each project", () => {
    setMockQuery({ data: PAYLOAD, isFetching: false, isError: false });
    renderPage();
    expect(screen.getByTestId("roi-table")).toBeInTheDocument();
    expect(screen.getByTestId("roi-row-101")).toBeInTheDocument();
    expect(screen.getByTestId("roi-row-102")).toBeInTheDocument();
  });

  it("clicking a row reveals the detail panel for that project", () => {
    setMockQuery({ data: PAYLOAD, isFetching: false, isError: false });
    renderPage();
    fireEvent.click(screen.getByTestId("roi-row-101"));
    expect(screen.getByTestId("roi-detail-101")).toBeInTheDocument();
  });

  it("detail panel exposes the per-project PDF export anchor", () => {
    setMockQuery({ data: PAYLOAD, isFetching: false, isError: false });
    renderPage();
    fireEvent.click(screen.getByTestId("roi-row-101"));
    const anchor = screen.getByTestId("roi-export-pdf-101");
    expect(anchor).toHaveAttribute(
      "href",
      "/api/v1/admin/reports/project-roi/101.pdf",
    );
  });

  it("renders loading skeleton during fetch", () => {
    setMockQuery({ data: undefined, isFetching: true, isError: false });
    renderPage();
    expect(screen.getByTestId("roi-skeleton")).toBeInTheDocument();
  });

  it("renders error box on failure", () => {
    setMockQuery({ data: undefined, isFetching: false, isError: true });
    renderPage();
    expect(screen.getByTestId("roi-error")).toBeInTheDocument();
  });

  it("blocks non-admin", () => {
    mockUserRole = "trainer";
    renderPage();
    expect(screen.getByTestId("roi-forbidden")).toBeInTheDocument();
  });

  it("exposes route metadata", () => {
    expect(ProjectROI.path).toBe("/admin/reports/project-roi");
  });
});
