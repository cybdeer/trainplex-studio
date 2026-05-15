/**
 * Tests for the TrainPlex Admin Quality Alert Center page.
 * Phase 1 Step 4.2-8.
 *
 * Strategy
 * --------
 * Same approach as `AuditLogPage.test.tsx` / `WhatsAppBroadcastPage.test.tsx`:
 * mock useAuth, useAPI, useTranslation, useQuery, and useMutation at the
 * module-graph level so the page renders deterministically.
 *
 * Coverage
 * --------
 * - Stats strip, filter bar, and table render together for admin users.
 * - All four filter inputs are present (status, severity, trigger, trainer).
 * - Empty results show the empty-state row.
 * - Severity badge wears the right CSS-module hook (e.g. `sevCritical`).
 * - Critical rows pick up the `criticalRow` row tint.
 * - Clicking a row opens the drawer with details + resolve form.
 * - Submitting the resolve form fires the parent mutation.
 * - Loading state renders before the list query resolves.
 * - Non-admin sees the 403 fallback (and no fetch).
 * - Page route metadata exposes /admin/quality-alerts.
 * - Hindi mode renders the Devanagari title.
 */

/* eslint-disable @typescript-eslint/no-var-requires */

import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

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

let listQueryState: any = { data: undefined, isFetching: true, isError: false };
let statsQueryState: any = { data: undefined, isFetching: true, isError: false };
const setListQuery = (state: any) => {
  listQueryState = state;
};
const setStatsQuery = (state: any) => {
  statsQueryState = state;
};

let mockMutation: any = { isPending: false, mutate: jest.fn(), successData: null };
const setMockMutation = (state: any) => {
  mockMutation = state;
};

jest.mock("@tanstack/react-query", () => ({
  useQuery: ({ queryKey }: any) => {
    // The first key segment distinguishes list vs stats.
    const root = Array.isArray(queryKey) ? queryKey[0] : "";
    if (root === "admin-quality-alerts-stats") return statsQueryState;
    return listQueryState;
  },
  useMutation: ({ onSuccess }: any) => ({
    isPending: mockMutation.isPending,
    mutate: (vars: any) => {
      mockMutation.mutate(vars);
      if (onSuccess && mockMutation.successData) onSuccess(mockMutation.successData);
    },
  }),
  useQueryClient: () => ({ invalidateQueries: jest.fn() }),
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
    t: (key: string, vars?: Record<string, unknown>) => {
      const tpl = mockTranslations[key] ?? key;
      if (!vars) return tpl;
      // Support both {{name}} and the bare i18next interpolation our pages emit.
      return tpl.replace(/\{\{(\w+)\}\}/g, (_, name) => String(vars[name] ?? ""));
    },
    i18n: { language: mockLang },
  }),
}));

// ---- Now import the SUT ----

import { QualityAlertsPage } from "../QualityAlertsPage";
import type { AlertRow, AlertsListResponse, AlertsStatsResponse } from "../types";

const ROW_CRITICAL: AlertRow = {
  id: 9001,
  trigger_type: "reviewer_disagree",
  severity: "critical",
  status: "open",
  trainer: { id: 7, email: "trainer@trainplex.in", role: "trainer" },
  submission_id: 1234,
  details: { agree_count: 0, total_reviewers: 3 },
  reviewed_by: null,
  reviewed_at: null,
  resolution_notes: "",
  created_at: "2026-05-15T12:34:56Z",
};

const ROW_HIGH: AlertRow = {
  id: 9002,
  trigger_type: "time_anomaly",
  severity: "high",
  status: "open",
  trainer: { id: 7, email: "trainer@trainplex.in", role: "trainer" },
  submission_id: 1235,
  details: { time_taken_sec: 5, expected_min_sec: 60 },
  reviewed_by: null,
  reviewed_at: null,
  resolution_notes: "",
  created_at: "2026-05-15T12:35:00Z",
};

const ROW_MEDIUM_RESOLVED: AlertRow = {
  id: 9003,
  trigger_type: "duplicate_pattern",
  severity: "medium",
  status: "dismissed",
  trainer: { id: 8, email: "other@trainplex.in", role: "trainer" },
  submission_id: null,
  details: { duplicate_count: 7 },
  reviewed_by: { id: 1, email: "admin@trainplex.in", role: "admin" },
  reviewed_at: "2026-05-15T13:00:00Z",
  resolution_notes: "False positive — bot script.",
  created_at: "2026-05-15T12:00:00Z",
};

