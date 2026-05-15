/**
 * Tests for the Leaderboard.
 * Phase 1 Step 7.
 *
 * Coverage
 * --------
 * - Renders leaderboard table + Hall of Fame tables given mock data.
 * - Period pills switch the active state.
 * - CSV export anchor URL includes the current period.
 * - Filter dropdowns render with the expected options.
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

let mockLang = "en";
jest.mock("@humansignal/app-common", () => ({
  useTranslation: () => ({
    t: (key: string, opts?: any) => {
      if (opts && typeof opts.count === "number") {
        return `${key}:${opts.count}`;
      }
      return key;
    },
    i18n: { language: mockLang },
  }),
}));

import { Leaderboard } from "../Leaderboard";
import type { LeaderboardPayload } from "../types";

const PAYLOAD: LeaderboardPayload = {
  period: "weekly",
  filters: { state: null, tier: null, language: null, project_type: null },
  total: 2,
  results: [
    {
      rank: 1,
      trainer_id: 1,
      name: "Geeta P.",
      state: "RJ",
      tier: "gold",
      language: "hi",
      project_type: "ocr",
      tasks_done: 103,
      earnings_inr: 5350,
      quality_score_pct: 96,
      consistency_pct: 92,
    },
    {
      rank: 2,
      trainer_id: 2,
      name: "Sunil M.",
      state: "UP",
      tier: "gold",
      language: "hi",
      project_type: "voice",
      tasks_done: 97,
      earnings_inr: 4950,
      quality_score_pct: 94,
      consistency_pct: 90,
    },
  ],
  hall_of_fame_lifetime: [
    { rank: 1, trainer_id: 1, name: "Geeta P.", state: "RJ", lifetime_tasks: 4944, lifetime_earnings_inr: 256800 },
  ],
  hall_of_fame_month: [
    { rank: 1, trainer_id: 1, name: "Geeta P.", state: "RJ", tasks_this_month: 412, earnings_this_month_inr: 21400 },
  ],
};

const renderPage = () =>
  render(
    <MemoryRouter>
      <Leaderboard />
    </MemoryRouter>,
  );

describe("Leaderboard", () => {
  beforeEach(() => {
    mockUserRole = "admin";
    mockLang = "en";
  });

  it("renders period pills with the default selected", () => {
    setMockQuery({ data: PAYLOAD, isFetching: false, isError: false });
    renderPage();
    expect(screen.getByTestId("period-daily")).toBeInTheDocument();
    expect(screen.getByTestId("period-weekly")).toBeInTheDocument();
    expect(screen.getByTestId("period-monthly")).toBeInTheDocument();
    expect(screen.getByTestId("period-weekly")).toHaveAttribute("aria-pressed", "true");
  });

  it("clicking a different period pill updates aria-pressed", () => {
    setMockQuery({ data: PAYLOAD, isFetching: false, isError: false });
    renderPage();
    fireEvent.click(screen.getByTestId("period-daily"));
    expect(screen.getByTestId("period-daily")).toHaveAttribute("aria-pressed", "true");
  });

  it("renders the leaderboard rows for each trainer", () => {
    setMockQuery({ data: PAYLOAD, isFetching: false, isError: false });
    renderPage();
    const table = screen.getByTestId("leaderboard-table");
    expect(table).toBeInTheDocument();
    expect(screen.getByText("Geeta P.")).toBeInTheDocument();
    expect(screen.getByText("Sunil M.")).toBeInTheDocument();
  });

  it("renders both Hall of Fame tables", () => {
    setMockQuery({ data: PAYLOAD, isFetching: false, isError: false });
    renderPage();
    expect(screen.getByTestId("hof-lifetime-table")).toBeInTheDocument();
    expect(screen.getByTestId("hof-month-table")).toBeInTheDocument();
  });

  it("CSV export anchor encodes the active period in the query string", () => {
    setMockQuery({ data: PAYLOAD, isFetching: false, isError: false });
    renderPage();
    const anchor = screen.getByTestId("leaderboard-export-csv");
    expect(anchor.getAttribute("href")).toContain("/api/v1/admin/reports/leaderboard.csv");
    expect(anchor.getAttribute("href")).toContain("period=weekly");
  });

  it("renders the filter dropdowns", () => {
    setMockQuery({ data: PAYLOAD, isFetching: false, isError: false });
    renderPage();
    expect(screen.getByTestId("filter-state")).toBeInTheDocument();
    expect(screen.getByTestId("filter-tier")).toBeInTheDocument();
    expect(screen.getByTestId("filter-language")).toBeInTheDocument();
    expect(screen.getByTestId("filter-project-type")).toBeInTheDocument();
  });

  it("renders loading skeleton during fetch", () => {
    setMockQuery({ data: undefined, isFetching: true, isError: false });
    renderPage();
    expect(screen.getByTestId("leaderboard-skeleton")).toBeInTheDocument();
  });

  it("renders error box on failure", () => {
    setMockQuery({ data: undefined, isFetching: false, isError: true });
    renderPage();
    expect(screen.getByTestId("leaderboard-error")).toBeInTheDocument();
  });

  it("blocks non-admin with RoleGate fallback", () => {
    mockUserRole = "trainer";
    renderPage();
    expect(screen.getByTestId("leaderboard-forbidden")).toBeInTheDocument();
  });

  it("exposes route metadata", () => {
    expect(Leaderboard.path).toBe("/admin/reports/leaderboard");
  });
});
