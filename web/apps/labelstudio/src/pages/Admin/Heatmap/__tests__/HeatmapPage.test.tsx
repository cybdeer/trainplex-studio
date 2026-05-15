/**
 * Tests for the TrainPlex admin India geographic heatmap page.
 * Phase 1 Step 4.2-6.
 *
 * Strategy mirrors `DashboardWidget.test.tsx`: mock the providers (Auth,
 * API, React Query, i18n) at the module-graph level + render with
 * controlled inputs.
 *
 * Coverage
 * --------
 * - Renders one tile per state given a 17-state snapshot (matches the
 *   backend's pinned count).
 * - Renders one row per state in the fallback table.
 * - Hindi mode renders Devanagari labels.
 * - Loading skeleton shows while fetching.
 * - Non-admin sees the RoleGate fallback (defensive — the backend already
 *   403s).
 * - Period pills are clickable + the active one carries the active class.
 * - Page metadata exposes /admin/heatmap as the route path.
 * - Colour intensity ramps: the page-max state lands in the darkest band.
 */

/* eslint-disable @typescript-eslint/no-var-requires */

import "@testing-library/jest-dom";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import React from "react";

// ---- Module mocks (must come before importing the SUT) ----

jest.mock("../../../../providers/ApiProvider", () => ({
  useAPI: () => ({ callApi: jest.fn() }),
  ApiContext: { Provider: ({ children }: any) => children },
}));

let mockUserRole: string | null = "admin";
const setMockRole = (role: string | null) => {
  mockUserRole = role;
};
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
const setMockLang = (lang: string) => {
  mockLang = lang;
};
const setMockTranslations = (table: Record<string, string>) => {
  mockTranslations = table;
};
jest.mock("@humansignal/app-common", () => ({
  useTranslation: () => ({
    t: (key: string) => mockTranslations[key] ?? key,
    i18n: { language: mockLang },
  }),
}));

// ---- Import the SUT ----

import { HeatmapPage } from "../HeatmapPage";
import type { StateActivity } from "../types";

// 17-state snapshot mirroring the backend's `_STATE_ACTIVITY_BASE`. RJ has
// the highest active_trainers count so it should land in the darkest band.
const SNAPSHOT: StateActivity[] = [
  { state_code: "RJ", state_name: "Rajasthan", active_trainers: 12, submissions_count: 87, total_earnings_inr: 38000 },
  { state_code: "UP", state_name: "Uttar Pradesh", active_trainers: 9, submissions_count: 76, total_earnings_inr: 25000 },
  { state_code: "MH", state_name: "Maharashtra", active_trainers: 8, submissions_count: 64, total_earnings_inr: 22500 },
  { state_code: "KA", state_name: "Karnataka", active_trainers: 8, submissions_count: 58, total_earnings_inr: 20800 },
  { state_code: "GJ", state_name: "Gujarat", active_trainers: 7, submissions_count: 54, total_earnings_inr: 18500 },
  { state_code: "PB", state_name: "Punjab", active_trainers: 6, submissions_count: 48, total_earnings_inr: 15200 },
  { state_code: "TN", state_name: "Tamil Nadu", active_trainers: 6, submissions_count: 45, total_earnings_inr: 14200 },
  { state_code: "MP", state_name: "Madhya Pradesh", active_trainers: 5, submissions_count: 40, total_earnings_inr: 12000 },
  { state_code: "TG", state_name: "Telangana", active_trainers: 5, submissions_count: 38, total_earnings_inr: 11800 },
  { state_code: "WB", state_name: "West Bengal", active_trainers: 5, submissions_count: 36, total_earnings_inr: 11200 },
  { state_code: "BR", state_name: "Bihar", active_trainers: 4, submissions_count: 32, total_earnings_inr: 9600 },
  { state_code: "KL", state_name: "Kerala", active_trainers: 4, submissions_count: 30, total_earnings_inr: 9000 },
  { state_code: "JH", state_name: "Jharkhand", active_trainers: 3, submissions_count: 24, total_earnings_inr: 7200 },
  { state_code: "OR", state_name: "Odisha", active_trainers: 3, submissions_count: 22, total_earnings_inr: 6800 },
  { state_code: "AP", state_name: "Andhra Pradesh", active_trainers: 3, submissions_count: 21, total_earnings_inr: 6400 },
  { state_code: "DL", state_name: "Delhi", active_trainers: 3, submissions_count: 19, total_earnings_inr: 6000 },
  { state_code: "AS", state_name: "Assam", active_trainers: 2, submissions_count: 15, total_earnings_inr: 4500 },
];

const renderHeatmap = () =>
  render(
    <MemoryRouter>
      <HeatmapPage />
    </MemoryRouter>,
  );

beforeEach(() => {
  setMockRole("admin");
  setMockLang("en");
  setMockTranslations({});
  setMockQuery({ data: SNAPSHOT, isFetching: false, isError: false });
});