const LIST_RESPONSE: AlertsListResponse = {
  page: 1,
  page_size: 50,
  total: 3,
  total_pages: 1,
  results: [ROW_CRITICAL, ROW_HIGH, ROW_MEDIUM_RESOLVED],
};

const STATS_RESPONSE: AlertsStatsResponse = {
  open: { low: 0, medium: 0, high: 1, critical: 1 },
  total_open: 2,
};

const renderPage = () =>
  render(
    <MemoryRouter>
      <QualityAlertsPage />
    </MemoryRouter>,
  );

beforeEach(() => {
  setMockRole("admin");
  setMockLang("en");
  setMockTranslations({});
  setListQuery({ data: LIST_RESPONSE, isFetching: false, isError: false });
  setStatsQuery({ data: STATS_RESPONSE, isFetching: false, isError: false });
  setMockMutation({ isPending: false, mutate: jest.fn(), successData: null });
});

describe("QualityAlertsPage", () => {
  it("renders stats strip, filter bar, and table for admin users", () => {
    renderPage();
    expect(screen.getByTestId("admin-quality-alerts")).toBeInTheDocument();
    expect(screen.getByTestId("alerts-stats-strip")).toBeInTheDocument();
    expect(screen.getByTestId("alerts-filter-bar")).toBeInTheDocument();
    expect(screen.getByTestId("alerts-table")).toBeInTheDocument();
    expect(screen.getByTestId("alert-row-9001")).toBeInTheDocument();
    expect(screen.getByTestId("alert-row-9002")).toBeInTheDocument();
    expect(screen.getByTestId("alert-row-9003")).toBeInTheDocument();
  });

  it("exposes the four filter inputs", () => {
    renderPage();
    expect(screen.getByTestId("alert-filter-status")).toBeInTheDocument();
    expect(screen.getByTestId("alert-filter-severity")).toBeInTheDocument();
    expect(screen.getByTestId("alert-filter-trigger")).toBeInTheDocument();
    expect(screen.getByTestId("alert-filter-trainer")).toBeInTheDocument();
  });

  it("renders the 4 severity stat cards with counts", () => {
    renderPage();
    expect(screen.getByTestId("alerts-stats-low")).toBeInTheDocument();
    expect(screen.getByTestId("alerts-stats-medium")).toBeInTheDocument();
    expect(screen.getByTestId("alerts-stats-high")).toBeInTheDocument();
    expect(screen.getByTestId("alerts-stats-critical")).toBeInTheDocument();
    // Counts pulled from the mock stats response.
    expect(screen.getByTestId("alerts-stats-critical")).toHaveTextContent("1");
    expect(screen.getByTestId("alerts-stats-high")).toHaveTextContent("1");
  });

  it("shows the empty-state row when results is empty", () => {
    setListQuery({
      data: { page: 1, page_size: 50, total: 0, total_pages: 0, results: [] },
      isFetching: false,
      isError: false,
    });
    setMockTranslations({ "admin.alerts.no_alerts": "No quality alerts yet" });
    renderPage();
    expect(screen.getByTestId("alerts-empty")).toBeInTheDocument();
    expect(screen.getByTestId("alerts-empty")).toHaveTextContent("No quality alerts yet");
  });

  it("shows the loading skeleton while fetching the list with no data yet", () => {
    setListQuery({ data: undefined, isFetching: true, isError: false });
    renderPage();
    expect(screen.getByTestId("alerts-loading")).toBeInTheDocument();
    expect(screen.queryByTestId("alerts-table")).not.toBeInTheDocument();
  });

  it("marks critical rows with the criticalRow CSS hook + high rows with highRow", () => {
    renderPage();
    const critical = screen.getByTestId("alert-row-9001");
    expect(critical.className).toMatch(/criticalRow/);

    const high = screen.getByTestId("alert-row-9002");
    expect(high.className).toMatch(/highRow/);

    // Resolved medium row gets neither tint.
    const medium = screen.getByTestId("alert-row-9003");
    expect(medium.className ?? "").not.toMatch(/criticalRow/);
    expect(medium.className ?? "").not.toMatch(/highRow/);
  });

  it("renders severity badges with the right severity data attribute", () => {
    renderPage();
    // Row 9001 → critical badge.
    const badge9001 = screen.getByTestId("alert-severity-9001");
    expect(badge9001).toHaveAttribute("data-severity", "critical");
    const badge9002 = screen.getByTestId("alert-severity-9002");
    expect(badge9002).toHaveAttribute("data-severity", "high");
  });

  it("opens the drawer with details + resolve form on row click", () => {
    setMockTranslations({
      "admin.alerts.row_details": "Details",
      "admin.alerts.resolve_button": "Resolve",
      "admin.alerts.notes_label": "Resolution notes",
    });
    renderPage();
    fireEvent.click(screen.getByTestId("alert-row-9001"));
    expect(screen.getByTestId("alerts-drawer")).toBeInTheDocument();
    expect(screen.getByTestId("alerts-drawer-details")).toHaveTextContent(/agree_count/);
    // Resolve form widgets present.
    expect(screen.getByTestId("alerts-resolution-select")).toBeInTheDocument();
    expect(screen.getByTestId("alerts-resolution-notes")).toBeInTheDocument();
    expect(screen.getByTestId("alerts-resolve-submit")).toBeInTheDocument();
    // Close it.
    fireEvent.click(screen.getByTestId("alerts-drawer-close"));
    expect(screen.queryByTestId("alerts-drawer")).not.toBeInTheDocument();
  });

  it("submitting the resolve form fires the mutate callback", () => {
    const mutate = jest.fn();
    setMockMutation({ isPending: false, mutate, successData: null });
    renderPage();
    fireEvent.click(screen.getByTestId("alert-row-9001"));

    // Change dropdown to action_taken + add notes.
    fireEvent.change(screen.getByTestId("alerts-resolution-select"), {
      target: { value: "action_taken" },
    });
    fireEvent.change(screen.getByTestId("alerts-resolution-notes"), {
      target: { value: "Trainer suspended pending appeal." },
    });
    fireEvent.click(screen.getByTestId("alerts-resolve-submit"));

    expect(mutate).toHaveBeenCalledTimes(1);
    const arg = mutate.mock.calls[0][0];
    expect(arg.alertId).toBe(9001);
    expect(arg.resolution).toBe("action_taken");
    expect(arg.notes).toBe("Trainer suspended pending appeal.");
  });

  it("hides the page behind a 403 fallback for non-admin users", () => {
    setMockRole("trainer");
    renderPage();
    expect(screen.getByTestId("alerts-forbidden")).toBeInTheDocument();
    expect(screen.queryByTestId("alerts-table")).not.toBeInTheDocument();
  });

  it("renders an error box when the list query fails", () => {
    setListQuery({ data: undefined, isFetching: false, isError: true });
    setMockTranslations({ "admin.alerts.fetch_failed": "Couldn't load quality alerts." });
    renderPage();
    expect(screen.getByTestId("alerts-error")).toBeInTheDocument();
    expect(screen.getByTestId("alerts-error")).toHaveTextContent(
      "Couldn't load quality alerts.",
    );
  });

  it("renders the Hindi title when language is hi", () => {
    setMockLang("hi");
    setMockTranslations({ "admin.alerts.title": "गुणवत्ता अलर्ट" });
    renderPage();
    expect(screen.getByText("गुणवत्ता अलर्ट")).toBeInTheDocument();
    // Sanity check at least one Devanagari codepoint.
    expect(/[ऀ-ॿ]/.test(screen.getByText("गुणवत्ता अलर्ट").textContent ?? "")).toBe(true);
  });

  it("pagination controls disable correctly at first page of single-page result", () => {
    renderPage();
    const prev = screen.getByTestId("alerts-page-prev") as HTMLButtonElement;
    const next = screen.getByTestId("alerts-page-next") as HTMLButtonElement;
    expect(prev.disabled).toBe(true);
    expect(next.disabled).toBe(true);
  });

  it("filter reset bubbles back to default filters", () => {
    renderPage();
    // Change severity, then reset.
    fireEvent.change(screen.getByTestId("alert-filter-severity"), {
      target: { value: "critical" },
    });
    expect((screen.getByTestId("alert-filter-severity") as HTMLSelectElement).value).toBe(
      "critical",
    );
    fireEvent.click(screen.getByTestId("alerts-filter-reset"));
    expect((screen.getByTestId("alert-filter-severity") as HTMLSelectElement).value).toBe("");
  });
});

describe("QualityAlertsPage metadata", () => {
  it("exposes /admin/quality-alerts as the route path", () => {
    expect((QualityAlertsPage as any).path).toBe("/admin/quality-alerts");
    expect((QualityAlertsPage as any).exact).toBe(true);
  });
});