describe("HeatmapPage", () => {
  it("renders one tile per state given the 17-state snapshot", () => {
    renderHeatmap();
    expect(screen.getByTestId("india-map")).toBeInTheDocument();
    // 17 states should produce 17 tiles.
    SNAPSHOT.forEach((s) => {
      expect(screen.getByTestId(`state-tile-${s.state_code}`)).toBeInTheDocument();
    });
  });

  it("renders one table row per state in the fallback StateTable", () => {
    renderHeatmap();
    expect(screen.getByTestId("state-table")).toBeInTheDocument();
    SNAPSHOT.forEach((s) => {
      expect(screen.getByTestId(`state-row-${s.state_code}`)).toBeInTheDocument();
    });
  });

  it("paints the highest-activity state in the darkest intensity band", () => {
    renderHeatmap();
    // RJ has the highest active_trainers (12) so it should be the darkest.
    const rjTile = screen.getByTestId("state-tile-RJ");
    expect(rjTile.getAttribute("data-intensity")).toBe("5");
    // AS has the lowest (2) — should be lighter but still active (>= 1).
    const asTile = screen.getByTestId("state-tile-AS");
    const asBand = parseInt(asTile.getAttribute("data-intensity") || "0", 10);
    expect(asBand).toBeGreaterThanOrEqual(1);
    expect(asBand).toBeLessThan(5);
  });

  it("renders all 3 period filter pills, with 'month' active by default", () => {
    renderHeatmap();
    const todayPill = screen.getByTestId("period-today");
    const weekPill = screen.getByTestId("period-week");
    const monthPill = screen.getByTestId("period-month");
    expect(todayPill).toBeInTheDocument();
    expect(weekPill).toBeInTheDocument();
    expect(monthPill).toBeInTheDocument();
    expect(monthPill.getAttribute("data-active")).toBe("true");
    expect(todayPill.getAttribute("data-active")).toBe("false");
    expect(weekPill.getAttribute("data-active")).toBe("false");
  });

  it("clicking 'Today' makes that pill the active one", () => {
    renderHeatmap();
    const todayPill = screen.getByTestId("period-today");
    fireEvent.click(todayPill);
    // After the click, today should be active and month should not be.
    expect(screen.getByTestId("period-today").getAttribute("data-active")).toBe("true");
    expect(screen.getByTestId("period-month").getAttribute("data-active")).toBe("false");
  });

  it("renders the loading skeleton when fetching with no data", () => {
    setMockQuery({ data: undefined, isFetching: true, isError: false });
    renderHeatmap();
    expect(screen.getByTestId("heatmap-skeleton")).toBeInTheDocument();
    expect(screen.queryByTestId("india-map")).not.toBeInTheDocument();
  });

  it("renders the error box when the heatmap query fails", () => {
    setMockQuery({ data: undefined, isFetching: false, isError: true });
    setMockTranslations({
      "admin.heatmap.load_failed": "Couldn't load heatmap data.",
    });
    renderHeatmap();
    expect(screen.getByTestId("heatmap-error")).toBeInTheDocument();
    expect(screen.getByTestId("heatmap-error")).toHaveTextContent(
      "Couldn't load heatmap data.",
    );
  });

  it("hides the page behind a 403 fallback when the user is not admin", () => {
    setMockRole("trainer");
    renderHeatmap();
    expect(screen.getByTestId("heatmap-forbidden")).toBeInTheDocument();
    expect(screen.queryByTestId("india-map")).not.toBeInTheDocument();
  });

  it("renders Devanagari labels when the language is Hindi", () => {
    setMockLang("hi");
    setMockTranslations({
      "admin.heatmap.title": "भारत गतिविधि हीटमैप",
      "admin.heatmap.period_today": "आज",
      "admin.heatmap.period_week": "इस हफ्ते",
      "admin.heatmap.period_month": "इस महीने",
      "admin.heatmap.col_state": "राज्य",
      "admin.heatmap.col_trainers": "सक्रिय ट्रेनर",
      "admin.heatmap.col_submissions": "जमा कार्य",
      "admin.heatmap.col_earnings": "कमाई",
      "admin.heatmap.legend_dark": "अधिक गतिविधि",
      "admin.heatmap.legend_light": "कम गतिविधि",
      "admin.heatmap.map_heading": "राज्य-वार गतिविधि",
      "admin.heatmap.table_heading": "राज्य विवरण",
    });
    renderHeatmap();
    expect(screen.getByText("भारत गतिविधि हीटमैप")).toBeInTheDocument();
    expect(screen.getByText("इस महीने")).toBeInTheDocument();
    expect(screen.getByText("अधिक गतिविधि")).toBeInTheDocument();
    // Devanagari unicode block sanity — Hindi text must contain ≥1 codepoint
    // in U+0900..U+097F (so we know the locale switched).
    const header = screen.getByText("भारत गतिविधि हीटमैप").textContent ?? "";
    expect(/[ऀ-ॿ]/.test(header)).toBe(true);
  });
});

describe("HeatmapPage page metadata", () => {
  it("exposes /admin/heatmap as the route path", () => {
    expect((HeatmapPage as any).path).toBe("/admin/heatmap");
    expect((HeatmapPage as any).exact).toBe(true);
  });
});
